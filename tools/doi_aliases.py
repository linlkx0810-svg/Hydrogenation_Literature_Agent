"""Known DOI alias families for identity-level leakage checks.

Some publishers issue two DOIs for one study. The most common case in this
corpus is Wiley's Angewandte Chemie German edition (``10.1002/ange.NNNN``)
versus the International Edition (``10.1002/anie.NNNN``). An exclusion
registry that stores only one form lets the other form pass a blind gate.
"""
from __future__ import annotations

import re

ALIAS_PREFIX_PAIRS = (("10.1002/ange.", "10.1002/anie."),)


def normalize(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value)
    value = re.sub(r"^doi:\s*", "", value)
    return value.rstrip(".")


def aliases(doi: str) -> set:
    """Return ``doi`` plus every equivalent-identity DOI form."""
    doi = normalize(doi)
    out = {doi} if doi else set()
    for left, right in ALIAS_PREFIX_PAIRS:
        if doi.startswith(left):
            out.add(right + doi[len(left):])
        elif doi.startswith(right):
            out.add(left + doi[len(right):])
    return out
