"""Field-level evidence verifier for extracted reaction data.

`verifier-v1` is deliberately separate from extraction. It receives one extracted
field value plus the exact evidence chunk used for that candidate and returns a
strict verification judgement. It never rewrites the extracted scientific value.

Scientific safeguards:
- verification is field-by-field;
- only supplied evidence may be used;
- unsupported plausible values are not accepted;
- conflicts and ambiguity remain unresolved;
- verifier output is schema-validated and versioned;
- source evidence/provenance are caller-controlled.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping, Protocol, runtime_checkable

from modules.llm_extractor import FIELD_NAMES

VERIFIER_VERSION = "verifier-v1"
VERIFIER_PROMPT_VERSION = "verifier-prompt-v1"

STATUSES = ("accepted", "rejected", "unresolved")
REASON_CODES = (
    "supported",
    "missing",
    "ambiguous",
    "conflict",
    "wrong_entity",
    "wrong_reaction",
    "format_error",
)

_ALLOWED_STATUS_REASONS = {
    "accepted": {"supported"},
    "rejected": {"wrong_entity", "wrong_reaction", "format_error"},
    "unresolved": {"missing", "ambiguous", "conflict"},
}

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["status", "reason_code"],
    "properties": {
        "status": {"type": "string", "enum": list(STATUSES)},
        "reason_code": {"type": "string", "enum": list(REASON_CODES)},
    },
}

SYSTEM_PROMPT = """You are an independent scientific evidence verifier for catalytic asymmetric hydrogenation data.

You are NOT an extractor. You are given exactly one field name, one extracted value, and the evidence chunk that was used to create the candidate.

Use ONLY that evidence chunk. Do not use outside chemistry knowledge, memory, other papers, databases, or plausibility.

Return exactly one JSON object with exactly two keys: status and reason_code.

Allowed status values:
- accepted: the evidence explicitly supports the exact extracted value for the same reaction/entity.
- rejected: the extracted non-null value is contradicted by the evidence or clearly belongs to the wrong entity/reaction, or has a format/unit representation error.
- unresolved: the evidence is missing, ambiguous, internally conflicting, or insufficient to decide.

Allowed reason_code values:
- supported
- missing
- ambiguous
- conflict
- wrong_entity
- wrong_reaction
- format_error

Required pairings:
- accepted -> supported only
- rejected -> wrong_entity, wrong_reaction, or format_error only
- unresolved -> missing, ambiguous, or conflict only

