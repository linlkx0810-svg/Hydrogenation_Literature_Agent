"""Guardrails for blind scientific benchmark integrity.

This module deliberately contains *infrastructure only*. It does not know any
blind labels, predictions, reviewer decisions, or scientific answers. Its job is
to keep model-development and ordinary extraction code from accidentally reading
reviewer-only or blind-gold artefacts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence


class BlindIntegrityError(RuntimeError):
    """Raised when a pipeline action would violate blind-test separation."""


# Markers are intentionally specific. A generic token such as ``gold`` is not
# blocked because it may legitimately occur in unrelated filenames or paper text.
SENSITIVE_PATH_MARKERS = (
    "reviewer_only",
    "reviewer-only",
    "reviewer_gold",
    "reviewer-gold",
    "blind_gold",
    "blind-gold",
    "sealed_predictions",
    "sealed-predictions",
    "adjudicated",
    "gold_labels",
    "gold-labels",
)

_ALLOWED_MANIFEST_TOP_LEVEL = {"schema_version", "split", "items", "notes"}
_ALLOWED_MANIFEST_ITEM_KEYS = {
    "item_id",
    "paper_id",
    "doi",
    "source_sha256",
    "source_id",
}


def _normalised_path_text(path: str | Path) -> str:
    return str(Path(path)).replace("\\", "/").lower()


def is_sensitive_path(path: str | Path) -> bool:
    """Return True when a path name indicates reviewer-only/blind-gold content."""

    text = _normalised_path_text(path)
    return any(marker in text for marker in SENSITIVE_PATH_MARKERS)


def assert_safe_input_path(
    path: str | Path,
    *,
    evaluation_mode: bool = False,
) -> Path:
    """Refuse reviewer-only/blind-gold inputs outside explicit evaluation mode.

    The check is name/path based by design: it is a first-line contamination
    guard, not a substitute for OS permissions or independent review procedures.
    No file is opened by this function.
    """

    resolved = Path(path)
    if is_sensitive_path(resolved) and not evaluation_mode:
        raise BlindIntegrityError(
            "Refusing reviewer-only/blind-gold input outside evaluation mode: "
            f"{resolved}"
        )
    return resolved


def assert_safe_output_path(
    path: str | Path,
    *,
    purpose: str,
) -> Path:
    """Prevent accidental mixing of adjudication outputs and model outputs.

    ``purpose`` must be one of ``model``, ``production`` or ``adjudication``.
    Model/production writers may not target paths carrying reviewer/adjudication
    markers. Adjudication writers must target a clearly separated sensitive path.
    """

    target = Path(path)
    purpose = purpose.strip().lower()
    if purpose not in {"model", "production", "adjudication"}:
        raise ValueError("purpose must be model, production, or adjudication")

    sensitive = is_sensitive_path(target)
    if purpose in {"model", "production"} and sensitive:
        raise BlindIntegrityError(
            f"Refusing {purpose} output into reviewer/adjudication path: {target}"
        )
    if purpose == "adjudication" and not sensitive:
        raise BlindIntegrityError(
            "Adjudication output must use a clearly separated reviewer/blind path: "
            f"{target}"
        )
    return target


def validate_blind_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a development-safe blind manifest.

    The manifest may expose stable identifiers and source hashes, but never gold
    labels, expected answers, predictions, adjudication decisions or free-form
    scientific values. A strict allow-list is used so new fields cannot leak in
    silently.
    """

    unknown_top = set(manifest) - _ALLOWED_MANIFEST_TOP_LEVEL
    if unknown_top:
        raise BlindIntegrityError(
            "Blind manifest contains disallowed top-level keys: "
            + ", ".join(sorted(unknown_top))
        )

    split = manifest.get("split")
    if split != "blind":
        raise BlindIntegrityError("Blind manifest split must be exactly 'blind'")

    items = manifest.get("items")
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        raise BlindIntegrityError("Blind manifest 'items' must be a sequence")

    cleaned_items: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise BlindIntegrityError(f"Manifest item {index} must be an object")
        unknown = set(item) - _ALLOWED_MANIFEST_ITEM_KEYS
        if unknown:
            raise BlindIntegrityError(
                f"Manifest item {index} contains disallowed keys: "
                + ", ".join(sorted(unknown))
            )
        if not any(item.get(key) for key in ("item_id", "paper_id", "doi", "source_id")):
            raise BlindIntegrityError(
                f"Manifest item {index} requires a stable identifier"
            )
        if "source_sha256" in item:
            digest = str(item["source_sha256"]).lower()
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                raise BlindIntegrityError(
                    f"Manifest item {index} has invalid source_sha256"
                )
        cleaned_items.append(dict(item))

    return {
        "schema_version": str(manifest.get("schema_version", "1.0")),
        "split": "blind",
        "items": cleaned_items,
        **({"notes": manifest["notes"]} if "notes" in manifest else {}),
    }
