# External footprint first + recovered PR audit — 16 November 2026

## Owner requirement and implementation boundary

On every original PlanReader PDF extraction, positively classify floor-plan pages and attempt to trace the **external building footprint first**, before internal wall/opening/room analysis. A failure must remain visible, not silently disappear.

This branch adds `pb_external_footprint_first_trace.py`, an immutable SHA-bound, original-PDF raster-ink exterior candidate for each selected plan page, with explicit `CANDIDATE` or `ABSTAINED` and original PDF-point polygon. It runs before `SourceVisibilityProducer.ingest_native_pdf_bytes` and wall/opening/room composition in `pb_live_physical_net_wall_integration.py`; the actual app extractor calls the same tracer ahead of its other geometry and exposes `external_footprint_trace_live` and the `extraction_status` field.

**This is a necessary first-stage diagnostic, not yet a full physical-wall-authenticated boundary.** Raster closure can include a ramp, roof projection or a site fence. Native building-wall identity, doorway-gap ownership, finished faces and geometric scale are unresolved. Therefore the traced outline is NEVER an authorized `floor_area`, `wall_area`, room, invoiced quantity, official score or FIRM source. The existing independently verified sealed quantities are untouched; **this branch does not yet implement a hard stop on every legacy issuer when tracing abstains**. Treat that as remaining release work, not implemented.

The first stage excludes obvious pale landscape/green strokes and sheet title band from its diagnostic ink mask, but does not delete any PDF source layer. This does not replace the original ring tracer's separately source-native green exclusions. It cannot automatically discover arbitrary A0 multi-building elevations or authenticate physical wall faces.

## Unfamiliar-house regression

Public PDF: https://www.yourhome.gov.au/sites/default/files/2024-07/Technical%20drawings%20Acacia%20Brisbane.pdf

Local original on owner PC (outside repo): `C:\Users\bryce\private_packets\external_house_acacia_20261116\Acacia_House_Brisbane_Technical_Drawings.pdf`. SHA256: `435a6b610fea904f2b27dc330667d92a25919ada3368e5905e58ff92e047f37a`. Real original floor-plan page index 1 (2/10) produced an outer rectangular *candidate* following the building, not the larger dashed site line. The original legacy production collector without this feature produced 3,104 candidate wall objects, 44 unclassified opening objects, zero rooms/floors, zero customer quantities in 104.86 s. **Neither that baseline nor this first-stage trace measures a customer's house.**

Local review image: `C:\Users\bryce\private_packets\external_house_acacia_20261116\acacia_footprint_first_overlay.png` (red CANDIDATE outline; not a source-proven building wall). No original PDF/image embedded in public repo.

## Selective PR recovery — no blanket mergers

Original historical ledger: `docs/engineering/historical_pr_audit_20261110/pr_ledger.csv`, PR #4270: 4,212 audited older PRs; 1,862 closed unmerged, of which 267 had positive inclusion evidence and 1,595 needed review. **Those counts do not represent 1,595 lost features**. This is a static Nov 10 snapshot and later PRs need live reconciliation.

| PR | Current finding | Action |
|---|---|---|
| #4300 anonymous black walls | Exact old head `8f446683d` is an ancestor of current `main`. | Present; do NOT cherry-pick again. |
| #4306 two-end room-gap scope | Current main contains `_unresolved_collinear_gap_breaches_outer_ring` enforcing both endpoints; old PR head not ancestor. | Behavior present in newer history; targeted regressions, no duplicate merge. |
| #4307 indexed `_gaps` wall-run reuse | Current main `_gaps` precomputes orientation runs, though old head not ancestor. | Performance feature present; require timing before making further claims. |
| #4302 wall-end stroke closures | Source code and default-off flag appear in main; draft history contains review-blocked local-edge heuristics. | Re-test and repair actual negative, do NOT merge old draft wholesale. |
| #4299 schedule door-head policy | Current original net-wall publisher retains sourced wall above a valid frame; historical independent schedule row reproof is not fully established in active app. | Compare source-positive exact head, protect exceptions. |
| #4296/#4297 source glyph/RCP mark reading | Optional source-native text/glyph flags exist but remain default OFF. | Verify against private originals and reconcile source customers before enabling. |
| #4305 performance optimisations | Previous source-verified Maryborough replay speed-up documented but exact current full-app parity not independently checked. | Benchmark performance and signed output, no stale stack merge. |
| #4312 closed room-area duplicate redaction | Old branch closed unmerged. | Audit current error redaction/tracebacks and transplant only missing negative regressions. |
| #4232 physical scale lineage | Old draft closed unmerged. | Compare current scale source/metric gate; recover missing veto only after original positive. |
| #4242/#4243 3Laurel wet/dry room scope | Historical closed-unmerged shadow and source seal. | Source-positive finished-wall ownership first; never convert label directly to billable face. |
| #4317 and merged child #4340 | 3Laurel 22 finish and Maryborough issuers landed on MAX integration branch, not independently verified on `main`. Earlier text-on-sheet and drawing-count gates did not authenticate physical room/floor/ceiling ownership. | Keep shadow until each exact source-face/metric/finish/customer chain is real. |
| #4335 | Dark room ring without finished-face gate. | Hold; original BED2/BED5 retained quantities not changed. |
| #4336 | Sliding wardrobe partition face handoff, `can_issue_area=False`. | Good topology only, finish issuer still needs real wall-face proof. |
| #4337 / #4343 | Distinct doorway hinge-tip identity P1 reproduced; Cursor child #4343 claims fix but still pending final-head dual CI/source/customer replay. | Integrate tested fix when accepted; avoid merged older #4337 unpatched. |
| #4284 | Draft `planreader_next` tracing/ceiling/frame research donor, not commercial issuer. | Port proven generic source algorithms into original app only. |

## Remaining technical work

- Prove real wall-ink source path ownership and gap closure for every outer envelope segment; exclude site fences, roof overhang, ramps and multiple-building competitors.
- Make external verified footprint the mandatory input for **new** physical room/wall/finish quantity promotion while leaving protected legacy signed outputs byte-identical. This branch only attempts the first trace and publishes diagnostic status.
- Integrate safe owner-independent inner wall tracing, temporary swing/slider/garage-panel closure, and real finished faces without granting customer numbers to unproved candidate rings.
- Show separate external and internal wall overlays with exact source-path IDs and failure reasons.
- Connect authenticated ceiling, wall, opening/frame and floor finish issuers through one production source/customer pipeline; validate Acacia and unchanged frozen120 protected originals.
- Run full dual-Python CI, real original customer retention and independent source accuracy before releasing or claiming a score gain.

Tests at time of writing: 8/8 new negative/positive trace contract tests, plus 11/11 focused tests including original extractor publication. Some broad tests can take much longer due protected original OCR and are **not claimed** here.
