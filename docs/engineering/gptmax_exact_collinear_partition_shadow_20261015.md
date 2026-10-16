# Exact collinear source intervals: separate shadow continuation

Tracker #2396. Pre-code architecture receipt: comment6185889303. Stacked on
source-incidence PR #2770; neither experiment is promoted into production.
AGENTS, engineering playbook, W1–W10 observability/spec, benchmark firewall and
CI were read. The traced path is original G17/F07 source paint → W2
`build_wall_graph_for_viewport` → `split_segments_at_intersections` → W3
`deduplicate_coincident_edges` / `classify_junctions` → W4 assembly. Frozen
benchmark facts are not algorithm inputs. No authority boundary is crossed.

## Observed behavior and hypothesis

At the actual lower a68 junction, source `raster_wall_band_face:1516` spans
`[716.16,429.36]..[760.32,429.36]`. Independently painted source
`raster_wall_band_end:1365` is contained at
`[737.76,429.36]..[740.40,429.36]`. Source1518 ends vertically at737.76.
Both original horizontal source spans have positive unchanged image paint.
The original splitter skips collinear inputs. It splits1516 at737.76 for the
vertical crossing but leaves the partial overlap to740.40 unsplit. W3 can
deduplicate exact node pairs, not unequal partially overlapping spans. Its
three collinear incident branches correctly abstain. PR #2770 keeps that
negative result intact.

Following the other actual a68 flank also reveals two independent whole-source
paint negatives in the full-sheet G17 scope: jamb1356 is13/14 solid original
cells, and face1499 is128/130. Both are inside the original image/F07 view and
all cells remain unchanged, but neither entire source span is solid. They
correctly never enter this scope's positive W2 input universe. The existing
opening-local `source_ink_supported=True` uses its own checks and remains
unchanged; it is not interchangeable with full-span original-pixel cover.
Neither observer result overrides the other. The exact negative source
observation receipts are `source_observation_de5bab94dff2a5769ec4965e134e538e`
and `source_observation_ec5bf71878c00a8b1703ed05a37a5625` in the all-page root.

The inference is that the source graph can represent coincident paint by its
elementary interval union without asserting any physical wall equivalence.
The proposed shadow change partitions existing W2 split fragments at existing
exactly collinear endpoints. Finite binary-float coordinates are compared as
exact rationals. It introduces no rounded point, offset tolerance, gap closure,
nearest selection or W3 threshold change. Existing plural lineage and graphic
attribute conflicts are unioned on each fully covering input interval; exact
emitting fragment addresses remain additional derivation diagnostics. Original
primitive/source records remain the evidence, not those derived addresses.

This intentionally conservative predicate may leave mathematically collinear
rotated float coordinates separate when their stored binary values differ.
It cannot turn a near-collinear source into an exact collinear source. Existing
splitter rounding and original plural containment ancestry are not redefined
or newly authenticated by this operation.

## Functional seam and expected abstentions

`partition_exact_collinear_overlaps_shadow=True` requires all existing exact
source-incidence policies explicitly enabled and zero snap. It runs after
original splitting/lineage capture and before exact snap/degree-two merge.
Original graphs remain present and byte-equivalent by default. The original
producer-owned G17 reader adds a separately scoped candidate graph and repeats
source exit authentication. No caller-owned JSON or geometry can enter that
reader as an authenticated wall universe.

Synthetic partial overlap becomes the unchanged W3 T classifier, while true
short isolated arms remain ambiguous. Source conservation, complete source
records and conflicting graphic state must survive. Same-side source overlap
is paint multiplicity, not a count of walls or physical openings. Structural
wall role, exact ordinary source membership, physical equivalence, host,
frame, measurement, vertical placement and complete count remain independent.
No case below has a new customer-ready quantity ID.

## First failing authority stages for the 13 nonquantity objects

Producer-issued selected-page snapshot:
`source_snapshot_3fcb6bc5c44b51d930e9600080501d27`; decision scope
`wall-source:page-3`. All-page source replay is separately
`source_snapshot_7ad8bf09e3ebbec9797df89842574683`; do not alias the roots.
Identity suffixes have prefix `physical_opening_existence_`.

