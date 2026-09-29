"""Provider-agnostic, evidence-bounded LLM reaction extractor.

This module implements `llm-extractor-v1` beside the deterministic rule baseline.
It deliberately does not call any particular model provider. A provider adapter
receives a strict JSON request and returns either a JSON string or mapping.

Scientific safeguards:
- the model sees one already-selected evidence chunk, not the whole corpus;
- every scientific field may be null (explicit abstention);
- missing, ambiguous, conflicting, or cross-reaction values must be null;
- no extra keys or free-form explanations are accepted;
- evidence and provenance metadata are supplied by the caller and cannot be
  rewritten by the model;
- schema failures raise controlled exceptions rather than being coerced.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Any, Mapping, Protocol, runtime_checkable

from modules.reaction_candidate_extraction import ReactionCandidate

EXTRACTION_VERSION = "llm-extractor-v1"
PROMPT_VERSION = "llm-extractor-prompt-v1"

FIELD_NAMES = (
    "ee_percent",
    "yield_percent",
    "h2_pressure_bar",
    "temperature_c",
    "reaction_time_h",
    "solvent",
    "ligand",
    "substrate_class",
)

NUMERIC_FIELDS = {
    "ee_percent": (0.0, 100.0),
    "yield_percent": (0.0, 100.0),
    "h2_pressure_bar": (0.0, None),
    "temperature_c": (-273.15, None),
    "reaction_time_h": (0.0, None),
}
TEXT_FIELDS = {"solvent", "ligand", "substrate_class"}

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": list(FIELD_NAMES),
    "properties": {
        "ee_percent": {"type": ["number", "null"], "minimum": 0, "maximum": 100},
        "yield_percent": {"type": ["number", "null"], "minimum": 0, "maximum": 100},
        "h2_pressure_bar": {"type": ["number", "null"], "minimum": 0},
        "temperature_c": {"type": ["number", "null"], "minimum": -273.15},
        "reaction_time_h": {"type": ["number", "null"], "minimum": 0},
        "solvent": {"type": ["string", "null"]},
        "ligand": {"type": ["string", "null"]},
        "substrate_class": {"type": ["string", "null"]},
    },
}

SYSTEM_PROMPT = """You are a scientific data extraction component for catalytic asymmetric hydrogenation literature.

Use ONLY the evidence chunk supplied by the caller. Do not use outside chemical knowledge, memory, or plausible inference to fill gaps.

Return exactly one JSON object with exactly these eight keys:
- ee_percent
- yield_percent
- h2_pressure_bar
- temperature_c
- reaction_time_h
- solvent
- ligand
- substrate_class

Rules:
1. Every value may be null. Null is the correct answer when the evidence does not explicitly support a field.
2. If a field is ambiguous, internally conflicting, or cannot be associated with the same reaction record, return null for that field.
3. If multiple candidate values for the same field occur and the evidence does not unambiguously identify which belongs to the target reaction, return null.
4. Never infer a ligand, catalyst-related identity, substrate class, stereochemistry, condition, yield, or ee from general chemistry knowledge.
5. Do not output explanations, citations, confidence scores, markdown, comments, or extra keys.
6. Percentages are numeric values from 0 to 100 without the percent sign.
7. H2 pressure must be returned in bar only when the pressure is explicitly supported. Simple unit conversion is allowed, but do not infer missing pressure.
8. Temperature is in degrees Celsius and reaction time is in hours.
9. If the chunk contains no extractable reaction information, return all eight keys with null values.
"""


class LLMExtractionError(RuntimeError):
    """Base class for controlled LLM extraction failures."""


class LLMResponseSchemaError(LLMExtractionError):
    """Raised when provider output is not valid strict extractor JSON."""


@dataclass(frozen=True)
class LLMExtractionRequest:
    """Request passed to a provider adapter."""

    system_prompt: str
    user_prompt: str
    response_schema: Mapping[str, Any]
    prompt_version: str = PROMPT_VERSION


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal provider contract.

    Real adapters may call any hosted or local LLM. Tests can use a deterministic
    replay provider. The core extractor never depends on a provider SDK.
    """

    model_name: str

    def complete_json(self, request: LLMExtractionRequest) -> str | Mapping[str, Any]:
        """Return one JSON object as text or a mapping."""


@dataclass
class ReplayJSONProvider:
    """Deterministic provider for tests, CI, and saved-response replay."""

    response: str | Mapping[str, Any]
    model_name: str = "replay-json"
    last_request: LLMExtractionRequest | None = None

    def complete_json(self, request: LLMExtractionRequest) -> str | Mapping[str, Any]:
        self.last_request = request
        return self.response


