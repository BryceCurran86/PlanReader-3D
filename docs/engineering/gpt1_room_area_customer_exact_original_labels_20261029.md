# GPT1 original room-area customer label source exactness — 2026-10-29

## Read and traced

Current main `65dc4684fbcf1ce36c704457d896fc7c12a651de`; `AGENTS.md`; `docs/AI_ENGINEERING_PLAYBOOK.md`; `docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md`; W1–W10 topology architecture/spec; retired public tender benchmark firewall; `.github/workflows/ci.yml`; #3462/#2017 current claims. Production `pb_room_area_quantity.py`, `pb_live_room_area_source_closed_export.py`, `pb_live_room_area_customer_projection.py`, `pb_quantity_takeoff_adapter.py`, `pb_live_floor_family_customer_output.py` and existing native-PDF tests.

## Observed repository behavior

The original room-area producer sets `room_label` and `location` from the source label. `_firm_room_area_quantities` and `build_live_room_area_source_traces` validate genuine FIRM source quantity, figured/scale authority, physical room/floor identity, source hash, page, viewport and evidence. `project_live_room_area_customer_rows` reuses these source traces and calls `quantity_evidence_to_takeoff_output_row`; the adapter uses `_clean(qmeta.get("location"))` for final commercial `location`. This strips padding and stringifies arbitrary source metadata without checking the literal original label type. An otherwise authentic FIRM quantity may therefore reach customer output with a repaired/forged source-owned location.

## Inference, not yet original-source proof

Source-owned room label metadata is a commercial identity receipt, not a source of m². Its conversion can conceal malformed source labels even while geometry and numeric area are genuine. This is a final-customer identity-integrity gap, **not** proof of physical OFFICE/PWD/FT2/FT3 ownership or an additional quantity.

## Proposed narrow production correction

Before customer-row adaptation, for each already-FIRM room quantity, require any explicitly supplied `room_label` and `location` metadata to be native `str`, nonblank and exactly unpadded. Missing optional fields remain missing; do not infer labels or change quantities. Reject malformed labels with `SourceClosedRunConflictError`, preserving genuine ABSTAIN, valid source/customer output and all upstream authority. Add native-PDF producer→trace→customer positive, adversarial source-label negatives, and input non-mutation tests.

## Benchmark separation and untouched paths

No benchmark truth, expected quantities, frozen evaluator, source PDFs, tokens, private receipts, GPT2 physical room/finish/RCP code, GPT MAX opening hosts, GPT3 signing/scoring, original signed/customer bodies, 20,000 raster cap or 2.5pt snap are changed. Do not count this source-integrity correction as FIRM, a frozen score gain or a merged milestone. Require exact-head Python 3.13/3.14 and trusted original-source replay with signed9/Maryborough retention before any merge.

## 2026-10-29 technical-review correction — independently bound room text

**Observed (review #5693737473):** the first negative-only guard rejects
padded/type-coerced labels but not a different clean room name. The trace
`room_label` is copied from mutable quantity metadata and cannot corroborate
that same quantity's `location`. The existing original source-room label
producer independently publishes `LiveCanonicalRoomObject.room_label`,
`room_label_binding_record_id`, and `room_label_evidence_ids` for the
canonical face that the room-area source trace identifies.

**Proposed/implemented:** keep the type-and-whitespace veto; for any supplied
customer `room_label` or `location`, resolve exactly one canonical room
from the already authenticated trace `room_entity_id` and require an
independently issued source label/binding/evidence inventory. Compare the
literal native customer label to that original semantic label using only the
existing cross-view case/word-spacing equivalence. Reject clean conflicting
room names, two mutually agreeing forged quantity labels, and missing label
authority. If both optional labels are absent, do not fabricate them.
The test uses a native generated PDF with distinct OFFICE/STUDY rooms,
original source metric/trace, commercial projector, and sealed verifier.

**Inference/limitation:** canonical source-room label binding is trusted only
within the existing producer/source-closed contract; this does not recreate
private original text observations from mutable caller objects, and does not
prove original Maryborough physical room ownership. No new quantity or
customer authority is minted. Full SHA-verified original-source replay and
signed9/Mary3 retention remain mandatory before merge. Benchmark values,
private PDFs/tokens, other lanes, frozen truth, raster cap and snap are untouched.
