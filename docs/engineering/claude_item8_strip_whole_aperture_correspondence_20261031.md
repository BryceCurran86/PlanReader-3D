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
- Opt-in `withhold_backdrop_fills` (default off, strict bool; provenance and a page reason change when it acts): an
  unstroked fill PATH is withheld from the authority only when every one of its edges was admitted, at least one
  admitted stroke touches its extent, and every admitted stroke that does is painted after it (an unreadable
  position counts as before; a fill with no readable position is never withheld). A fill painted after a stroke it
  touches can cover that stroke, so it stays as a mask. The rule uses only extents and content-stream positions.
  Withheld edges are counted in the receipt and stay in the inventory; nothing else is changed.
- Opt-in `withhold_terminal_adjacent_fills` (default off, strict bool; independent of the first, and a second run of
  the authority only for the strips it can change): the authority pools every stroke within its 2.5 pt snap distance
  of a terminal station, so an unstroked fill edge that merely lies near a jamb is counted as an uncertain jamb
  stroke. For each nominated strip, a fill path whose edge sits in the terminal set of a reading related to that
  strip is withheld only when, for EVERY such reading, no stroke of that reading's terminal, host-face or glazing ink
  is both touched by the fill's extent and painted before it (or at an unreadable position), the fill's extent and
  position are proven, and every id the readings rest on is known to the inventory. The strip is then judged on a
  second run of the unchanged authority, and the second run's readings (which can include readings that only exist
  because of the withholding) are checked the same way; a failed check keeps the faithful decision. The scope is the
  strip's own readings, so a fill that does cover another wall's jamb elsewhere on the page does not block it.
  What a reading rests on is its terminal jambs, its host faces, **the nominated strip's own ink** (the authority
  leaves `glazing_strip_ids` empty, so the glazing is the nominator's ink ids) and the members of the posts it
  discriminated; a post that cannot be resolved is unknown ink. Both coverage checks (before and after the second
  run) use that one definition. Reproduced defect, fixed: a late white rectangle that covers the strip's glass lines
  and sits beside a jamb used to be withheld and the strip became CANDIDATE.
- Independently of both options, an admitted unstroked fill that is painted at or after (or at an unreadable position
  relative to) a stroke of the strip's own ink that its extent touches stops the correspondence
  (`strip_ink_possibly_covered_by_a_later_fill`): such a fill can hide the glazing even when none of its edges is near
  a terminal. A backdrop painted before the ink never blocks.
