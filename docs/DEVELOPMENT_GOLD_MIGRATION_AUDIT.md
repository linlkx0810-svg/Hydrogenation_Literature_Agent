# Development Gold migration audit

Date: 2026-09-24. Branch `agent-v1-ligand-verifier`.
Scope: the 12-paper `real_development_set_v1`. **Development only, never a blind benchmark.**

## 1. What the legacy Gold actually is, and what survived

| Item | Result |
|---|---|
| Legacy set | `real_development_set_v1`, 12 cases |
| Legacy Gold | Gold v1, 96 slots (12 cases × 8 fields) |
| Attested Gold sha256 | `990799475b89051a2013c77fbcbb3128b3af278817dd67ba008ee93109c25cc5` |
| **Populated Gold artifact recovered** | **No** |
| Case identities recovered | Yes, 12/12 |
| Per-case target anchor recovered | Yes, 12/12 |
| Per-case null-field map recovered | Yes, 12/12 |
| Individual Gold values recovered | Partially, only where quoted in the source-review record |

The populated Gold was deliberately kept local and private: `gold_freeze_attestation_v1.json` states `"gold_values_published": false` and "No populated gold values are committed to the public repository". A content-addressed search over 8399 candidate files in the five local project roots found no file matching the attested hash. The artifact is gone, and this migration does not pretend otherwise.

What did survive, recovered from `origin/codex/p0-prospective-blind-v2-eval-freeze` and copied byte-identically into `benchmark/development_gold/legacy/`:

| File | blob |
|---|---|
| `manifest_v1.csv` | `703c0deef2d7fdb427b4bc9dad05bb1d6008f0ab` |
| `source_review_progress_v1.csv` | `107f76b03af9c0c1e3f3931b88f1743ff463c3ad` |
| `seed_curation_status_v1.csv` | `1149b5e147fa4695a657fec491d1fa6463faf2a4` |
| `selection_change_log_v1.md` | `83f7ffd673dc20db9c4c00e3b70e2ca027a475bc` |
| `gold_freeze_attestation_v1.json` | `27b9d5461684969405e3a3d1f193b5ff70162a40` |
| `gold_record_template_v1.json` | `02efccc336f8affceb0c204410d2d370ea994fed` |

The legacy Gold v1 is not modified, not re-hashed and not impersonated. The new artifact is a separate lineage: `legacy Gold v1 (8 fields) + source adjudication → development Gold FIELD_SCHEMA_V1`.

## 2. Case identity

The legacy case IDs are `DEV-001` … `DEV-012`, each bound to a `combined_record_id` (`FE-H2-AH-xxxx` / `NI-H2-AH-xxxx`), a DOI and one frozen target anchor. Those IDs are kept as `gold_case_id`; no new numbering was invented.

Structure check: the legacy set is 12 papers × exactly one target reaction each. `source_review_progress_v1.csv` records one `target_anchor_status` per case and `finalized_field_slots = 8` for all 12, which is 96 slots, matching the attestation. No paper carries more than one Gold target.

## 3. Field crosswalk

| old field | new field | migration type | result |
|---|---|---|---|
| `h2_pressure_bar` | `h2_pressure` | `LEGACY_GOLD_LOSSLESS_MIGRATION` | unit identical (bar); state map migrated, values unrecoverable |
| `temperature_c` | `temperature` | `LEGACY_GOLD_LOSSLESS_MIGRATION` | unit identical (°C) |
| `reaction_time_h` | `reaction_time` | `LEGACY_GOLD_LOSSLESS_MIGRATION` | unit identical (h) |
| `solvent` | `solvent` | `LEGACY_GOLD_LOSSLESS_MIGRATION` | same semantics |
| `yield_percent` | `yield` | `LEGACY_GOLD_LOSSLESS_MIGRATION` | same semantics; conversion was already excluded by the legacy review |
| `ligand` | `ligand` | `LEGACY_GOLD_LOSSLESS_MIGRATION` | same semantics; `reported_value` and `canonical_value` are now separate |
| `ee_percent` | `ee_or_er` | `LEGACY_GOLD_TYPED_MIGRATION` | becomes `{kind: "ee_percent", value: n}`; no ee→er conversion, no configuration inferred |
| `substrate_class` | `substrate` | `NON_EQUIVALENT_REQUIRES_REVIEW` | **never copied**; the class label is kept only as `legacy_support` |
| — | `reaction`, `catalyst`, `product`, `stereochemical_outcome` | `NOT_IN_LEGACY_GOLD` | cannot be migrated; source adjudication only |

Because the populated values are unrecoverable, a "lossless migration" here migrates the **state map** (which slots were answered, which were final nulls) rather than the numbers. A slot the legacy record shows as answered becomes `needs_source_review`, not a value.

## 4. Phase A output

