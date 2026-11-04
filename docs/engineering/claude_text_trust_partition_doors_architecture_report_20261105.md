# Claude vertical slice: text trust, physical partition, internal door swings — architecture report (2026-11-05)

Status: first deliverable under `AGENTS.md` ("Before changing code, produce a short architecture report ... then proceed with the authorized implementation"). Docs only. Base `origin/main` `d75273eda`. Counts and gate names only; no private coordinates, ids or drawing text.

Labels: **OBSERVED** (read or measured this session), **INFERENCE**, **PROPOSED**, **BENCHMARK** (must not influence implementation).

## 0. Compliance

**Read in full:** `AGENTS.md` (current main; the local checkout was 579 commits behind and carried an older copy that still said "stop for review"), `docs/AI_ENGINEERING_PLAYBOOK.md` (and its diff against main), `docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md`.

**Not read:** the other four playbook-listed documents (`docs/wall_topology_observability_architecture.md`, `docs/planreader_wall_room_topology_spec.md`, `docs/planreader_public_tender_benchmarks.md`, `.github/workflows/ci.yml`). They describe the wall-length path and CI, not the text-trust and opening path traced here. `ci.yml` (truth-separation job) will be read before any PR is opened.

**Functions traced (file + name):**
- `pb_source_visibility_authority.py`: `_derive_visibility_page`, `SourceVisibilityProducer.__init__` (the `source_native_finish_text_shadow` explicit bool), `ingest_native_pdf_bytes` (receipt minting, ~L2138-2229), `text_integrity_authority`.
- `pb_pdf_text_integrity_authority.py`: `classify_native_word_integrity`, `_decode_status`, `_glyph_unicode_consistency_reasons`, `_font_for_glyph_validation`, `_source_embedded_symbol_byte_glyph_reasons`, `PdfTextIntegrityAuthority.resolve_text`.
- `pb_raster_text_corroboration_authority.py`: `RasterTextCorroborationProducer.publish` and its constructors.
- `pb_font_glyph_mapping_corroboration_shadow.py`: module contract, `word_glyphs`. `pb_source_amortized_glyph_text_corroboration_shadow.py`: `SourceAmortizedGlyphTextProducer` (all methods).
- `pb_plan_door_swing_geometry.py`, `pb_plan_raster_door_swings.py` (heads), `pb_door_height_owner_gate_shadow.py` (docstring and denylist).
- Callers of `compare_identity` / `partition_receipt` (grep only).

**Not read this session:** the bodies of `pb_physical_opening_authority.py::compare_identity / partition_receipt / _pairwise_identity` and of `pb_opening_callout_dimension_binder.py`. Claims about them rest on 49 passing tests (section 3) and on grep of their callers.

**Authority boundaries crossed:** primitive capture (native words and trace) -> text integrity receipt (`text_glyph_mapping_unverified` gate) -> trusted text -> opening label/tag/schedule consumers. No quantity boundary is crossed by the proposed change.

**Files that stay untouched:** `pb_planreader_pdf_extractor.py`, `pb_planreader_jobhub_publish_contract.py`, `pb_opening_production_v175.py`, `pb_opening_deduction_pipeline.py`, `pb_opening_callout_dimension_binder.py`, `pb_plan_door_swing_geometry.py`, `pb_plan_raster_door_swings.py`, `classify_native_word_integrity` and the default path of `_glyph_unicode_consistency_reasons`, everything under `benchmarks/frozen_holdout/full_plan_v2/`, `documents/sources/*.pdf`, W10 defaults.

## 1. The directive against the contract

The 2026-11-05 directive names three tasks. Reading each against the code:

| # | Directive text | Finding |
|---|---|---|
| 1 | Text trust for 3Laurel callouts in `pb_source_visibility_producer.py` and `pb_opening_callout_dimension_binder.py` | `pb_source_visibility_producer.py` does not exist; the producer is `pb_source_visibility_authority.py`. The binder is a legacy raw-text parser called only from the live extractor; the authenticated seam is the text-integrity receipt. Real work exists (section 4). |
| 2 | Physical-partition defect #4147 in `pb_physical_opening_authority.py` | Already on main (merged through #4148). 49 existing tests pass at `d75273eda`. No change proposed (section 3). |
| 3 | Bridge `pb_plan_door_swing_geometry.py` to customer `QuantityEvidence` for internal 870 doors | Blocked for three independent reasons (section 5). Not started. |

