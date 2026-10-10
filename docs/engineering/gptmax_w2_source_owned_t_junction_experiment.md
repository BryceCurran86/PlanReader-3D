# Experimental W2 exact source-owned through-junction anchoring (NOT APPROVED)

## Real source root cause (Lot16 original)
Original source SHA 10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844.
In the archived source scope, the ordinary raster source primitive ending :1567
supports vertical wall at x=381 from y=297..349 page points. The registered
local edge fragments are 297..336.75, 338.75..342.72, and 342.72..349.
The **336.75..338.75 gap remains unproven** and must not be bridged.

An independently source-painted terminal horizontal segment
(381,342.72) -> (410.25,342.72) meets the ordinary wall at an exact
positive source-owned T at (381,342.72). The W2 centroid instead snaps
the node to (380.64,342.72); a new short segment of the original wall
then exceeds the existing host-orientation check. The physical opening
38c03575... loses its previously authenticated host and frame.

The first two experimental ideas (#2147: suppress overlapping/crossing/T
supplements) failed actual original-source retention and one real synthetic
compact flank; the legitimate T must not disappear.

## Narrow experimental fix
Preserve W2's existing endpoint-snap 2.5-point tolerance, adjacency,
source/edge membership, branch, splitter and all unproven source gaps.
At degree >=3 graph junctions only, correct the snapped junction **coordinate**
to the exactly shared ORIGINAL raw point if:

1. two opposing original fragments share exactly one authenticated primitive
   source ID and a byte-identical split endpoint (within splitter float epsilon);
2. both original fragment endpoints and the junction lie on that same positive
   original source line, and the anchor is strictly in its interior;
3. the pair is exactly collinear with opposing tangents (not L bends);
4. there is a UNIQUE anchor across all available candidate source-line pairs;
5. every incident raw endpoint, and the displaced snapped centroid, lie within
   the **existing** snap tolerance from the positive source anchor.

No absence of a true wall is inferred. No wall host or count is minted.
This does not prove the source gap; it only prevents an orthogonal branch
from distorting a point whose straight through-line is independently
supported by two positive original-source fragments.

## Adoption gate
DRAFT only until full Python 3.13/3.14, Lot16 original-source exact physical
opening/host/frame identity and Maryborough original-source parity pass.
A host count increase may not compensate for a lost original host/frame;
a newly rekeyed host/frame requires explicit independent source-equivalence
review and is **NOT** silently acceptable. New geometry must never weaken
source origin, line-angle, scale or 20,000 source-primitive cap.

No frozen V2 manifests/evaluator/object universe/reference takeoffs/denominators
or predicted benchmark labels are read, edited or used as algorithm inputs.


## Narrowed positive supplemental raster source gate

The first clean-main version (#2158) failed actual original Lot16 source retention
despite 23/14/9 aggregate parity: it churned ten host receipts and five source
frame receipts. The reason was overly broad junction reanchoring even when
there was NO compact/terminal supplemental source competing at the node.

This combined stacked branch now requires an independent producer-owned
supplemental compact/terminal raster observation for any correction:
first-party compact_solid_wall_band_v1 or terminal_solid_wall_band_v1 source
identity, sole original parent source record with positive page-coordinate
authority, endpoint exactly at the already source-authenticated through point,
and orthogonal outgoing T stem. Ordinary raster, native linework, missing
or ambiguous ancestors, near-endpoint, remotely extending parents and diagonal
branches cannot trigger reanchoring. The old source gap remains unresolved.

A passing clean-main negative-control run alone is not acceptance. Only the
stacked real compact plus narrowed W2 original-source Lot16 and Maryborough
source CI can demonstrate retained proof and any legitimate host recovery.
