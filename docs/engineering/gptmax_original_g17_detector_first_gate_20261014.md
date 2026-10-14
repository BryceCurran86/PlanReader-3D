# GPT MAX — unhosted G17 original pixel first-failure trace

## Repo architecture and observed call path

Read `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, `docs/wall_topology_observability_architecture.md`, `docs/planreader_wall_room_topology_spec.md`, `docs/planreader_public_tender_benchmarks.md`, `.github/workflows/ci.yml`, and the following current-main functions:

`SourceVisibilityProducer.ingest_native_pdf_bytes` → `augment_with_raster_opening_primitives` → `PhysicalOpeningAuthority.prove_existence` → `SourceVisibilityProducer.augment_with_raster_visible_segments`. The last function publishes the original **144-DPI ordinary raster** from `detect_axis_aligned_raster_segments`, and source-only **300-DPI G17 terminal** from `detect_unchanged_terminal_band_segments`. Terminal candidates pass three ordered vetoes: (1) exact unchanged original images-only/full render solid paint; (2) original native source image-region coverage and `band_segment_already_observed` at 144DPI; (3) `_proven_raster_opening_flank_boxes` ownership, which on current production incorrectly requires an authenticated full `area_m2` before *source perception* nomination. Those source segments subsequently reach W2/W3/W4 from `pb_physical_wall_candidate_authority`; opening-local supplemental walls must remain outside the page-wide W4 universe, and can bind only under independent `pb_opening_host_binding_authority` physical/source equivalence gates. A pixel run cannot itself authenticate a wall or metric quantity.

## Original source observation, not an algorithm constant

Exact original Lot16 13-page PDF SHA `10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`. At accepted main before unsafe experiment #2660, 21 authenticated G17 physical existences, 15 hosts, nine frames, 2094 W4 page-3 records, eight already authenticated area quantities. The six remaining source-positive raster openings have twelve closed G17 face/end source rectangles. Original Bathroom 870 source short left 300DPI raster band has 17 inclusive painted pixel cells x2421–2437 = 4.08pt source support despite 3.84pt endpoint-centre span; it is absent from the current accepted W4 local edge inventory. On unsafe #2660, output changed 15→17 hosts but all existing 15 host IDs, nine frames, eight area-evidence lists, and source room-face topology shifted; 1215's W4 members also changed. That production change remains blocked and must not be merged or scored. None of those historical numbers or identifiers enters a detector predicate.

## Minimal proposed correction in this task

Introduce **only read-only original-source detector first-failure instrumentation**, `tools/diag_gptmax_g17_detector_first_gate.py`. It:
- Rechecks PDF bytes by SHA against the original produced full-page source report and the unchanged 20,000 primitive input cap.
- Consumes the merged #2658 + #2670 already authenticated, immutable G17 source receipt sidecar and `source_only_closed_flanks`, maintaining every original physical opening ID, page and source snapshot address.
- Re-ingests the supplied exact original PDF into an **independent private source producer** and uses the real producer renderer at 144DPI, images-only and full at 300DPI, with exact original source frame agreement. It calls the actual original `detect_axis_aligned_raster_segments`, `detect_unchanged_terminal_band_segments`, `_axis_aligned_geometry_fully_covered_by_rect_union`, `band_segment_already_observed`, `_unchanged_segment_inside_flank` functions, not a second independent raster detector/scale authority.
- For every original G17 flank, records **all** 300DPI terminal candidates, original source tile-ownership candidates, 144DPI dedup survivors and the first failing detector stage. A 144DPI candidate may veto an original 300DPI duplicate even if W2 later lost its local edge; no dedup gate is bypassed by this observer.
- Reads original figured-area evidence only to report whether the production source-nomination prerequisite is satisfied. Never treats a single `870` witness as a width+height or full opening area.
- Returns explicit false flags for structural wall owner, physical host, count, quantity and benchmark score. The script cannot mutate any existing accepted source snapshot, source PDF, W4 record, opening host, sealed customer row or frozen truth.

## Synthetic/adverse validation and independent original source test

The pure ordered classifier `classify_original_terminal_flank_pixel_gate` has synthetic positive 17-cell source runs, absent terminal source, missing image-region ownership, explicit 144DPI ordinary-duplicate veto, unrelated original 144DPI negative, invalid axis/bbox. Python 3.13 and 3.14 jobs run focused tests, original V2 integrity, provider isolation, undefined-name lint and compile. Separate original immutable PDF job runs all 13 pages' original authority once, then independently replays page-3 exact renderer and source-stage gate; verifies accepted 21/15/9/2094/8 controls and expected six original source-positive opening identities/twelve boxes from original receipt. These are **regression fixture controls**, never prediction inputs. Writes an original-source artifact for first failure analysis; no new FIRM.

Expected ABSTAIN until producer source fragment is retained through correct W2 snap/merge and authenticated unique physical W4 wall role/equivalence, a second instance-owned dimension is authenticated, GPT1 publishes true QuantityEvidence and GPT3 independently seals and scores against frozen truth. A candidate that only passes source paint is **not** a new construction quantity.

### Out of scope / untouched

No production source detector threshold, W2 snap tolerance, 20k primitive cap, G17 physical opening authority, W4 assembly, host or frame publisher, snapshot ID, canonical quantity, commercial takeoff writer or JobHub code is changed. Frozen V2 source files, evaluator and truth untouched. No project names/expected quantities are inspected by the diagnostic's geometry classifier. This is a prerequisite first-authority-stage diagnostic, not a new source or quantity publisher.
