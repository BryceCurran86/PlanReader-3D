# Original PlanReader: exterior-opening continuity contract

**Scope:** geometry preview only. This document describes the implementation in
`pb_source_window_footprint_continuity.py` and
`pb_source_garage_door_footprint_continuity.py`.

## Ownership

An exterior window or garage-panel door creates an *aperture in wall material*,
but does not break the two-dimensional building footprint. The virtual
topological bridge across the aperture is **not** a wall or a floor finish.
Any customer wall area, wall length, frame, opening, ceiling, slab or
building-footprint quantity must obtain its own independently authenticated
original-source evidence and commercial seal.

Bridges must carry the original page-native source path identities for both
host wall faces and for native opening markers/jamb caps, with source word
evidence. An absent, competing, disconnected or inferred host is not evidence.
The preview may show a candidate opening without promoting the entire
perimeter to an authoritative polygon.

### Window

A source-supported exterior window code (for example ASW) combined with a
unique same-layer pair of dark, collinear exterior wall fills and its original
paired window-marker line permits one **footprint-only** continuity span.
Narrow, source-painted sash infill can be present inside this span; an
intervening full-thickness wall makes it ambiguous and prevents the span.
Door jambs or schedules without unique window ownership cannot substitute.

### Panel-lift garage door

A native label with Panel, Lift and Door on an externally hosted aperture,
two uniquely source-owned dark wall ends and two separate grey source-painted
jamb caps permits one **footprint-only** garage opening span. The two caps
must be separately anchored at the wall ends. Do not use the printed width
alone to create a wall or deduct a customer opening quantity.

### Standard hinged / swing entry door

A source-painted swing-door arc, two same-layer dark exterior wall host faces,
and two separate original jamb-cap rectangles form a 2D footprint-only
threshold aperture. Preserve the original wall, swing and jamb path IDs.
Authentic jamb-side wall stubs can be short: omission by an unrelated
commercial wall-band collector must not veto their independent source proof.
If a host, cap, swing or viewport identity is missing or contradictory,
ABSTAIN. Door gaps are never filled as billable opaque wall; floor finish
transitions end at the doorway threshold, subject to original room finish
evidence.

### Outside boundary vs. envelope of the sheet

For the 3Laurel original p3, the ALFRESCO and PORCH are not in the enclosed
building footprint. The actual outer wall runs alongside the Bed 5 and
Living room faces. Do not confuse a roof outline, open external area,
freestanding timber post or internal wall junction with the outer building
wall. On the original review overlay the three missed hosted swing doors
were numbered 4, 5 and 6; their native arc path IDs are 3336, 1163
and 1912 respectively. These are acceptance witnesses, never a
plan-specific production coordinate rule.

Do not use a page bounding rectangle, convex hull, or nearest-endpoint snap
to claim closure. The original selected floor plan can contain open alcoves,
covered alfresco, porches, garages and disconnected details. Such geometry
requires a scoped outside-region/footprint graph and source-backed open-space
classification. A window or door bridge alone **does not prove** the full
exterior cycle; when the plan scope or remaining boundaries are unresolved
the tracing status remains `ABSTAINED`.

## Regression evidence

The Python 3.13 focused suite includes synthetic positive windows/garage
doors and negatives for missing labels, one-sided markers, unhosted windows,
full-thickness intervening walls, detached/interior joins, missing garage caps
and competing hosts. Original private-plan visual acceptance is executed
locally without committing or distributing private source PDFs.

Frozen 120 benchmark denominator and historical signed opening/floor
quantities remain unchanged by this candidate-only preview.
