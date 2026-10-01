# Q7 real-source rotated-sheet investigation (PR #1143, PRE-PATCH head d389ae5b)

Read-only. Nothing under `benchmarks/frozen_holdout` was opened; no gold/expected/mapping/scorer/tolerance file was read; `claude/page-frame-shadow-v1` was not modified. All shadow runs used a scratch merge of #1143 head `d389ae5b` onto `main` `c51b46e`. **Rerun required on ChatGPT's patched head (not yet available).**

## 1. Search
All mounts, `/mnt/user-data`, `/mnt/attach`, git history, and the trees of all 1,186 remote branches were searched first: no real plan PDF existed. The only real plans are the 5 user uploads in this session (`/root/.claude/uploads/...`). None is the sealed holdout.

## 2. REAL USER-SUPPLIED SOURCES: rotation census (metadata only; own + inherited /Rotate, cross-checked against PyMuPDF `page.rotation` and a whole-file sweep of every object's /Rotate key)

| file | pages | rot 0 | rot 90 | rot 180 | rot 270 | non-orthogonal | MuPDF disagreements | sha256 |
|---|---|---|---|---|---|---|---|---|
| Arch_Combined_Maryborough_Service_Station.pdf | 31 | 2 | 29 | 0 | 0 | 0 | 0 | `b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007` |
| Q5446_Standard_Plans_V1_20220320.pdf | 10 | 10 | 0 | 0 | 0 | 0 | 0 | `5f29aa0122d72e2cc8886b3f19239ff32865c8d705eee99f785c389ca27fb7f0` |
| 1._Construction_Plans_-_Lot_16_Power_REV_E.pdf | 13 | 13 | 0 | 0 | 0 | 0 | 0 | `10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844` |
| 4._Structural_Engineering_-_Lot_16_Power.pdf | 11 | 11 | 0 | 0 | 0 | 0 | 0 | `b40259589dd39a46e45d25e145cfa789d9a9415b50613ebc4fee01dceab6b3d6` |
| 3LAUREL_-_Construction_Plan_Set_Rev3_08.05.26.pdf | 18 | 18 | 0 | 0 | 0 | 0 | 0 | `014e9f68b377bef4fb556de61b83a94388792dfa4bfb8ea981644f9c323e9e2e` |

Only genuine rotation found: **Maryborough Service Station, source pages 1-29 = /Rotate 90 (own entry, MediaBox 1684x2384 -> displayed 2384x1684, no CropBox difference, no UserUnit); pages 30-31 = /Rotate 0 (A4).** No real 180 or 270 exists in any of the 5 sets (83 pages).

## 3. REAL SOURCE RESULTS
### 3a. Page-frame descriptor (`describe_page_frame`, PR code unchanged) on all 83 real pages
All 83 pages: status `raw` (coherent), 0 reason codes. Maryborough: 29 pages rot 90, native 1684x2384, display 2384x1684; 29 `display_extent_differs_from_native` notes. Rot-0 sets: native extents match MediaBox.

### 3b. Premise + mapping checks on the 29 real rot-90 pages (Maryborough)
- Raw vertices read from `get_drawings`: 1,015,790; **0 outside the declared native extent**; 351,997 (34.7%) outside the display extent; all 29 pages have vertices that cannot be display-space (max y 2333 > display height 1684). Raw coordinates are native (unrotated) space.
- Descriptor `native_to_display` vs MuPDF `page.rotation_matrix`: max abs diff 6.1e-5 pt; **pixel-index agreement 100% on every grid point of all 29 pages (max index delta 0 px)**. Round trip exact.
- Rendered-pixel equivalence (page rendered displayed vs rotation forced to 0): descriptor mapping match on ink 72-98% (median ~88-90%) vs wrong mappings mostly 1-6% (dense pages up to 45%). Not 100% because MuPDF antialiasing differs by orientation: an exact numpy rot90 of the unrotated render, using no descriptor code, matches at the same rate (p1 97.8%, p22 81.7%, mean abs gray diff 0.5-3.9).
- Rot-0 pages 30-31: descriptor = identity, 100%.

### 3c. Existing shadow comparison (`_page_report`, PR code unchanged) -- 20 of 29 rot-90 pages + 2 rot-0 controls
Run on page-subset PDFs cut from the real file (/Rotate preserved, verified). The whole 31-page document could not be ingested: the existing `ingest_native_pdf_bytes` was OOM-killed at 12.9 GB RSS after ~25 min. Wrapper change (not a PR change): the selector uses the *refreshed* published snapshot (see defect D1).

