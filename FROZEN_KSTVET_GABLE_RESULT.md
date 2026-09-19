# FROZEN source-derived KSTVET gable result (BOQ-C36-B)

Recorded before any benchmark comparison, per sprint Step 8. Not modified
after scoring.

## Source

- Document: `1727358888238-bq-nd-drawing.pdf` (KSTVET/008/24, "PROPOSED CLASSROOM AND INTEGRATED RESOURCE CENTER")
- Page: 54 ("A.02.5.10", drawing sheet "CLASSROOM BLOCK - CBC")
- Views used: ELEVATION E-03 (1:75), ELEVATION E-05 (1:75)
- General note (same page): "15 degree roof pitch with IT5 gauge 26 on 50mm x 50mm s/w battens on s/w timber trusses."
- Dimension calibration: native dimension witness line `(1516.2, 394.6)–(1824.2, 394.6)` = 308.0 pt, labelled `8,150` (mm) between grid 1 and grid 2 → scale = 8.150 m / 308.0 pt = 0.026461 m/pt.

## Cross-view identity (Step 6)

- Floor plan (same sheet) carries elevation-reference triangles: `◁E-03` at the grid-A end of the plan, `▷E-05` at the grid-D end. Both E-03 and E-05 share the same grid-1/grid-2 baseline span (8,150mm), confirming each is a genuine end-on view of a distinct short (1–2 direction) wall.
- Grid correspondence: E-03 and E-05 both dimension grid 1→2 as 8,150mm, matching the floor plan's own A–D end-wall spans.
- Verdict: **PROVEN_DISTINCT** — E-03 = grid-A end wall, E-05 = grid-D end wall. Not the same physical wall viewed twice; not doubled by assumption.

## Physical gable end 1 — Elevation E-03 (grid A)

Vector-measured roofline (page-native PDF points):
- Left slope: `(1491.1, 463.8) → (1658.4, 419.0)`, measured pitch = 15.00°
- Right slope: `(1658.4, 419.0) → (1901.3, 484.1)`, measured pitch = 15.00°
- Ridge apex (shared endpoint): `(1658.4, 419.0)`
- Both slopes match the drawing's own stated "15 degree roof pitch" exactly (0.00° residual).
- Note: the right slope's roofline continues well past grid 2 (to x=1901.3, ≈2.04m beyond grid 2) — this is the separate verandah roof plane, NOT part of this gable wall; the gable polygon is evaluated at the grid-2 boundary (x=1824.2), not the roofline's outer overhang tip.

