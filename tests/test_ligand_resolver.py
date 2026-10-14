from modules.ligand_resolver import (
    extract_alias_definitions,
    resolve_ligand_mention,
    resolve_ligands_in_text,
)


def test_explicit_named_ligand_resolves():
    result = resolve_ligand_mention("BINAP", "BINAP was used.")
    assert result.status == "resolved"
    assert result.canonical_id == "LIGAND:BINAP"


def test_source_defined_alias_resolves():
    text = (
        "Xyl-BINAP (L2) was prepared. "
        "The hydrogenation was then performed with ligand L2."
    )
    result = resolve_ligand_mention(
        "L2", text, extract_alias_definitions(text)
    )
    assert result.status == "resolved"
    assert result.canonical_id == "LIGAND:XYL-BINAP"


def test_undefined_alias_abstains():
    result = resolve_ligand_mention(
        "L9", "The reaction used ligand L9 under hydrogen."
    )
    assert result.status == "unresolved"
    assert result.canonical_id is None


def test_conflicting_alias_is_ambiguous():
    text = "L1 = BINAP. In a conflicting table note, L1 = SEGPHOS."
    result = resolve_ligand_mention("L1", text)
    assert result.status == "ambiguous"
    assert set(result.candidates) == {
        "LIGAND:BINAP",
        "LIGAND:SEGPHOS",
    }


def test_resolve_mentions_in_evidence():
    source = (
        "SEGPHOS (L3) was used. "
        "The best result was obtained with L3."
    )
    out = resolve_ligands_in_text(
        "The best result was obtained with L3.", source
    )
    assert len(out) == 1
    assert out[0].canonical_id == "LIGAND:SEGPHOS"
