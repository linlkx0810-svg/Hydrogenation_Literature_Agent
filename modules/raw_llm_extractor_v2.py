"""Raw LLM extraction layer, `llm-extractor-v2`.

This is the formal Raw LLM stage of the Agent v1.0 execution graph. It is a new
module rather than an edit of `modules/llm_extractor.py`: v1 stays on the branch
unchanged as the historical implementation (see
`docs/LLM_EXTRACTOR_LINEAGE_V1_TO_V2.md`).

What changed against v1:

- the field set is the 12 atomic fields of `benchmark/FIELD_SCHEMA_V1.json`,
  which is the single source of truth and is read at import time;
- `conditions` is gone; pressure, temperature, time and solvent are separate;
- selectivity is split into `ee_or_er` (value plus the reported kind) and
  `stereochemical_outcome`;
- every null carries an explicit abstention reason, so `not_reported`,
  `not_applicable`, `unresolved` and `ambiguous` stop being the same thing.

Scientific safeguards kept from v1:

- the model sees one already-selected evidence chunk and nothing else;
- every field may be null, and null is the correct answer when the evidence does
  not support a value;
- no extra keys, no free text, no confidence score;
- a schema violation raises; it is never repaired into a prediction;
- provenance is supplied by the caller and cannot be rewritten by the model.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field as dataclass_field
from pathlib import Path
from typing import Any, Mapping, Protocol, runtime_checkable

EXTRACTION_VERSION = "llm-extractor-v2"
PROMPT_VERSION = "llm-extractor-prompt-v2"
SCHEMA_VERSION = "raw-extraction-schema-v2"

FIELD_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "benchmark" / "FIELD_SCHEMA_V1.json"

ABSTENTION_REASONS = ("not_reported", "not_applicable", "unresolved", "ambiguous")
EE_KINDS = ("ee_percent", "er_ratio")

_NUMERIC_BOUNDS: dict[str, tuple[float, float | None]] = {
    "h2_pressure": (0.0, None),
    "temperature": (-273.15, None),
    "reaction_time": (0.0, None),
    "yield": (0.0, 100.0),
}


def _load_field_schema(path: Path = FIELD_SCHEMA_PATH) -> dict[str, Any]:
    schema = json.loads(path.read_text(encoding="utf-8"))
    if schema.get("schema_version") != "agent-v1-field-schema-v1":
        raise RuntimeError(f"unexpected field schema version in {path}")
    return schema


FIELD_SCHEMA = _load_field_schema()
FIELD_NAMES: tuple[str, ...] = tuple(f["name"] for f in FIELD_SCHEMA["fields"])
_FIELD_TYPES: dict[str, str] = {f["name"]: f["type"] for f in FIELD_SCHEMA["fields"]}
NUMERIC_FIELDS = tuple(n for n, t in _FIELD_TYPES.items() if t == "numeric")
TEXT_FIELDS = tuple(
    n for n, t in _FIELD_TYPES.items() if t in {"categorical_text", "entity", "entity_or_class"}
)
SELECTIVITY_FIELD = "ee_or_er"


def _build_response_schema() -> dict[str, Any]:
    """Derive the strict JSON schema sent to the provider from FIELD_SCHEMA_V1."""
    properties: dict[str, Any] = {}
    for name in FIELD_NAMES:
        kind = _FIELD_TYPES[name]
        if kind == "numeric":
            lower, upper = _NUMERIC_BOUNDS[name]
            spec: dict[str, Any] = {"type": ["number", "null"], "minimum": lower}
            if upper is not None:
                spec["maximum"] = upper
            properties[name] = spec
        elif kind == "numeric_with_kind":
            properties[name] = {
                "type": ["object", "null"],
                "additionalProperties": False,
                "required": ["value", "kind"],
                "properties": {
                    "value": {"type": ["number", "null"], "minimum": 0},
                    "kind": {"type": ["string", "null"], "enum": [*EE_KINDS, None]},
                },
            }
        else:
            properties[name] = {"type": ["string", "null"]}
    properties["abstention_reasons"] = {
        "type": "object",
        "additionalProperties": {"type": "string", "enum": list(ABSTENTION_REASONS)},
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [*FIELD_NAMES, "abstention_reasons"],
        "properties": properties,
    }


RESPONSE_SCHEMA: dict[str, Any] = _build_response_schema()

SYSTEM_PROMPT = """You are a scientific data extraction component for catalytic asymmetric hydrogenation literature.

Use ONLY the evidence chunk supplied by the caller. Do not use outside chemical knowledge, memory, or plausible inference to fill gaps.

Return exactly one JSON object with exactly these thirteen keys:
- reaction
- catalyst
- ligand
- substrate
- product
- h2_pressure
- temperature
- reaction_time
- solvent
- yield
- ee_or_er
- stereochemical_outcome
- abstention_reasons

