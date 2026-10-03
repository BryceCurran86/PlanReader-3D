# Claude -> GPT handoff: Lot16 plan sheet is a raster underlay (diagnosis only)

Date: 2026-10-03. Measured on `origin/main` 7566be79 / f26e77fe (the page-3 opening census was re-run at f26e77fe with identical output). No production code, V2 truth, scoring, tolerance or denominator is changed by this document. Source: Lot16 architectural plan set, sha256 `10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`, 13 pages; all 27 V2 items are on its floor-plan sheet (page 3).
Labels: OBSERVED = executed here. INFERENCE = derived. CONTROL = compared with V2 truth read-only; it must not set thresholds.
No page renders of the client drawing are committed. Scripts that reproduce every number are in `data/` (they hard-code local paths).

## 1. Headline (OBSERVED)
Page 3 is **a raster underlay with a vector annotation overlay**, the Murera/Ghazi class, not native CAD.
- `page.get_images()` returns 9 images: 8 tiles of about 300 dpi, each 238 pt wide, that tile the whole sheet, plus a logo.
- With the 9 images deleted from an in-memory copy and the page re-rendered, the remaining vector layer contains only text, the dimension chains, the notes/legend panel and the title block. **No walls, windows, doors, room fills, swing arcs or logo remain.**
- The vector census of the page has 1,234 paths (1,053 stroked lines, 170 filled rectangles, a handful of curves). **None lies within 40 x 12 pt of the `1218 SGW` window gap**, and a probe for a vector window symbol of the decoded length at any of the 10 callouts found none.
INFERENCE: every authority that proves physical geometry from vector linework (G17 face/jamb patterns, hosted-opening spans, vector wall candidates, room faces) is looking at annotations, not at the plan.

## 2. What the existing opening authorities see on page 3 (OBSERVED)
- G17 candidate structures: 664 on the native snapshot, 672 after wall-candidate raster augmentation (1,727 native + 2,356 raster visible segments). All are `jamb_bounded_two_face_interruption`. Gap width quantiles in points: min 0.5, p10 11.3, p25 36.5, median 105, p75 274, p90 553, max 840; 147 candidates are wider than 300 pt. Most are not window-sized openings.
- For each of the 10 compact callouts the nearest candidate of gap width at most 250 pt has its centre 50 to 130 pt away. At the sheet's printed 1:100 a window would be 25 to 140 pt wide and its centre within a few points of its label. **No candidate sits on any window.**
- `resolve_hosted_opening_spans` inside the shadow candidate viewport abstains: "no jamb-bounded, both-face-confirmed wall interruption found in viewport" (0.12 s).
- Raster-visible segments in a window-gap box (x 525-600, y 185-205): six short dash pieces plus one continuous run (x 324.8 to 886.5 at y 193.5) that crosses every window gap. The window symbol bridges the gap, so there is no face-line interruption to detect. INFERENCE: the physical gap exists only as an interruption of thick wall poche in the raster tiles.
- The live composition on page 3 (f26e77fe): 67 representative observations, 28 existence-proven records (host ABSTAINED `complete_authenticated_host_wall_universe_required`) and 39 `ambiguous_physical_opening_candidates`. Wall scope `physical_wall_candidate_scope_bounds_unresolved` over 2,634 candidates. All 28 canonical openings have `geometry_complete=False` and `viewport_id=None`.
- Label binding experiment (scratch, `data/lot16_label_bind2.py`): all 10 compact callouts are text-integrity-trusted lines (312 trusted lines on the page). With the compact grammar injected into the #1242 label producer, 0 labels bind to a proven opening: 20 proven openings give `opening_label_dimension_text_unavailable`, 3 give `opening_label_dimension_ambiguous`. The proven records' gap spans are 769 to 829 pt wide, so a label always falls inside "an opening" but never near a window.