## 2. Observed: why 3Laurel text is untrusted

Measured on the SHA-verified original (`014e9f68`, 18 pages), page 3, `classify_native_word_integrity` called per word, once with defaults and once with the producer's native finish text opt-in (`source_symbol_font_chain_shadow` and `source_raw_no_active_text_clip_shadow` on). Script is a read-only scratch file, not committed.

- 1,215 words; **0 trusted in both modes**. The opt-in changes no count.
- `text_glyph_mapping_unverified` on 1,144 words (decode status `tounicode_glyph_unverified`: the ToUnicode CMap is valid, the glyph proof is what fails). 1,140 words carry that reason alone or with `text_clip_state_unresolved`.
- All 1,144 are `Type0` fonts (1,070 regular-weight, 74 bold, same family). `_source_embedded_symbol_byte_glyph_reasons` accepts only `TrueType` (`pb_pdf_text_integrity_authority.py` L425), so the opt-in cannot help. `_font_for_glyph_validation` can load the subset, but a subset without a Unicode cmap gives `has_glyph(...) <= 0` -> unverified.
- 71 words have no font binding (`text_font_binding_ambiguous` 63, `text_trace_unavailable` 8). They are a separate, smaller gate.
- The raw (untrusted) text is **not garbled**. A raw-token scan of the same pages finds size-code tokens, alphabetic codes and WINDOW/DOOR words on page 3, and a "SCHEDULE" page with 35 four-digit tokens on page 8. The earlier note "3Laurel raw text shows no tags (inference: glyph-garbled)" was wrong; the gate is trust, not extraction.