`benchmark/development_gold/development_gold_migration_stage1.jsonl`, built by `tools/build_development_gold_stage1.py`: 12 cases × 12 fields = 144 slots, of which 8 are `not_reported` (the legacy final nulls: yield ×5, reaction_time ×1, temperature ×1, plus DEV-001's pair) and 136 `needs_source_review`. No value is filled in Phase A.

## 5. Phase B adjudication

`benchmark/development_gold/phase_b_adjudications_v1.csv` holds every adjudicated slot as an auditable row with provenance, source role, locator, evidence type, review status and comparison mode. Sources used:

- `LEGACY_SOURCE_REVIEW_RECORD` — a value stated in the legacy source-review note for the frozen target entry;
- `LEGACY_TARGET_ANCHOR` — an identity named in the frozen anchor itself;
- `SOURCE_REVIEW_RECORD_SCOPE` — the record establishes that a field was not reported within the reviewed scope.

No value came from an Agent prediction; `tools/build_development_gold.py` and `tools/freeze_development_gold.py` both reject an Agent-prediction provenance outright.

Three `stereochemical_outcome` slots are `not_reported` because the reviewed target reports er or ee only. No configuration is derived from an ee value, and that rule is written into the record.

## 6. Known gaps

118 of 144 slots remain `needs_source_review`. Filling them requires a chemist reading the 12 frozen target anchors in the local main articles and SI. The Gold freeze refuses to mark the artifact frozen while any such slot exists, and those slots leave every accuracy denominator.

`reaction` carries a second, separate problem: `FIELD_SCHEMA_V1` describes it as a controlled reaction type but defines no controlled vocabulary. Inventing one while writing Gold would be exactly the "build the format as you go" failure the protocol forbids, so all 12 `reaction` slots are marked `SCHEMA_DEFINITION_GAP` in their note and stay unadjudicated until the vocabulary is added to the schema as an explicit amendment.

## 7. Candidate binding

`benchmark/development_candidate_id_crosswalk.csv`, from `tools/bind_development_gold_candidates.py` over text extracted from the 12 local main PDFs:

| status | cases |
|---|---|
| `BOUND` | 1 |
| `CANDIDATE_BINDING_FAILURE` | 3 |
| `BINDING_PENDING_ADJUDICATION` | 8 |

A binding is recorded only when the adjudicated Gold values pin exactly one candidate chunk; "the first candidate" is never chosen. The three failures are a genuine pipeline finding: for those cases the deterministic evidence builder does not surface a chunk reproducing the adjudicated target, which is an extractor problem to fix, not a Gold problem to paper over.

## 8. Reproducing the binding corpus

The binding audit reads one `.txt` per source artifact. That corpus used to be built outside the repository and was never recorded, so `candidate_binding_v1.csv` could not be regenerated: rerunning the audit against a differently extracted corpus moved cases between binding statuses with nothing to flag it.

The corpus is now a derived artifact with a stated input. The paper PDFs are not redistributed here and the extracted text is not committed; what is committed is `benchmark/development_gold/binding_corpus_manifest.json`, holding the sha256 of every text artifact plus the extractor version that produced it.

To rebuild and re-audit:

```bash
python tools/build_binding_corpus.py \
  --pdf-root <dir with main_articles/ and supporting_information/> \
  --out-dir <corpus dir>

python tools/audit_candidate_binding.py \
  --gold benchmark/development_gold/development_gold_field_schema_v1.jsonl \
  --source-dir <corpus dir> \
  --out benchmark/development_gold/candidate_binding_v1.csv
```

The audit verifies the corpus against the manifest first and refuses to run on a corpus that does not match. `--allow-unattested-corpus` overrides that and marks the result as not reproducible.

Two limits are worth stating. The manifest hashes are tied to the recorded `pypdf` version, so a different pypdf may produce a different corpus and fail verification; the version is in the manifest for that reason. And CI has no PDFs, so it cannot rebuild the corpus at all — `tests/test_binding_corpus_contract.py` instead checks that the committed binding result still agrees with the committed Gold about which adjudicated values were usable, which is what catches a binding CSV left behind by a Gold edit.

## 9. Enantiomer ratios in the candidate builder

The rule baseline captured only `ee_percent`, so a paper reporting an enantiomer ratio gave the builder nothing to match. `modules/reaction_candidate_extraction.py` now also reads `er_major`/`er_minor`, and an er anchors a candidate window the way an ee or a yield does.

The ratio is read only where the source labels it one (`e.r.`, `er`, `enantiomer ratio`). A bare `d:d` is far too common here — eluent gradients, solvent mixtures, S:C:B loadings, dr values — and none of those is a selectivity. The two forms are never converted into each other, in the builder or in the binding comparison: an er matches an er on both terms, an ee matches an ee, and neither satisfies the other's pin.

This changed two bindings, both for the better.

`DEV-001` moves from `UNREPRESENTABLE_V1` to `AMBIGUOUS_BINDING`. Its only adjudicated value is the er `65:35`, which the builder now captures from the SI; one value still cannot pin a chunk uniquely, so the case is ambiguous rather than unreachable. Note that its anchor sentence reports `>99% GC yield`, which matches no yield pattern — without er support nothing anchored that window at all.

`DEV-003` moves from `BOUND_EXACT` to `AMBIGUOUS_BINDING`, and that is a correction. The previous binding pinned the chunk at span 6246-6432, the Scheme 2 optimization sentence reporting 99% yield and 76:24 er — not the frozen target `TABLE3_ENTRY15_BENZOXAZINONE_1A`, whose Gold is 88% yield and 91:9 er. It matched on pressure and temperature alone, two table-wide conditions, and looked unique only because the builder could not read `91:9 er` and so scored the correct chunk lower. With the ratio readable, the correct chunk reaches the same score and the tie is reported honestly. A 2-of-6 match was never a confident binding.

One consequence worth recording: `candidate_id` is positional (`rxn-NNNN`), so adding an anchor renumbers later candidates. The stable identifier is `source_chunk_id`, which carries the artifact and the character span.

A known gap is pinned by an `xfail` in `tests/test_reaction_candidate_extraction.py`: the sentence splitter reads the period in `e.r.` as a sentence end, so a window opening with the abbreviation is cut before its ratio. Value-first forms, which is how this literature overwhelmingly writes it, are unaffected.
