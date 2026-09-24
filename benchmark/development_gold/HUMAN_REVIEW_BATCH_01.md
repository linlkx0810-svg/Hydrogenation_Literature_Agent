# Development Gold — human review batch 01

Date: 2026-09-24. Role of Claude in this batch: `SOURCE_REVIEW_ASSISTANT`, not the reviewer.

Every row below is a **proposal**. Nothing here has entered the formal Gold, and nothing will until
`reviewer_decision` is filled in `human_review_batch_01.csv` and `tools/apply_human_gold_reviews.py` is run.
High confidence is not human confirmation.

Scope: the queue reason `VALUE_MUST_BE_READ_FROM_THE_FROZEN_TARGET_ANCHOR` only. Structure-only ligands,
catalysts, substrates and products, and any configuration needing structure interpretation, are deliberately
left for batch 02.

Rows: 19 across 4 cases. HIGH 14, MEDIUM 5, LOW 0.

Review order below is by expected binding information gain, not by case id.

## DEV-008 — FE-H2-AH-0011 — target: EXACT_TARGET_PARAGRAPH

B01-001 | DEV-008 | h2_pressure
Proposed: answered = 50 bar   (source wording: 50 bar H2)
Source: MAIN, Procedure for Larger-Scale AH of Acetophenone
Confidence: HIGH
Decision: [ ] APPROVE  [ ] REJECT  [ ] MODIFY  [ ] UNRESOLVED

B01-002 | DEV-008 | temperature
Proposed: answered = 45 degree_celsius   (source wording: 45 C)
Source: MAIN, Procedure for Larger-Scale AH of Acetophenone
Confidence: HIGH
Decision: [ ] APPROVE  [ ] REJECT  [ ] MODIFY  [ ] UNRESOLVED

B01-003 | DEV-008 | reaction_time
Proposed: answered = 12 hour   (source wording: 12 h)
Source: MAIN, Procedure for Larger-Scale AH of Acetophenone
Confidence: HIGH
Decision: [ ] APPROVE  [ ] REJECT  [ ] MODIFY  [ ] UNRESOLVED

B01-004 | DEV-008 | solvent
Proposed: answered = MeOH   (source wording: MeOH (50 mL))
Source: MAIN, Procedure for Larger-Scale AH of Acetophenone
Confidence: HIGH
Decision: [ ] APPROVE  [ ] REJECT  [ ] MODIFY  [ ] UNRESOLVED

B01-005 | DEV-008 | yield
Proposed: answered = 98 percent   (source wording: 98% isolated yield (11.93 g))
Source: MAIN, Procedure for Larger-Scale AH of Acetophenone
Confidence: HIGH
Decision: [ ] APPROVE  [ ] REJECT  [ ] MODIFY  [ ] UNRESOLVED

B01-006 | DEV-008 | ee_or_er
Proposed: answered = 96 percent_ee   (source wording: 96% ee)
Source: MAIN, Procedure for Larger-Scale AH of Acetophenone
Confidence: HIGH
Decision: [ ] APPROVE  [ ] REJECT  [ ] MODIFY  [ ] UNRESOLVED

## DEV-009 — FE-H2-AH-0017 — target: EXACT_TABLE_ROW

B01-007 | DEV-009 | h2_pressure
Proposed: answered = 30 bar   (source wording: 30 bar)
Source: MAIN, Table 1 entry 4
Confidence: HIGH
Decision: [ ] APPROVE  [ ] REJECT  [ ] MODIFY  [ ] UNRESOLVED

B01-008 | DEV-009 | temperature
Proposed: answered = 80 degree_celsius   (source wording: 80 C)
Source: MAIN, Table 1 entry 4
Confidence: HIGH
Decision: [ ] APPROVE  [ ] REJECT  [ ] MODIFY  [ ] UNRESOLVED

B01-009 | DEV-009 | reaction_time
Proposed: answered = 20 hour   (source wording: 20 h)
Source: MAIN, Table 1 entry 4
Confidence: HIGH
Decision: [ ] APPROVE  [ ] REJECT  [ ] MODIFY  [ ] UNRESOLVED

B01-010 | DEV-009 | solvent
Proposed: answered = toluene   (source wording: toluene)
Source: MAIN, Table 1 entry 4
Confidence: HIGH
Decision: [ ] APPROVE  [ ] REJECT  [ ] MODIFY  [ ] UNRESOLVED