Boundary (end-wall extent): grid 1 x=1516.2 pt, grid 2 x=1824.2 pt (8,150mm span, matching the floor plan's own A–D end-wall dimension).

Reconstructed polygon (left eave, ridge, right eave):
- `(1516.2, 457.079)`, `(1658.4, 419.0)`, `(1824.2, 463.436)`
- Area = 4.4225 m²

## Physical gable end 2 — Elevation E-05 (grid D)

Vector-measured roofline:
- Left slope (grid-1 side): `(1514.7, 837.5) → (1682.0, 792.7)`, measured pitch = 15.00°
- Right slope (grid-2 side): `(1682.0, 790.8) → (1849.3, 835.6)`, measured pitch = 15.01°
- Ridge apex (averaged shared endpoint): `(1682.0, 791.75)`
- Both slopes match 15° within 0.01°. This end has small, roughly symmetric eave overhangs on both sides (≈25pt / 0.66m each) — no adjoining verandah extension on this end.

Boundary: same grid 1/2 x-positions (1516.2, 1824.2).

Reconstructed polygon:
- `(1516.2, 837.098)`, `(1682.0, 791.75)`, `(1824.2, 828.879)`
- Area = 4.4127 m²

## Frozen summed result

| Gable end | Ridge apex (pt) | Area (m²) |
|---|---|---|
| E-03 (grid A) | (1658.4, 419.0) | 4.4225 |
| E-05 (grid D) | (1682.0, 791.75) | 4.4127 |
| **Total** | | **8.8352** |

Both ends are genuinely close in area (0.2% apart) despite the ridge sitting off-centre on the wall span (≈46% of the way from grid 1 on both ends) and the two eave heights differing by ~150–170mm on each end — this is a real, source-proven asymmetric-ridge roof, not a symmetric textbook gable, and the near-equal areas are a geometric consequence of triangle area being height/base-driven rather than peak-position-driven, not an assumption.

No opening deductions: no window/door openings are shown within either gable triangle above eaves level.

**This roofline result is frozen prior to any benchmark comparison and was not adjusted after seeing it.**

## Addendum — measurement-scope audit (does "gable walling" measure this region?)

A second, independent question was audited: does the commercial BOQ term
"gable walling" actually measure the bare above-eaves triangle, or some
other region (e.g. above a ring beam, above a wall plate set back from
the roofline, or the full end wall)? This uses
`pb_gable_measurement_scope_authority.py`, which never modifies the
roofline geometry above — it only decides where to cut the wall from
below.

**Exact BOQ wording (page 36, "ELEMENT NO.3 WALLING → EXTERNAL WALLING"):**
```
A   150 mm Thick walling.        58  SM   1,400   81,200
B   Ditto gable walling.         13  SM   1,400   18,200
    [Three-ply bituminous felt DPC, measured nett, 300mm laps:-]
C   200mm wide under walls       35  LM      80    2,800
```
Both A and B share the same rate (1,400/SM) and are both listed under one
external-walling header specifying 150mm natural stone walling. "Ditto"
in B explicitly ties it to A's same walling spec, as a separate
(residual) measured region, not a restatement.

**Candidate lower datums investigated:**

| Candidate | Evidence | Verdict |
|---|---|---|
| Ring beam (structural) | BOQ page 35, "Ring Beams": 3 CM concrete, formwork "sides and soffits of beams" = 25 SM. Two equations (volume, formwork area), three unknowns (length, width, depth) — no structural detail drawing is included in this package (general notes explicitly defer to "Structural Engineer's drawings", not present here) to independently fix a width or depth. | **REJECTED — underdetermined.** Not used to shift the datum, and not solved for using the expected BOQ-C36-B quantity (that would be exactly the reverse-engineering this audit is required to avoid). |
| Wall-plate / parapet band | 600-DPI close-up of both E-03 and E-05 (`kstvet_e03_eaves_closeup.png`, region 1220–1700×380–500 thumbnail-scale) shows continuous, undifferentiated masonry coursing hatch running directly from the wall body to the underside of the sloped roofline — no drawn band, step, or material change. | **REJECTED — no distinguishing feature drawn.** A continuous, undifferentiated surface is itself evidence against an intermediate datum, not merely an absence of proof. |
| Ceiling line | Section S-02 shows the truss and wall in profile; no separate ceiling line is drawn anywhere below the truss. | **Not evidenced — not applicable.** |
| Full end wall (ground to ridge) | Order-of-magnitude check only (never used to select a datum near 13.0): assuming a plausible 2.5–3.3m eaves height, the full end-wall area for both ends is 49.6–62.6 m² — 4–5× the expected 13.0 m², regardless of the exact height assumed. | **REJECTED — implausible by scale**, independent of the benchmark figure's exact value. |

**Resolved scope:** `ABOVE_EAVES` for both E-03 and E-05 — accepted specifically because (a) BOQ-C36-B is worded as a residual "Ditto" of BOQ-C36-A, and (b) no distinguishing intermediate feature was found between the eaves and the roofline in either elevation. This is a resolved, evidenced proposition, not a silent default.

**Frozen commercial measurement-scope result:** identical to the roofline-only result, because no evidence proves the scope extends beyond the bare above-eaves triangle:

| | Roofline-only area | Measurement-scope area |
|---|---|---|
| E-03 | 4.4225 m² | 4.4225 m² |
| E-05 | 4.4127 m² | 4.4127 m² |
| **Total** | **8.8352 m²** | **8.8352 m²** |

**Benchmark comparison (performed only after freezing):** BOQ-C36-B expects 13.0 m² → 32.03% error, still a gross mismatch. Per the sprint's Step 12: **SOURCE-DERIVED COMMERCIAL PROPOSITION DOES NOT RECONCILE WITH BENCHMARK GOLD.** Classified as *benchmark quantity relies on evidence outside the available drawing set* (the referenced Structural Engineer's drawings, which would be the only place a genuinely different, independently-dimensioned ring-beam/wall-plate datum could come from) — not a defect in this reconstruction, and not touched further.
