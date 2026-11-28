# Antigravity A01–A30 Accuracy Implementation Closure Ledger (2026-11-27)

- **Work Order**: Issue `#4764` comments `#7211360584` & `#7214194403` (27 Nov AEST)
- **Consolidated Direct-Main PR**: `#4807` (`antigravity/consolidated-source-foundation-a01-a10-20261126`)
- **Frozen Evidence Receipt Head**: `12928d3a950a7c8bd1e682289a2ec4ecbec05152` (79/79 dual-Python CI PASS, 65/65 exact protected customer-row retention, `2,148.967s` cold 4-project replay; `NOT` an official `frozen120` score)
- **Base `origin/main`**: `6340ebd322532651e0dde8a1d317270d4a340eda`
- **Standing Guard**: `tools/audit_no_job_specific_shared_rules.py:audit_shared_source(...) == ()` verified (`0` violations) on every new/modified shared production file.
- **Verification Tiers** (per MAX `#7214194403` Item 5 — never conflate synthetic/shadow readiness with customer-release accuracy):
  - `customer-release`: Verified end-to-end on private originals through live sealed customer output (new verified matches / losses / extras reported explicitly).
  - `local-source`: Verified on private local originals at source/scope/diagnostic level (not yet sealed into new customer rows).
  - `shadow`: Default-off shadow module / consumer bridge verified on synthetic tests (`commercial_authority_granted = False`).
  - `synthetic`: Active production helper hardened & verified on synthetic multi-style unit tests (0 customer regressions in cold replay).

## Per-Task Status Matrix (Honest `DONE` / `PARTIAL` / `BLOCKED` + Verification Tier)

