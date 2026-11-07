# W2-W4 physical-wall axis disagreement: demotion-only correction

Date: 2026-11-08 (Australia/Brisbane). Owner-support implementation; coordination issue #4135.

## Proven source-neutral defect

In `pb_physical_wall_identity._classify_physical_wall_pair_with_features`,
`_axis_interval` chooses a dominant **h** or **v** axis using the
path's endpoint vector. Equal/partly-shared original ancestry can have
nearly identical diagonal paths with h versus v dominant axes. Prior code
classified these pairs `DISTINCT_PHYSICAL_WALLS` by using
`_intervals_disjoint` (h/v => true) for equal ancestry, and
`not _intervals_overlap` (h/v => true) for partly-shared ancestry.
These compare an x-coordinate range to a y-coordinate range, which cannot
prove longitudinal separation or independent physical walls.

## Bounded correction

If both source-related paths have intervals **but the dominant axes
disagree**, return the existing
`AMBIGUOUS_PHYSICAL_EQUIVALENCE` status before either
distinctness branch. This is strictly a demotion from an unsafe positive
distinctness result. It **does not** establish SAME, bypass candidacy,
change interval arithmetic for comparable axes, infer installed geometry,
or grant metric, finish, opening or customer quantity.

Changed production path: `pb_physical_wall_identity.py` only.
Updated the independent uncached feature-cache oracle to preserve its
cached/uncached differential test under the corrected rule; added
`tests/test_physical_wall_axis_disagreement_abstain.py`.

## Tests and safety gates

Source-neutral assertions: equal original ancestry and partly shared
ancestry both ABSTAIN under h/v disagreement (both input orders);
the full identity-component resolver also withholds both competitors;
same-axis disjoint is still DISTINCT, same path/equal ancestry stays SAME,
and unrelated ancestry gains no identity. Existing cached/uncached random
and adversarial gates continue to apply.

The unchanged ten private source PDFs, four-project 120-item truth and
evaluator, 20,000 primitive limit, 2.5-point snap, all historical signed
Lot16 eight and Maryborough three source-sealed/customer bodies are NOT
modified. Main, Claude's semantic work and MAX's mixed-family runner
have not been edited by this branch.

**Release requirements (not asserted until actual receipts):**
same-head Python 3.13 and 3.14 checks, protected actual-original
Lot16-eight/Maryborough-three historical byte retention, and MAX's
integration acceptance. No new FIRM item, commercial output, metric
receipt, project seal or official frozen benchmark score is claimed.
