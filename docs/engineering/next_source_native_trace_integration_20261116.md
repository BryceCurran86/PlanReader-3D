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


## Follow-up: source native wall connectivity + automatic numbered room key

**Exact original real-world diagnostic on Bryce's PC** (unchanged originals, review-only):

| Project / floor | Native candidate wall bands | Source-connected wall components | Largest connected network | Free native band endpoints |
|---|---:|---:|---:|---:|
| Lot16 | 50 | 45 | 4 bars | 8 |
| Q5446 ground | 23 | 18 | 2 bars | 1 |
| Q5446 upper | 20 | 16 | 3 bars | 2 |
| Acacia | 43 | 21 | 6 bars | 4 |

These graph facts are obtained from the actual **source path strips**, not a guessed exterior bounding rectangle. The largest components are NOT proven exterior. The topology uses 0.03 pt representation-noise contact, never extends lines or uses a 2.5 pt commercial snap. The app draws yellow-centred red tip circles only where source-native wall bands in the largest connected network have unjoined long-axis endpoints. These diagnostics reveal why a full exterior cannot yet be authenticated.

The **new numbered-space source reader** also runs automatically inside the same new preview after outer wall preflight and before inner room topology. It reads the actual PDF's vector outlined room KEY using the existing portable RapidOCR backend, dynamically cropping from a detected KEY/LEGEND header (no job names, fixed page coordinates, or hard-coded room numbers). Number/name pairs must share a source row and a consecutive sequence. It reports key entries, match status and generic indoor/outdoor/service candidate role, but does NOT create boundaries or m².

- Acacia original page 2: **15/15 printed room-key names read**, including courtyards, carport and service/tank areas, **10 unique on-plan numeric markers**, 5 unmatched. Same result from the fully integrated new app preview in ~13.1s (including wall tracing and portable OCR).
- Room/key semantic candidates are NOT wall authority, cannot rehabilitate failed physical exterior, and never authorize a billable room/floor/ceiling quantity.
- Pages with genuinely sparse native ink and no glyph text bypass the heavy OCR backend. The native original PDF byte hash and page index are retained.
- Original Q5446 and Lot16 remain exterior ABSTAINED; connected network diagnostics help pinpoint source-path stitching rather than guessed contour fixes.

**Remaining:** full authenticated exterior source path graph and doorway ownership. The number-to-name key cannot substitute for a physical exterior / room face chain; original production customer issuer still needs full independent source acceptance. This PR is draft.


## Later source-native heavy-wall recovery (third commit)

Q5446's actual original PDF carries many real walls as **single opaque 1.92-pt BLACK vector strokes**, not native wall-layer filled rectangles and not paired thin faces. The Next donor had no such source representation. New generic \`_collect_source_heavy_stroke_strips\` admits ONLY original visible black, opaque, axis-aligned, >=12-pt spans with source stroke width 1.2–6.0 pts and retains original source path index and actual source paint thickness. Thin 0.48-pt glyph/dimension ink, green annotation, weak alpha and short marks fail the negative tests. This is *unclassified tracing evidence*, never a customer wall.

Observed original Q5446 PDF:
- Ground floor: previously 22 wall-strip candidates and zero region candidates; **77 and 1** after source-heavy strokes.
- Upper floor: previously 20 and zero; **66 and 2** after source-heavy strokes.
- Physical exterior remains **ABSTAINED** on both. The visual overlays still reveal a few thick title-block lines; no building-only crop or outdoor filter is falsely claimed.
- 3Laurel, Maryborough, Lot16 and Acacia stay on the same new engine code; full unchanged-original replay is underway. Original source PDFs and generated page overlays reside locally on the authorized PC only.

The initial restoration also ported the source 1.92-pt property only as a diagnostic; no signed BOQ quantities or frozen denominator changed.


## AntiGravity source modality / wall recovery handoff — integrated and adversarially tested

Source: AntiGravity's local wall_tracing_complete_recovery_architecture_20261116.md (Bryce PC) and original PDFs, not copied code. This follow-up adds only original source diagnostic tracing; the separate commercial customer issue pipeline is unchanged.

### Verified real PDF facts
- **Lot16 selected floor plan** is original PDF page index **2** (third PDF page), with 1,234 native drawings but approximately 100% raster image-tile coverage. Actual page has **11 displayed image instances** (10 dominant architectural tiles + separate reflected title/logo), 9 unique XREFs. The handoff's "page 2 / 9 raster tiles / 1,234 drawings" is a page-number/xref-count conflation. The architectural walls are in image pixels, not the 1,234 native vector paths.
- **Acacia page index 1** native strokes exported in near-neutral RGB 0.09/0.10; the stricter original wall-owner gate rejected **1,458 native paths**. The new tracing shadow only now recovers 1,458 via opacity, channel spread <=0.015 and max 0.12, without widening original customer wall-ink authority.
- **Q5446** native single-heavy 1.92 pt black strokes remain supported; 3Laurel and Maryborough use native filled/paired wall evidence and must not regress.