@dataclass(frozen=True)
class LLMExtractionResult:
    """One unverified LLM candidate plus immutable extraction metadata."""

    candidate: ReactionCandidate
    model_name: str
    prompt_version: str
    extraction_version: str
    unresolved_fields: tuple[str, ...]
    verification_status: str = "unverified"
    source_locator: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = self.candidate.to_dict()
        payload.update(
            {
                "model_name": self.model_name,
                "prompt_version": self.prompt_version,
                "extraction_version": self.extraction_version,
                "unresolved_fields": list(self.unresolved_fields),
                "verification_status": self.verification_status,
                "source_locator": dict(self.source_locator) if self.source_locator else None,
            }
        )
        return payload


def build_request(evidence_text: str) -> LLMExtractionRequest:
    """Build a strict, evidence-bounded extraction request."""

    if not isinstance(evidence_text, str) or not evidence_text.strip():
        raise ValueError("evidence_text must be a non-empty string")

    user_prompt = (
        "Extract one reaction candidate from the evidence chunk below. "
        "When any field is missing, ambiguous, conflicting, or belongs to a "
        "different reaction, return null for that field.\n\n"
        "<evidence>\n"
        f"{evidence_text}\n"
        "</evidence>"
    )
    return LLMExtractionRequest(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_schema=RESPONSE_SCHEMA,
    )


def _parse_json_object(raw: str | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        return dict(raw)
    if not isinstance(raw, str):
        raise LLMResponseSchemaError(
            f"Provider response must be JSON text or mapping, got {type(raw).__name__}"
        )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMResponseSchemaError(f"Malformed provider JSON: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise LLMResponseSchemaError("Provider JSON must be a single object")
    return parsed


def validate_response(raw: str | Mapping[str, Any]) -> dict[str, Any]:
    """Strictly validate provider output without silent scientific coercion."""

    data = _parse_json_object(raw)
    keys = set(data)
    required = set(FIELD_NAMES)
    missing = required - keys
    extra = keys - required
    if missing:
        raise LLMResponseSchemaError(
            "Provider JSON is missing required keys: " + ", ".join(sorted(missing))
        )
    if extra:
        raise LLMResponseSchemaError(
            "Provider JSON contains disallowed keys: " + ", ".join(sorted(extra))
        )

    validated: dict[str, Any] = {}
    for field in FIELD_NAMES:
        value = data[field]
        if value is None:
            validated[field] = None
            continue

        if field in NUMERIC_FIELDS:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise LLMResponseSchemaError(
                    f"{field} must be a number or null, got {type(value).__name__}"
                )
            number = float(value)
            if not math.isfinite(number):
                raise LLMResponseSchemaError(f"{field} must be finite")
            lower, upper = NUMERIC_FIELDS[field]
            if number < lower or (upper is not None and number > upper):
                bounds = f">= {lower}" if upper is None else f"between {lower} and {upper}"
                raise LLMResponseSchemaError(f"{field} must be {bounds}")
            validated[field] = number
            continue

        if field in TEXT_FIELDS:
            if not isinstance(value, str):
                raise LLMResponseSchemaError(
                    f"{field} must be a string or null, got {type(value).__name__}"
                )
            if not value.strip():
                raise LLMResponseSchemaError(f"{field} must not be an empty string")
            validated[field] = value
            continue

        raise AssertionError(f"Unhandled extractor field: {field}")

    return validated


def extract_reaction_chunk(
    evidence_text: str,
    provider: LLMProvider,
    *,
    candidate_id: str = "rxn-llm-0001",
    evidence_start: int = 0,
    evidence_end: int | None = None,
    source_locator: Mapping[str, Any] | None = None,
) -> LLMExtractionResult:
    """Extract one unverified candidate from one pre-selected evidence chunk.

    `confidence` is intentionally set to 0.0. The current LLM extractor does not
    claim a calibrated scientific confidence score; verification is a separate
    stage (Issue #4). Benchmarking should evaluate the scientific fields directly.
    """

    request = build_request(evidence_text)
    raw = provider.complete_json(request)
    values = validate_response(raw)

    if evidence_end is None:
        evidence_end = evidence_start + len(evidence_text)
    if evidence_start < 0 or evidence_end < evidence_start:
        raise ValueError("invalid evidence offsets")

    candidate = ReactionCandidate(
        candidate_id=candidate_id,
        ee_percent=values["ee_percent"],
        yield_percent=values["yield_percent"],
        h2_pressure_bar=values["h2_pressure_bar"],
        temperature_c=values["temperature_c"],
        reaction_time_h=values["reaction_time_h"],
        solvent=values["solvent"],
        ligand=values["ligand"],
        substrate_class=values["substrate_class"],
        confidence=0.0,
        evidence_text=evidence_text,
        evidence_start=evidence_start,
        evidence_end=evidence_end,
        extraction_method=EXTRACTION_VERSION,
    )
    unresolved = tuple(field for field in FIELD_NAMES if values[field] is None)

    return LLMExtractionResult(
        candidate=candidate,
        model_name=str(provider.model_name),
        prompt_version=request.prompt_version,
        extraction_version=EXTRACTION_VERSION,
        unresolved_fields=unresolved,
        source_locator=source_locator,
    )
