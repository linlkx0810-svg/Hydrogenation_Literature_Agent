"""Independent evidence verifier for extracted reaction candidates.

The verifier does not generate new chemistry values. It only checks whether a
candidate value is directly supported by its bound evidence window. Ligand aliases
are resolved only from explicit source definitions.
"""
from __future__ import annotations
import math
from dataclasses import asdict, dataclass
from typing import Any

from modules.ligand_resolver import (
    extract_alias_definitions,
    resolve_ligand_mention,
)
from modules.reaction_candidate_extraction import (
    EE_RE,
    PRESSURE_RE,
    SOLVENT_RE,
    SUBSTRATE_RE,
    TEMP_RE,
    TIME_RE,
    YIELD_RE,
    pressure_to_bar,
)


@dataclass
class FieldVerification:
    field: str
    value: Any
    status: str
    reason: str
    evidence_text: str
    canonical_id: str | None = None
    canonical_name: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CandidateVerification:
    candidate_id: str
    evidence_integrity: str
    overall_status: str
    fields: list[FieldVerification]

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "evidence_integrity": self.evidence_integrity,
            "overall_status": self.overall_status,
            "fields": [field.to_dict() for field in self.fields],
        }


def _close(a: float, b: float, tol: float = 1e-4) -> bool:
    return math.isclose(float(a), float(b), rel_tol=0.0, abs_tol=tol)


def _numeric_supported(pattern, evidence: str, value) -> bool:
    if value is None:
        return False
    return any(
        _close(float(match.group("value")), float(value))
        for match in pattern.finditer(evidence)
    )


def _pressure_supported(evidence: str, value) -> bool:
    if value is None:
        return False
    for match in PRESSURE_RE.finditer(evidence):
        converted = pressure_to_bar(
            float(match.group("value")), match.group("unit")
        )
        if _close(converted, float(value), 5e-4):
            return True
    return False


def _text_supported(pattern, evidence: str, value: str | None) -> bool:
    if not value:
        return False
    return any(
        match.group(0).strip().lower() == value.strip().lower()
        for match in pattern.finditer(evidence)
    )


def _integrity(candidate, source_text: str) -> tuple[str, str]:
    start = getattr(candidate, "evidence_start", None)
    end = getattr(candidate, "evidence_end", None)
    evidence = getattr(candidate, "evidence_text", "") or ""

    if not isinstance(start, int) or not isinstance(end, int):
        return "unverifiable", evidence
    if start < 0 or end < start or end > len(source_text):
        return "invalid_offsets", evidence

    source_slice = source_text[start:end].strip()
    return (
        "verified" if source_slice == evidence.strip() else "mismatch",
        evidence,
    )


def verify_candidate(candidate, source_text: str) -> CandidateVerification:
    """Verify one candidate strictly against its attached evidence window."""
    integrity, evidence = _integrity(candidate, source_text)
    results: list[FieldVerification] = []
    fields = (
        "ee_percent",
        "yield_percent",
        "h2_pressure_bar",
        "temperature_c",
        "reaction_time_h",
        "solvent",
        "ligand",
        "substrate_class",
    )

    if integrity != "verified":
        for field in fields:
            value = getattr(candidate, field, None)
            if value is not None:
                results.append(
                    FieldVerification(
                        field,
                        value,
                        "unsupported",
                        f"Evidence integrity check failed: {integrity}.",
                        evidence,
                    )
                )
        return CandidateVerification(
            getattr(candidate, "candidate_id", ""),
            integrity,
            "reject",
            results,
        )

    checks = [
        (
            "ee_percent",
            getattr(candidate, "ee_percent", None),
            _numeric_supported(
                EE_RE, evidence, getattr(candidate, "ee_percent", None)
            ),
        ),
        (
            "yield_percent",
            getattr(candidate, "yield_percent", None),
            _numeric_supported(
                YIELD_RE, evidence, getattr(candidate, "yield_percent", None)
            ),
        ),
        (
            "h2_pressure_bar",
            getattr(candidate, "h2_pressure_bar", None),
            _pressure_supported(
                evidence, getattr(candidate, "h2_pressure_bar", None)
            ),
        ),
        (
            "temperature_c",
            getattr(candidate, "temperature_c", None),
            _numeric_supported(
                TEMP_RE, evidence, getattr(candidate, "temperature_c", None)
            ),
        ),
        (
            "reaction_time_h",
            getattr(candidate, "reaction_time_h", None),
            _numeric_supported(
                TIME_RE, evidence, getattr(candidate, "reaction_time_h", None)
            ),
        ),
        (
            "solvent",
            getattr(candidate, "solvent", None),
            _text_supported(
                SOLVENT_RE, evidence, getattr(candidate, "solvent", None)
            ),
        ),
        (
            "substrate_class",
            getattr(candidate, "substrate_class", None),
            _text_supported(
                SUBSTRATE_RE,
                evidence,
                getattr(candidate, "substrate_class", None),
            ),
        ),
    ]

    for field, value, supported in checks:
        if value is None:
            continue
        results.append(
            FieldVerification(
                field,
                value,
                "supported" if supported else "unsupported",
                "Value is directly present in the bound evidence window."
                if supported
                else "Candidate value is not directly supported by the bound evidence window.",
                evidence,
            )
        )

    ligand = getattr(candidate, "ligand", None)
    if ligand:
        resolution = resolve_ligand_mention(
            ligand,
            source_text,
            extract_alias_definitions(source_text),
        )
        status = "supported" if resolution.status == "resolved" else resolution.status
        results.append(
            FieldVerification(
                "ligand",
                ligand,
                status,
                f"Ligand resolved via {resolution.resolution_method}."
                if status == "supported"
                else resolution.note,
                resolution.evidence_text or evidence,
                resolution.canonical_id,
                resolution.canonical_name,
            )
        )

    statuses = {result.status for result in results}
    if "unsupported" in statuses:
        overall = "reject"
    elif "ambiguous" in statuses or "unresolved" in statuses:
        overall = "review"
    else:
        overall = "accept"

    return CandidateVerification(
        getattr(candidate, "candidate_id", ""),
        integrity,
        overall,
        results,
    )


def verify_candidates(candidates, source_text: str) -> list[CandidateVerification]:
    return [verify_candidate(candidate, source_text) for candidate in candidates]
