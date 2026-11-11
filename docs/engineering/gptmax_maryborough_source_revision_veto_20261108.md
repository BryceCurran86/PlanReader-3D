# Maryborough p7↔p11 live correspondence: exact source revision byte veto

**8 November 2026 (Brisbane)** — additive, demotion-only repair stacked on AntiGravity's #4236 original branch head `4114471989ae9bcd1088c54fce338b3801d1e39e`.

## Observed production defect

The real `pb_live_physical_net_wall_integration._collect_live_physical_net_wall_claim` computes documented cross-view room-area records and passes them to `pb_source_cross_view_floor_correspondence_shadow.resolve_cross_sheet_floor_correspondence_for_claim`, then to `CrossViewFloorFinishProducer.from_source`. The resolver selected the floor's original PDF bytes from `store.source_bytes_by_revision[floor.revision_id]`; **if the owned revision was absent**, it instead selected the *first completely different cached revision's PDF* while passing the requested floor's revision/SHA/snapshot identifiers to downstream correspondence. This is an authority-laundering path: another source can provide attractive ink.

## Corrective behavior

Require the exact requested revision key with a producer-stored `bytes` payload, independently recheck SHA-256 against the physical canonical floor's source SHA and reject unavailable/foreign/modified payloads **before** the source geometry, D15 or material marks may be considered. No fallback/alias/first or cross-revision source selection. Unknown/foreign always returns no correspondence and therefore cannot feed a new finish quantity. An exact owned payload is passed to the unchanged existing correspondence helper; no physical, opening or material authority is newly created.

The new test matrix uses source-neutral fake byte inputs, never real customer drawings, gold values or source hashes: absent owned revision with foreign cached record, altered owned bytes, bytearray, malformed store, wrong declared source digest, no store, happy exact ownership, and downstream ABSTAIN/CONFLICT/CANDIDATE. Positive source-neutral test establishes only byte ownership, **not D15 door/threshold, FT3 material, finished-face, figured dimension, sealed customer or benchmark FIRM**.

## Integration and release gates

Only `pb_source_cross_view_floor_correspondence_shadow.py`, new tests, this report, focused CI; no modification to AntiGravity's active #4236 branch, Claude's 3Laurel semantic branch, MAX's #4238 customer handoff, frozen120 truth/evaluator/maps, original source PDFs, 2.5pt snap or 20k primitive cap. Do not merge stacked child into main independently. Parent #4236 is still BLOCKED on synthetic source/geometry-based CORROBORATED grants, D15 actual schedule/door threshold/finished-face owner and hardcoded Decimal metric FIRM. AntiGravity must repair those upstream gates and re-run the protected genuine-original source/customer tests; no validated accuracy or new commercial quantity is claimed by this child.

CI on exact head must check dual Python 3.13/3.14, existing correspondence/physical source-neutral regressions, private source-negative and historical Lot16 8/Maryborough 3 signed/customer retention before merging the integrated parent.