| Physical identity suffix | First quantity-path authority failure | Independent source detail |
| --- | --- | --- |
| 00d50eb9ef77840451522efdc25f2df5 | Metric axes / vertical placement | Authenticated frame; no original opening label; no owned schedule/height. |
| 33d277d4c6b6ce758b0594f9d47ce4d8 | Host wall identity | Original3.84pt terminal and source-positive flank retained; no structural wall/equivalence. Single870 figure is not an area. |
| 38c03575cd66ed19cae7f9e4489f1609 | Metric axes / vertical placement | Authenticated frame; no original opening label or owned schedule/height. |
| 4b8c096b603c87f06f2692aa00494ab8 | Host frame | Authenticated host; single870 figure, no independently owned second axis. |
| 81a45c3a33c2a4c0bfdf243aa45a780d | Host wall identity | Positive flank paint; right ordinary source membership/structural identity unproved; single870 figure. |
| 86236fe338e5f5efb4cddf273a5013ff | Metric axes / vertical placement | Authenticated frame; no original opening label or owned schedule/height. |
| 8ecb81b6524804c80710ec323050be6b | Metric axes / vertical placement | Authenticated frame; single870 figure only; width witness topology and independent height absent. |
| a68d0b7d738b5de9a1588b4e680e1a8f | Host wall identity | Source-incidence corrections are candidates; original W3 overlap negative retained. Opposite full-sheet jamb/face paint13/14 and128/130 remain negative; structural wall/equivalence unproved; single870 figure. |
| ab431bf4eca30b24da97e2fe3b0f424b | Host frame | Authenticated host; single870 figure, no independent second axis. |
| b248972669988c108ebc90c6ca3908fd | Host wall identity | Original whole flank paint negative retained; distinct0.24pt terminal below existing gate; label unavailable. |
| ba7f75a2e5f68bcce87cd00ac1acf90b | Host wall identity | Original whole flank paint negative retained;76.8pt contained source terminal has no structural role/equivalence; single870 figure. |
| c3c1e04acd78419e4f707dfcd89c7096 | Host frame | Authenticated host; single870 figure, no independent second axis. |
| f819752382d44a00d9f28feca4b00787 | Host wall identity | Positive paint without ordinary same-source W4/structural identity/equivalence; original label remains ambiguous. |

The other eight quantity objects are preserved. Three already published
figured-area objects independently lack complete frames; do not revoke their
existing quantities or claim their void geometry is complete. Raw raster
count closure remains30 raw /21 resolved /9 unresolved; no count=1 or complete
physical universe is inferred. Native typed opposition and ABSTAIN remain.

## Verification

The synthetic matrix covers exact similarities (including rotations with
exactly representable coordinates), translation/scale, source direction/order,
splitting, unrelated content/viewport expansion, deterministic IDs, no mutation,
same-side/full/nested duplicates, genuine gaps, true one-ULP offsets, oblique
lookalikes, source attribute conflict, invalid/nonfinite input, strict flags,
actual producer source tampering and unchanged baseline graphs/receipts.
Local focused suites passed232 tests. Fresh immutable-PDF replay completed on
2026-10-15: all1162 positive original spans conserved, lower a68 junction is
a candidate T, all four preceding source graphs are exactly retained, and
the complete original eight quantity/seal/customer receipts equal the prior
verified replay. The committed source-workflow assertions passed against
that fresh report. The lower-source partition has no host or metric grant.
Exact-head CI/artifact verification remains required before review.

PR #2770 independently passed original-source workflow38691884887 and both
3.13/3.14 source-negative jobs at head97d0e3bbb0c305819312fe1476fd73a8881041cb.
Downloaded artifact11952387464 ZIP SHA
`ea4a6330724cb688dfa01e1a4685ede50b8d963e3d1d0cbdb710cdbd056afeea`
passed the committed assertions and complete sealed/customer receipt equality.
Its issued F07 ownership is `f07_viewport_ownership_07a54af7c72e173422397c404f4892dc`;
local replay issued `f07_viewport_ownership_a6137915bb59bf4f11e4330622f859b7`.
These distinct producer ownership records are retained as issued, never
aliased or used to transfer experimental wall identity across runs.
Original20k cap, commercial output, authenticated host/frame/canonical IDs,
native/raster negatives, W10 and frozen V2 reference/evaluator are untouched.