### New code
1. **Source modality BEFORE wall topology**: pb_new_source_modality_router.classify_source_page_modality uses original PDF image XREF placements and union coverage. A sheet with >=74% large tiled raster coverage and >=4 substantial image placements is routed to tiled_raster_underlay; a logo or normal CAD drawing stays native vector. Frozen original 20,000 native primitive safety gate is untouched.
2. **Actual raster image bytes, not old page envelope**: pb_new_raster_source_wall_trace.trace_source_raster_wall_lines reconstructs original raster tile pixels (actual extract_image bytes, including repeated tile XREF placement), excludes native vector dimensions and reflected title-block logos, finds axis-aligned source-ink line candidates, and records image XREF lineage and page coordinates. It does not guess a hull, wall role, door gap, enclosing room or area. Raster line candidate cap = 2,500. Unsupported significant transformed tiles explicitly abstain instead of faking a page render.
3. **Neutral-dark source CAD strokes**: pb_new_source_dark_ink_scope re-admits original source-stroke rows only when RGB neutral within .015, channel max <=.12, and visible opaque paint. Colors, green, white, weak-alpha, short marks remain negative. Original path index preserved. New source-native wall pairing and heavy stroke producers accept the neutral-dark candidate ink; original commercial producer remains unchanged.
4. **Cavity and wider source-faced candidates**: _collect_cavity_multi_face_strips recovers 3–4 source parallel CAD faces with overlapping native straight spans, <=16 pt total wall band, and >=3 distinct source paths; _collect_source_wide_face_pairs handles 8–16 pt isolated two-face spans. Both retain original path owner IDs and are displayed in distinct colours. **Crucial regression guard:** they DO NOT enter the room barrier producer until authenticated source wall family/endpoint ownership is established. A first replay that forced them directly into barriers lowered 3Laurel candidate regions from 16 to 9; the incorrect admission has been removed.
5. **Two-stage CAD joining diagnostic**: pb_new_wall_graph_diagnostic preserves first-stage .03pt native identity connectivity and reports only source proximity join proposals at .50pt for distinct connected components, recording two endpoint coords, source paths and distance. Proposals are never actually snapped or admitted into quantities.
6. The original drawing app displays source modality and an explicit raster warning, showing magenta source-image candidate ink and no old envelope fallback.

### Remaining gates (not claimed complete)
- Continuous physical **external-wall perimeter** remains source-ABSTAINED; the raster/vector/near-grey candidate stages identify evidence but cannot certify the building outer face cycle.
- Aperture/window jamb/slider host attribution and source-bounded thermal-envelope graph walk require independent original-source proof. Merely closing an unowned 222.624 pt opening risks false rooms.
- Three-/four-face cavity bands, wider faces and .5pt snaps are **unverified diagnostics only**; they must not silently modify original customer wall/room quantities.
- Dual Python 3.13/3.14 CI and source-protected four-project customer retention needed before merge. Current local PC has Python 3.13 and 3.9 only; 3.14 must run on CI. No frozen120 score changes, no private original PDFs committed.

Source diagnostic outputs under Bryce PC private_packets/external_house_acacia_20261116/new_engine_five_job_20261116. Original protected replay waits on GPT1 source-first integration and GPT MAX validation per owner instruction.


### Protected source replay — 6 floor sheets after regression guard

Source: unchanged original PDFs on Bryce's PC, same new tracing preview, no old envelope fallback. These are unclassified candidate values, not official score.

| Original floor-plan sheet | Source lane | Existing room-barrier candidates | Newly visible (but not admitted) source faces | Candidate rooms | Exterior |
|---|---|---:|---:|---:|---|
| Lot16 PDF page 3 | tiled raster JPEG | 0 vector walls; 250 source raster line segments | source raster pixels, not vector dimensions | 0 | ABSTAINED |
| Q5446 ground | native vector | 77 wall bands | 39 cavity + 2 wide paired bands | 1 | ABSTAINED |
| Q5446 upper | native vector | 66 wall bands | 34 cavity + 2 wide paired bands | 2 | ABSTAINED |
| 3Laurel | native vector | 404 wall bands, 48 temporary closures | 40 cavity + 12 wide face proposals | 16 | ABSTAINED |
| Maryborough | native vector | 88 wall bands, 2 temporary closures | 74 cavity + 19 wide face proposals | 5 | ABSTAINED |
| Acacia | native vector | 38 wall bands | 1,458 neutral dark paths, 5 cavity + 2 wide face proposals | 0 | ABSTAINED |

Regression was observed and repaired: when NEW cavity/wide-face proposals were mistakenly added to room barriers, 3Laurel candidate rings fell from 16 to 9, while Q5446 proposals increased. The final guarded code prevents those unverified classes entering room topology. These extra faces are for visual evidence and the exterior diagnostic ONLY pending physical validation. Original 3Laurel 16 and Maryborough 5 preserved.

Raster extraction additionally uses the PDF XObject source image bytes rather than a composited page pixmap: a synthetic separate native dimension line at y=80 must never appear as a raster candidate. A reflected title-block logo on the same sheet cannot invalidate the ten actual architectural tiles; on real Lot16 the original-source-only raster tracer found 250 line segments, down from 324 when vector overlays were incorrectly present in the render. The image-only result is the trusted candidate diagnostic, not a building footprint.

Original source PDFs/screenshots are retained only on Bryce's PC, outside this PR. Details in private_packets/external_house_acacia_20261116/new_engine_five_job_20261116/guarded_handoff_6sheet_summary.json.
