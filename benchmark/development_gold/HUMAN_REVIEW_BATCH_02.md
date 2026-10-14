# Development Gold — human review batch 02 (open)

Prepared: 2026-10-10. Status: **AWAITING_HUMAN_DECISION**.

These are two **proposals only**, based on the already visually inspected
Table 2, entry 7, of the DEV-007 main article (PDF page 5, journal page 739).
The authoritative `reviewer_decision` and `reviewer_note` cells are blank
in `human_review_batch_02.csv`; **Gold has not changed for these slots**.

Frozen target: `DEV-007 / FE-H2-AH-0006 /
TABLE2_ENTRY7_COMPLEX6_ACETOPHENONE`.

| review_id | field | proposed Gold value | exact evidence | decision |
| --- | --- | --- | --- | --- |
| B02-001 | reaction_time | `18 hour` (reported `18 h`) | MAIN, Table 2 entry 7, time column | Pending |
| B02-002 | ee_or_er | `{kind: ee_percent, value: 61}` (reported `61% ee`) | MAIN, Table 2 entry 7, e.e. column | Pending |

Entry 7 reports catalyst `6`, `S:C:B = 225:1:15`,
`T = 50 °C`, `PH₂ = 25 atm`, `time = 18 h`,
`conv. = 4%` and `e.e. = 61%`.
There is no row-specific footnote or table-wide conditions default.
The single footnote defines S, C and B. The 4% conversion must
**not** be promoted as yield: existing `yield = not_reported` is unchanged.

After explicit human decisions, replay the newly approved review rows
using `tools/apply_human_gold_reviews.py` and refresh Gold status, freeze
hash, binding audit, queue, and CI replay. A pending proposal alone
does not confer `HUMAN_CONFIRMED`. No builder, Agent, PBV3,
or prediction artifacts are to be changed in this batch.
