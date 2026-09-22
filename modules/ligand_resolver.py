"""Evidence-grounded ligand identity resolution.

The resolver is deliberately conservative:
- explicit named ligands can resolve through a small canonical registry;
- source-local aliases such as L1/L2 resolve only when the article text explicitly
  defines the alias;
- contradictory definitions are returned as ambiguous;
- aliases with no source definition remain unresolved rather than guessed.

This module does not infer structures from names and does not call external APIs.
"""
from __future__ import annotations
import re
from dataclasses import asdict, dataclass

_CANONICAL_LIGANDS = {
    "binap": ("LIGAND:BINAP", "BINAP"),
    "xyl-binap": ("LIGAND:XYL-BINAP", "Xyl-BINAP"),
    "xylbinap": ("LIGAND:XYL-BINAP", "Xyl-BINAP"),
    "josiphos": ("LIGAND:JOSIPHOS", "Josiphos"),
    "segphos": ("LIGAND:SEGPHOS", "SEGPHOS"),
    "biphep": ("LIGAND:BIPHEP", "BIPHEP"),
    "synphos": ("LIGAND:SYNPHOS", "SYNPHOS"),
    "mandyphos": ("LIGAND:MANDYPHOS", "Mandyphos"),
    "chiraphos": ("LIGAND:CHIRAPHOS", "Chiraphos"),
    "me-bpe": ("LIGAND:ME-BPE", "Me-BPE"),
    "mebpe": ("LIGAND:ME-BPE", "Me-BPE"),
    "duphos": ("LIGAND:DUPHOS", "DuPhos"),
    "diop": ("LIGAND:DIOP", "DIOP"),
    "dppe": ("LIGAND:DPPE", "DPPE"),
    "dppp": ("LIGAND:DPPP", "DPPP"),
    "dppm": ("LIGAND:DPPM", "DPPM"),
    "triphos": ("LIGAND:TRIPHOS", "Triphos"),
}

_ALIAS_TOKEN = r"L(?:igand\s*)?\d+[A-Za-z*′'\-]*"
ALIAS_RE = re.compile(rf"\b(?P<alias>{_ALIAS_TOKEN})\b", re.I)
_NAMED_FORMS = sorted(
    {name for _, name in _CANONICAL_LIGANDS.values()} | set(_CANONICAL_LIGANDS.keys()),
    key=len,
    reverse=True,
)
_NAMED_ALT = "|".join(re.escape(x) for x in _NAMED_FORMS)
NAMED_LIGAND_RE = re.compile(rf"\b(?P<name>{_NAMED_ALT})\b", re.I)

_DEFINITION_PATTERNS = [
    re.compile(
        rf"(?P<name>{_NAMED_ALT})\s*"
        rf"(?:\(|,\s*(?:denoted|labelled|labeled|designated)\s+)"
        rf"(?P<alias>{_ALIAS_TOKEN})\)?",
        re.I,
    ),
    re.compile(
        rf"(?P<alias>{_ALIAS_TOKEN})\s*"
        rf"(?:=|:|was|is|corresponds?\s+to)\s*"
        rf"(?P<name>{_NAMED_ALT})",
        re.I,
    ),
]


@dataclass(frozen=True)
class LigandDefinition:
    alias: str
    canonical_id: str
    canonical_name: str
    evidence_text: str
    evidence_start: int
    evidence_end: int


@dataclass
class LigandResolution:
    raw_mention: str | None
    canonical_id: str | None
    canonical_name: str | None
    status: str
    confidence: float
    resolution_method: str
    evidence_text: str | None = None
    evidence_start: int | None = None
    evidence_end: int | None = None
    candidates: tuple[str, ...] = ()
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _norm_name(value: str) -> str:
    return (
        re.sub(r"[\s_]+", "", value.strip().lower())
        .replace("–", "-")
        .replace("—", "-")
    )


def _norm_alias(value: str) -> str:
    value = value.strip().upper().replace("LIGAND", "L")
    value = re.sub(r"\s+", "", value)
    return value.replace("’", "'").replace("′", "'")