Rules:
1. A plausible value is not enough; it must be explicitly supported by the supplied evidence.
2. If multiple rows/reactions/entities are present and the association is unclear, return unresolved/ambiguous.
3. If the evidence contains conflicting values for the same target, return unresolved/conflict.
4. If a value clearly belongs to another compound, ligand, substrate, product, row, or reaction, return rejected/wrong_entity or rejected/wrong_reaction.
5. Do not silently select between main-text/SI conflicts.
6. Do not rewrite or correct the extracted value. Verification only judges support.
7. Do not output explanations, confidence scores, markdown, citations, or extra keys.
"""


class VerificationError(RuntimeError):
    """Base class for controlled verification failures."""


class VerificationSchemaError(VerificationError):
    """Raised when verifier output violates the strict response contract."""


@dataclass(frozen=True)
class VerificationRequest:
    field_name: str
    extracted_value: Any
    evidence_text: str
    system_prompt: str
    user_prompt: str
    response_schema: Mapping[str, Any]
    prompt_version: str = VERIFIER_PROMPT_VERSION


@runtime_checkable
class VerifierProvider(Protocol):
    model_name: str

    def complete_json(self, request: VerificationRequest) -> str | Mapping[str, Any]:
        """Return one strict verification JSON object."""


@dataclass
class ReplayVerifierProvider:
    """Deterministic field-response provider for CI and replay tests."""

    responses: Mapping[str, str | Mapping[str, Any]]
    model_name: str = "replay-verifier"
    requests: list[VerificationRequest] | None = None

    def __post_init__(self) -> None:
        if self.requests is None:
            self.requests = []

    def complete_json(self, request: VerificationRequest) -> str | Mapping[str, Any]:
        assert self.requests is not None
        self.requests.append(request)
        if request.field_name not in self.responses:
            raise VerificationError(
                f"Replay verifier has no response for field: {request.field_name}"
            )
        return self.responses[request.field_name]


@dataclass(frozen=True)
class FieldVerification:
    field_name: str
    extracted_value: Any
    status: str
    reason_code: str
    verifier_version: str
    prompt_version: str
    model_name: str
    evidence_locator: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "extracted_value": self.extracted_value,
            "status": self.status,
            "reason_code": self.reason_code,
            "verifier_version": self.verifier_version,
            "prompt_version": self.prompt_version,
            "model_name": self.model_name,
            "evidence_locator": (
                dict(self.evidence_locator) if self.evidence_locator else None
            ),
        }


@dataclass(frozen=True)
class CandidateVerificationResult:
    candidate_id: str
    field_verifications: Mapping[str, FieldVerification]
    verifier_version: str = VERIFIER_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "verifier_version": self.verifier_version,
            "fields": {
                name: verification.to_dict()
                for name, verification in self.field_verifications.items()
            },
            "summary": summarize_verification(self.field_verifications.values()),
        }


def build_verification_request(
    field_name: str,
    extracted_value: Any,
    evidence_text: str,
) -> VerificationRequest:
    if field_name not in FIELD_NAMES:
        raise ValueError(f"Unknown scientific field: {field_name}")
    if not isinstance(evidence_text, str) or not evidence_text.strip():
        raise ValueError("evidence_text must be a non-empty string")

    rendered_value = json.dumps(extracted_value, ensure_ascii=False)
    user_prompt = (
        f"Field: {field_name}\n"
        f"Extracted value: {rendered_value}\n\n"
        "<evidence>\n"
        f"{evidence_text}\n"
        "</evidence>\n\n"
        "Judge whether this exact extracted value is supported for the same target."
    )
    return VerificationRequest(
        field_name=field_name,
        extracted_value=extracted_value,
        evidence_text=evidence_text,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_schema=RESPONSE_SCHEMA,
    )


def validate_verifier_response(
    raw: str | Mapping[str, Any],
) -> dict[str, str]:
    if isinstance(raw, Mapping):
        data = dict(raw)
    elif isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise VerificationSchemaError(
                f"Malformed verifier JSON: {exc.msg}"
            ) from exc
        if not isinstance(parsed, dict):
            raise VerificationSchemaError("Verifier JSON must be a single object")
        data = parsed
    else:
        raise VerificationSchemaError(
            f"Verifier response must be JSON text or mapping, got {type(raw).__name__}"
        )

    required = {"status", "reason_code"}
    missing = required - set(data)
    extra = set(data) - required
    if missing:
        raise VerificationSchemaError(
            "Verifier JSON is missing required keys: " + ", ".join(sorted(missing))
        )
    if extra:
        raise VerificationSchemaError(
            "Verifier JSON contains disallowed keys: " + ", ".join(sorted(extra))
        )

    status = data["status"]
    reason = data["reason_code"]
    if status not in STATUSES:
        raise VerificationSchemaError(f"Invalid verification status: {status}")
    if reason not in REASON_CODES:
        raise VerificationSchemaError(f"Invalid verification reason_code: {reason}")
    if reason not in _ALLOWED_STATUS_REASONS[status]:
        raise VerificationSchemaError(
            f"Invalid status/reason pairing: {status}/{reason}"
        )
    return {"status": status, "reason_code": reason}


def verify_field(
    *,
    field_name: str,
    extracted_value: Any,
    evidence_text: str,
    provider: VerifierProvider,
    evidence_locator: Mapping[str, Any] | None = None,
) -> FieldVerification:
    request = build_verification_request(field_name, extracted_value, evidence_text)
    raw = provider.complete_json(request)
    judgement = validate_verifier_response(raw)
    return FieldVerification(
        field_name=field_name,
        extracted_value=extracted_value,
        status=judgement["status"],
        reason_code=judgement["reason_code"],
        verifier_version=VERIFIER_VERSION,
        prompt_version=request.prompt_version,
        model_name=str(provider.model_name),
        evidence_locator=evidence_locator,
    )


def verify_candidate(
    candidate: Mapping[str, Any],
    *,
    provider: VerifierProvider,
    evidence_text: str | None = None,
    evidence_locator: Mapping[str, Any] | None = None,
) -> CandidateVerificationResult:
    """Verify all scientific fields without mutating the candidate mapping."""

    candidate_id = str(candidate.get("candidate_id", "unknown-candidate"))
    source_evidence = evidence_text if evidence_text is not None else candidate.get("evidence_text")
    if not isinstance(source_evidence, str) or not source_evidence.strip():
        raise ValueError("candidate verification requires non-empty evidence text")

    loc = evidence_locator
    if loc is None and isinstance(candidate.get("source_locator"), Mapping):
        loc = candidate["source_locator"]

    results: dict[str, FieldVerification] = {}
    for field_name in FIELD_NAMES:
        results[field_name] = verify_field(
            field_name=field_name,
            extracted_value=candidate.get(field_name),
            evidence_text=source_evidence,
            provider=provider,
            evidence_locator=loc,
        )
    return CandidateVerificationResult(
        candidate_id=candidate_id,
        field_verifications=results,
    )


def summarize_verification(
    verifications: Any,
) -> dict[str, Any]:
    """Report verification statistics separately from extraction coverage."""

    items = list(verifications)
    status_counts = {status: 0 for status in STATUSES}
    reason_counts = {reason: 0 for reason in REASON_CODES}
    extracted_non_null = 0
    accepted_non_null = 0

    for item in items:
        status_counts[item.status] += 1
        reason_counts[item.reason_code] += 1
        if item.extracted_value is not None:
            extracted_non_null += 1
            if item.status == "accepted":
                accepted_non_null += 1

    total = len(items)
    return {
        "fields_total": total,
        "extraction_coverage": extracted_non_null / total if total else 0.0,
        "accepted_extracted_fraction": (
            accepted_non_null / extracted_non_null if extracted_non_null else 0.0
        ),
        "status_counts": status_counts,
        "reason_counts": reason_counts,
    }
