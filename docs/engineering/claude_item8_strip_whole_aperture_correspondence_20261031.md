# Item 8: callout strip to whole-opening aperture correspondence (shadow, opt-in)

Status: implemented as a default-off shadow; nothing here grants a physical opening, host, kind, frame, scale,
metric, count, quantity or customer output, and nothing imports it. Written under `AGENTS.md` and the 2026-10-24
owner policy (independent review optional; checks, original-source evidence and retention mandatory). It consumes
the merged #3869 callout shadow's strips and AntiGravity's merged `StructuralWholeOpeningApertureProducer`
without editing either.

## 1. Observed repository behavior

- The callout shadow names a glazing strip per CANDIDATE callout: `GlazingStrip` has `axis`, `band`,
  `frame_along` (the whole frame extent), `extent_complete` and immutable `ink_ids`.
- `StructuralWholeOpeningApertureProducer.analyze_page(seed, strokes)` takes caller-supplied
  `ApertureSourceStroke` records (width, colour, opacity, dashes, `is_fill_mask`, `is_clipped`) and returns every
  aperture reading it discovers, plus `authority().all_discriminated_subdivisions()` (posts it discriminated).
  Its `wall_band_across` is the glass pair's band, not the wall thickness. `glazing_strip_ids` is always `()`.
- The aperture `record_id` is derived from document, page, span and axis only. Records of the same span with a
  different glass band, status or jamb set share one id; `authority().all_apertures()` keeps only the last of them,
  while the list `analyze_page` returns keeps all.
- A terminal jamb that is an unstroked fill edge, clipped, or translucent makes the record
  `original_terminal_paint_structural_role_unproven`. A record with a stepped lining offset carries
  `ambiguous_multi_layer_offset` even when CANDIDATE.
- `SourceVisibilityProducer` publishes a native segment as VISIBLE only with no active clip or a proven
  axis-aligned rectangular clip that contains it. Every other segment is simply absent from the visible inventory.

## 2. Inference (labelled)

- A strip corresponds to one physical frame only if exactly one structurally proven aperture record has the strip's
  extent and its glass band lies inside the strip's band. This is location, not identity of a physical opening.
- Because the authority supplies no strip linkage and no whole-versus-nested veto, any record that could be another
  reading of the same ink (nested, containing, overlapping) must be retained as a rival and block, unless the
  authority itself discriminated internal posts of that exact record that cut the rival's ends.
- Source ink the producer could not admit inside the strip's region could add to or hide what the authority saw. A
  fill that the content stream paints before every admitted stroke of the region cannot cover them; nothing else is
  cleared.

## 3. Proposed change (as built)

New files only: `pb_callout_strip_whole_aperture_correspondence_shadow.py`, tests, this note.

- Pure core `evaluate_whole_aperture_correspondence(ownership, nominations, apertures, subdivisions, inventory,
  coordinate_quantum_pt=...)`; the equality tolerance is a quarter of the coordinate quantum (the callout shadow's).
- Producer-owned adapter `StripWholeApertureCorrespondenceShadow(source, enabled=False).audit(...)`: every stroke
  handed to the authority is a visible observation resolved CORROBORATED by the producer's own visibility authority,
  joined to the producer's primitive of the same id with identical geometry and drawing sequence. Anything that does
  not join is counted and makes the inventory incomplete (every strip abstains). Fill-only edges are passed as
  `is_fill_mask=True`, never dropped. It runs the authority unchanged and uses the full list of readings.
- Relations: `equal_extent`, `nested_inside_strip_extent`, `contains_strip_extent`, `partly_overlaps_strip_extent`,
  each with the record's own status and reasons, shared ink by observation id, and `end_offsets` (diagnostic only).
- Decision: CANDIDATE only when exactly one equal-extent reading is structurally proven (jamb and wall continuity
  proven, no ambiguity reason), its glass band lies in the strip band, no linked glazing contradicts the strip, every
  strip ink id is in the authenticated inventory, no unadmitted source ink blocks the region, and every other
  related reading is a nested run cut at both ends by that record's own discriminated posts. A positive unvetoed rival
  is CONFLICT; an unproven one ABSTAINED. Duplicate equal-extent readings are CONFLICT.
- Typed standing limits are always present: equal extent is location, the authority links no strips, the authority
  does not decide whole versus nested, the 0.8 pt jamb threshold sits between observed widths, and kind, host and
  quantity are not established.

## 4. Expected abstentions

Unproven terminals (fill-mask, translucent, clipped), no equal-extent reading, rivals the authority does not
account for, an incomplete or unjoinable stroke inventory, unadmitted ink in the region, a strip claimed by two
callouts, an incomplete strip extent, ownership mismatch or invalid records on the page, id collisions among
subdivisions, and exceeded budgets. Each has a typed reason.

### Original-source measurement (SHA-verified original, private, read-only, replayed)

Tree: main `953d4951f` + #4016 + #4024 (elevation records) + #3986 (occupancy), plan p7, elevation p29. The nominator
corresponds two strips there (W01 horizontal, W02 vertical); the other four are not nominated and not evaluated.

- Stroke authentication: 52,242 stroked and 2,824 fill-only visible observations, all joined to the producer's
  primitives (zero failed joins). 4,808 native segments are not admitted (3,846 `visibility_active_clip_unresolved`,
  962 `visibility_geometry_invalid`).
- Inside the two strips' regions every unadmitted item is an unstroked white fill (the opening knock-outs and the pane
  backgrounds), each under a clip written as line items whose scissor equals the fill, which the extractor does not
  recognise as a rectangle. All are painted before every admitted stroke of the region, so the paint-order rule
  clears them; without that rule both strips would also abstain on `unadmitted_source_ink_in_strip_region`.
- Authority output: 821 distinct readings (repeats collapsed), 1,079 discriminated subdivisions. Record ids are not
  unique (`aperture_authority_record_ids_not_unique`): `authority().all_apertures()` would silently drop readings.
- W01: ABSTAINED. One equal-extent reading (843.6..1047.6) exists but it is `original_terminal_paint_structural_role_unproven`;
  the two nested runs are cut at both ends by its own discriminated posts and are set aside; no unvetoed rival.
- W02: ABSTAINED. No reading has the strip's extent. The nearest, a whole-width reading, starts one heavy stroke
  width (0.96 pt) inside the strip's low end and is nested, with two pane-level readings; none is accounted for.
- Sensitivity (diagnostic only, NOT an authenticated input and not part of the module): withholding the 2,824
  fill-only edges from the authority gives every nominated strip a proven equal-extent reading. The unstroked fill
  edges are therefore what stops the terminals, and the authority's input carries no paint order with which it could
  tell a white fill painted before the ink from one painted after it.

First remaining gates, in order: (1) the aperture authority cannot distinguish a fill edge that precedes the ink from
one that follows it; (2) the extractor does not recognise a clip written as a closed line polygon equal to its scissor
as rectangular, which keeps those fills out of the visible inventory; (3) the extent conventions of the strip (outer
face of the frame) and the aperture (jamb station) differ by a stroke width at W02, and neither authority declares a
tolerance; (4) nested pane readings are set aside only where the authority discriminated the posts at both ends.
None of these is changed here.

## 5. Benchmark observations that must not influence implementation

None were used. No tag, project, file, page number, expected quantity or tolerance derived from a benchmark appears
in the module or the unit tests; the original-source test takes every parameter from the environment and asserts
only structure (ownership, grants, claim fidelity, stroke authentication, replay).
