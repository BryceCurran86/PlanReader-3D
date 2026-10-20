# Batch41 ID-namespace host lever — architecture note

## Observed repository behavior

- Segment-parent line IDs are `raster_opening_primitive:…:raster_wall_band_{face|end}|…:{n}`.
- Usable W4 `source_primitive_ids` are predominantly `d{n}i0`.
- Exact and `visible:`-strip intersections are empty on Lot16 unhosted openings.
- Digit-tail collisions exist (`…:1467` vs `d1467i0`) for all 6 unhosted openings — **ambiguous across namespaces**.
- FACE spans mean ~31.9 pdf-pts; END spans mean ~2.7 pdf-pts (short stubs).
- Page snapshot `visible_observation_ids` count is 0 on this ingest path.
- Production `_authenticated_raster_source_lines` still requires `RASTER_PDF_VISIBLE_SEGMENT`.

## Inference (not authority)

- Digit-tail numeric coincidence is **not** identity proof. Treating it as host would be nearest/heuristic authority forbidden by AGENTS.md.
- A producer-owned identity map (or authenticated parent-kind promotion into the visible-line assembler) remains required.

## Proposed change (shadow only)

- Keep namespace-bridge + span-length censuses in shadow.
- Gate `digit_tail_collision_ambiguous_abstain` must stay fail-closed.
- Do not mutate production host assembler in this PR.

## Benchmark observations that must not influence implementation

- Expected BOQ / Full Plan V2 scores.
- Signed quantity **values** (IDs only may be retained).
