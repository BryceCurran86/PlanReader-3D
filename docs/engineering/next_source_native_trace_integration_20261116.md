# Original PlanReader — source-native tracing-only integration

**16 Nov 2026 | GPT1 | draft, not commercial measurement authority**

## What was actually integrated

The original app's `plan_mapper_page` uses `pb_new_source_trace_preview.source_native_trace_preview` from the registered original PDF before permitting manual drawing. The former `Auto-detect building envelope` button no longer creates automatic cladding/floor-area shapes from a raster hull. A dedicated rerun button invokes the SAME new source-native tracing engine, not a fallback. This leaves manual takeoff drawing accessible.

The preview follows these stages:

1. SHA-bind the actual original PDF and page. Prepare source ink: reuse the original typed-negative outlined vector glyph filter on dense outlined-text PDFs, preserving all original path IDs and all curves/fills; mask green and non-wall paint through the original `_source_wall_ink_candidate_drawings`.
2. **FIRST GEOMETRY STEP:** attempt the exterior wall ring from actually joined source wall strips, including anonymous painted black/gray bars AND original paired native face strokes. No rectangular ink hull. Ambiguous/outside/rival/open perimeter is `ABSTAINED`.
3. Trace native inner wall candidates, source-evidenced swing/slider/garage-panel closures and candidate room rings using the bounded PlanReader Next ring implementation. Its original PDF 20,000 source-primitive cap is **unchanged**. It does not silently fallback to the legacy raster envelope.
4. Render the original plan PDF sheet with candidate source wall ink (blue/cyan/purple), topology-only closures (orange), possible room rings (green); only a source-backed continuous outer candidate could be red. Viewer prominently warns that NO source-authenticated exterior, room, area, wall, finish, count or physical quantity is yet issued.

## Historical implementations missed by the old new-engine prototype and recovered

- **PR #4300**: source opaque anonymous black/gray wall-bar recognition and source-black arc/door leaf witness (not generic all-colour ink); tests compare original vs new for simple black room and swing.
- **PR #4306**: both endpoints of an unresolved collinear gap must actually breach THIS room perimeter before vetoing its ring; a remote gap is not an automatic room failure.
- **PR #4307**: cached per-orientation wall-run inventory for gap search, avoiding quadratic recomputation on large CAD page.
- **Q5446 typed-negative font/drafting filter** from `pb_physical_wall_candidate_authority`. Original source page 1: 47,184 raw native line segments -> 8,669 retained; page 2: 35,997 -> 6,562. New preview discards 9,266 stroke-only paths on ground floor, 7,470 upstairs; still uses original source index and preserves curves/filled bars. **Not floor or wall score evidence.**
- **Source green exclusions**: drawing-colour hygiene applies to native inner wall candidates, not only outer boundary/swing.
- **3Laurel crash**: source-viewport clipping produced `None` rows, crashing sliding-leaf later-paint inspection. Empty inert path-preserving records fix both item-clipping and row-clipping; an explicit None guard protects the occlusion loop.

## Original-source preview observations (not accepted accuracy)

| Original PDF floor sheet | New wall-strip candidates | Doorway closures | Candidate room regions | Exterior role |
|---|---:|---:|---:|---|
| Q5446 floor 1, index 0 | 22 | 0 | 0 | ABSTAINED |
| Q5446 floor 2, index 1 | 20 | 0 | 0 | ABSTAINED |
| Lot16, index 2 | 54 | 0 | 0 | ABSTAINED |
| 3Laurel, index 2 | 404 | 48 | 16 | ABSTAINED |
| Maryborough, index 6 | 88 | 2 | 5 | ABSTAINED |
| Acacia, index 1 | 50 | 6 | 0 | ABSTAINED |

Private source originals and visual previews are on the authorized local Windows PC only:
`C:\Users\bryce\private_packets\external_house_acacia_20261116\new_engine_five_job_20261116\`.
No original PDFs or screenshots were committed. Current baseline source hash Q5446: `5f29aa0122d72e2cc8886b3f19239ff32865c8d705eee99f785c389ca27fb7f0`.

The 3Laurel candidate count improved from 12 to 16 after correcting the source-gap veto and clipped source provenance, but **no independently source-verified commercial room** was minted.

## Remaining release blockers

- **Critical**: none of these six sheets has source-authenticated, gap-complete physical exterior WALL topology; outside line filtering cannot be declared complete, and coloured lines remain review-only unclassified ink.
- Original app automatic customer extraction must consume authenticated *outer -> inner -> doors -> rooms -> finishes -> ceilings/frames* provenance before any new automatically measured customer row is minted. This PR adds a preview and no issued quantity.
- Acacia numbered 1–15 room-name key is legible with portable OCR but is NOT yet automatically bound to unique room rings; source OCR's number/name cross-row mapping and inside/outside semantic authority need separate tested integration.
- Cursor #4343 hinge/cased/source-view P2 and previous #4335/#4336 draft room scope require independent proof; do not blindly cherry-pick them or override original settled source quantities.
- Source-native dimension line/furniture versus real paired wall faces still insufficient for Lot16 and Q5446.
- Run original protected four-project full acceptance and dual-Python 3.13/3.14 CI against the PR's exact HEAD. Preserve frozen 120 and signed Lot16 eight opening areas.

Tests: 111 passed, 4 skipped across relevant new-preview, anonymous black PR, original room rings, Q5446 vector-negative and original gap-regression suites (Python 3.13, before final UI-warning-only change); compilation, Ruff F821/F823, diff whitespace checked. **No official accuracy claim.**
