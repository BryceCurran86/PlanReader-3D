# Spatially indexed native wall-end contact checks

Source-only wall graph diagnostics, original PlanReader. 16 November 2026.

The old `pb_new_wall_graph_diagnostic.inspect_native_wall_graph`
computed each open terminal by checking **every wall in the largest
connected component**. With hundreds or thousands of actual native
source wall strokes, the terminal check repeats unnecessary polygon
distance calculations. The source topology preprocessor had already
built a Shapely `STRtree` for those same input wall polygons.

This change reuses that index to select only nearby wall bars, then
applies the **identical original exact distance** `<= 0.03 PDF pt`,
**identical largest-component owner membership** and distinct owner
check. It cannot join an unverified gap, create an opaque wall over an
aperture, infer physical or commercial wall area or change any
customer/benchmark. It is an algorithmic acceleration, not a weaker
physical authority rule.

## Acceptance and provenance

- 91 focused Python 3.13 tests PASS, including real source wall,
  dual-dwelling outside face, room preview, junction graph and
  4 new spatial-index tests. The tests include 500 consecutive
  source-owned bars, a real T-junction, a near-miss separation which
  must stay unjoined, and exact terminal coordinates.
- Unmodified original private 3Laurel Rev3 page 3: 200 actual
  source-named 0.71pt heavy wall strokes. The old and new source
  endpoint diagnostics were executed side by side, using exactly
  the same original PDF paths. `dataclasses.asdict(result)` is
  **byte-for-byte logically equal** (full record equality):
  115 connected source wall-ink components, 10 bars in largest,
  3 open endpoints, 352 near misses. Recorded this isolated run:
  original 0.0590 sec, new 0.0401 sec (1.47x faster), small as
  this sample is. Do not infer 1.47x performance for the entire app.
- No private PDF or original document bytes are added to GitHub.
- No claimed impact on full original 3Laurel footprint closure:
  3Laurel two-dwelling shared building external walk still
  ABSTAINS until native external right house/garage wall-face
  junctions and openings are source authenticated.
- Separately, Maryborough full source 31-page extraction has a
  much larger cost; this spatial diagnostic change is NOT claimed
  to make the full Maryborough OCR run 8 minutes.

This fixes a single avoidable quadratic precheck while retaining
all original join/abstain and frozen-120 release gates.
