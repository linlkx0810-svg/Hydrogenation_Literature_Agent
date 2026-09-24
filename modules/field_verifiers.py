"""Conservative evidence checks for the fields `evidence-verifier-v1` never covered.

These implement the `LITERAL_EVIDENCE_CHECK` and `EXPLICIT_STEREO_CHECK` modes of
`benchmark/VERIFIER_COVERAGE_V1.json` for `catalyst`, `product` and
`stereochemical_outcome`. `reaction` stays `NOT_CHECKED_V1`.

Three rules shape every function here:

- not checked is not unsupported;
- not verifiable is not incorrect;
- the verifier verifies a prediction and never performs recovery extraction, so
  a null prediction stays null no matter what the evidence contains.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONTRACT_PATH = Path(__file__).resolve().parents[1] / "benchmark" / "VERIFIER_COVERAGE_V1.json"

NOT_CHECKED = "not_checked_v1"
NOT_VERIFIABLE = "not_verifiable_v1"

_DASHES = dict.fromkeys(map(ord, "‐‑‒–—―−"), "-")
_QUOTES = {
    ord("‘"): "'", ord("’"): "'", ord("“"): '"', ord("”"): '"',
    ord("´"): "'", ord("′"): "'",
}


def load_coverage_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(Path(path).read_text(encoding="utf-8"))
    if contract.get("contract_version") != "verifier-coverage-contract-v1":
        raise RuntimeError(f"unexpected verifier coverage contract in {path}")
    return contract


COVERAGE_CONTRACT = load_coverage_contract()
FIELD_MODES: dict[str, str] = {
    entry["field"]: entry["coverage_mode"] for entry in COVERAGE_CONTRACT["fields"]
}
CHECKED_FIELDS: dict[str, bool] = {
    entry["field"]: entry["checked_by_verifier"] for entry in COVERAGE_CONTRACT["fields"]
}


@dataclass(frozen=True)
class FieldVerdict:
    field: str
    value: Any
    status: str
    reason: str
    evidence_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "value": self.value,
            "status": self.status,
            "reason": self.reason,
            "evidence_text": self.evidence_text,
        }


def normalize_for_matching(text: str) -> str:
    """Unicode, punctuation and whitespace normalization, nothing chemical."""
    text = unicodedata.normalize("NFKC", text or "")
    text = text.translate(_DASHES).translate(_QUOTES)
    text = re.sub(r"\s+", " ", text)
    return text.strip().casefold()


def literal_match(value: str, evidence: str) -> bool:
    """Boundary-aware literal containment after safe normalization.

    No fuzzy matching, no edit distance, no token overlap, no synonyms. A value
    either appears in the evidence as written, up to Unicode, punctuation and
    whitespace normalization, or it does not.
    """
    needle = normalize_for_matching(value)
    haystack = normalize_for_matching(evidence)
    if not needle or not haystack:
        return False
    pattern = re.compile(rf"(?<![0-9a-z]){re.escape(needle)}(?![0-9a-z])")
    return bool(pattern.search(haystack))


def verify_catalyst(value: Any, evidence: str) -> FieldVerdict:
    """LITERAL_EVIDENCE_CHECK for `catalyst`; it can accept but never block."""
    if value is None:
        return FieldVerdict("catalyst", None, NOT_VERIFIABLE, "No catalyst value to verify.")
    if literal_match(str(value), evidence):
        return FieldVerdict(
            "catalyst",
            value,
            "supported",
            "Catalyst is named literally in the bound evidence window.",
            evidence,
        )
    return FieldVerdict(
        "catalyst",
        value,
        NOT_VERIFIABLE,
        "No literal catalyst mention in the bound evidence. A metal name, a ligand "
        "plus metal combination, a precatalyst or a catalyst number is never "
        "assembled into a catalyst identity, so no verdict is issued.",
        evidence,
    )


def verify_product(value: Any, evidence: str) -> FieldVerdict:
    """LITERAL_EVIDENCE_CHECK for `product`; it can accept but never block."""
    if value is None:
        return FieldVerdict("product", None, NOT_VERIFIABLE, "No product value to verify.")
    if literal_match(str(value), evidence):
        return FieldVerdict(
            "product",
            value,
            "supported",
            "Product is named literally in the bound evidence window.",
            evidence,
        )
    return FieldVerdict(
        "product",
        value,
        NOT_VERIFIABLE,
        "No literal product mention in the bound evidence. A product drawn only in "
        "a scheme cannot be verified from text, so no verdict is issued.",
        evidence,
    )


_STEREO_PATTERNS = (
    re.compile(r"\((?P<d>[RS])\)"),
    re.compile(r"(?<![0-9A-Za-z])(?P<d>[RS])-(?:configured|configuration|enantiomer|isomer|product)"),
    re.compile(r"(?<![0-9A-Za-z])(?P<d>[RS])\s+(?:configuration|configured|enantiomer|isomer)"),
    re.compile(r"(?<![0-9A-Za-z])(?P<d>[RS])(?![0-9A-Za-z])\s*(?:absolute\s+configuration)"),
)
_RACEMIC_RE = re.compile(r"(?<![0-9a-z])racemic(?![0-9a-z])", re.I)
_MAJOR_RE = re.compile(r"major\s+enantiomer", re.I)


def _stereo_descriptors(evidence: str) -> set[str]:
    """Explicit stereochemical descriptors present in the evidence."""
    found: set[str] = set()
    text = unicodedata.normalize("NFKC", evidence or "").translate(_DASHES)
    for pattern in _STEREO_PATTERNS:
        for match in pattern.finditer(text):
            found.add(match.group("d").upper())
    if _RACEMIC_RE.search(text):
        found.add("RACEMIC")
    return found


def _normalize_descriptor(value: str) -> str | None:
    token = normalize_for_matching(value).strip("()").replace("-", " ").strip()
    if token in {"r", "(r)", "r configuration", "r configured", "r enantiomer"}:
        return "R"
    if token in {"s", "(s)", "s configuration", "s configured", "s enantiomer"}:
        return "S"
    if token.startswith("rac") or "racemic" in token:
        return "RACEMIC"
    return None


def verify_stereochemical_outcome(value: Any, evidence: str) -> FieldVerdict:
    """EXPLICIT_STEREO_CHECK: only descriptors stated in the evidence count."""
    if value is None:
        return FieldVerdict(
            "stereochemical_outcome", None, NOT_VERIFIABLE, "No stereochemical value to verify."
        )

    present = _stereo_descriptors(evidence)
    claimed = _normalize_descriptor(str(value))

    if claimed is None:
        if literal_match(str(value), evidence) and _MAJOR_RE.search(evidence or ""):
            return FieldVerdict(
                "stereochemical_outcome",
                value,
                "supported",
                "The named major enantiomer appears literally in the bound evidence.",
                evidence,
            )
        return FieldVerdict(
            "stereochemical_outcome",
            value,
            NOT_VERIFIABLE,
            "The predicted descriptor is not one this check can read, and no explicit "
            "stereochemical statement in the evidence matches it literally.",
            evidence,
        )

    if not present:
        return FieldVerdict(
            "stereochemical_outcome",
            value,
            NOT_VERIFIABLE,
            "The evidence reports no explicit configuration. Configuration is never "
            "inferred from an ee or er value, from catalyst sense or from precedent.",
            evidence,
        )
    if claimed in present:
        return FieldVerdict(
            "stereochemical_outcome",
            value,
            "supported",
            f"The evidence states the {claimed} configuration explicitly.",
            evidence,
        )
    return FieldVerdict(
        "stereochemical_outcome",
        value,
        "unsupported",
        f"The evidence states {', '.join(sorted(present))} explicitly, which contradicts "
        f"the predicted {claimed}.",
        evidence,
    )


EXTENDED_VERIFIERS = {
    "catalyst": verify_catalyst,
    "product": verify_product,
    "stereochemical_outcome": verify_stereochemical_outcome,
}


def verify_extended_field(field: str, value: Any, evidence: str) -> FieldVerdict:
    """Verify one field this module is responsible for."""
    if field not in EXTENDED_VERIFIERS:
        return FieldVerdict(
            field, value, NOT_CHECKED, "No verifier exists for this field in v1.", ""
        )
    return EXTENDED_VERIFIERS[field](value, evidence)
