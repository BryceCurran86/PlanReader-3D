# Bounded wall equivalence: default-off experiment (MAX 7240613240)

## Observed (code and the Maryborough plan viewport, 28–29 Nov)
- Without a producer-owned graphic scale (`_producer_owned_points_per_mm` returns None here), any parallel pair with
  longitudinal overlap competes, wherever it is (`_physical_wall_pair_identity_candidacy_with_features`).
- Any ambiguous pair abstains its whole connected component. On the viewport: 3,467 walls, 479 published, 2,988
  ambiguous; every Office, Cold Room and Freezer ring-edge candidate sits in one 2,383-wall component.

## Inference
A wall whose paint is a source-drawn paired body cannot be the same physical wall as a line that never claims the same
stretch within the two walls' own thickness. The component rule blocks it anyway (transitive contamination).

## Proposed (default off, `bounded_wall_equivalence_shadow=True`)
`pb_bounded_wall_equivalence_shadow` after the existing overrides: release an ambiguity-only abstention only when
exactly one painted body (the layered builder's filled, dark, stroke-pair or merged-face collectors) covers 90% of the
straight wall with the wall's own source paths, and no direct competitor exists. Direct: shared primitive, other
viewport or level, non-straight, or a shared stretch within the combined body thickness (unowned competitor: twice the
wall's own), plus the existing 2.5 pt snap tolerance. Floor-grid-only candidates are typed non-walls: they neither
compete nor release. Never demotes, never removes a pair record, never publishes raster walls.

One representative per body stretch: walls owned by one body that claim the same stretch (its two faces, or copies)
release at most one, chosen by the existing deterministic representative rule, with the others recorded as represented
by it and those pairs as the same wall. Faces covering different stretches, or a stretch already published, release
nothing.

## Synthetic proof
28 tests: chain A-B-C (only the far wall releases), two unpainted lines, cavity and narrow leaves, thick neighbours,
shared paint, other viewport, junctions and end-to-end pieces, two faces and duplicates (exactly one), a rival beside
one face, partial faces, already published, grid typed or not, raster/several/partial/foreign bodies, order and input
checks, painted bodies from a page, and the real producer and composer (default off, one face of the free wall, the
option refused with another wall scope option). 20 single-line mutants caught.

## Authority boundaries
Equivalence is a publication gate: releasing walls can change host binding and downstream quantities, so the option
stays off until MAX accepts it with original retention. No scale, quantity or benchmark file is changed.

## Limits
Two leaves of one construction drawn further apart than their combined thickness plus 2.5 pt would both publish; walls
with unpainted faces (single lines) and raster walls stay blocked.

## Must not influence implementation
Room areas, wall counts wanted for any row, benchmark values.