**Existing pieces, all unwired for this purpose:**
- `pb_raster_text_corroboration_authority.RasterTextCorroborationProducer.publish`: producer-owned, two render scales, strict equality with the native claim. It is the proof for exactly `text_glyph_mapping_unverified`. One word at a time, seconds per word.
- `pb_font_glyph_mapping_corroboration_shadow` (#2861 lineage): vote ledger per (font program, glyph id). Shadow; no live caller.
- `pb_source_amortized_glyph_text_corroboration_shadow.SourceAmortizedGlyphTextProducer` (#3435): only imported by its own test. Its `record_direct_ocr_result(observation_id, success: bool)` takes a **caller-asserted boolean** (no production caller), and its records are `CANDIDATE` with `commercial_projection_allowed=False`. Wiring it as-is would let a caller self-certify OCR success.

## 3. Observed: partition (#4147) is already live

`PhysicalOpeningAuthority.compare_identity`, `partition_receipt` and `verify_partition_receipt` are on main. Callers: `pb_live_append_only_opening_area_composition.py` (L206-210, requires a verified receipt), `pb_generic_opening_count_authority.py` (L659), `pb_opening_host_binding_authority.py` (L543), `pb_g17_plan_wall_scope_shadow.py` (L374). `pb_live_physical_opening_void_composition.py` contains no differing-id DISTINCT shortcut.

`tests/test_physical_opening_identity_partition_v1.py`, `tests/test_physical_opening_partition_receipt_v1.py`, `tests/test_raster_aperture_identity_conflict.py`: **49 passed** at `d75273eda` (12.6 s). Overlapping extents with distinct observation ids resolve to CONFLICT or ABSTAINED, not DISTINCT. INFERENCE: the directive text predates #4148. PROPOSED: no code change. A full audit of every consumer for an id-inequality shortcut has not been done; I will report any counterexample as a test first.

## 4. Proposed change (task 1 only), shadow-first and default-off

**Intended production behaviour:** words whose **only** blocking reason is `text_glyph_mapping_unverified` become trusted text when every glyph in the word has a verified (font program, glyph id) -> character mapping, where each mapping is supported by at least two independent raster-corroborated words and contradicted by none. All other reasons (clip, occlusion, trace, binding, Unicode) keep the word untrusted.

1. `SourceVisibilityProducer` gains an explicit-bool, default-False option (new name, not tied to `source_native_finish_text_shadow`, so the Maryborough and Lot16 paths stay byte-identical when off). Forwarded only when on.
2. A small orchestrator composes the existing `GlyphMappingLedger` (planner and vote partition) with the existing `RasterTextCorroborationProducer.publish`. **Outcomes are derived from sealed CORROBORATED records, never from a caller boolean.** Scope = the pages the composition requests, not the whole document.
3. Receipts are minted at ingest (`ingest_native_pdf_bytes`), and `RasterTextCorroborationProducer` reads the already-published snapshot and receipts, so it can only run after ingest. The upgrade is therefore a second, sealed receipt layer merged inside `text_integrity_authority()`; `resolve_text` and `receipt.trusted` stay the single trust vocabulary (no new enum). The new decode status string records the ledger lineage.
4. Typed negatives retained: contradicted and under-supported glyphs keep their words untrusted with reason codes; nothing is deleted.
5. Consumers (schedule binder, label dimension and semantic authorities) are not edited. Done means a real opening on the 3Laurel plan page reaches `compose_live_physical_opening_voids` with an authenticated text-to-aperture binding, measured through the real consumer, or the next failing gate is named with its function.

**Rejected:** matching embedded glyph outlines to a system Arial (environment- and licence-dependent, not in the repo); trusting ToUnicode alone (the module docstring already says it cannot prove glyph identity); a second OCR engine or confidence threshold.

**Determinism note (INFERENCE):** upgrades depend on `select_production_ocr_backend()`. With no backend the option abstains with a typed reason; sealed replays must pin the backend (GPT3 owns pins). Cost on a page was ~380 s with ~120 recognitions in the earlier #2861 measurement; to be re-measured on this code.

## 5. Task 3: why it is blocked as written

1. **Wrong module for the source.** `pb_plan_door_swing_geometry.iter_quarter_circle_cubics` reads vector drawings; its contract is a count that emits `D1` only for exactly one unlabeled swing, and its sole caller is the live extractor. Lot16 is picture-based, so it sees nothing there. The authenticated raster door-swing evidence lives in `PhysicalOpeningAuthority` (handover reports 7 CORROBORATED door swings among 21 Lot16 openings; not re-measured this session).
2. **No source for an area.** An area needs width and height. A swing arc radius is the leaf, not the opening (using a typical width is forbidden). The directive's per-door area implies a **2100 mm height**; `pb_door_height_owner_gate_shadow.py` names 2100 mm as non-evidence in its denylist, the levers document (section 3 item 4 and section 4) forbids a default, and the owner decision recorded against draft #4171 on 2026-11-02 was "keep abstaining" (from my lane notes; not re-read from GitHub this session).
3. **Benchmark-shaped inputs.** The directive lists per-room item names and an area value. Those are BENCHMARK facts and are not used here.

Path that would be allowed: the owner approves a documented per-project door height as an explicit `USER_APPROVED` record (source, scope, approver); then the existing issuer path consumes it. Six of the thirteen unsigned Lot16 openings still lack a host (AntiGravity and MAX functions), so even then not every door moves.

## 6. Predicted abstentions (before tests)

- Flag off: output byte-identical; Lot16 default eight and Maryborough three unchanged.
- Flag on, no OCR backend: no upgrade, typed reason.
- 71 unbound or trace-less words on the 3Laurel page stay untrusted.
- Any glyph read as two different characters: its words stay untrusted.
- A glyph appearing in fewer than two corroborated words: its words stay untrusted.
- Trusted text alone does not bind a callout: aperture containment, distance and ambiguity rules in the existing label and schedule authorities still decide; many callouts are expected to abstain.

## 7. Test matrix (written first)

Synthetic positives (fixture font with no Unicode cmap, mock OCR backend); look-alike negatives (0/O, 1/l glyph swaps, a ToUnicode that remaps a glyph); contradiction and under-support cases; translation, rotation and scale of the page; word-order and word-splitting invariance; unrelated-page and added-content invariance; deterministic replay and stable ids; no input mutation; flag-off byte-identity of receipts for existing fixtures; proof that live predictions and commercial quantities are unchanged with the flag off; real-source run on the 3Laurel original through the real consumer.

## 8. Benchmark observations that must not influence implementation

Item counts, item names, expected quantities and score figures in the directive. Nothing in this report or the proposed rules uses them; no threshold is tuned on a project.

## 9. Owner decision (resolved 2026-11-05)

Section 5 asked whether to record a `USER_APPROVED` door height. The owner answered in the session (07:10 +10:00, two choices presented):

- Height: **2100 mm**. Scope: **all Lot16 doors** (internal and external), on the Lot16 architectural plan (SHA-256 prefix `10109b4b`).
- Approver: the repository owner (account `BryceCurran86`, commit name "Bryce Curran"). The approver-name question was not answered separately; this is my reading and the owner may correct it.
- The approval is an **assumption supplied by the owner, not a measurement**. Rows that depend on it must be labelled user-approved and counted separately from source-measured rows. It is never FIRM, never a code default, and is supplied to a run as an explicit input record (never a module constant). A run given no record behaves exactly as today.

## 10. Task 3 re-scoped: the existing path and where an approved second axis can enter (OBSERVED)

- Width carrier: `OpeningLabelDimensionProducer.publish_scope` (`pb_opening_label_dimension_authority.py` L984) returns a CORROBORATED `OpeningLabelDimensionEvidence` for a single printed figure (`dimension_values_mm=(w,)`, `area_m2=None`; `_area_from_dimension_values` returns `None` unless there are exactly two figures), bound to a proven physical opening by `_label_matches_gap`.
- Area decision: `pb_live_physical_opening_void_composition._canonical_opening_area` (L253) returns an area only from complete width+height geometry, an elevation frame, a frame schedule, or a two-figure label. Nothing else.
- Issuer: `pb_live_opening_area_quantity_publication._opening_quantity` (L36) accepts exactly four `area_basis` values and returns `None` for any other; it also needs a host wall, a host-binding or frame receipt, and a door/window kind.
- Review-only precedents: `pb_nominal_opening_canonical_shadow._build_approved_single_width_review` (a `USER_APPROVED` `MeasurementRecord` with a named approver, timezone-aware time, unit mm, page and `geometry_ref` equal to the opening's record id; width only, `height_m=None`) and `pb_door_height_owner_gate_shadow.assess_door_height_owner_gate_shadow` (a bare boolean; `measurement_published=False`).
- Customer projection: `quantity_evidence_to_takeoff_output_row` always emits an unreviewed `origin: AI`, `quantity_status: To review` row carrying `quantity_authority`; an estimator review transition is required before it counts. An approved-height area is therefore a reviewable row with its basis stated, never an automatic FIRM row.

**Lot16 page 3 on `d75273eda` (gate census, SHA-verified original, counts only):** 21 physical openings, 15 hosts, 9 frames, 8 signed areas. First remaining gate across the 21: host unavailable 6, whole-wall frame unavailable 6, filling kind unproven 3, axis order unproven 5 (all five already signed), single figured dimension unproven 1. Only **one** opening has host, frame and kind all proven and is blocked first by the missing second axis. Doors that lack a host (6), a frame (3 further openings after the signed ones) or a proven kind (3) stop earlier; an approved height cannot reach them. The census gate is stricter than the issuer: three of the eight signed areas have a host but no frame, and `_opening_quantity` needs only a host binding **or** a frame receipt.

**Printed figures per opening (same page, existing `OpeningLabelDimensionProducer`, counts only):** 8 openings carry two figures (7 windows, 1 door; these are the signed eight and the approval never applies to them), 8 carry **one** figure (6 authenticated as door, 2 with no authenticated kind), 4 have no readable label text and 1 is ambiguous. Intersecting the single-figure group with the host and kind gates: **4 doors** have one printed figure, a proven host and a door kind (one of them also has a frame); 2 further single-figure doors have no host; the 2 kind-less single-figure openings have no host and no kind. The other doors have no printed width at all, and a swing-arc radius is never a width. So the approval can reach at most 4 doors today, not 9; the rest need a printed figure that the drawing does not have, or the host gate (6 openings, `pb_opening_host_binding_authority.py`, held by AntiGravity and MAX).

**Convention I am recording, not assuming silently:** a lone figure on an authenticated door is read as the door's nominal **width**, so height 2100 mm is its second axis. The label authority itself refuses to infer axis order from two figures; for one figure the width reading is part of the owner's approval and is stored in the record (`single_figure_axis=width`). If the owner means otherwise the record is wrong and must be withdrawn.

## 11. Proposed change for task 3 (shadow first, default-off)

1. `assess_owner_approved_door_area_shadow` beside the existing owner gate (same file family, no new vocabulary): inputs are the physical opening's existence record, its CORROBORATED single-figure label evidence and an explicit approval record. It returns a review dict (`basis=owner_approved_second_axis`, width from the label, height from the record, area their product, `measurement_published=False`).
2. Checks, all recomputed from sealed records and never from a replayed area: door kind authenticated (structural pattern or semantic authority, not a suffix guess); exactly one printed figure bound to this opening; no printed second axis (a two-figure label keeps the existing figured path and the approval is ignored, so the signed eight stay byte-identical); approval is `USER_APPROVED` with named approver, timezone-aware time, unit mm, finite positive value, matching document SHA-256, page and opening record id; no duplicate or conflicting approvals; no stale revision.
3. Promotion (separate commit, after the shadow run on the original): a fifth `area_basis` in `_canonical_opening_area` and `_opening_quantity` with its own authority string and metadata marking `second_axis_basis=user_approved` plus the approval id. Default off; no approval input means no change.
**Shadow run (done, commit `78b9942f8`, SHA-verified Lot16 original, page 3, counts only).** The approval record was built from the owner's decision and passed as an explicit input to the new function; nothing is hard-coded in production code. Outcome across the 21 proven openings: **6 `owner_approved_door_area_review_only`** (one printed figure, authenticated door), 8 `printed_second_axis_present` (the signed eight; the approval is ignored, as designed), 5 `label_dimension_not_corroborated` (no readable label text, or an ambiguous label), 2 `opening_kind_not_door_authenticated`. Of the 6, **4 have an authenticated host binding and 2 have none**, so only 4 can pass the issuer's host requirement; the 2 hostless ones stay with the host gate. Nothing was published and no quantity, score or customer row changed. The function's tests are 40 (written first, collection failed before the function existed), four guards were mutation-checked and each mutant was killed.

4. Predicted abstentions: no host, frame or kind receipt; no printed single figure (a swing arc radius is never a width); two-figure labels; approval not matching sha, page or opening id; window openings; a figure the semantic authority reads as a height.
5. Tests: synthetic positive; look-alike negatives (two-figure label with an approval present, window with approval, label bound to another opening); conflicting and duplicate approvals; translation, rotation, scale; order and splitting invariance; replay and stable ids; no mutation; and proof that with no approval record the Lot16 signed outputs are byte-identical.

## 12. Task 3, layer A: default-off canonical opening and issuer (done, commit `757d5a658`)

- `compose_live_physical_opening_voids` takes an explicit, default-empty `owner_approved_second_axis` (list or tuple of `MeasurementRecord`; any other type raises `TypeError` before any work). For a door that prints exactly one figure and has no other area basis, the shadow check from section 11 supplies the area. `LiveCanonicalOpeningObject` gains three optional fields (approval id, width mm, height mm) that serialise **only when set**, so every default object is byte-identical. `width_m` and `height_m` stay `None`: the approved axes never masquerade as metric axes.
- `_opening_quantity` gains a fifth area basis that recomputes the product from retained records (never a replayed area), requires the approval id and the label evidence id in the retained evidence, a door kind, and no back-filled metric axes. The quantity is `review_required`, `shadow_only=True`, `commercial_projection_allowed=False`, carries `second_axis_basis=user_approved` and the reason `owner_approved_second_axis_is_an_assumption`. The four existing bases, statuses and metadata are untouched.
- Tests: 29 new (written first; collection failed before the change), ten mutants all killed, 510 tests in the neighbouring opening, issuer, customer-filter and shadow suites pass (7 skipped, original-source gated); lint (F821, F823, F401, F841) clean; truth separation passes.
- **Real chain, Lot16 page 3, SHA-verified original, run twice on the same snapshot (without and with the approval record), counts only:** 21 canonical openings, **15 byte-identical** (the signed eight among them), **6 changed** and only in area, basis, retained evidence and the three owner fields. Published area quantities: 8 -> 12. All 8 original quantities are retained and equal. The 4 new ones are the doors with an authenticated host; the other 2 stay with the host gate. Every new quantity is `review_required`, shadow-only and not projectable. The composition status is `abstained` with and without the record (an existing upstream state, unchanged).
- Customer projection (`pb_live_opening_customer_projection._eligible_area_quantities`) accepts only `corroborated`, so these rows do not reach customer output or the seal. That is intended for this layer.

**Layer B (not started): how an owner-approved row may reach customer output.** There is a precedent for a review lineage that is not a final firm quantity: ceiling promotion (`pb_ceiling_lining_review_promotion.py`, the `source_owned_ceiling_promotion` exception in `pb_source_closed_run_export.py`, `pb_live_ceiling_source_closed_export.py`). Doors would need the same three parts: a promotion that flips only the explicit flags, a seal exception keyed on the opening-specific receipt, and a customer projection that emits the row as `To review` with its basis. It would never be FIRM or `corroborated`, and the sealed and customer bodies of the signed eight must stay identical. This touches sealed-run machinery, so it is a separate commit with its own retention proof.
