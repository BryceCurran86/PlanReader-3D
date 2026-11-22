# Footprint native-edge support: shadow check, default-off first-trace flag, and a coordinate-space finding (23 Nov 2026)

Shadow only. Counts and public identifiers only: no private source content, coordinates, overlays or customer data. Item 2 of the owner order (#2608 comment 7082410634): reject site, roof and decorative outlines that the raster footprint stage closes into a candidate. This replaces the approach of #4573, which this change does not port verbatim (section 2).

## 1. What changed

- New `pb_source_footprint_native_edge_support_shadow.py`: `assess_footprint_native_edge_support(polygon, native_rows)` returns SUPPORTED, UNSUPPORTED, NOT_APPLICABLE or UNVERIFIABLE with per-edge evidence. Every authority flag is False. It only reads its inputs.
- `pb_external_footprint_first_trace.py` (+29 lines): keyword-only `require_native_edge_support: bool = False`. With the default, results are identical and the new module is not even imported (tested). With `True`, only an UNSUPPORTED verdict abstains the page, with the reason code `external_footprint_unverified_native_wall_edges` that #4573 introduced.
- `tests/test_source_footprint_native_edge_support_shadow_v1.py` (68 tests; 26 of 26 single-line mutants killed).

## 2. Why not a verbatim port of #4573

Its idea is right (a frame drawn in a much lighter pen than the walls it encloses is not the building), its fixtures are reused in spirit. Running its guard over 702 pages of 58 local original PDFs (the four project originals and 54 other documents, mostly residential plan sets of varied formats; first trace on main gives 293 CANDIDATE and 409 ABSTAINED pages) showed five problems:

| Donor behaviour | Observed | This change |
|---|---|---|
| The raster polygon is compared directly with native rows | On a rotated sheet the raster polygon is in VISIBLE page space and `get_drawings()` rows are in the UNROTATED space. The corpus has 35 candidate pages on rotated sheets (7 originals); 12 are near-rectangular and the donor vetoed all 12. With the polygon derotated, 11 are backed and 1 is a real conflict | derotate with `page.derotation_matrix` in the wiring (identity on an upright page) |
| Missing evidence is a veto (no usable dark native ink, or more than 20,000 rows) | 6 near-rectangular candidates were vetoed only because the page had no usable dark native ink | UNVERIFIABLE; never a veto |
| Page-wide cutoff: 65th percentile by segment count, with 20 pt and 0.2 pt absolute floors | The cutoff depends on every short or thin element on the page. On the Acacia floor plan it is 0.84 pt with the donor's 20 pt segment floor, 0.48 pt with a floor of 2 percent of the shorter side (nothing about the building changed), and 0.24 pt in a first version of this check that also counted filled strips; at 0.24 pt the false frame passes | the reference pen comes from the candidate's own interior; no absolute width or length |
| Only stroked rows count | filled wall strips (common in CAD exports) can never back an edge | dark filled strips count, with their thickness as the pen |
| Flat 2.5 pt position tolerance | a thick wall's outer face is half a thickness from its centre line | the 2.5 pt snap plus half the ink's own thickness |

Overall the donor guard would flip 70 of the 91 near-rectangular candidates (77 percent). This check flags 4 (4 percent), and returns UNVERIFIABLE for 38 instead of vetoing.

## 3. The rule in words

For a candidate with at most 8 vertices and at least 4 long axis-aligned edges (an edge is long at 18 percent of the shorter side): find the **interior wall pen**, the heaviest pen (stroke width, or filled-strip thickness) whose linework inside the candidate, edge bands excluded, adds up to one shorter side. An edge is backed when ink at least half as heavy as that pen (two pen steps of the usual line-weight series) covers a quarter of its length. If every edge is backed: SUPPORTED. If an edge is covered by native ink but only lighter ink: UNSUPPORTED (the positive conflict, a hairline frame around wall-weight linework). Edges with no native ink, edges covered only by dark fills the strip reader cannot read, no interior reference, no dark native ink, or more than 20,000 rows: UNVERIFIABLE. Complex or non-rectilinear contours: NOT_APPLICABLE (existing semantics kept). "Dark" and "green" use the raster ink mask's own predicate. Nothing else is read.

## 4. Measured (local replay on private originals, counts only, nothing committed)

Of the 293 candidates, 202 are NOT_APPLICABLE (more than 8 vertices, or fewer than 4 long edges). Of the 91 near-rectangular candidates: 49 SUPPORTED, 38 UNVERIFIABLE, 4 UNSUPPORTED. The 4 are three regional sets of one catalogue house (the floor plan page of each, the same format and legend, so it generalises within the format) and one non-plan sheet. Eleven near-rectangular candidates carry floor-plan text: 3 UNSUPPORTED (those three), 7 SUPPORTED, 1 UNVERIFIABLE (a cover sheet). No other floor-plan page is touched. Per page time stays under 2.4 s.

## 5. Tests (AGENTS.md matrix)

Synthetic positives (one pen, filled strips, thick wall), look-alike negatives (one pen step lighter is not a conflict; exactly two steps is the inclusive boundary), ambiguity (unreadable fills, no reference, no native ink), translation, 90 degree rotation, both mirrors, uniform scale (0.25 and 4), row-order shuffles, splitting walls into collinear pieces, unrelated heavier content and a swarm of ticks outside the candidate (the property a page-wide cutoff loses), deterministic replay, no mutation of the input rows, fitz-like and tuple inputs, malformed rows, the 20,000-row boundary, and on real PDF pages: default-off equality, opt-in abstention on a hairline frame, a real enclosure kept (stroked and filled), a rotated page, a raster-only page, and the one-step-lighter frame left alone. Not covered: plans drawn at an arbitrary angle (NOT_APPLICABLE by design) and a frame drawn in the wall pen (no conflict to detect).

## 6. Not claimed

No measurement, commercial or deduction authority; the flag is OFF in every caller, so live predictions are unchanged and the commercial output is untouched. Public CI cannot see the originals and the protected runner is offline, so no signed or customer parity is claimed. Only 11 floor-plan candidates in the corpus were near-rectangular, which is thin evidence on true building rectangles; enabling the flag in the live callers (`pb_planreader_pdf_extractor`, `pb_live_physical_net_wall_integration`) needs MAX's retention and promotion review.

## 7. Finding not changed here: the footprint chain mixes coordinate spaces on rotated sheets

`trace_external_footprint_first` returns `polygon_pdf_pts` and `bbox_pdf_pts` in visible (rotated) page space. `refine_external_footprint_against_wall_ink` and `bound_native_drawings_to_footprint`, as `tools/run_original_footprint_first.py` calls them, compare those with `page.get_drawings()` rows in the unrotated space. On the 8 candidate pages of one rotated original (every page rotated 90 degrees) the scoped window selects 19,459 rows in total, against 49,836 with the polygon derotated; only 9,162 rows are in both, and three pages share no row at all. I did not change that chain here: it alters which native rows reach the bounded room tracing and needs its own change with parity on rotated sheets. It is the natural next step of item 2.

## 8. Promotion path

1. This PR (draft, shadow, default off). 2. MAX review of the flag and a protected replay on rotated and unrotated originals. 3. A separate change for the derotation in the scoping chain (section 7). 4. #4573 can be closed once this lands; that is MAX's and GPT2's call.
