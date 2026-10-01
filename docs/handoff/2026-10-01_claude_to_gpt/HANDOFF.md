# Handoff: Claude -> GPT (2026-10-01). Read this first.

Written because Claude's credit ran out mid-task. Everything below is either committed in this folder or reproducible from it.
The source PDFs (user uploads) are NOT in the repo and were only in Claude's container under `/root/.claude/uploads/<session>/` - **ask the user to re-upload them.**
Hashes (all verified against the V2 source manifests in #1149 where listed):

| file | sha256 |
|---|---|
| Arch_Combined_Maryborough_Service_Station.pdf (31 pp) | `b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007` |
| Q5446_Standard_Plans_V1_20220320.pdf (10 pp) | `5f29aa0122d72e2cc8886b3f19239ff32865c8d705eee99f785c389ca27fb7f0` |
| 1._Construction_Plans_-_Lot_16_Power_REV_E.pdf (13 pp) | `10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844` |
| 4._Structural_Engineering_-_Lot_16_Power.pdf (11 pp) | `b40259589dd39a46e45d25e145cfa789d9a9415b50613ebc4fee01dceab6b3d6` |
| 3LAUREL_-_Construction_Plan_Set_Rev3_08.05.26.pdf (18 pp) | `014e9f68b377bef4fb556de61b83a94388792dfa4bfb8ea981644f9c323e9e2e` |

Standing rules (AGENTS.md + user): shadow only; no production change; never mix production code and benchmark-defining files in one PR;
do not touch `benchmarks/frozen_holdout/tenders_ke_olv_laboratory_complex` (the sealed holdout); do not use PlanReader output as truth; do not merge #1143 or the benchmark PR.

---------------------------------------------------------------------------------------------------------------------------------

## LANE 1: PR #1143 (page-frame shadow descriptor), branch `claude/page-frame-shadow-v1`

**Head now: `cd44926ede56d720e071461bcbd901772603ac7f`** (base `48034e66`; previous head `d389ae5b`). Draft PR https://github.com/BryceCurran86/PlanReader-3D/pull/1143 . Not merged; stop at merge-ready.

Done by Claude on this lane
- Pushed one commit (fast-forward) fixing the **stale-snapshot bug** in `scripts/page_frame_wall_boundary_shadow_diff.py` plus 4 stub fixtures in the hardening tests and a NEW test file
  `tests/test_page_frame_wall_boundary_shadow_diff_snapshot_v1.py` (14 tests). Schema 1.0.0 -> 1.1.0 (additive).
- Bug: `_page_report` selected the wall scope with the ingest-time snapshot id; `PhysicalWallCandidateProducer.from_source_visibility_producer` runs
  `augment_with_raster_visible_segments`, which publishes a NEWER snapshot, so `resolve_scope` returned `physical_wall_candidate_scope_unavailable` with 0 walls while
  `pipeline_status` stayed `ok` and `cross_check` stayed `match` (silent false negative). Fix: re-read `src.published_snapshot_for_revision(revision_id)` per page (fail closed on missing /
  ownership-mismatched snapshot); a scope that is not `physical_wall_candidate_scope_resolved` => `pipeline_status="scope_unresolved"`, `comparison_valid=false`, `cross_check="not_run"`, no walls.
  New report fields: `snapshot_id_at_ingest`, `snapshot_id_consumed`, `snapshot_refreshed`, `scope_resolution_status`, `comparison_valid`; top level `unresolved_pages`.
  `label_page_report` / `rotation_equivalence` now refuse invalid comparisons; CLI prints a stderr warning (exit code still 0).
- Proof on a raster-only synthetic page (real augmentation, no mocks): original script -> `ok/match/0 walls/scope_unavailable`; patched -> 10 walls resolved (rot 0 and 90).
- Local verification at push time: all 5 page-frame test files **396 passed** (382 + 14) on Python 3.13.14 / PyMuPDF 1.28.0; `py_compile`, `ruff --select F` clean;
  `check_benchmark_gold_separation.py` (CI-style, paths on stdin) passed; `check_provider_gold_isolation.py` rc 0; frozen-holdout integrity passed.
- Hosted CI on `cd44926` was RUNNING at handoff (fastpath 3.13/3.14 green; `test (3.13/3.14)` and `kstvet-wall-authority-shadow` in progress). **Check it first.** Claude was subscribed to PR activity; that subscription dies with the session.

Still to do on lane 1
1. Check hosted CI on `cd44926`; if red, root-cause (do not skip/disable tests; one re-run only if the failure is clearly not the PR's).
2. The PR body still says "8 new files / head d389ae5b / 382 passed". Update: now 9 new files vs main, head `cd44926`, 396 tests, add the stale-snapshot fix + schema 1.1.0 note. (Claude did not edit the body.)
3. ChatGPT-owned items NOT done by Claude (verify whether you did them): page-selection silently drops out-of-range pages (`--pages 999` -> `pages: []`, exit 0); the `label_page_report` docstring says 1e-3 is "about 30 float32 ulp" but measured 16.4 ulp at A4 and 4.1 ulp at 2384 pt;
   possible crash path: the dangling-end `RuntimeError` and `describe_page_frame` sit outside the try/except meant to "report, never raise" (read, not executed); docs `docs/rotated_sheet_page_frame_architecture_report.md` lines 12/145/161 still call #1137 "NOT present / UNVERIFIED" and Q6 open - #1137 merged (d3e93fb), the PR comment also says "unmerged".
4. #1143 is behind `main` (base 48034e66; main moved on, no file overlap; scratch merge was clean). Do not rebase/force-push; merge main only if required.
5. Real-source Q7 evidence (details in `Q7_real_source_report.md` and `Q7_patched_rerun_table.txt` in this folder):
   - Census of 5 user plan sets (83 pages): the ONLY rotated source is Maryborough, pages 1-29 own `/Rotate 90` (MediaBox 1684x2384 -> displayed 2384x1684), pages 30-31 `/Rotate 0`. **No real /Rotate 180 or 270 exists anywhere.**
   - Descriptor on all 83 real pages: status `raw`, no reason codes. On the 29 real rot-90 pages: 0 of 1,015,790 vertices outside the declared native extent (34.7 % outside the display extent); descriptor mapping = MuPDF `rotation_matrix`, pixel-index agreement 100 % (max delta 0 px).
   - Patched-script shadow comparison on bounded page subsets (same document id `real-q7-maryborough`), 20 of 29 rotated pages + the 2 rot-0 controls: 0 pipeline errors, 0 cross-check mismatches, 0 divergences, **0 dangling ends at a page edge in either frame => the boundary predicate was NOT exercised; zero divergence is vacuous.**
     Source pages 4-12 (densest, incl. page 7 with 109k drawings) were NOT run (ingest cost). Full 31-page ingest is infeasible (OOM-killed at 12.9 GB).
   - **Q7 stays OPEN:** need real 180 and 270 sources, and a real page that actually has page-edge wall ends.

Separate follow-ups the user asked to keep OUT of #1143 (record as their own issues/docs)
- **Mixed coordinate frames (existing pipeline).** On real rot-90 page 1: 224 vector segments (`d#i#`) span x<=1649, y<=2333 (native frame) while 1,940 `raster_segment` lines span x<=2323, y<=1649 (the displayed 2384x1684 frame);
  both feed one wall graph. 25 of 143,206 wall ends (0.02 %) lie outside the native extent (pages 1, 14, 21, 22; page 1 explained by raster segments, others consistent but not individually verified);
  55,140 (38.5 %) lie outside the rotated `page.rect` the existing consumer uses. Likely cause: `SourceVisibilityProducer.augment_with_raster_visible_segments` renders the page in DISPLAYED orientation and stores `geometry_pt` in the same space as native vector segments
  (see `pb_source_visibility_authority.py` ~1010-1100) - a hypothesis, not verified. Needs its own architecture/diagnostic PR (relates to AI playbook priority 1, lossless primitive provenance). Do NOT fix inside #1143.
- **document_id dependence (existing code).** Same bytes, rot-90 page 1 of the rotB subset gave 1796 / 1797 / 1799 walls under three different document ids; repeat runs with the same id and different PYTHONHASHSEED gave identical counts. Cause not investigated. Keep separate.
- **Ingest cost.** `SourceVisibilityProducer.ingest_native_pdf_bytes` re-runs the page per word (`get_bboxlog` in `_exact_fill_stroke_overprint_pair`): minutes per dense A1 page, GBs of RAM.

Tools for lane 1 are in `benchmarks/truth_tools/q7_page_frame/` (scratch-quality, read-only; they import the PR's script from a worktree path - adjust `repo`). `q7_rerun.py <repo> <pdf> <doc_id> <out.json>` calls the patched `run_shadow_diff`; `q7_table.py <dir>` tabulates.

---------------------------------------------------------------------------------------------------------------------------------

## LANE 2: V2 benchmark truth packages for Maryborough and Q5446 (ChatGPT owns #1149, Lot 16, 3LAUREL and the final run)

Branch for this lane: base on `origin/benchmark/full-takeoff-v2-impl` (#1149 head `f70aa3db`), files only under
`benchmarks/frozen_holdout/full_plan_v2/projects/au_qld_maryborough_service_station/` and `.../au_qld_q5446_armstrong32_harlequin/` (that is the V2 suite directory, NOT the sealed OLV holdout project).
Open the PR as a draft stacked on #1149's branch. Do not merge it.

**User decision recorded (AskUserQuestion): scope = "Verified-only core".** Ship only items verified by two independent routes; put geometric room / wall / ceiling surface candidates in a separate UNVERIFIED file; both projects stay `INCOMPLETE` with precise reason codes; never a false VERIFIED.

What the V2 contract in #1149 requires (read from `evaluator.py`, `manifest_io.py`, tests)
- Item fields: `item_id, description, trade_category (lower-cased), unit (lower-cased), expected_quantity (>=0), tolerance_policy_id, tolerance_fraction, expected_object_refs, source_document_refs, source_location_refs, denominator_eligible, verification_status`.
- Tolerance policy already defined by V2: `tolerance_policy_id = "relative-tolerance-v1"`, `tolerance_fraction = 0.05`. Use exactly that.
- `verification_status` must be `VERIFIED` for EVERY item (even non-denominator ones) - unverified candidates cannot live in `source_manifest.json`.
- Denominator-eligible items need non-empty refs, source documents and source locations. `source_document_refs` must be NAMES of entries in `reference_takeoff_documents`.
  So a hashed reference-takeoff document authored by us (e.g. `reference_takeoff.json`: name, role, sha256, size_bytes) must be listed in `reference_takeoff_documents`.
- Denominator uniqueness key = (trade_category, unit, expected_object_refs). Matching is `set(produced.object_refs) == set(expected_object_refs)` plus equal trade and unit => PARTIAL/MISSED otherwise. So refs must be the EXACT physical object set; ChatGPT's reconciliation maps them to production ids.
- `VERIFIED` project needs `source_package_complete`, non-empty source docs AND reference docs AND items. Non-VERIFIED needs `reason_codes`.
- Production quantity families that exist (semantic keys): `room_area:`, `wall_length:`, `wall_gross_area:`, `wall_net_area:`, `wall_height:`, ceiling lining, schedule-row quantities, opening counts. The adapter attaches `quantity_family` but NO `trade` field to rows (`pb_quantity_takeoff_adapter.py`); the trade->category mapping on the produced side is ChatGPT's call. Suggest keeping a human trade (painting/doors/windows) AND the production family token in each item.
- #1149 test `test_all_four_configured_projects_are_source_complete_but_not_falsely_verified` asserts all four manifests are INCOMPLETE with reason `reference_takeoff_not_supplied`; it must be updated when a project gains reference documents.
- Separation gate: benchmark-defining names are `source_manifest.json, manifest.json, tolerances.json, benchmark_rules.json, .holdout_lock.json, expected_*.json` under `benchmarks/{public_tenders,plans,frozen_holdout}/`; any `.py/.js/.html` outside `tests/` and `benchmarks/` is production. Tools under `benchmarks/` are fine.

### Maryborough Service Station (Verve, sheets A000-A610, 22 Enterprise Cct, Maryborough W.; 29 pages /Rotate 90)
Has real text layers and schedules. **Verified now (two routes):**
- Doors: A600 schedule D01-D28 (28 rows, transcribed in `data/maryborough_door_schedule.json`) vs tag census on the A110 floor plan (`data/maryborough_tag_census.json`): exactly 28 distinct tags D01..D28, each once, none missing/extra. Classes: 11 painted solid-core flush doors finish IPF3 (D03, D07-D15, D28), 3 Laminex partition doors (D04-D06), 2 aluminium glazed doors (D01, D02), 2 coolroom-contractor doors (D16, D17), 10 lessee shelving doors (D18-D27) = 28.
  Proposed lines: IPF3 painted doors count = 11 nr; IPF3 leaf area one face = 20.2368 m2 (9 x 0.92x2.04 + 2 x 0.82x2.04); partition doors 3 nr; aluminium glazed 2 nr;
  D16/D17 and D18-D27 as `denominator_eligible=false` with the independent classification "supplied/installed by others per schedule" (so they are not silently excluded).
  A second check for widths/heights: the A600 door elevations carry the same widths (920/820/900/800) - re-read before relying on heights (2040 leaf vs 2050-2100 drawn).
- Windows: W01-W06 each once on the A110 plan, again on A610, W01-W05 on A200. NPW (night pay window, STERLING) is legend equipment, classify out. Sizes read by eye only (in the JSON, marked NOT VERIFIED).
- Finish codes: IPF2 = Taubmans interior paint 'Crisp White' low sheen "applied to internal walls"; IPF3 = semi-gloss for internal doors. Wall types WA01-WA09 on A140 (WA03/WA04/WA05 plasterboard on metal stud; WA01/WA02 precast; WA06/WA07 coldroom panels). Ceiling/finish heights: internal elevations show 2400.
- Sheet map (page -> content): 1 A000 title & drawing schedule, 2 A001 notes, 3 A050 grid setout, 4-6 A100-A102 site plans, 7 A110 floor plan (1:50), 8 roof plan, 9 reflected ceiling plan, 10 slab setout, 11 A140 floor finishes & partitions, 12-13 A200/A201 elevations, 14 sections, 15-22 canopy elevations/sections, 23 wall sections,
  24-27 A500-A503 amenities/laundry/PWD/ambulant internal elevations (with finishes schedules), 28 A600 door schedule, 29 A610 window elevations, 30 transmittal, 31 sheet index (A4 portrait, rot 0).
**Not built (listed as UNVERIFIED candidates / reason codes, not denominator):** room floor areas, internal wall IPF2 paint areas, ceiling areas, tile areas (FT1-3, WT1-2), external surfaces. Reasons: geometry route unreliable so far (below); A110 black 0.48 layer mixes walls and fixture outlines; internal rooms such as WC & SHOWER cubicles are about 2935 x 1620 (A500 dims) but the flood fill mis-bounded them.
Suggested reason codes: `reference_takeoff_not_supplied` (no independent takeoff doc exists; truth is derived from the drawings), `wall_ceiling_finish_surface_universe_not_built`, `room_area_universe_not_built`.

### Q5446 (Simonds "Armstrong 32_298-14D Harlequin", QLD standard plans, 10 A3 sheets, 1:100)
Facts and limits are in `data/q5446_figured_dimension_chains_READ_VISUALLY.md` and `data/q5446_door_arc_census.json`. Key points:
- **No text layer, no schedules.** Plans only; areas table is designer-declared (Ground 123.89, First 121.81, Porch 4.08, Garage 36.40, Alfresco 12.00, Total 298.19 m2); internal consistency checks pass (see file); Alfresco = 3000 x 4000 exactly.
- **The five companion documents listed in the V2 manifest (Siting, Standard Inclusions, mysimonds specification, Colour Boards, Sales Advice Estimate) were NOT available to Claude** - their hashes could not be re-verified and the sales estimate could not be used for reconciliation. Ask the user for them (needed for ceiling lining / paint spec and to prove "source package hash matches").
- Verifiable now: the declared-area items (route 1 designer table + internal sum consistency, route 2 recomputation where possible: Alfresco exact), door-swing arc census (geometric), plus nothing else yet. Window census is UNRECONCILED (23 plan tags W01-W12, W13, W13A, W14-W22 vs about 20 openings on elevations).
- Q5446 will almost certainly stay `INCOMPLETE` until the companion documents arrive: use reason codes `source_package_companion_documents_not_available_for_hash_verification`, `sales_estimate_is_not_complete_measured_takeoff`, `reference_takeoff_not_supplied`, `verified_surface_universe_not_built`.

### Geometry methods tried (what worked, what failed) - tools in `benchmarks/truth_tools/`
- Scale: nominal plotted scale validated (Q5446 1 pt = 35.2778 mm at 1:100, 0.03 % on the overall chain; Maryborough A110 is 1:50 on A1: 1 pt = 17.639 mm in the DISPLAY frame; native frame is rotated 90).
- Wall layers on Q5446 plans: black strokes widths 0.96 and 1.92 (walls), 0.72 door swings, blue glazing/annotation, red text. Walls are drawn as several parallel lines per wall, so "room-side face" depends on the drawing's wall build-up convention (measured faces differ from figured dimensions by about one stud thickness on some walls).
- FAILED/fragile: raster flood fill (leaks through door/window gaps), median-of-parallel-rays (fails where a wall is mostly a window), planar-arrangement flood fill with bridged gaps (`plan_measure.flood_room`: result depends on the bridge threshold; merges across open openings), automatic snap of hand-estimated rectangles (`snap_rect`).
  On Q5446 sample rooms: ENS' 2328x1863 vs figured 2320x1820; PDR 1651x1757 vs 1610x1710; GUEST flood 3239x3323 vs 3150x3320; several rooms failed to bound at all (garage, living, entry: open walls/windows).
- WORKED: wall-face cluster listing (garage 5995 x 5503 vs figured 6000 x 5510), figured-dimension chain tick positions (`dim_ticks.py` finds ticks on some chains; tick marks are tiny polygons so extraction is partial), door-swing arcs by radius, text-layer schedule parsing (Maryborough), tag censuses.
- Recommended path if the full surface universe is later wanted: snapped digitisation with an overlay image per room and a human/GPT visual QA pass; define exact object refs per room/wall run; keep unverified candidates out of the manifest.

### Concrete next steps for GPT on lane 2 (order)
1. Get the PDFs re-uploaded (and the five Q5446 companion docs).
2. Create the branch from `origin/benchmark/full-takeoff-v2-impl`; add for each project: `reference_takeoff.json` (verified lines + per-line evidence/lineage/routes; hashed), `object_universe.json` (all objects found, each classified in-denominator / excluded-by-independent-classification / unverified-candidate), `unresolved_items.json`, `verification_report.json` (the user's 7 proofs, each pass/fail with evidence), and update `source_manifest.json` (reference_takeoff_documents, verified_takeoff_items, status INCOMPLETE + reason codes).
3. Tests (benchmark-only): loader accepts the manifests; every denominator item has refs/docs/locations; the reference doc hash in the manifest equals the file's real sha256; uniqueness of denominator keys; door universe reconciles 28 = 11+3+2+2+10; update the #1149 "all four INCOMPLETE" assertion if needed.
4. Run `pytest tests/benchmarks/test_full_plan_takeoff_v2*.py` and the CI-style separation gate on the diff (paths on stdin). Push, open a draft stacked PR, do not merge.
5. Report: branch/head SHA, exact files, denominators (Maryborough proposed 6 verified lines of which 4 denominator-eligible + 2 exclusion lines; Q5446 about 5 declared-area items), unresolved list, per-project status, tests/gates.

Open question for the user (not answered): whether to later invest in the full wall/ceiling/finish-area universe (many hours, semi-manual) - recorded answer for THIS pass is "verified-only core".

## Housekeeping
- Local Claude artifacts that are NOT preserved: renders, ~100 MB of rerun JSONs (`rerun_*.json`), synthetic fixtures, venvs. Regenerate with the tools; the key tables are in this folder.
- No production file, benchmark-defining file, or holdout file was modified by Claude in this lane. This handoff PR contains only docs and `benchmarks/truth_tools/*.py`.
