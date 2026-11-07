# GPT1 — source-owned net-wall metric safety at wall-finish producer (2026-10-30)

## Files and actual functions studied

- `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, `docs/wall_topology_observability_architecture.md`, `docs/planreader_wall_room_topology_spec.md`, `docs/planreader_public_tender_benchmarks.md`, `docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md`, `.github/workflows/ci.yml`.
- `pb_bound_wall_finish_quantity_authority.py`: `SourceBoundWallFinishQuantityProducer.publish`, `SourceBoundWallFinishQuantityRecord`, `SourceBoundWallFinishQuantityAuthority.resolve`.
- `pb_net_wall_boolean_union_authority.py`: `NetWallBooleanUnionRecord` and `NetWallBooleanUnionAuthority`.
- `pb_live_wall_finish_quantity_publication.py`: `publish_bound_wall_finish_quantity` source record-ID reproof and positive metric checks.
- `pb_bound_wall_finish_customer_bridge.py`: `build_bound_wall_finish_rows` and `bound_wall_finish_record_to_takeoff_row`, called from `pb_auto_geometry_v1219.py`.
- `tests/test_bound_wall_finish_quantity_authority_v1.py` existing source-owned positive, incomplete, conflict and input-order tests.

## OBSERVED repository behavior

The producer verifies complete physical face/finish binding and source-matched net-wall authority before summing each `NetWallBooleanUnionRecord.net_area_m2`. At the **first numeric gate**, `math.isfinite(float(area))` allows `True` and numeric strings as positive m²; an arbitrary object or a huge integer can raise `TypeError`/`OverflowError` rather than returning typed ABSTAIN. Two individually finite `1e308` source areas can produce an infinite aggregate, which is rejected only by the positive-record constructor with an exception, not a source-negative result. The downstream `publish_bound_wall_finish_quantity` checks record IDs, source receipts and positive finite values, but cannot repair the producer's missing typed negative or crash.

## INFERRED first failing real quantity gate

Original PDF → independently source-proven physical wall and opening void → `NetWallBooleanUnionAuthority` → complete finish-face binding → `SourceBoundWallFinishQuantityProducer.publish` (FIRST metric defect) → `publish_bound_wall_finish_quantity` → `build_bound_wall_finish_rows` → live customer takeoff. Source-closed sealing and unchanged frozen V2 evaluation remain separate downstream authority gates; no source-neutral test grants original source FIRM, signed customer or a score. A producer crash can also suppress other otherwise valid quantities.

## PROPOSED narrow change

Accept only exact native `int`/`float` per-face m², safely convert and require positive finite metric. Reject boolean, numeric text, objects, unrepresentable huge integers, zero and nonfinite values through the existing `FINISH_QUANTITY_INVALID_AREA` typed ABSTAIN; after each original-order sum reject a nonfinite aggregate before record construction. Preserve existing valid floating-point summation, record-ID formula, source roots, complete face universe, gross-minus-void authority and customer row formatting. Never default a missing face or area.

## Validation and negative controls

Synthetic valid one/two-face original-shaped producer → record → `QuantityEvidence` → customer row; malformed numeric source universe; valid-first/invalid-second all-or-none; finite-input aggregate overflow; permutation and deterministic replay; input no-mutation. Public exact-head Python 3.13/3.14 CI is necessary but not source authority. Original SHA-verified production replay and byte-exact retention of nine Lot16 and three Maryborough signed/customer quantities remain mandatory before any merge.

## BENCHMARK firewall / untouched scope

No expected quantities, tolerances or benchmark labels informed the fix. Do not edit `benchmarks/frozen_holdout/full_plan_v2/`, original PDFs, credentials, GPT2 FT2/FT3/room/RCP ownership, GPT MAX/Claude opening hosts, GPT3 signing/scoring, other GPT1 PR paths, 20,000-primitive cap or 2.5 pt snap. This is an integrity improvement, **not** an accuracy milestone until source-validated and safely merged; no new official score is claimed.