- Opt-in `existing_pattern_view` (default off, strict bool): the handoff into the existing opening path. For each
  strip with exactly one equal-extent reading, `PhysicalOpeningAuthority.seeded_candidate_structures` (a new
  read-only accessor in `pb_physical_opening_authority.py`, pure addition, CANDIDATE or ABSTAINED only, no existence
  record, none of the per-page memos used or written, callers pinned by a test) runs the EXISTING six-line
  enumerator on a universe restricted to that reading's members (terminal jambs and host faces). The module then
  reports what that rule made of them: `existing_pattern_describes_the_reading` (one structure whose two jambs sit at
  the reading's ends), `..._finds_layered_structures_of_the_same_gap` (several, sharing a face line),
  `..._finds_distinct_structures_of_the_same_gap`, or `..._does_not_describe_the_reading`; plus the stroked ink
  strictly inside the gap that neither the members, the strip's ink nor the posts' members account for, because the
  rule never saw it. It decides nothing and changes no status. Why an accessor and not `prove_existence`: that method
  derives its candidates from its own page universe and has no point at which a proposed structure can be injected;
  injecting one would issue a CORROBORATED existence record from evidence the authority did not enumerate, which is
  an authority-promotion decision.
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
  the two nested runs (starting 66.48 and 134.64 pt in, same high end) are cut at both ends by its own two
  discriminated posts and are set aside; no unvetoed rival.
- W02: ABSTAINED. No reading has the strip's extent. Three nested readings share its high end: one starts 0.96 pt
  (one heavy stroke width) inside the strip's low end, the others 76.08 and 153.6 pt inside. All three are
  `original_terminal_paint_structural_role_unproven` and none is accounted for by a discriminated post.
- Sensitivity (diagnostic only, NOT an authenticated input and not part of the module): withholding the 2,824
  fill-only edges from the authority gives every nominated strip a proven equal-extent reading. The unstroked fill
  edges are therefore what stops the terminals, and the authority's input carries no paint order with which it could
  tell a white fill painted before the ink from one painted after it.

With `withhold_backdrop_fills=True` (same tree and drawing; 1,196 fill-edge segments withheld, 645 distinct readings,
910 discriminated posts): **W01 is CANDIDATE** — exactly one equal-extent reading (843.6..1047.6, glass band
1955.4..1956.12) that the authority itself marks CANDIDATE with `structural_terminal_jamb_proven` and
`host_wall_continuity_proven`, no rival of any kind, linkage by span equality only (no record names a strip ink id).
**W02 stays ABSTAINED under this option alone**: its whole-width reading (starts 0.96 pt inside the strip) is still
`original_terminal_paint_structural_role_unproven`, and exactly one uncertain stroke remains in its low terminal set:
the edge of a white rectangle (13.9 x 13.2 pt, the background of a printed label) painted after three strokes it
touches, among them a long vertical line it partly covers.

With both options (`withhold_terminal_adjacent_fills=True` as well; one extra run; 4 more fill-edge segments
withheld, all of that one rectangle): **W02 is CANDIDATE** — exactly one equal-extent reading (1557.44..1789.76, glass
band 1119.84..1120.56) that the authority marks CANDIDATE with the same two proofs, no rival, linkage by span equality
only. The label background lies 0.96 pt beyond W02's low terminal station and touches none of the ink that reading
rests on (its jambs, host faces, glazing); the strokes it does cover belong to a different wall's readings, which is
why a page-wide version of the rule keeps it and the per-strip scope releases it. The 0.96 pt "extent gap" seen
earlier was this pooled edge pulling the authority's low terminal to 1558.4; no extent tolerance exists or was added.

First remaining gates, in order (default, faithful input): (1) the aperture authority counts a fill-only edge near a
terminal as an uncertain jamb stroke although a fill edge is not ink; the two opt-in rules above are this module's
evidence-based way to separate a mask that can cover a reading's ink from one that cannot, and would be redundant if
the authority adopted a coverage rule itself; (2) the extractor does not recognise a clip written as a closed line
polygon equal to its scissor as rectangular, which keeps those fills out of the visible inventory (cleared here only
by paint order); (3) nested pane readings are set aside only where the authority discriminated the posts at both
ends. Beyond the whole aperture: physical opening existence, host wall and the `type_mark` for the opening, then
the issuer, which needs the separate authority-promotion review. None of these is changed here.

## 5. Handoff into the existing opening path

Measured with `existing_pattern_view=True` on the original (same tree, both fill options): **W01** - the existing
rule, restricted to the reading's members, finds **two structures whose two jambs sit exactly at the reading's ends**
(843.6 and 1047.6), which share two face lines: two layers of one wall (faces at y 1946.48 / 1951.52 and
1951.52 / 1959.92) for one gap; no stroked ink is left unaccounted inside the gap. **W02** - the same rule finds **no
structure**: its terminals are stepped returns across three layers, not one jamb line joining two faces, so the
existing pattern does not describe them. Two things follow: the existing path cannot issue one existence for W01
until a rule says that layered structures of an identical gap are one opening (today two candidates containing the
same observation are `ambiguous_physical_opening_candidates`), and it cannot describe W02 at all until a stepped-return
terminal pattern exists. Both are changes to the existing authority and to commercial output, so they need the
authority-promotion review; this module changes neither.

Before that, what the existing stack does with the strips on the unrestricted page (what the assessment shadow said, faithful input):

Read from the structural assessment shadow on merged main with the producer's faithful inventory (no withholding;
that shadow re-derives from the producer and cannot take a filtered inventory): for both nominated strips the
existing `PhysicalOpeningAuthority` returns only **fragments**: many `jamb_bounded_two_face_interruption` candidates,
some `corroborated` and many `contested`, none spanning the strip's whole extent, with
`ambiguous_physical_opening_candidates`, `strip_fragments_only_no_whole_extent_candidate` and
`original_terminal_paint_structural_role_unproven`. So the first failing gate of the existing path for a multi-panel
window is that its candidate enumeration never forms the whole-extent candidate, not that a measurement is missing.
The whole-extent reading this module relates to a strip comes from `StructuralWholeOpeningApertureProducer`, whose own
`filter_opening_candidates` only removes post-only candidates and is not wired anywhere. Removing this gate needs: a
whole-extent candidate (terminal jambs, host faces, the strip's ink) presented to the existing
`PhysicalOpeningAuthority.prove_existence` so its own rules decide existence, then the existing host binding, and a
`type_mark` for the opening that `pb_live_physical_opening_void_composition` can read (it takes it from schedule /
plan-tag binding, which cannot see a tag drawn outside the strip). Each of those is an existing authority's seam and a
change to commercial output, so it needs the separate authority-promotion review; this module adds none of it.

## 6. Benchmark observations that must not influence implementation

None were used. No tag, project, file, page number, expected quantity or tolerance derived from a benchmark appears
in the module or the unit tests; the original-source test takes every parameter from the environment and asserts
only structure (ownership, grants, claim fidelity, stroke authentication, replay).