## 3. Viewport and wall scope (OBSERVED)
- F.07 returns one `unsupported` `legend` viewport for page 3: the only in-drawing anchor is the `LEGEND` heading, and the real title ("FLOOR PLAN") is a title-block field value that `extract_view_title_anchors` deliberately excludes. A non-empty but unresolved viewport list is what turns every dangling wall end into `bounds_unresolved`. Your #1243 targets exactly this.
- Shadow authority PR #1249 (`pb_title_block_viewport_shadow.py`) proposes a floor-plan viewport candidate for such sheets. Used as the authenticated viewport for G17 gating in a scratch run it removes 3 "openings", all title-block table lines (y >= 697), and gives the rest a viewport id.
- Scratch what-if (monkeypatch, not code): ignoring the legend-only structure resolves page-3 wall scope and gives 9 openings a host, then stops at `no_authenticated_host_wall_band`, `physical_wall_equivalence_required_for_host`, `source_room_face_boundary_unresolved`, with 2,554 of 2,634 walls physically unresolved.

## 4. Compact callouts on the sheet (OBSERVED, source text only)
Ten trusted lines match #1207's grammar: `0906 SGW obs`, `1215 SGW obs`, `1218 SGW` (x2), `0621 SGW`, `0630 FG`, `0615 SGW`, `2124 CRNR STACK`, `2127 STACKER`, `2148 PANEL LIFT`. Elevation sheets repeat several of the same callouts (p4 5, p5 3, p10 1 under an ungated parse), so any binding must stay on the floor-plan sheet.
The #1242 grammar reads a 4-digit token as a literal mm value, allows compact hundreds only for 1-2 digit pair tokens, and rejects the `SGW`, `FG`, `STACKER`, `CRNR STACK` tails. #1207 reads the same token as height x width in hundreds. Hinged doors and internal openings carry bare `870` / `1200` tokens near the swing, with heights from the FSL-to-JL datum in the section.
Production position (Bryce, 2026-10-03): text must not mint a physical opening; the callout is measurement/type evidence that must bind to an independently proven opening.

## 5. Consequence for the Lot16 opening items (INFERENCE)
Under that position the ten callout areas cannot publish until an independent physical-existence proof exists for windows and doors on raster-poche sheets. Neither viewport ownership (#1249/#1243) nor a grammar extension changes that. Options, none started:
1. A raster-poche opening-existence authority: along each long axis-aligned raster wall band, find a gap in the thick-ink profile bounded by continuing equal-thickness wall on both sides, with window/door symbol ink across it. Existing raster seams to reuse: `pb_raster_visible_segment_detector`, `pb_raster_wall_network_authority`, `pb_plan_raster_door_swings`.
2. The figured-dimension span identity workstream already named in AGENTS.md (dimension line -> terminators -> witnesses -> endpoints -> exact physical span -> exact target entity). The exterior chains on this sheet are vector and carry the window spans. This proves a dimensioned span, not by itself that an opening exists there.
3. Leave raster-poche openings as unbound evidence and publish nothing for them.
CONTROL: scratch sealing of today's #1207 quantities through the merged V2 tooling with a placeholder viewport scores 10/27, which only measures the publication seam. Official Lot16 stays 0/27.

## 6. Related work and a design finding (OBSERVED)
- #1244 / #1251 / #1252 already carry label area -> canonical opening -> QuantityEvidence -> seal. I deliberately did not duplicate them.
- The live physical net-wall chain has no first-class evidence-only page. `compose_live_gross_wall_geometry` requires every page in `wall_opening_composition.page_ids` to have a corroborated, `scope_complete` wall scope, while `CrossSheetRegistrationProducer` requires the TARGET (elevation) page's wall scope to be corroborated. The customer bridge passes every selected sheet (11 pages for Lot16: 163 canonical openings and 577 walls, 135 openings on non-floor-plan sheets), so a non-plan page with an incomplete scope blocks the whole claim. The extractor passes floor-plan pages only, which leaves no elevation target for height registration. A draft branch splits topology pages from evidence pages; see its PR.
- Runtime baseline (measured at main 7566be79): extractor 372-408 s, peak working set 1,166 MB; customer `analyse_workspace` 691 s; page-3 G17 + voids 10.3 s; page-3 net-wall claim 32.7 s.

## 7. Not done and not claimed
No production change, no accuracy claim, no merge. Maryborough and Q5446 sources were not available locally.
