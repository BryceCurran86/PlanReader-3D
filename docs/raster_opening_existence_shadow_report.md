# Raster physical-opening existence: shadow authority and bridge specification

Status: DRAFT, SHADOW ONLY. Nothing in the live extractor, the customer path, G17 or any quantity imports `pb_raster_opening_existence_shadow`. No customer output changes. Not mergeable without an authority-promotion review.

Labels: OBSERVED = executed or read in this repository. INFERENCE = derived from observations. PROPOSED = what this PR adds. CONTROL = compared with V2 truth read-only; never an input.

Process note (AGENTS.md "first deliverable"): the assignment named the shadow authority as the first deliverable, so this report and the shadow module ship together in one draft PR. The module is isolated and unimported; a reviewer can reject the code and keep the report.

## 1. Observed repository behaviour

- OBSERVED: the Lot16 floor-plan sheet (page 3) is a raster underlay. Eleven image placements (render dpi 300) carry the walls, windows and doors; the vector layer holds only text, dimension chains, notes and the title block. G17 on the vector layer produced 664 structural candidates, none on a window (measured earlier in this lane, data in PR #1245).
- OBSERVED: the existing raster seam is `SourceVisibilityProducer.augment_with_raster_visible_segments`. It renders the whole page at 144 dpi (vector overlay included), thresholds with Otsu, and `detect_axis_aligned_raster_segments` emits one centre-line per connected component. On this sheet the wall poche and the thin window symbol lines share a component, so the interruption is invisible to it.
- OBSERVED: `PhysicalOpeningAuthority.prove_existence` publishes `PHYSICAL_OPENING_EXISTS` (CORROBORATED) for any visible candidate contained by exactly one viewport-scoped candidate. Its candidate patterns are `jamb_bounded_two_face_interruption` (six distinct segments with six distinct derivation parents, endpoints equal within 1e-6) and the generic gap-corroborated door/window patterns. It consumes only `NATIVE_PDF_VISIBLE_SEGMENT` and `RASTER_PDF_VISIBLE_SEGMENT`.
- OBSERVED: `OpeningLabelDimensionProducer` derives the gap span from the physical record's support lines (`_gap_span` needs exactly one group of collinear pairs) and binds a label when its centre lies inside the span along the wall and within `max(3 x glyph height, 2 x cross spread)` across it.
- INFERENCE: feeding raster wall-face edges and jamb caps to G17 as ordinary visible segments is unsafe. G17's vector patterns have no frame, swing or face-continuity requirement, because vector face lines are exact. A raster poche gap that is a niche, a bare break or a dash would be published as `PHYSICAL_OPENING_EXISTS`.

## 2. Proposed shadow authority

`pb_raster_opening_existence_shadow.py`: `raster source -> candidate wall/opening geometry -> physical opening existence -> exact source lineage`. It reads nothing but the page's image placements. It never reads text, vector paths, annotations, drawing scale, file names, page numbers or coordinates, and every threshold is in paper points at the page's own render dpi or a ratio of the wall's measured thickness.

Layer 1, pixels to primitives (no decision about openings):
- the page is copied in memory, text/vector/line art are redacted, images are kept, and the copy is rendered to gray at the largest native image dpi clamped to 100-300 (`render_spec = page_images_only_gray_v1`; annotations off);
- wall poche = gray < 200 mass that survives a 2 pt square opening (black or uniform gray fill; thinner ink is linework);
- axis-aligned band pieces: runs >= 4 pt, thickness <= 12 pt, aspect >= 1.5;
- hairlines: gray < 160 ink that is neither poche nor touching it (3x3 halo), used for swing evidence.

Layer 2, rule on geometry:
1. pair collinear band pieces across a gap with end-thickness overlap >= 0.8 and thickness within 35%;
2. the gap must be clean (no mass before the partner), >= 8 pt and >= 2 wall thicknesses;
3. positive evidence inside the gap is required. Either frame lines (two or more thin parallel lines spanning >= 80% of the gap inside the wall rows) provided neither wall face keeps ink across the gap, or a door swing (a hairline leaf at a jamb plus a hairline quarter-circle whose radius equals the gap within 15%, arc coverage >= 0.8, leaf coverage >= 0.9, exactly one hinge/side configuration);
4. a bare break, a recess outlined on the faces, a face-continuous glazing ribbon, an ambiguous swing, overlapping proven candidates, a rotated page, no raster layer, an oversized layer or a band storm all ABSTAIN or CONFLICT, and every candidate decision is retained.

Record = `RasterOpeningExistenceRecord` (not a `PhysicalOpeningExistenceRecord`; its own proposition string; `shadow_only=True`, `authoritative=False`, result `canonical_publication=False`), with stable ids from `stable_contract_id`, the exact pixel and point gap box, both flank pieces, the symbol evidence, and lineage (source sha256, page, render dpi, layer id built from every image placement's xref, raw-stream sha256 and bbox).

## 3. Results (the seven requested items)

1. Raster primitives and evidence used: images-only gray render; solid-poche band pieces; hairline mask; frame-line rows across the gap; leaf strip and quarter-circle samples; nothing else. `docs/data/raster_opening_existence_shadow_lot16_p3.json` carries the exact boxes and lineage.
2. Physical-existence rule: section 2, Layer 2, steps 1-4. Existence is a wall-band interruption between two continuing collinear bands, clean, wide enough, with positive frame or swing evidence that does not rely on the wall faces continuing across the gap.
3. Lot16 candidate count (page 3): 75 band pieces, 30 candidate decisions, 21 proven (14 frame-line windows/openings, 7 door swings) and 9 retained rejections: 4 wall face continues across the gap, 1 gap without evidence (a window whose frame lines span less than 80%), 4 logo-letter gaps. The other 12 Lot16 plan pages and the 11 structural pages prove nothing.
4. Compact callouts (CONTROL, `scripts/raster_opening_callout_control.py`, label-binding rule restated from `pb_opening_label_dimension_authority`): 7 of 10 bind to exactly one raster-proven opening. The other three: `0906 SGW obs` has a proven opening whose span ends 0.8 pt before the label centre (rule near-miss, label authority's call); `2124 CRNR STACK` has a proven 118 pt opening but its label sits 20.7 pt beyond the span and 55.8 pt to the side (leader-placed label); `2127 STACKER` is abstained by this authority (its hairline track lines run along both wall faces, so it cannot be told from a recess at pixel level). No callout, label, room name or quantity is an input; the authority cannot create or move an opening from text.
5. False-positive census (756 pages, 8 PDFs, `scripts/raster_opening_existence_shadow_diff.py`, 7 negative-control files gated with `--expect-none`):
   - native raster layers: 111 pages carry an image layer; all 21 records are on Lot16 page 3; zero on the other 755 pages (Lot16 plan and structural sets, 3Laurel and KSTVET vector sets, Lamu, Umma, and the Ghazi and Murera scans);
   - simulated scan at 150 dpi (every page rendered whole as if scanned): 21 records. 14 are 3Laurel door openings on its two floor plans, all reviewed by eye and genuine (870/720 mm doors with leaf and arc); 7 are Lot16 page 3 (6 doors and 1 window; hairline-inset windows are not resolvable at 150 dpi, which is the intended fail-closed behaviour). Zero on KSTVET (55 double-line-wall pages), Ghazi (167), Lamu (45), Umma (209), Murera (238) and the Lot16 structural set (11);
   - the census found real failure modes while this was built, each fixed with a principled rule and a regression test, not a project constant: 24 false records from dashes in the Ghazi p167 glazing ribbon and 2 wall niches (a through-opening interrupts both wall faces; recesses and ribbons keep their outline on them); a swing matched to sink outlines in a 5 pt gap (paper-unit floor of 8 pt, exact radius tolerance, leaf coverage 0.9); 3 glyph false records from bold lettering (swing leaf and curve must be hairlines, thinner than the poche); an even-kernel off-by-one visible only at 288/144 dpi.
   - cost of the strict face rule: the bed-1 west window (exterior sill line on the face) and `2127 STACKER` abstain.
6. Runtime: Lot16 page 3 about 1.0 s (0.4-0.5 s render and redaction, 0.5 s analysis), peak RSS about 520 MB for the 17.4 Mpx layer; all 13 Lot16 pages 10.6 s; the 756-page census about 35 s native and 63 s simulated; results are byte-identical across PYTHONHASHSEED 0, 1 and 777.
7. Downstream bridge: section 4.

## 4. Exact downstream bridge (not implemented)

G17 owns `PHYSICAL_OPENING_EXISTS`; the producer owns observations. The evidence rules therefore must live in G17 as a new pattern over producer-owned raster primitives, never in the producer:

1. Producer, `SourceVisibilityProducer`: a sibling of `augment_with_raster_visible_segments` publishes Layer 1 primitives from a producer-owned images-only native-dpi render: wall band pieces, thin ink runs along band faces and across gaps, and wall-face edge segments with exact shared gap endpoints. Each primitive is a `RASTER_PDF_SEGMENT` parent plus a visible child with a receipt naming the image sha256s, dpi, pixel geometry and detector version. No opening decision is made there.
2. G17, `pb_physical_opening_authority`: new patterns for the framed and swing interruptions implement Layer 2 over those observations (reuse this module's constants), produce the only `PhysicalOpeningExistenceRecord`, viewport-scoped like the existing patterns, with `AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES` for overlaps. Door-swing arc evidence is candidate-driven (radius equals the gap), so the producer publishes the arc and leaf measurements per Layer 1 gap candidate or G17 asks for them; it must not become a page-wide circle search. The existing `pb_plan_raster_door_swings` is built for inverted CAD rasters and tag emission and is not a reusable primitive.
3. Label support, `_gap_span`: the candidate's support set must contain the face-edge segments (two collinear pairs, one gap group) or #1242 returns no span and the label stays unbound.
4. Host binding, `OpeningHostBindingProducer` and `pb_physical_wall_candidate_authority`: the wall candidate path already consumes `RASTER_PDF_VISIBLE_SEGMENT` for raster-only geometry; the face-edge segments must also feed wall bands so a host band is centred on the opening (`authenticated_host_wall_band_not_centered_on_opening`). Unverified: how the current raster wall path treats poche faces; check before building.
5. Scope: Lot16 page 3 still needs authenticated viewport ownership (#1249 / #1243); primitives are published at page level and G17's viewport scoping applies.
6. Unchanged downstream: #1242 label binding, #1244 area quantities, #1251, #1252 sealing, #1253 compact-callout safety, #1256, #1258. Rejected alternative: the producer emits face segments only at gaps this module already proved (it would launder an existence decision into observation selection).
7. Gate: G17 vector outputs identical (existing G17 suites unchanged), raster set equals this census, negatives zero, deterministic ids, W10 flags untouched. This changes `PhysicalOpeningExistenceRecord` production on raster pages, so it needs an authority-promotion review.

## 5. Limits and abstentions by design

Hatched and double-line walls (no poche) abstain; so do pages with `/Rotate`, no image layer, layers over 60 Mpx, and scans above 300 dpi are analysed at 300. Windows whose frame or sill lines run on the wall faces abstain (bed-1 west window, `2127 STACKER`); recovering them needs panel or track evidence as a separate primitive. Hairline-inset windows need roughly 190 dpi or more. Lot16 page 3 is the development drawing, so its recall is a development figure, not held-out; the held-out evidence is the 3Laurel simulated-scan result and the zero-record negative controls. This module makes no accuracy claim and the official Lot16 score stays 0/27.

## 6. Tests and reproduction

`tests/test_raster_opening_existence_shadow.py` (77): synthetic positives (window, four door hinge/swing combinations, vertical, two windows); look-alike negatives (bare break, single line, niche, glazing dashes, small gap, thickness step, offset continuation, free end, noise, arc radius, arc without leaf, heavy swing curve); ambiguity and conflict; duplicate and overlap handling; dpi (192-300), translation, quarter-turn rotation, mirroring, padding, unrelated-content and tiling/order invariance; deterministic replay and stable ids; no input or document mutation; text, vector, annotation and metadata isolation (text and drawing APIs patched to fail); rotated page, quarter-turn placement, oversize, band storm, dtype; and architecture checks (no production importer, only the two scripts import it, firm seams do not, stdlib + numpy + cv2 + contract module only, no authority module loaded, no benchmark fragments, W10 flags false).

```
python scripts/raster_opening_existence_shadow_diff.py --pdf plan=PLAN.pdf --pdf vec=VECTOR.pdf --expect-none vec --simulate-scan 150 --montage plan:3 --out census.json
python scripts/raster_opening_callout_control.py --pdf PLAN.pdf --page 3
```

## 7. Review checklist

- Confirm that G17, not the producer, should own the framed and swing patterns (section 4).
- Confirm the strict face-continuity trade (two abstentions on Lot16) is the right side of the fail-closed line.
- `0906 SGW obs` and `2124 CRNR STACK` belong to the label authority: a 0.8 pt near-miss and a leader-placed label.
