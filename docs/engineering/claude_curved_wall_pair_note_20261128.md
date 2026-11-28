# Curved walls from paired arcs (CL-R26, 2026-11-28, report only)

## Observed
Wall candidates are assembled from straight segments only; curves are not extracted, so a curved wall is never a
candidate. The ring builder reads arcs only to find door swings (a quarter arc with its straight leaf).

## Inference
A curved wall drawn as two faces appears as two concentric arcs of one ink, a wall's thickness apart, over the same
angles.

## Built (nothing imports it)
`pb_curved_wall_pair_shadow.curved_wall_pairs(drawings)` fits circles to native Bezier curves (0.8 pt, radius at least
20 pt), merges pieces of one circle and ink, and reports pairs 1.2–14 pt apart (the ring builder's thickness limits)
sharing at least 30 degrees. It abstains on a third concentric arc nearby and on arcs carrying a door leaf from the
centre; full circles never count. Synthetic positives (moved, turned, wrapping, split, clockwise), look-alikes (one
face, too thick, short overlap, mixed ink, columns, small symbols, offset centres), rings, door swing, order and
no-mutation. Mutants caught.

## Not authority
No wall, id, room, host, measurement or quantity. Originals not yet read through it; curved walls drawn as polylines
are not covered.