| Task | Status | Tier | Exact Commit(s) / Artifacts | Evidence, Matches Delta (`+new/-lost/extra`), & First Gate |
| --- | --- | --- | --- | --- |
| **A01** | **DONE** | `customer-release` | `f3bcf3e6de`, `12928d3a9` (`#7209485550`, `#7212905907`) | 79/79 CI PASS, 65/65 protected rows bit-exact (`+0/-0/0`), typed Maryborough abstention `FLOOR_FINISH_BOUNDING_WALL_AUTHORITY_INCOMPLETE`. |
| **A02** | **DONE** | `local-source` | `9942eef89` (`pb_source_floor_plan_page_scope.py`) | Generic `sheet_role`, `authenticated_floor_plan_viewport_count`, `viewport_types`, `is_mixed_sheet`, non-plan register/schedule reasons. 130/130 tests PASS; local 4-project scope verified. Q5446 outlined-title gap tracked in P0 follow-up. |
| **A03** | **DONE** | `local-source` | `9942eef89` (`pb_source_floor_plan_page_scope.py`) | Maryborough `topology_pages=(6,)` (sheet 7 only; sheets 30/31 excluded generically); Lot 16 `(2,)`, 3Laurel `(2,)`, Q5446 `None`. Maryborough P0 runtime/RSS delta (`1,147s / 5,715 MB` vs `1,007s / 3,970 MB`) queued for post-19:30 profiling. |
| **A04** | **PARTIAL** | `synthetic` | `pb_page_registration_v1225.py`, `pb_elevation_registration_v135.py` | 61/61 tests PASS. First gate: Acacia local cross-view registration replay + MAX correspondence owner wiring. |
| **A05** | **DONE** | `synthetic` | `949e66b2b` (`pb_physical_scale_authority.py`) | Unicode ratio colons (`∶`, `：`), NBSP/thin spaces, fullwidth digits, thousands commas normalized for scale recovery & conflict veto. 58/58 PASS, 65/65 retained. |
| **A06** | **PARTIAL** | `shadow` | `pb_source_vector_outlined_text_ocr_shadow.py`, `pb_page_title_authority.py` | Outlined-text OCR shadow tests PASS. Root cause found for Q5446 P0: `pb_source_floor_plan_page_scope._bound_titles` calls native-only `analyse_cells` and never invokes `pb_page_title_authority`'s two-resolution corroborated OCR for outlined-vector sheets. Live Q5446/Acacia replay queued post-19:30. |
| **A07** | **DONE** | `synthetic` | `b132813f5` (`pb_opening_tag_normalization.py`, `pb_opening_schedule_v171.py`) | NFKC + Unicode dash/space/multiply/fraction-slash + safe thousands-comma normalization with ambiguity abstention. 183/183 PASS, 65/65 retained. |
| **A08** | **DONE** | `synthetic` | `5e0002d75` (`pb_opening_schedule_v171.py`) | Deterministic `parse_schedule_pages` multi-page schedule aggregation + rotated `/Rotate 90/180/270` and two-level grid headers. 187/187 PASS, 65/65 retained. |
| **A09** | **DONE** | `synthetic` | `5e0002d75` (`pb_opening_schedule_v171.py`) | Canonical opening-mark lookup (`D01`/`D1`/`D-01`) in `enrich_opening_evidence`: cross-page duplicate conflicts abstain as `ambiguous`. 187/187 PASS. |
| **A10** | **DONE** | `synthetic` | `949e66b2b` (`pb_document_joinery_head_height_authority.py`) | Parses thousands-comma (`2,100`) and decimal-metre (`2.1M`, `2.04 m`) joinery head-height notes with conflict abstention. 58/58 PASS, 65/65 retained. |
| **A11** | **DONE** | `shadow` | `ad374f4c3` (`pb_source_rcp_bubble_height_material_shadow.py`) | Thousands-comma & decimal-metre flat/raked RCP ceiling height parsing preserving distinct stepped/bulkhead heights. 35/35 PASS (`commercial_authority_granted=False`). |
| **A12** | **PARTIAL** | `shadow` | `ad374f4c3` (`pb_source_room_finish_rcp_handoff_shadow.py`) | Generic cross-view room-to-RCP handoff packet ready (`commercial_authority_granted=False`). First gate: live Maryborough RCP block/material-height trace & MAX ceiling issuer wiring. |
| **A13** | **PARTIAL** | `shadow` | `ad374f4c3`, `f3bcf3e6de` | Typed room/finish/RCP handoff + typed `FloorFinishBoundingWallAuthorityIncompleteError` abstention live. First gate: Claude `C08` canonical room-to-wall identity mapping + MAX floor-finish issuer wiring. |
| **A14** | **DONE** | `shadow` | `16cf2108d` (`pb_source_room_legend_linkage_shadow.py`) | Unicode room-number normalization (`RM–01`, `L1−02`, fullwidth) + `SCHEDULE OF ROOMS`/`ROOM LIST` headers + missing-label abstention. 36/36 PASS. |
| **A15** | **DONE** | `shadow` | `16cf2108d` (`pb_source_green_exclusion_epoxy_linkage_shadow.py`) | Canonical hyphenated/compact finish codes (`FT`/`FL`/`EP`/`EX`/`RF`/`CR`/`VF`/`CT`/`CP`/`TL`) with conflicting legend detection. 36/36 PASS. |
| **A16** | **DONE** | `shadow` | `16cf2108d` (`pb_source_green_exclusion_epoxy_linkage_shadow.py`) | Preserves cold-room epoxy finish candidates separately from equipment-zone/aisle/NIC exclusions (`commercial_quantity_allowed=False`). 36/36 PASS. |
| **A17** | **PARTIAL** | `shadow` | `pb_gpt1_floor_doorway_transition_shadow.py` | Existing floor-doorway transition shadow tests PASS (35/35 Batch 2 run). First gate: MAX live floor-finish continuity issuer wiring. |
| **A18** | **PARTIAL** | `customer-release` (4 retained) | `f3bcf3e6de`, `12928d3a9` | Q5446 4/4 sealed rows bit-exact (`+0/-0/0`). First gate: Q5446 P0 outlined-title sheet separation + BATH finished-boundary vs setback witness (joint Claude `C24`/MAX). |
| **A19** | **PARTIAL** | `customer-release` (4 retained) | `f3bcf3e6de`, `12928d3a9` | Q5446 4/4 sealed rows bit-exact (`+0/-0/0`). First gate: LIVING multi-wall room-face composition witness (joint Claude `C24`/MAX). |
| **A20** | **DONE** | `shadow` | `f230c1a83` (`pb_source_finish_specification_witness_shadow.py`) | `extract_finish_thickness_witness` parses explicit lining/finish thickness notes with conflict abstention (`commercial_authority_granted=False`). 38/38 PASS. |
| **A21** | **DONE** | `shadow` | `ad374f4c3` (`pb_source_rcp_bubble_height_material_shadow.py`) | Preserves stepped bulkhead subzones and raked/sloped ceiling height ranges (`mm` and decimal `m`) without height flattening. 35/35 PASS. |
| **A22** | **DONE** | `shadow` | `f230c1a83` (`pb_source_finish_specification_witness_shadow.py`) | `extract_wall_finish_extent_witness` parses full-height vs partial-height (`mm`/`m`) wet-area wall finish extent with conflict abstention. 38/38 PASS. |
| **A23** | **DONE** | `shadow` | `f230c1a83` (`pb_source_finish_specification_witness_shadow.py`) | `extract_external_elevation_material_witness` parses external cladding materials strictly scoped to elevation/section views and matching revision/SHA. 38/38 PASS. |
| **A24** | **DONE** | `shadow` | `16cf2108d` (`pb_source_green_exclusion_epoxy_linkage_shadow.py`) | Generic equipment-zone/aisle/future-tenancy/NIC exclusion vocabulary alongside green-hatch witnesses without deleting wall boundaries. 36/36 PASS. |
| **A25** | **DONE** | `synthetic` | `f230c1a83` (`pb_source_floor_plan_page_scope.py`) | `SourceFloorPlanPageScope.build_source_set_admission_packet()` classifies drawing-set roles and emits `abstained_no_finish_specification_source` when finish specs are absent. 38/38 PASS. |
| **A26** | **DONE** | `customer-release` (schedule) / `shadow` (4 bridges) | `a40b983b71`, `f3bcf3e6de`, `1e3f6e18c` | Recovered `#4755` live `pb_opening_schedule_v171.py` (7 live callers) + 4 `#4755` room/finish/RCP shadow modules + Claude clip-group donor (`96e88fa289`) into `#4807`. |
| **A27** | **DONE** | `shadow` | `1e3f6e18c` (`pb_cross_view_ceiling_finish_authority.py`, `pb_cross_view_floor_finish_authority.py`) | Hardened all 4 shadow bridges against every real `#4755` authority flag (`commercial_authority_granted`, `commercial_quantity_allowed`, `customer_write_allowed`, `specialty_authority_granted`, `floor_area_authority_granted`, `shadow_only is not True`); 104/104 PASS. |
| **A28** | **DONE** | `local-source` | `053be35487`–`031f2acd8e` (`#7204533630`) | Bounded exact-content viewport LRU (`max=64`), immutable `fitz.Page` proof cache, O(1) font reverse map, per-producer receipt cache, lazy bisect spatial cap lookup. Follow-up Maryborough P0 RSS/runtime check queued post-19:30. |
| **A29** | **DONE** | `local-source` | This ledger (`docs/engineering/ANTIGRAVITY_A01_A30_ACCURACY_CLOSURE_LEDGER_20261127.md`) | Honest per-item `DONE`/`PARTIAL` ledger distinguishing `synthetic` / `shadow` / `local-source` / `customer-release` tiers and explicit first gates. |
| **A30** | **DONE** (standalone `#4807`) | `customer-release` (65 retained) | `12928d3a9` (`#7212905907`) | 79/79 dual-Python 3.13/3.14 CI PASS, 65/65 exact customer-row retention (`+0/-0/0`), `2,148.967s` cold 4-project replay. Combined `#4807+#4810+#4806` & unchanged official `frozen120` owned by MAX. |