def canonicalise_named_ligand(name: str) -> tuple[str, str] | None:
    norm = _norm_name(name)
    for key, value in _CANONICAL_LIGANDS.items():
        if _norm_name(key) == norm or _norm_name(value[1]) == norm:
            return value
    return None


def extract_alias_definitions(text: str) -> dict[str, list[LigandDefinition]]:
    """Extract explicit alias→canonical definitions from full source text."""
    out: dict[str, list[LigandDefinition]] = {}
    seen: set[tuple[str, str, int, int]] = set()

    for pattern in _DEFINITION_PATTERNS:
        for match in pattern.finditer(text):
            alias = _norm_alias(match.group("alias"))
            canon = canonicalise_named_ligand(match.group("name"))
            if not canon:
                continue
            canonical_id, canonical_name = canon
            key = (alias, canonical_id, match.start(), match.end())
            if key in seen:
                continue
            seen.add(key)
            definition = LigandDefinition(
                alias=alias,
                canonical_id=canonical_id,
                canonical_name=canonical_name,
                evidence_text=text[match.start():match.end()],
                evidence_start=match.start(),
                evidence_end=match.end(),
            )
            out.setdefault(alias, []).append(definition)
    return out


def resolve_ligand_mention(
    mention: str | None,
    source_text: str,
    definitions: dict[str, list[LigandDefinition]] | None = None,
) -> LigandResolution:
    """Resolve a candidate ligand mention without guessing missing identities."""
    if not mention or not mention.strip():
        return LigandResolution(
            mention, None, None, "unresolved", 0.0, "no_ligand_mention",
            note="No ligand mention was supplied.",
        )

    direct = NAMED_LIGAND_RE.search(mention)
    if direct:
        canon = canonicalise_named_ligand(direct.group("name"))
        if canon:
            return LigandResolution(
                mention, canon[0], canon[1], "resolved", 1.0,
                "explicit_named_ligand",
                evidence_text=direct.group(0),
                note="Resolved from an explicit ligand name in the candidate evidence.",
            )

    alias_match = ALIAS_RE.search(mention)
    if not alias_match:
        return LigandResolution(
            mention, None, None, "unresolved", 0.0,
            "unknown_ligand_string",
            note="Mention is neither a registered explicit ligand name nor a recognised source alias.",
        )

    alias = _norm_alias(alias_match.group("alias"))
    definitions = (
        definitions if definitions is not None else extract_alias_definitions(source_text)
    )
    defs = definitions.get(alias, [])
    if not defs:
        return LigandResolution(
            mention, None, None, "unresolved", 0.0,
            "alias_without_source_definition",
            note=f"{alias} occurs as an alias but no explicit ligand definition was found in the source text.",
        )

    unique = {(d.canonical_id, d.canonical_name) for d in defs}
    if len(unique) > 1:
        return LigandResolution(
            mention, None, None, "ambiguous", 0.0,
            "conflicting_source_definitions",
            candidates=tuple(sorted(x[0] for x in unique)),
            note=f"{alias} has conflicting explicit definitions in the source text.",
        )

    chosen = defs[0]
    return LigandResolution(
        mention,
        chosen.canonical_id,
        chosen.canonical_name,
        "resolved",
        0.95,
        "source_defined_alias",
        evidence_text=chosen.evidence_text,
        evidence_start=chosen.evidence_start,
        evidence_end=chosen.evidence_end,
        note=f"{alias} resolved only because the source explicitly defines the alias.",
    )


def find_ligand_mentions(text: str) -> list[str]:
    """Return registered ligand names and L-number aliases in reading order."""
    matches: list[tuple[int, str]] = []
    for match in NAMED_LIGAND_RE.finditer(text):
        matches.append((match.start(), match.group(0)))
    for match in ALIAS_RE.finditer(text):
        matches.append((match.start(), match.group("alias")))
    matches.sort(key=lambda x: x[0])

    out: list[str] = []
    for _, value in matches:
        if value not in out:
            out.append(value)
    return out


def resolve_ligands_in_text(
    evidence_text: str,
    source_text: str,
) -> list[LigandResolution]:
    definitions = extract_alias_definitions(source_text)
    return [
        resolve_ligand_mention(mention, source_text, definitions)
        for mention in find_ligand_mentions(evidence_text)
    ]
