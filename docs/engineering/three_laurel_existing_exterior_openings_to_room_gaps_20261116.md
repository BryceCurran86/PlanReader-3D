# Existing exterior opening evidence linked to room wall gaps — 16 Nov 2026

**Not a new door/window detector. Not a production measurement issuer.**

This child of PR #4383 consumes the **existing and already successful
source-native opening detectors** for fixed exterior windows, hosted swing
doors, ASD/SGD sliders and garage panel-lift doors. Nothing in those modules
was changed or reimplemented.

`pb_three_laurel_floor_opening_correspondence_shadow.py` takes an existing
`FloorWallCandidateReceipt` and a collection of independently source-owned
opening receipts. It places those receipts only along **uncovered** original
floor candidate boundary intervals with matching original page, edge axis
and location. It retains source opening path owners and distinguishes
`closed_room_edge_not_opaque_wall` for fixed windows from
`doorway_threshold_not_solid_wall` for every door family.

It must **not**:
- turn a window span into opaque wall/paint,
- bill a door opening as wall area,
- extend the floor finish across a threshold or into outdoor alfresco/porch,
- declare a room fully enclosed merely because some gaps match,
- infer an opening when source arc, cap, track, window markers or callout is missing,
- accept conflicting window/door claims on the same edge,
- change the frozen120 benchmark or customer quantities.

It always emits `physical_wall_authenticated=False` and
`measurement_authorized=False`, and cannot promote any existing issuer to
`FIRM`.

## Real original-source read-only replay

On the unchanged private 3Laurel Rev3 ground-floor plan page index 2,
existing native producers emit **22 original source-backed exterior openings**
(16 windows, 3 hinged swing doors, 2 ASD sliding doors, 1 garage panel-lift
door). Independent shadow floor wall correspondence finds seven overlaps
along previously unsupported room boundary segments:

- MEDIA north: original window marker paths 2841/2842
- BED 2 south: window marker paths 1343/1344
- BED 3 south: window marker paths 1369/1370
- LIVING north: window marker paths 1762/1763
- LIVING south: window marker paths 1447/1448 and swing arc 3336, jambs 3337/3338
- LIVING west: ASD sliding door jambs 1642/1643 and tracks 1646/1651/1658/1663
- GARAGE: currently no verified closed `Finish_Floor` candidate in this diagnostic lane; it is NOT evidence the real garage is missing or that the garage panel-lift was not detected.

The **existing internal swing-door producer** from merged PR #4382
also emits seven source-authenticated, candidate-only internal doorway
receipts on the original page. Without changing its detector, the same
read-only boundary matcher associates two more:

- BED 2 east: existing original internal swing arc path **2195**, jamb
  paths **2196/2197**, ~26.93 PDF pt threshold
- BED 3 west: existing original internal swing arc path **2591**, jamb
  paths **2592/2593**, ~26.93 PDF pt threshold

The combined audit now reports **nine source intersections**: seven
external-window/door correspondences and two internal-door correspondences.
These are **NOT nine scored items or room closure proofs**. They use only
existing opening producers; this change adds no door/window detection rule.
The private original PDF and JSON report stay only on Bryce's PC:
`C:\Users\bryce\private_packets\gpt6_max_original_3laurel_9_hosted_room_witnesses_20261116.json`.

**MAX action:** reuse these receipts in the typed room ownership graph after
room side/host, remaining wall junction and source finish/scale checks.
Neither external nor internal thresholds are opaque material or floor finish
on the far side of the entrance. Garage remains without a floor candidate in
this diagnostic and requires independent source region correspondence. Do
not reimplement any of the already detected doors.

## Existing CS / robe-sliding candidate source (not hosted/physical approval)

The production `pb_next_wall_ring_preview.build_layered_wall_doorway_room_rings`
already recovers CS cavity-slider and paired sliding-leaf/frame *candidate*
closures. The new `pb_three_laurel_floor_layered_closure_shadow.py`
cross-references those existing typed producer closures with the remaining
**uncovered floor candidate boundary segments**, using exact source SHA,
page, source reference, edge direction and proximity. It creates no new
door or window detector and never fills an unproved solid wall or promotes
a room quantity.

Against the original 3Laurel p3, it identifies three **candidate only** matches:

- MEDIA east: existing `cavity_slider_cs_closure`, ~36.28 PDF pt,
  with source native CS word ref `p3:w342` **but no native wall-host path
  IDs** in the existing closure receipt. Must remain
  `word_only_unhosted`.
- BED 2 robe north: existing `sliding_leaf_frame_closure`, ~51.02 PDF pt,
  with native leaf/frame path IDs `2292,2293,2302,2303` but **no confirmed
  wall host IDs**. Remains `native_leaf_without_host_wall_ids`.
- BED 3 robe north: existing `sliding_leaf_frame_closure`, ~51.02 PDF pt,
  with original path IDs `2270,2271,2280,2281`, similarly no host IDs.

The source original plan prints **ROBE / 1,800 / VSD** at the bedrooms and
**CS** at Media; these text labels are background corroboration only.
Without independently authenticated native physical host and threshold
ownership, none of these candidates proves a closed room ring or correct
floor-finish limit. The remaining LIVING west CS and GARAGE source assignment
continue to abstain in this lane. Private diagnostic JSON stays only on
Bryce's PC:
`C:\Users\bryce\private_packets\gpt6_max_3laurel_existing_CS_VSD_closure_candidate_matches_20261116.json`.

Do not count these three candidate links or nine existing hosted links as
frozen120 measured items. In all branches, `measurement_authorized=False`,
`physical_wall_authenticated=False`, and
`room_enclosure_authenticated=False`.