B01-011 | DEV-009 | yield
Proposed: answered = 85 percent   (source wording: 85% yield)
Source: MAIN, Table 1 entry 4
Confidence: MEDIUM
Why not HIGH: The target row gives 85% under a yield column and the prose repeats 85% yield, but the entry itself does not say isolated; a neighbouring entry is described as isolated. Reviewer should confirm the yield kind.
Decision: [ ] APPROVE  [ ] REJECT  [ ] MODIFY  [ ] UNRESOLVED

## DEV-012 — NI-H2-AH-0029 — target: EXACT_TABLE_FOOTNOTE

B01-012 | DEV-012 | h2_pressure
Proposed: answered = 50.6625 bar   (source wording: hydrogen (50 atm))
Source: MAIN, Table 2 entry 2
Confidence: HIGH
Decision: [ ] APPROVE  [ ] REJECT  [ ] MODIFY  [ ] UNRESOLVED

B01-013 | DEV-012 | temperature
Proposed: answered = 50 degree_celsius   (source wording: 50 C)
Source: MAIN, Table 2 entry 2
Confidence: HIGH
Decision: [ ] APPROVE  [ ] REJECT  [ ] MODIFY  [ ] UNRESOLVED

B01-014 | DEV-012 | reaction_time
Proposed: answered = 24 hour   (source wording: 24 h)
Source: MAIN, Table 2 entry 2
Confidence: HIGH
Decision: [ ] APPROVE  [ ] REJECT  [ ] MODIFY  [ ] UNRESOLVED

B01-015 | DEV-012 | ee_or_er
Proposed: answered = 99 percent_ee   (source wording: 99% ee)
Source: MAIN, Table 2 entry 2
Confidence: HIGH
Decision: [ ] APPROVE  [ ] REJECT  [ ] MODIFY  [ ] UNRESOLVED

B01-016 | DEV-012 | solvent
Proposed: answered = TFE   (source wording: CF3CH2OH)
Source: MAIN, Table 2 entry 2
Confidence: MEDIUM
Why not HIGH: Gold already holds TFE from the legacy record; the source writes CF3CH2OH. Same substance, different naming. Reviewer should decide whether Gold stores the source spelling or the abbreviation, and whether the comparison key covers both.
Decision: [ ] APPROVE  [ ] REJECT  [ ] MODIFY  [ ] UNRESOLVED

## DEV-007 — FE-H2-AH-0006 — target: STANDARD_CONDITIONS_FOR_TABLE

B01-017 | DEV-007 | h2_pressure
Proposed: answered = 25.33125 bar   (source wording: 25 atm H2)
Source: MAIN, Table 2 entry 7 (complex 6)
Confidence: MEDIUM
Why not HIGH: The prose states the standard iron-catalysis conditions for this table as 25 atm H2 at 50 C. The individual entry-7 row is not recoverable from the extracted text, so the reviewer must confirm entry 7 runs under standard conditions.
Decision: [ ] APPROVE  [ ] REJECT  [ ] MODIFY  [ ] UNRESOLVED

B01-018 | DEV-007 | temperature
Proposed: answered = 50 degree_celsius   (source wording: 50 C)
Source: MAIN, Table 2 entry 7 (complex 6)
Confidence: MEDIUM
Why not HIGH: Same standard-conditions sentence as the pressure; entry-7 row not directly readable.
Decision: [ ] APPROVE  [ ] REJECT  [ ] MODIFY  [ ] UNRESOLVED

B01-019 | DEV-007 | solvent
Proposed: answered = isopropanol   (source wording: basic isopropanol)
Source: MAIN, Table 2 entry 7 (complex 6)
Confidence: MEDIUM
Why not HIGH: The hydrogenation of acetophenone is described as being run in basic isopropanol for this table. Base is an additive, not part of the solvent value.
Decision: [ ] APPROVE  [ ] REJECT  [ ] MODIFY  [ ] UNRESOLVED

## If this batch is approved

- candidate binding exact: 2 -> 2
- ambiguous: 2 -> 2
- unrepresentable: 8 -> 8

One case would move to `BOUND_EXACT`. One case would move from `AMBIGUOUS_BINDING` to
`UNREPRESENTABLE_V1`: with more adjudicated values it becomes provable that no candidate chunk reproduces a
target whose conditions live in a table footnote. That is a real evidence-builder limitation surfacing, not a
regression in the Gold.

## How to record decisions

1. fill `reviewer_decision` in `benchmark/development_gold/human_review_batch_01.csv`
2. for `MODIFY`, also fill `reviewer_value`, `reviewer_state` and `reviewer_note`
3. run `python tools/apply_human_gold_reviews.py --gold <gold> --reviews <batch csv> --out <gold>`

`REJECT` and a blank decision both leave the slot open. Only a filled decision can change the Gold.