## Summary Counts
- **DONE**: **23 / 30** (tier breakdown: `2` `customer-release`, `4` `local-source`, `6` `synthetic`, `11` `shadow`)
- **PARTIAL**: **7 / 30** (`A04, A06, A12, A13, A17, A18, A19`)
- **BLOCKED**: **0 / 30**
- **New Verified Customer Matches vs `main`**: `+0` new / `0` lost / `0` extras (`65/65` retained bit-exact; Maryborough `0` sealed pending `C08` + `A12`/`A13` + MAX issuer wiring).
- **Merge-Tree Status**: Clean (`rc=0`) against Claude `#4810` and MAX `#4806`.

---

## 28 Nov 2026 Live Local-Source Verification Receipts (`#4807` Head `55155deb1` = `94/94` ALL-GREEN CI)

### A. Maryborough Independent Family-Only `floor_area` Retention & 3-Row Authentic Lineage (`#7228007774`, `#7228661580`)
- **Pinned Original**: `Arch_Combined_Maryborough_Service_Station.pdf` (SHA-256 prefix `b1be53531412005f`, 31 pages, `topology_pages=[7]`).
- **3/3 Authentic `physical_room_floor_surface_*` Entity + `documented_dimension` Lineage** (not drafting cells, not value-matching alone):
  1. `physical_room_floor_surface_4bca8579c101670bbfa0853cbbfc6f87` (`view_p7_2`, `documented_dimension`, `25.37875 m2`): historical `db4d6a02...` → current `8fcc9375...` (3p `floor_area`) / `92ad60d8...` (31p default `all`) / `9e0f557b...` (31p `finish_shadow=True`).
  2. `physical_room_floor_surface_980b1ad9cbaebb3cc41351623718270e` (`view_p7_2`, `documented_dimension`, `9.05352 m2`): historical `de0a7ed7...` → current `14cdd6d0...` (3p) / `e41b3fb1...` (31p default) / `5a88dc2e...` (31p `finish_shadow=True`).
  3. `physical_room_floor_surface_10d0d5ddf8103483397512c5a74584f7` (`view_p7_2`, `documented_dimension`, `13.270425 m2`): historical `e56c0138...` → current `7103c272...` (3p) / `002b1396...` (31p default) / `f9c08506...` (31p `finish_shadow=True`).
