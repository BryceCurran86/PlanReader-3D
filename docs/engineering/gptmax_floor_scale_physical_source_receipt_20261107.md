# Original physical scale receipt → canonical floor customer authority

**GPT MAX | 7 November 2026 | scope: source-bound floor scale proof (not geometry/area detection)**

## Verified first failure

In Claude's SHA-original 3Laurel page-3 opt-in ring run, an internal `room_area` and canonical `floor_area` both carried `pdf_scaled` 12.50979 m², but `project_live_floor_area_customer_rows` failed `MissingCommercialAuthorityError`. The final projection requires `resolved_scale_id`, `scale_status` and no conflicts. It must *not* infer these from a number, copied string, OCR label or a `scale_fingerprint` alone.

Production trace:
- `pb_live_physical_net_wall_integration._collect_live_physical_net_wall_claim` holds a `PhysicalScaleCalibrationBridgeResult` for each authenticated room-face scope. The bridge binds real `PhysicalScaleEvidence.record_id` with full revision, SHA, snapshot, page and a native graphic scale-bar evidence set.
- `pb_source_room_area_bridge` calls `pb_room_area_quantity.build_room_area_quantities`, which runs `validate_scale_binding`, checks FIRM and carries the exact `scale_calibration_fingerprint` into the room-area quantity.
- `pb_live_canonical_floor_surface.enrich_live_canonical_floor_metric_areas` links the already-FIRM room-area quantity one-to-one to the exact canonical floor.
- `pb_live_floor_area_quantity_publication.publish_live_floor_area_quantities` creates floor `QuantityEvidence` but has **no source-owned physical-scale record**. Customer projection rightly refuses to turn `scale_fingerprint` into measurement authority.

## Bounded design and authority

One additional **producer-owned, typed floor-scale receipt** is constructed *only from* an already `CORROBORATED` real `PhysicalScaleCalibrationBridgeResult` and the matching live source-area quantity and canonical floor. It binds:
- the original scale selector `document_id, revision_id, source_sha256, snapshot_id, page_id, viewport_id`;
- `native_graphic_scale_bar`, the physical-scale record ID, positive original ink/text observation IDs and source-span ↔ physical-span calibration;
- the exact canonical floor, physical floor, room entity, original room-face record and upstream area quantity;
- the independently produced `scale_fingerprint` and FIRM calibration on that same page and revision.

The final floor quantity re-checks all of these against its already authenticated source quantity and canonical floor before emitting `resolved_scale_id`, `scale_status='resolved'` and `scale_conflicts=()`. A receipt cannot create a room, floor, physical scale, normalized area, FIRM status, or new customer row on its own. Duplicate, malformed, out-of-scope, unowned, stale or competing scale receipts **do not add authority**. For `pdf_scaled` without a valid receipt, original FIRM internal area remains usable as diagnostic but no borrowed `resolved_scale_id` may be passed into the customer projection. Documented-dimension output and all prior legacy behaviors remain unchanged.

The trust boundary is *not* just a self-asserted metadata string or copied six-part lineage key: it consumes the existing calibrated producer-owned scale bridge and its original stroke/text receipts. The full original-source and customer seal remain independent release gates.

## Out of scope / exit gates

No `pb_source_room_face_authority.py`, Claude #4230 room-ring/doorway code, AntiGravity D15 ownership, benchmark reference, expected quantities, 20k primitive cap, 2.5pt snap, or default-OFF behavior will be changed.

Run synthetic negative tests (wrong SHA/revision/snapshot/page/viewport/face/floor/upstream quantity, duplicate/competing scale, missing source witnesses, non-FIRM stale calibration, forged scale metadata) and positive original-equivalent typed record. Then run exact-head Python 3.13/3.14 CI, unchanged Lot16 eight and Maryborough three + Q5446 protected original/customer retention, and real 3Laurel source->room->scale->floor->sealed/customer. Even a new customer row is **not** a frozen120 score until independent mapping and unchanged scorer publish it.

## Source commercial veto discovered during continuation

**Observed:** `_valid_source_room_area_quantity` accepts a FIRM original room
quantity even when its metadata explicitly says
`commercial_projection_allowed=False`. Both canonical quantity reissuers then
replace that metadata with `True`. A local reproduction using the existing
producer-owned scale test fixture changes an upstream False to downstream True
and obtains a nonempty customer measurement authority. The shared commercial
adapter correctly rejects False when it reaches that adapter unchanged.

**Inference:** adding valid physical scale metadata can expose this earlier
permission-loss bug; physical scale does not revoke an upstream publication
veto. The original room-area diagnostic must remain inspectable without being
reissued as a commercial floor or canonical room quantity.

**Bounded correction:** reject the explicit upstream False at the shared source
quantity validator, before either canonical reissuer. Leave claims without an
explicit veto and genuine True permissions unchanged. Verify both documented
and PDF-scaled paths, including an otherwise genuine sealed scale receipt and
the actual floor customer projector. This does not treat a canonical floor's
default `commercial_quantity_authority=False` as an upstream veto: that field
describes the pre-issuer geometry object, whose commercial authority is decided
by the existing final quantity issuer.

**Benchmark observations:** the protected page-3 scale census on an earlier
head reported hundreds of source faces. Such counts are not proof of finished
rooms, correct physical boundaries, verified customer takeoffs or scored items;
they must not choose the implementation or its thresholds. Keep this PR draft
until fixed-head original source/customer and historical retention gates pass.

The exact `767a3fb...` protected boundary replay `42349587803` subsequently
completed all existing source-trace, seal and customer-verification functions:
292 faces/scale receipts/rows, 10 authenticated labels, but **zero rooms with
complete canonical wall relationships**. That green execution is a contract
and lineage result, not independent physical finished-face validation. In
particular it does not disprove the earlier original-source evidence of
fixture/hatch/joinery fragments. Do not release the scale grant or call those
rows correct rooms until the independent physical boundary gate is resolved.
The commercial-veto correction is necessary but does not fix that geometry
blocker. Claude's default-off source-ring work remains separate.
