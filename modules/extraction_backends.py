"""Backend abstraction for reaction-candidate extraction.

The project keeps a deterministic rule-based extractor as the scientific
baseline. Additional extractors (including LLM-backed implementations) should
implement the same contract so they can be evaluated with the same benchmark.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from modules.reaction_candidate_extraction import ReactionCandidate, extract_reaction_candidates


class ExtractionBackend(Protocol):
    name: str

    def extract(self, text: str, *, context_sentences: int = 2) -> list[ReactionCandidate]:
        ...


@dataclass
class RuleBasedBackend:
    name: str = "rule-baseline-v1"

    def extract(self, text: str, *, context_sentences: int = 2) -> list[ReactionCandidate]:
        return extract_reaction_candidates(text, context_sentences=context_sentences)


@dataclass
class CallableBackend:
    """Adapter for experimental model/LLM extractors using the common schema."""

    extractor: Callable[[str, int], list[ReactionCandidate]]
    name: str = "experimental-callable"

    def extract(self, text: str, *, context_sentences: int = 2) -> list[ReactionCandidate]:
        candidates = self.extractor(text, context_sentences)
        if not isinstance(candidates, list) or not all(isinstance(c, ReactionCandidate) for c in candidates):
            raise TypeError("Extraction backend must return list[ReactionCandidate]")
        return candidates


def get_backend(name: str) -> ExtractionBackend:
    normalised = name.strip().lower()
    if normalised in {"rule", "rule-baseline", "rule-baseline-v1"}:
        return RuleBasedBackend()
    raise ValueError(
        f"Unknown backend: {name!r}. Available built-in backend: 'rule'. "
        "Experimental model backends should be registered through CallableBackend."
    )