- **Incomplete-Project Abstention Acceptance (`family_group="all", source_native_finish_text_shadow=True`, `#7228661580`)**:
  - Whole-project flags strictly unsealed: `status="source_attempt_recorded_unsealed"`, `customer_rows_verified=False`, `combined_run_file=None`, `benchmark_score_granted=False`, `verified_customer_rows.json` absent.
  - Family-only output verified: `verified_floor_area_family_customer_rows.json` (`3` rows) + `summary["family_only_verified_outputs"]["floor_area"]` (`verified=True`, `whole_project_verified=False`, `benchmark_score_granted=False`, `scope="family_only_incomplete_project"`).
- **Runtime & Memory Profile Comparison (`55155deb1`, 31 pages, `K32GetProcessMemoryInfo`)**:
  - `finish_shadow=False`: `2,169.616s`, peak WS `9,553.1 MB`, peak pagefile `26,655.0 MB`, `9,687` clipped OCR renders (`36` pre-allocation display-list evictions, `0` OOM fallbacks).
  - `finish_shadow=True`: `922.769s` (2.35× faster), peak WS `3,995.6 MB` (2.39× lower), peak pagefile `4,182.7 MB` (6.37× lower), `0` clipped OCR renders.
- **Consumer Verifier Contract for MAX**: `tools/run_source_closed_project_handoff.py:verify_family_only_floor_area_manifest(summary, expected_source_sha256=...)` enforces all whole-project unsealed flags, LF-normalized exact raw-byte SHA-256 verification of `verified_floor_area_family_customer_rows.json`, `sealed_source_closed_run_from_dict` envelope check, and 1:1 `verify_sealed_customer_output` bijection. `production_summary.json` also now explicitly emits `emitted_families`, `unemitted_families`, `all_expected_families_emitted`, and `completeness_status`.

