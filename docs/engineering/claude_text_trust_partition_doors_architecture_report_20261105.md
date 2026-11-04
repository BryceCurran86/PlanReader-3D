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

## 9. Open decision for the owner

Whether to record a `USER_APPROVED` door height for a named scope (section 5). Until then door areas abstain.