Rules:
1. Every scientific field may be null. Null is the correct answer when the evidence does not explicitly support a value.
2. If a field is ambiguous, internally conflicting, or cannot be associated with the same reaction record, return null for that field.
3. If several candidate values for one field occur and the evidence does not unambiguously identify which belongs to the target reaction, return null.
4. Never infer a reaction type, catalyst, ligand, substrate, product, condition, yield, enantioselectivity or configuration from general chemistry knowledge.
5. Do not output explanations, citations, confidence scores, markdown, comments, or extra keys.
6. h2_pressure is in bar, temperature in degrees Celsius, reaction_time in hours, yield a number from 0 to 100 without the percent sign. Convert units only when the source unit is explicit.
7. ee_or_er is an object with "value" and "kind". Use kind "ee_percent" for an ee in percent and "er_ratio" for a ratio. Report the value as the source reports it; never convert er to ee yourself.
8. stereochemical_outcome carries the configuration or the designated major enantiomer only when the source states it. Never derive it from the enantioselectivity value.
9. For every field you return as null, add one entry to abstention_reasons with the field name as the key and one of: not_reported, not_applicable, unresolved, ambiguous.
   - not_reported: the chunk simply does not report it
   - not_applicable: the field cannot exist for this reaction
   - unresolved: it is mentioned but cannot be pinned down from this chunk
   - ambiguous: the chunk supports more than one mutually exclusive reading