| source page | /Rotate | frame | pipeline | cross-check | walls | dangling ends | at-boundary current / shadow | divergent (default / quantised) |
|---|---|---|---|---|---|---|---|---|
| 1 | 90 | raw | ok | match | 1797 | 201 | 0 / 0 | 0 / 0 |
| 2 | 90 | raw | ok | match | 104 | 29 | 0 / 0 | 0 / 0 |
| 3 | 90 | raw | ok | match | 913 | 821 | 0 / 0 | 0 / 0 |
| 13 | 90 | raw | ok | match | 2175 | 1048 | 0 / 0 | 0 / 0 |
| 14 | 90 | raw | ok | match | 13899 | 1531 | 0 / 0 | 0 / 0 |
| 15 | 90 | raw | ok | match | 4602 | 1623 | 0 / 0 | 0 / 0 |
| 16 | 90 | raw | ok | match | 2209 | 667 | 0 / 0 | 0 / 0 |
| 17 | 90 | raw | ok | match | 1669 | 625 | 0 / 0 | 0 / 0 |
| 18 | 90 | raw | ok | match | 2129 | 530 | 0 / 0 | 0 / 0 |
| 19 | 90 | raw | ok | match | 3649 | 1222 | 0 / 0 | 0 / 0 |
| 20 | 90 | raw | ok | match | 3048 | 996 | 0 / 0 | 0 / 0 |
| 21 | 90 | raw | ok | match | 3809 | 586 | 0 / 0 | 0 / 0 |
| 22 | 90 | raw | ok | match | 5124 | 726 | 0 / 0 | 0 / 0 |
| 23 | 90 | raw | ok | match | 4920 | 791 | 0 / 0 | 0 / 0 |
| 24 | 90 | raw | ok | match | 6646 | 517 | 0 / 0 | 0 / 0 |
| 25 | 90 | raw | ok | match | 3989 | 300 | 0 / 0 | 0 / 0 |
| 26 | 90 | raw | ok | match | 3591 | 465 | 0 / 0 | 0 / 0 |
| 27 | 90 | raw | ok | match | 4517 | 480 | 0 / 0 | 0 / 0 |
| 28 | 90 | raw | ok | match | 1812 | 625 | 0 / 0 | 0 / 0 |
| 29 | 90 | raw | ok | match | 1001 | 675 | 0 / 0 | 0 / 0 |
| 30 | 0 | raw | ok | match | 136 | 24 | 0 / 0 | 0 / 0 |
| 31 | 0 | raw | ok | match | 36 | 12 | 0 / 0 | 0 / 0 |

Totals (rot 90, 20 pages): pipeline errors 0, cross-check mismatches 0, divergent ends 0, **at-boundary ends 0 in both frames**. Page-edge ends do not occur on these margin-framed CAD sheets, so zero divergence is VACUOUS: the boundary predicate was not exercised. Not run (pipeline cost): source pages 4-12 (rotD; includes the 109k-drawing page 7).

## 4. Defects / observations found (not fixed here)
- **D1 (PR #1143 diff script, ChatGPT's patch scope).** `_page_report` builds its selector from the pre-producer `pub.snapshot.snapshot_id`. `PhysicalWallCandidateProducer.from_source_visibility_producer` runs raster augmentation, which publishes a NEW snapshot; the lookup then misses and `resolve_scope` returns `physical_wall_candidate_scope_unavailable` with 0 walls while `pipeline_status` stays `ok` and `cross_check` stays `match`. Verified: rotB snapshot before != after; stale lookup -> unavailable, refreshed -> resolved (1796/104/913 walls). Control pages (no augmentation) are unaffected. Fix: refresh `pub = src._published_by_revision[revision_id]` after building the authority. Unpatched, the script reports a silent false negative on any page set the raster augmenter touches.
- **O1 mixed frames on one rotated page (existing pipeline).** Page 1 (rot 90): `raster_segment` lines (1,940) span x<=2323, y<=1649 (fit the displayed 2384x1684 frame; never reach native y up to 2333) while vector `d#i#` lines (224) span x<=1649, y<=2333 (native frame). Both feed one wall graph. 25 of 143,206 wall ends on the 20 rot-90 pages (4 pages: 1, 14, 21, 22) lie outside the native extent (page 1 explained by raster segments; the others consistent with it, not individually verified).
- **O2 consumer frame mismatch, real-scale.** 55,140 of 143,206 wall ends (38.5%) on the 20 rot-90 pages lie outside the extent the existing consumer uses (rotated page.rect 2384x1684); 25 (0.02%) lie outside the declared native extent.
- **O3 document_id dependence (existing code).** Identical bytes gave 1796 / 1797 / 1799 walls (page 1) under three document ids; same id + same/different PYTHONHASHSEED gave identical counts. Cause not investigated.
- **O4 ingest cost.** `ingest_native_pdf_bytes` (per-word `get_bboxlog` page re-runs) is ~minutes per dense A1 page and the 31-page set exhausted 16 GB.

## 5. SYNTHETIC FIXTURE RESULTS (existing, from PR #1143 -- NOT real-source evidence)
- 382 page-frame tests pass on Python 3.13.14 / PyMuPDF 1.28.0 with #1143 merged onto current main (re-run this session).
- PR body A4 plain-stream shadow diff: current FN/FP 4/2 at /Rotate 90 and 270, 0/0 at 0 and 180; shadow (extent) 0/0 at all four. This is the only evidence of non-zero current-vs-shadow divergence; it has no real-source counterpart yet.

## 6. Verdict
**Q7 cannot be closed.** Real rotated evidence exists for 90 only; real 180 and 270 are absent from all supplied sets. The frame/mapping premise holds on real 90 (see 3b). The shadow diff produced no usable divergence evidence on real pages (vacuous) and has defect D1. Needed: a real source with genuine /Rotate 180 and 270, and a real page that actually has page-edge wall ends.