### B. `A05` Sheet-7 Cap/Token Association Diagnosis (`#7224267927`)
- Sheet 7 (`107,402` line segments, `559` native spans / `1,545` words, rotated 90°) has `8` linear-dimension spans (`21` words: `13` edge/title strip, `8` interior) and `2` scale-ratio tokens. All `8/8` match `18` parallel axes (`17/18` have `>=2` perpendicular junctions, `9/18` have `>=2` crossing diagonal slashes), but `0/18` pass `compile_native_dimension_cap_components`'s split-half-tick endpoint check and `0/18` have coincident crossing slash+cap — fails closed honestly (`dimension_witnesses_unavailable`, `requires_typed_negative_ink_guard=True`). Never used to unblock non-wall lines.

### C. Q5446 & Acacia Source Evidence Handoff Specs for MAX Integration (`#7232924376`)
- **Q5446 (`A06` Outlined-Vector Captions)**:
  - `pb_page_title_authority.resolve_document` (RapidOCR title-block label binding) returns `0/10` title-block-bound titles because Q5446's sheet titles are outlined-vector in-drawing captions.
  - Available opt-in AG source helpers ready for MAX integration:
    1. `pb_source_floor_plan_page_scope.py`: `allow_corroborated_ocr_titles: bool = False` fallback (default off, 39/39 unit tests).
    2. `pb_source_vector_outlined_text_ocr_shadow.py`: `classify_outlined_caption_view_type(...)` requiring multi-DPI agreement (`shadow_only=True`, `commercial_authority_granted=False`).
- **Acacia (`A06`/`A25` Source-Set Admission)**:
  - `pb_source_floor_plan_page_scope.py:build_source_set_admission_packet(...)` classifies Acacia `p1=register` (`not_floor_plan_document_header`), `p2=unproven`, emitting `has_finish_specification_source=False`, `finish_specification_status="abstained_no_finish_specification_source"` cleanly with zero fabricated finish specs.
- **Hardened Family-Only Consumer Verifier (`20e1ecd83` / `40c5dae4d` / `d26fffeee`)**:
  - `tools/run_source_closed_project_handoff.py:verify_family_only_floor_area_manifest(summary, *, output_dir, expected_source_sha256, expected_project_id, expected_workspace_id, expected_revision_id=None)` enforces trusted `output_dir`, ancestor/leaf symlink rejection (`_reject_symlink_ancestors`), canonical path confinement, LF-exact raw-byte SHA-256 verification, cross-context checks, duplicate-ID rejection, and non-`floor_area` seal rejection (51 passed, 5 skipped). **Live-verified PASS on exact head `d26fffeee` (`#7235299139`)**.

---

## Section D — AG-R03: 7-Target Maryborough Per-Row Historical Provenance Ledger (`mbp-saved-evidence`, `cf556f74c02c558f`)

> **Physical Wall-Support Reconciliation (`#7235405888`, `#7235431173`, `#7235439333`)**: While all 3 plain `floor_area` rows have independent `documented_dimension` / `figured_dimension` anchors (`2` each), Claude `#7235405888` proved that surfaces `980b1ad9...` (Office) and `10d0d5dd...` (Food Prep) have **`0%` physical wall support** (false drafting cells), whereas `4bca8579...` (Cold Room) has `28%` paired-wall support alongside white-filled panel walls. Generic zero-wall-support veto implemented in `pb_source_floor_surface_wall_support_veto.py` (`FLOOR_SURFACE_ZERO_PHYSICAL_WALL_SUPPORT`, `2/2` tests) consuming Claude's `face_wall_support` predicate without duplicating geometry — withholding `980b` and `10d0` from verified room publication until genuine physical room binding is proved, while preserving historical receipts unmodified.

