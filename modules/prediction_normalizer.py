"""Entity normalization stage, `prediction-normalizer-v1`.

This stage sits between the frozen raw prediction and the evidence verifier. It
is deliberately narrow:

- `ligand` is `ACTIVE`: the raw mention is resolved through
  `modules.ligand_resolver` against the bound evidence and its source document;
- every other field is `PASS_THROUGH_V1`: the raw value is carried forward
  unchanged. No substrate, product, catalyst or reaction ontology is invented
  here, because none of them has a validated implementation yet.

The normalizer never edits the raw artifact. It emits a new record that keeps
`raw_value` next to `canonical_value`, so a reader can always see what the model
said before anything touched it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field as dataclass_field
from typing import Any, Mapping

from modules.ligand_resolver import extract_alias_definitions, resolve_ligand_mention
from modules.raw_llm_extractor_v2 import FIELD_NAMES

NORMALIZER_VERSION = "prediction-normalizer-v1"
ACTIVE_FIELDS = ("ligand",)
PASS_THROUGH_POLICY = "PASS_THROUGH_V1"

NORMALIZATION_STATUSES = (
    "resolved",
    "unresolved",
    "ambiguous",
    "not_applicable",
    "not_reported",
    "pass_through",
)


@dataclass(frozen=True)
class FieldNormalization:
    field: str
    raw_value: Any
    canonical_value: Any
    normalization_status: str
    normalization_method: str
    normalization_confidence: float | None = None
    normalization_evidence: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NormalizedRecord:
    candidate_id: str
    source_artifact_id: str
    raw_predictions_sha256: str
    fields: Mapping[str, FieldNormalization]
    normalizer_version: str = NORMALIZER_VERSION
    active_fields: tuple[str, ...] = dataclass_field(default=ACTIVE_FIELDS)
    pass_through_policy: str = PASS_THROUGH_POLICY

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_artifact_id": self.source_artifact_id,
            "raw_predictions_sha256": self.raw_predictions_sha256,
            "normalizer_version": self.normalizer_version,
            "active_fields": list(self.active_fields),
            "pass_through_policy": self.pass_through_policy,
            "fields": {name: value.to_dict() for name, value in self.fields.items()},
        }

    def canonical(self, field: str) -> Any:
        entry = self.fields.get(field)
        return None if entry is None else entry.canonical_value


def _normalize_ligand(
    raw_value: Any, source_text: str, abstention_reason: str | None
) -> FieldNormalization:
    if raw_value is None:
        return FieldNormalization(
            field="ligand",
            raw_value=None,
            canonical_value=None,
            normalization_status=abstention_reason or "not_reported",
            normalization_method="no_raw_value",
        )
    resolution = resolve_ligand_mention(
        str(raw_value), source_text, extract_alias_definitions(source_text)
    )
    status = resolution.status if resolution.status in NORMALIZATION_STATUSES else "unresolved"
    return FieldNormalization(
        field="ligand",
        raw_value=raw_value,
        canonical_value=resolution.canonical_name if status == "resolved" else None,
        normalization_status=status,
        normalization_method=resolution.resolution_method,
        normalization_confidence=getattr(resolution, "confidence", None),
        normalization_evidence=resolution.evidence_text or None,
    )


def normalize_record(raw_record: Mapping[str, Any], source_text: str) -> NormalizedRecord:
    """Normalize one frozen raw prediction record without modifying it."""
    values = raw_record["values"]
    reasons = raw_record.get("abstention_reasons", {})
    fields: dict[str, FieldNormalization] = {}

    for name in FIELD_NAMES:
        raw_value = values.get(name)
        if name in ACTIVE_FIELDS:
            fields[name] = _normalize_ligand(raw_value, source_text, reasons.get(name))
            continue
        fields[name] = FieldNormalization(
            field=name,
            raw_value=raw_value,
            canonical_value=raw_value,
            normalization_status=(
                "pass_through" if raw_value is not None else (reasons.get(name) or "not_reported")
            ),
            normalization_method=PASS_THROUGH_POLICY,
        )

    return NormalizedRecord(
        candidate_id=raw_record["candidate_id"],
        source_artifact_id=raw_record["source_artifact_id"],
        raw_predictions_sha256=raw_record.get("raw_predictions_sha256", ""),
        fields=fields,
    )
