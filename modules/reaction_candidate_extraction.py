"""Reaction-level candidate extraction with provenance and confidence scoring.

This module complements the paper-level Stage 5 extractor. Instead of selecting
one global maximum ee/yield from an entire article, it identifies local evidence
windows that look like individual reaction records and keeps the source text used
to support each field.

The implementation is intentionally deterministic and model-free. It provides a
stable baseline that can later be compared with an LLM extractor using the same
output schema.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Iterable

EE_RE = re.compile(r"(?P<value>\d{1,3}(?:\.\d+)?)\s*%\s*ee", re.I)
YIELD_RE = re.compile(r"(?P<value>\d{1,3}(?:\.\d+)?)\s*%\s*yield", re.I)
PRESSURE_RE = re.compile(
    r"(?P<value>\d{1,4}(?:\.\d+)?)\s*(?P<unit>bar|atm|psi|MPa|kPa)\b",
    re.I,
)
TEMP_RE = re.compile(r"(?P<value>-?\d{1,3}(?:\.\d+)?)\s*°?C\b", re.I)
TIME_RE = re.compile(r"(?P<value>\d{1,3}(?:\.\d+)?)\s*h(?:ours?|r)?\b", re.I)

SOLVENTS = (
    "THF", "dichloromethane", "DCM", "methanol", "MeOH", "ethanol",
    "EtOH", "toluene", "acetonitrile", "MeCN", "DMF", "DMSO",
    "hexane", "heptane", "isopropanol", "iPrOH", "ethyl acetate",
    "diethyl ether", "chloroform", "dioxane",
)
SOLVENT_RE = re.compile(r"\b(?:" + "|".join(map(re.escape, SOLVENTS)) + r")\b", re.I)

LIGANDS = (
    "BINAP", "Xyl-BINAP", "Josiphos", "SEGPHOS", "BIPHEP", "SYNPHOS",
    "Mandyphos", "Chiraphos", "Me-BPE", "DuPhos", "DIOP", "DPPE",
    "DPPP", "DPPM", "Triphos",
)
LIGAND_RE = re.compile(r"\b(?:" + "|".join(map(re.escape, LIGANDS)) + r")\b", re.I)

SUBSTRATE_RE = re.compile(
    r"\b(?:ketone|aryl ketone|imine|alkene|olefin|aldehyde|ester|amide|"
    r"enamide|enamine|acetophenone|quinoline|pyridine)\b",
    re.I,
)

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass
class ReactionCandidate:
    candidate_id: str
    ee_percent: float | None
    yield_percent: float | None
    h2_pressure_bar: float | None
    temperature_c: float | None
    reaction_time_h: float | None
    solvent: str | None
    ligand: str | None
    substrate_class: str | None
    confidence: float
    evidence_text: str
    evidence_start: int
    evidence_end: int
    extraction_method: str = "rule-baseline-v1"

    def to_dict(self) -> dict:
        return asdict(self)


def _first_float(pattern: re.Pattern, text: str) -> float | None:
    match = pattern.search(text)
    return float(match.group("value")) if match else None


def _first_text(pattern: re.Pattern, text: str) -> str | None:
    match = pattern.search(text)
    return match.group(0) if match else None


def pressure_to_bar(value: float, unit: str) -> float:
    unit = unit.lower()
    factors = {
        "bar": 1.0,
        "atm": 1.01325,
        "psi": 0.0689476,
        "mpa": 10.0,
        "kpa": 0.01,
    }
    return value * factors[unit]


def _extract_pressure_bar(text: str) -> float | None:
    match = PRESSURE_RE.search(text)
    if not match:
        return None
    return round(pressure_to_bar(float(match.group("value")), match.group("unit")), 4)


def _sentence_spans(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    cursor = 0
    for part in SENTENCE_SPLIT_RE.split(text):
        part = part.strip()
        if not part:
            continue
        start = text.find(part, cursor)
        if start < 0:
            start = cursor
        end = start + len(part)
        spans.append((start, end, part))
        cursor = end
    return spans


def _candidate_confidence(values: dict[str, object], evidence: str) -> float:
    score = 0.15
    if values.get("ee_percent") is not None:
        score += 0.25
    if values.get("yield_percent") is not None:
        score += 0.20
    if values.get("h2_pressure_bar") is not None:
        score += 0.15
    if values.get("temperature_c") is not None:
        score += 0.08
    if values.get("reaction_time_h") is not None:
        score += 0.05
    if values.get("ligand"):
        score += 0.05
    if values.get("substrate_class"):
        score += 0.04
    if re.search(r"\b(?:H2|H₂|hydrogen)\b", evidence, re.I):
        score += 0.03
    return round(min(score, 1.0), 2)


def extract_reaction_candidates(text: str, context_sentences: int = 1) -> list[ReactionCandidate]:
    """Extract local reaction candidates from plain article text.

    Candidate anchors are sentences containing ee or yield. Neighboring sentences
    are included as context so that conditions reported immediately before/after
    the result can be associated with the same candidate. Duplicate windows are
    removed deterministically.
    """
    spans = _sentence_spans(text)
    if not spans:
        return []

    anchor_indices = [
        i for i, (_, _, sentence) in enumerate(spans)
        if EE_RE.search(sentence) or YIELD_RE.search(sentence)
    ]

    candidates: list[ReactionCandidate] = []
    seen_windows: set[tuple[int, int]] = set()

    for n, anchor in enumerate(anchor_indices, start=1):
        lo = max(0, anchor - context_sentences)
        hi = min(len(spans), anchor + context_sentences + 1)
        start = spans[lo][0]
        end = spans[hi - 1][1]
        window_key = (start, end)
        if window_key in seen_windows:
            continue
        seen_windows.add(window_key)

        evidence = text[start:end].strip()
        values = {
            "ee_percent": _first_float(EE_RE, evidence),
            "yield_percent": _first_float(YIELD_RE, evidence),
            "h2_pressure_bar": _extract_pressure_bar(evidence),
            "temperature_c": _first_float(TEMP_RE, evidence),
            "reaction_time_h": _first_float(TIME_RE, evidence),
            "solvent": _first_text(SOLVENT_RE, evidence),
            "ligand": _first_text(LIGAND_RE, evidence),
            "substrate_class": _first_text(SUBSTRATE_RE, evidence),
        }

        candidates.append(
            ReactionCandidate(
                candidate_id=f"rxn-{n:04d}",
                confidence=_candidate_confidence(values, evidence),
                evidence_text=evidence,
                evidence_start=start,
                evidence_end=end,
                **values,
            )
        )

    return candidates


def candidates_to_dicts(candidates: Iterable[ReactionCandidate]) -> list[dict]:
    return [candidate.to_dict() for candidate in candidates]