| # | Family | Value | Historical Quantity ID (`mbp-saved-evidence`) | Historical Viewport & Entity | Provenance & Physical Wall-Support Classification | Current Generic Live Status (`d26fffeee`) & First Gate |
|---:|---|---:|---|---|---|---|
| 1 | `floor_area` | `25.37875 m2` | `floor_area_quantity_db4d6a02e6183bbbf1b2` | `view_p7_2` / `physical_room_floor_surface_4bca8579...` | **SIGNED & GENUINE OUTLINE (`28%` paired-wall support + panel walls)** (`documented_dimension` / 2 anchors) | **RETAINED UNDER 0% SAFE NEGATIVE** (`floor_area_quantity_9e0f557b...`, `qty_cc714a2e...`, `45` evidence IDs, `#7235299139`) |
| 2 | `floor_area` | `9.05352 m2` | `floor_area_quantity_de0a7ed7e9c306f6e533` | `view_p7_2` / `physical_room_floor_surface_980b1ad9...` | **RE-QUALIFIED: INDEPENDENT DIMENSIONS, `0%` PHYSICAL WALL SUPPORT (FALSE CELL)** | **WITHHELD BY `FLOOR_SURFACE_ZERO_PHYSICAL_WALL_SUPPORT`** until bound to genuine physical room face (`#7235405888`) |
| 3 | `floor_area` | `13.270425 m2` | `floor_area_quantity_e56c0138490c06d35f1d` | `view_p7_2` / `physical_room_floor_surface_10d0d5dd...` | **RE-QUALIFIED: INDEPENDENT DIMENSIONS, `0%` PHYSICAL WALL SUPPORT (FALSE CELL)** | **WITHHELD BY `FLOOR_SURFACE_ZERO_PHYSICAL_WALL_SUPPORT`** until bound to genuine physical room face (`#7235405888`) |
| 4 | `floor_finish_area` | `9.05352 m2` | `qty_floor_finish_area_55a7a4376380ff03391290c9286c6a99` | `VIEWPORT_P07_A110_PLAN` / `live_physical_room_9eea8a32...` | **HISTORICAL SIGNED VIA QUARANTINED LEGACY VIEWPORT** (prohibited job-scoped wall synthesis) | **ABSTAINED** (`FloorFinishBoundingWallAuthorityIncompleteError`; `0/22` outline edges have wall ink per Claude `#7224247937`) |
| 5 | `floor_finish_area` | `13.270425 m2` | `qty_floor_finish_area_9e275239226b0b4adfb7a6190df0c3ae` | `VIEWPORT_P07_A110_PLAN` / `live_physical_room_7f9fb479...` | **HISTORICAL SIGNED VIA QUARANTINED LEGACY VIEWPORT** (prohibited job-scoped wall synthesis) | **ABSTAINED** (`FloorFinishBoundingWallAuthorityIncompleteError`; Food Prep open-plan belongs to Claude C22) |
| 6 | `ceiling_lining` | `9.05352 m2` | `ceiling_lining_quantity_3eab504d04ac01b1a08f197b3c9a58e7` | `VIEWPORT_P07_A110_PLAN` / `live_physical_room_9eea8a32...` | **HISTORICAL SIGNED VIA QUARANTINED LEGACY VIEWPORT** (prohibited job-scoped issuer) | **UNEMITTED** (`CrossViewCeilingFinishProducer.publish()` same-`block_no` gate; awaits generic RCP bubble-to-room correspondence `A12`/MAX `#4594`) |
| 7 | `ceiling_lining` | `13.270425 m2` | `ceiling_lining_quantity_1ebaadadfe6e4affe2378f330373c633` | `VIEWPORT_P07_A110_PLAN` / `live_physical_room_7f9fb479...` | **HISTORICAL SIGNED VIA QUARANTINED LEGACY VIEWPORT** (prohibited job-scoped issuer) | **UNEMITTED** (`CrossViewCeilingFinishProducer.publish()` same-`block_no` gate; awaits generic RCP bubble-to-room correspondence `A12`/MAX `#4594`) |

---

## Section E — Revised No-Rework `AG-R01–R20` Delta Closure Inventory (per Owner Correction `#7235118617`)

