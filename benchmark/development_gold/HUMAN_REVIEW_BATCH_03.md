# Human review batch 03 — absolute configuration

8 proposals covering the `stereochemical_outcome` slots. Claude proposed them from the
sources; every `reviewer_decision` ships blank. Nothing reaches the Gold until
`tools/apply_human_gold_reviews.py` is run over decisions recorded here.

## What the sources actually say

The queue reason for these slots is `ABSOLUTE_CONFIGURATION_NOT_ESTABLISHED`, and the
three slots closed earlier were closed as `not_reported` on the scope of the legacy
review record rather than on a reading of the papers. Reading the papers reverses the
expectation: **six of the nine state a configuration outright**, so these are Gold
values gained, not slots written off.

| review | case | proposal | confidence | basis |
|---|---|---|---|---|
| B03-001 | DEV-004 | `answered` S | HIGH | Table 1 footnote [a], the anchor's own table |
| B03-002 | DEV-005 | `answered` R | MEDIUM | table footnote for the same 1a; anchor is the SI procedure |
| B03-003 | DEV-006 | `answered` R | MEDIUM | product-level assignment, (R)-GVL |
| B03-004 | DEV-008 | `answered` S | MEDIUM | SI characterization of the same product |
| B03-005 | DEV-011 | `answered` S | HIGH | the anchor's own sentence, (S)-2l |
| B03-006 | DEV-012 | `answered` R | HIGH | footnote above Table 2, naming product 2a |
| B03-007 | DEV-002 | `answered` R | LOW | the SI descriptor and its own rotation disagree |
| B03-008 | DEV-007 | `not_reported` | HIGH | stated nowhere in article or SI |

No configuration is inferred from an ee or an er anywhere in this batch, and none is
carried across from a ligand's descriptor.

## The two that need your eye

**B03-007 (DEV-002)** is the one real conflict. The SI titles the product
`(R)-1-(sec-butyl)-4-methoxybenzene (2a)` but reports `[a]20D = -23.2 (c 1.11, CHCl3)`
against a cited literature value of `[a]23D = +27.0 (c 1.0, CHCl3)` at 94% ee. The
printed descriptor and the measured rotation point opposite ways and the text does not
explain it. The proposal records only what the SI literally prints; resolving which
enantiomer this is needs a chemist, and `REJECT` or `UNRESOLVED` are both reasonable
answers.

**B03-003 (DEV-006)** and **B03-004 (DEV-008)** are product-level assignments that are
not printed at the anchor itself. They are chemically sound — same substrate, same
catalyst, same product — but they are a cross-reference, not a direct read, which is
why they are MEDIUM.

## DEV-010 is deferred, not missing

`NI-H2-AH-0007` names no configuration in prose, but Table 1's footnote declares a sign
convention: *"Reactions favoring (R)-2a are denoted with positive values of % ee while
reactions favoring (S)-2a are denoted with negative values of % ee."* The configuration
of the frozen target is therefore recoverable from the **sign** of Table 2 entry 20's
ee — which is itself still an open slot.

Two things are unestablished: whether the Table 1 convention extends to Table 2, which
the paper does not say, and what entry 20's signed value is, which has to be read off
the typeset table. Proposing `not_reported` here would be wrong, and proposing a
configuration would be a guess. The slot belongs with the value read for
`TABLE2_ENTRY20_MODEL_1A`.
