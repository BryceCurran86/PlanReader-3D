# Original PlanReader — room perimeter gap ownership (2026-11-12)

## Observed production behavior (not benchmark predictions)

- The original SHA-authenticated 18-page 3Laurel project handoff on
  consolidated production head `aa1f985f` completed but yielded
  `no_sealable_quantities`, no customer rows and no new scored project.
  Its canonical wall/room counts are *candidates*, not physical quantities.
- On the same immutable original A0.3 source page, the opt-in original
  wall/doorway ring builder at parent `2569e8a0` yielded 8 free-space
  ring records: 4 CANDIDATE and 4 ABSTAINED for unresolved collinear gaps.
  There were 80 unresolved source-band hypotheses; these are **not** 80 doors.
- A private, read-only source diagnostic showed that 3 of the 4 blocked
  free-space rings were adjacent only to collinear gap intervals for which
  **one or neither** interval endpoint belonged to that ring's exterior.
  An unrelated source wall extending a band or an internal partition break
  was being treated as a breach of the room's enclosing outer perimeter.

## First failing gate and reusable fix

`pb_layered_wall_doorway_room_ring_shadow.build_layered_wall_doorway_room_rings`
formerly used `part.buffer(NOISE_PT).intersects(gap.rect())` for
`open_wall_gap_unresolved`. That asks whether a gap intersects ANY portion
of a free region, not whether it actually breaks **this** region's perimeter.
Even checking one point on `part.exterior` is not enough: a gap may extend
out to an unrelated collinear source wall.

The bounded generic rule now requires **both original gap endpoints** to
touch this specific free region's outer perimeter within the existing
0.05 PDF-point representation noise. Endpoints are checked as short wall-band
cross sections, not bare center points. Internal holes, disconnected wall
runs outside the region and one-sided touches therefore do not veto an
independently enclosed region. Genuine two-ended source wall interruptions
continue to ABSTAIN absent a source-attested doorway closure.

The fix changes only topology *candidate/abstention interpretation*.
It does **not** infer source continuity, authenticate a room, estimate a
dimension, install a physical door, change wall lengths, enable finishes,
or add any customer or benchmark record.

## Evidence / negatives

Synthetic regressions cover enclosed outer rings with interior partial wall
stubs; open external perimeters; two-ended unresolved outer gaps; one-ended
external/unrelated source runs; horizontal/vertical axis exchange; translation;
0.5x/2x scale; input order; no input mutation; and the default-off customer
restriction. Existing source ring, face, structural and segmented-door tests
must remain green.

A repeat exact-source opt-in shadow probe on the same original after the change
yielded 8 records: **7 CANDIDATE, 1 ABSTAINED**, versus 4/4 before.
Remaining 1 stays blocked. **No source-authenticated physical room, metric
area, commercial line or new frozen benchmark score is claimed.**

## Publication and follow-on

- Private original PDF and source diagnostic coordinates/IDs remain private.
- Frozen 120 (27/24/63/6), 2.5 pt production snap, 20k primitive cap and all
  previous sealed customer receipts remain unchanged.
- This branch is stacked on Cursor's `#4302` head `2569e8a0`; no overwrite
  of Cursor's wall-end helper or GPT MAX Maryborough source work.
- Next stage is to source-authenticate the remaining single unresolved region
  and independent physical/finished-face/scale/door ownership, then verify
  source-to-customer quantities through the original existing issuers.
- Historical 3Laurel sealed development score remains **19/63** from its
  separate 35-opening-area signed/customer run; the new unsealed project
  attempt must not be scored as 0/63 or 100%.