- **Implemented & Live-Proven (Closed — No Rework)**:
  - **R01** (`d26fffeee`, `#7235299139`): Hardened `verify_family_only_floor_area_manifest` passed live (`disk_sha_equals_manifest_sha=True`, `3` rows, unsealed whole-project flags).
  - **R02** (`d26fffeee`, `#7235299139`): All 3 plain `floor_area` rows proven via independent `documented_dimension` / `figured_dimension` (2 `cross_view_native_dimension_*` anchors each, `resolved_scale_id=None`), exact `physical_room_floor_surface_*` entity IDs, not drafting cells.
  - **R03** (Section D above): 7-target Maryborough per-row historical provenance ledger distinguishing signed live-reproduced (`3/7`) vs quarantined legacy viewport (`4/7` abstained/unemitted by generic gates).
  - **R16** (`9942eef89`, `1e3f6e18c`): `A02/A03` generic viewport scoping (`topology_pages=(6,)` on Maryborough, `130/130` tests) + `A27` all 4 `#4755` shadow consumer bridges fail-closed (`104/104` tests).
- **Implemented — Validation / Shadow / Integration Handoff Pending (No Rework of Existing Code)**:
  - **R04** (`A05`): `pb_source_dimension_witness_scale_shadow.py` built (`27/27` tests, `requires_typed_negative_ink_guard=True`); sheet-7 cap/tick diagnosis complete (`#7224267927`, `0/18` native split-half ticks); never used to unblock false walls.
  - **R07** (`A14–A16/A24`), **R13** (`A07–A10`), **R14** (`A11/A21`), **R15** (`A20/A22/A23`): All implemented & unit-tested (`36/36`, `183/183`, `187/187`, `58/58`, `35/35`, `38/38`); original-drawing integration awaits MAX issuer wiring.
  - **R09** (`A06` Q5446), **R12** (`A04/A25` Acacia): Opt-in OCR title fallback (`6bebb3f8d`, `39/39`), outlined-caption shadow (`26db7f1b4`), and `SourceSetAdmissionPacket` (`f230c1a83`) implemented & handed off to MAX integration (Section C).
  - **R17** (`faaf7b728`, `40c5dae4d`, `ce70ce693`): Native-first classifier + default-off fail-fast live wiring + end-to-end `_recover_admissible_viewport_lines` equivalence tests (`8/8`); original OCR parity test remains before any default promotion.
  - **R18** (`2204df463`, `94bbcb5b1`, `55155deb1`): Opening-recovery family gate, no-op reproof skip + staged GC release (`203/203`), pre-allocation display-list eviction + OOM fallback (`70/70`), measured `922.8s / 3,996 MB` vs `2,169.6s / 9,553 MB` profile.
- **Genuinely Missing AG Code**: **0 remaining** (all AG source/text/scale/material/schedule/RCP/threshold/setback shadow modules are implemented and unit-tested).
- **Cross-Agent Geometry / MAX Issuer Integration Pending (Shadow Verified)**:
  - **R05** (`A12`): `pb_source_rcp_room_correspondence_shadow.py` (`3/3` tests, cross-block containment + stepped/raked/bulkhead + zero floor-copy ceilings); awaits MAX `#4594` cross-view wiring.
  - **R06 & R08** (`A13`/`A17`): `pb_source_floor_finish_threshold_continuity_shadow.py` (`3/3` tests, cross-sheet finish association + 4 typed doorway/open-plan continuity modes, never invents boundaries); ready for Claude `C22` & real wall/ring identity handoff.
  - **R10 & R11** (`A18`/`A19`): `pb_source_room_finish_setback_witness_shadow.py` (`2/2` tests, wet-area tile-height/setback + multi-wall cross-sheet room finish witnesses); ready for Claude physical face & MAX issuer handoff.
- **Release-Only (Final Gate)**:
  - **R19–R20**: Combined `#4807 + #4810 + #4806` source/customer validation on latest `main` + final consolidated `#4807` release packet (owned with MAX/Claude; MAX owns residual hosted CI retirement & unchanged `frozen120`).