10. Do not add abstention_reasons entries for fields that carry a value.
11. If the chunk contains no extractable reaction information, return every scientific field as null with an abstention reason for each.
"""


class RawExtractionError(RuntimeError):
    """Base class for controlled raw-extraction failures."""


class RawResponseSchemaError(RawExtractionError):
    """Raised when provider output is not valid strict raw-extraction JSON."""


@dataclass(frozen=True)
class RawExtractionRequest:
    system_prompt: str
    user_prompt: str
    response_schema: Mapping[str, Any]
    prompt_version: str = PROMPT_VERSION
    schema_version: str = SCHEMA_VERSION


@runtime_checkable
class RawLLMProvider(Protocol):
    model_name: str

    def complete_json(self, request: RawExtractionRequest) -> str | Mapping[str, Any]:
        """Return one JSON object as text or a mapping."""


@dataclass
class ReplayJSONProvider:
    """Deterministic provider for tests, CI and saved-response replay."""

    response: str | Mapping[str, Any]
    model_name: str = "replay-json"
    last_request: RawExtractionRequest | None = None

    def complete_json(self, request: RawExtractionRequest) -> str | Mapping[str, Any]:
        self.last_request = request
        return self.response


@dataclass(frozen=True)
class RawPredictionRecord:
    """One raw LLM prediction for one evidence chunk, before any verification."""

    candidate_id: str
    source_artifact_id: str
    evidence_start: int
    evidence_end: int
    evidence_sha256: str
    values: Mapping[str, Any]
    abstention_reasons: Mapping[str, str]
    model_name: str
    extraction_version: str = EXTRACTION_VERSION
    prompt_version: str = PROMPT_VERSION
    schema_version: str = SCHEMA_VERSION
    field_schema_version: str = dataclass_field(
        default_factory=lambda: FIELD_SCHEMA["schema_version"]
    )
    verification_status: str = "unverified"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["values"] = dict(self.values)
        payload["abstention_reasons"] = dict(self.abstention_reasons)
        return payload


def build_request(evidence_text: str) -> RawExtractionRequest:
    """Build a strict, evidence-bounded extraction request."""
    if not isinstance(evidence_text, str) or not evidence_text.strip():
        raise ValueError("evidence_text must be a non-empty string")
    user_prompt = (
        "Extract one reaction candidate from the evidence chunk below. "
        "When any field is missing, ambiguous, conflicting, or belongs to a "
        "different reaction, return null for that field and record why.\n\n"
        "<evidence>\n"
        f"{evidence_text}\n"
        "</evidence>"
    )
    return RawExtractionRequest(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_schema=RESPONSE_SCHEMA,
    )


def _parse_json_object(raw: str | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        return dict(raw)
    if not isinstance(raw, str):
        raise RawResponseSchemaError(
            f"Provider response must be JSON text or mapping, got {type(raw).__name__}"
        )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RawResponseSchemaError(f"Malformed provider JSON: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise RawResponseSchemaError("Provider JSON must be a single object")
    return parsed


def _validate_number(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RawResponseSchemaError(
            f"{name} must be a number or null, got {type(value).__name__}"
        )
    number = float(value)
    if not math.isfinite(number):
        raise RawResponseSchemaError(f"{name} must be finite")
    lower, upper = _NUMERIC_BOUNDS.get(name, (None, None))
    if lower is not None and number < lower:
        raise RawResponseSchemaError(f"{name} must be >= {lower}")
    if upper is not None and number > upper:
        raise RawResponseSchemaError(f"{name} must be <= {upper}")
    return number


def _validate_text(name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise RawResponseSchemaError(
            f"{name} must be a string or null, got {type(value).__name__}"
        )
    if not value.strip():
        raise RawResponseSchemaError(f"{name} must not be an empty string")
    return value


def _validate_selectivity(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        raise RawResponseSchemaError(
            f"{SELECTIVITY_FIELD} must be an object or null, got {type(value).__name__}"
        )
    keys = set(value)
    if keys != {"value", "kind"}:
        raise RawResponseSchemaError(
            f"{SELECTIVITY_FIELD} must have exactly the keys value and kind"
        )
    number, kind = value["value"], value["kind"]
    if number is None and kind is None:
        return None
    if number is None or kind is None:
        raise RawResponseSchemaError(
            f"{SELECTIVITY_FIELD} must carry both a value and a kind, or be null"
        )
    if kind not in EE_KINDS:
        raise RawResponseSchemaError(
            f"{SELECTIVITY_FIELD} kind must be one of {', '.join(EE_KINDS)}"
        )
    if isinstance(number, bool) or not isinstance(number, (int, float)):
        raise RawResponseSchemaError(f"{SELECTIVITY_FIELD} value must be a number")
    number = float(number)
    if not math.isfinite(number) or number < 0:
        raise RawResponseSchemaError(f"{SELECTIVITY_FIELD} value must be finite and >= 0")
    if kind == "ee_percent" and number > 100:
        raise RawResponseSchemaError("ee_percent must be between 0 and 100")
    return {"value": number, "kind": kind}


def validate_response(raw: str | Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    """Strictly validate provider output without silent scientific coercion."""
    data = _parse_json_object(raw)
    required = set(FIELD_NAMES) | {"abstention_reasons"}
    missing = required - set(data)
    extra = set(data) - required
    if missing:
        raise RawResponseSchemaError(
            "Provider JSON is missing required keys: " + ", ".join(sorted(missing))
        )
    if extra:
        raise RawResponseSchemaError(
            "Provider JSON contains disallowed keys: " + ", ".join(sorted(extra))
        )

    values: dict[str, Any] = {}
    for name in FIELD_NAMES:
        value = data[name]
        if value is None:
            values[name] = None
        elif name == SELECTIVITY_FIELD:
            values[name] = _validate_selectivity(value)
        elif name in NUMERIC_FIELDS:
            values[name] = _validate_number(name, value)
        elif name in TEXT_FIELDS:
            values[name] = _validate_text(name, value)
        else:  # pragma: no cover - guarded by the schema loader
            raise AssertionError(f"Unhandled extractor field: {name}")

    reasons = data["abstention_reasons"]
    if not isinstance(reasons, Mapping):
        raise RawResponseSchemaError("abstention_reasons must be an object")
    validated_reasons: dict[str, str] = {}
    for name, reason in reasons.items():
        if name not in FIELD_NAMES:
            raise RawResponseSchemaError(f"abstention_reasons has unknown field {name}")
        if values[name] is not None:
            raise RawResponseSchemaError(
                f"abstention_reasons must not describe {name}, which carries a value"
            )
        if reason not in ABSTENTION_REASONS:
            raise RawResponseSchemaError(
                f"abstention reason for {name} must be one of {', '.join(ABSTENTION_REASONS)}"
            )
        validated_reasons[name] = reason

    nulls = {name for name in FIELD_NAMES if values[name] is None}
    undocumented = nulls - set(validated_reasons)
    if undocumented:
        raise RawResponseSchemaError(
            "null fields without an abstention reason: " + ", ".join(sorted(undocumented))
        )
    return values, validated_reasons


def extract_reaction_chunk(
    evidence_text: str,
    provider: RawLLMProvider,
    *,
    candidate_id: str = "rxn-llm-0001",
    source_artifact_id: str = "unknown-source",
    evidence_start: int = 0,
    evidence_end: int | None = None,
) -> RawPredictionRecord:
    """Extract one raw prediction from one pre-selected evidence chunk."""
    request = build_request(evidence_text)
    raw = provider.complete_json(request)
    values, reasons = validate_response(raw)

    if evidence_end is None:
        evidence_end = evidence_start + len(evidence_text)
    if evidence_start < 0 or evidence_end < evidence_start:
        raise ValueError("invalid evidence offsets")

    return RawPredictionRecord(
        candidate_id=candidate_id,
        source_artifact_id=source_artifact_id,
        evidence_start=evidence_start,
        evidence_end=evidence_end,
        evidence_sha256=hashlib.sha256(evidence_text.encode("utf-8")).hexdigest(),
        values=values,
        abstention_reasons=reasons,
        model_name=str(provider.model_name),
    )
