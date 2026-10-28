# GPT1 external wall net-face geometry replay — 2026-10-28

## Files and exact production call path read
- `AGENTS.md`; `docs/AI_ENGINEERING_PLAYBOOK.md`; `pb_live_external_physical_net_wall_publication.py`; `pb_live_external_wall_surface_area_quantity_publication.py`; `pb_net_wall_boolean_union_authority.py`; `tests/test_gpt1_source_closed_external_per_wall_surface_m2.py`; `tests/test_gpt1_external_wall_original_aggregate_roster_seal.py`.
- Source-authenticated physical wall, gross and opening void compositions → `compose_live_external_physical_net_wall_publication` → canonical wall's original gross/net WKB, original physical voids, source SHA/revision/snapshot/receipts → `publish_live_per_wall_surface_area_quantities` → `seal_live_per_wall_surface_area_run` → `seal_source_closed_run`. The unchanged frozen evaluator consumes only separately authorized signed/customer quantities, not this proposal.

## OBSERVED
The upstream producer calls `subtract_void_union_from_wall_polygon(gross_polygon, void_polygons)`, with void rectangles constructed from original wall-local `u0,z0,u1,z1` and retains both gross/net WKB. The downstream per-wall issuer independently checks source scope, aggregate receipt rosters, aggregate stable ID, each net WKB's validity and area, and aggregate area total. It does not replay the source-backed gross-minus-void polygon before minting a per-wall source-closed quantity. The net WKB is included in the new per-wall ID, but that does not authenticate its geometry against the upstream original physical wall.

## INFERRED failure and safety boundary
A copied immutable `LiveCanonicalWallObject` with a different but same-area valid net WKB can pass the existing per-wall issuer while retaining all original receipt IDs, total area and aggregate ID. The sealed run then binds an altered physical face to original evidence. A similar mismatch can be introduced by changing retained void geometry while leaving the original net polygon unchanged. This is a source-lineage integrity issue, not new wall existence, metric scale, material finish, paint-side or customer authority.

## PROPOSED narrow implementation
At the real per-wall issuer, load original gross and net WKB, reconstruct every retained physical opening void as the upstream wall-local rectangle, call the **existing** `subtract_void_union_from_wall_polygon`, and require exact topological equality with the retained net WKB. Validate gross area against its existing metric field, and fail closed on invalid, empty, non-finite or inconsistent geometry. Do not add tolerances, select a competing source, infer a finish or alter the original producer. Keep all existing roster/aggregate and complete-universe checks. Test same-area displaced WKB, changed voids, gross geometry conflict, malformed coordinates and original positive deterministic sealed output.

## Authority and untouched files
No original PDFs/tokens, frozen V2 truth/evaluator, GPT2 Maryborough FT2/FT3/RCP, GPT MAX Wxx hosts, GPT3 signed scoring, existing nine Lot16 customer bodies, or raster 20,000 cap / 2.5 pt snap are modified. No benchmark expected quantity or score informs this rule. Synthetic fixtures cannot prove an original-source FIRM quantity; trusted SHA-verified owner-original replay and exact-head dual-Python CI remain merge gates. This is an integrity-only milestone until merged with complete proof.
