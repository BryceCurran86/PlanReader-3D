# Explicit single-width opening review

## Observed behavior and trace

`OpeningLabelDimensionProducer.publish_scope` binds a figured callout to one
source-owned physical opening. A one-number callout deliberately has no area or
ordered width/height pair. `build_nominal_opening_canonical_shadow` handles owned
HHWW pairs only, so `build_opening_review_packets` previously omitted even an
explicitly approved single nominal width from the canonical review item.

`OpeningDimensionAuthority.resolve_width` separately requires a dimension line
and jamb-connected witnesses. An owner-approved nominal width must not change
that source-measurement authority or override an independently bound schedule.

## Implemented review path

The optional `nominal_width_approvals` argument consumes existing
`MeasurementRecord` objects, with explicit USER_APPROVED source and status,
approver and timezone-aware date. Each record must retain the exact current
document/revision/SHA/snapshot/page, physical opening ID, original label evidence
ID, complete text-observation set, millimetre unit and the single printed value.
Duplicate or absent targets, transferred records and differing values fail.
An existing schedule binding, schedule dimension or resolved width vetoes this
partial annotation. There is no project-name rule or implicit size convention.

The existing CanonicalOpening carries the approved nominal width with height,
wall, sill and position absent. Source width authority, takeoff and deductions
remain false. The work queue retains the missing nominal height, rough opening,
placement and opening-universe obligations. Default calls remain unchanged.
An opening whose filling kind is unproved remains GENERIC and retains an
explicit filling-kind blocker; a width approval cannot classify it as a door.

The offline package exports the evidence and displays the approved width with
height unresolved. It creates no OBJ rectangle for a one-axis item and rejects
partial records carrying an invented height or placement.

## Authority and validation boundaries

This is a review annotation, not an automatic source measurement, quantity,
signature, count, benchmark match, schedule override or authority promotion.
Production source/width/height publishers, original signed rows, topology,
20,000 primitive cap, snap policy and frozen truth/evaluator are untouched.
Synthetic tests cover genuine producer-owned source input, owner/value/scope
transfer failures, schedule conflicts, replay/order stability, no mutation and
no invented height/asset. Private original-source execution remains separate
from the public test fixtures and must be reported at its exact code head.

Local verification: 201 focused tests passed. An independently hash-verified
original-source replay produced eight explicitly scoped width-only review
annotations with complete parent DAGs; two retained unknown filling kind and
all retained unknown height. The original 21 physical objects, 15 hosts,
nine frames, eight signed areas, original snapshot and default review packets
were unchanged. The complete retained production receipt equalled the earlier
validated receipt. This is no new FIRM quantity or benchmark gain.
