# Lamu roof outer-edge architecture report (shadow only)

Source: public tender PDF, SHA-256 `fa53c9b72fd35189f11848f9a26ccc3512c8c03b5316e78cad6a4d55c09330f2`, drawing page 41. This document is diagnostic evidence; no PDF filename, project identity, or benchmark value is an extractor input.

## Observed repository path

- `pb_viewport_segmentation.segment_page_viewports` identifies the floor-plan and elevation viewports.
- `pb_source_roof_covering_authority.extract_elevation_segments_from_page` captures elevation diagonals and support verticals; `resolve_gable_apex_in_viewport` binds opposing gable slopes to structural supports; `measure_source_roof_covering` multiplies a structural footprint axis by its sloped counterpart and explicitly **excludes eaves overhang**. `resolve_document_gable_roof_covering` collects one compatible gable across selected pages.
- `GenericPlanReaderExtractor.extract_from_pdf` in `pb_planreader_pdf_extractor.py` calls that resolver near lines 2792–2923 and stores its result in `roof_covering_shadow`. It does not publish this quantity as a live roof prediction.
- `pb_page_scale_calibration_authority.resolve_page_scale_calibration` and `pb_viewport_scale_binding.bind_viewport_scale` own firm scale. The Lamu elevation viewport reported `scale_denominator=None`; title-block scale text alone stays provisional. `pb_figured_dimension_authority.resolve_measurement_authority` firms an owned figured span, but an unfigured roof-edge extension is not automatically a firm measured span.

## Source observations, before benchmark comparison

The front elevation has roof outline horizontal paths at x 184.28–671.96 (487.68 PDF pt), above structural corner x 201.32–654.92 (453.60 pt). The rear elevation independently repeats the 487.68 pt roof width. The gable elevation has roof slope ends at x 311.72 and 572.48 (260.76 pt), outside the support endpoints at x 328.64 and 561.20 (232.56 pt). The existing resolver independently establishes ~18.019° slope.

The sheet prints 16,000 mm along the long structural axis and 8,200 mm across the gable structure. Dividing the corresponding vector spans gives 28.350 and 28.361 pt/m (about 0.04% disagreement). Using those ratios solely as a **diagnostic** suggests an outer roof plan length of 17.202 m, width 9.194 m, and area 166.32 m² after pitch. This is not a firm calibration or publishable quantity.

## Inference and proposed next seam

The three elevations appear to depict the same classroom roof, and the lines appear to be outer covering boundaries. A generic source-owned edge collector should retain drawing path indexes, stroke, viewport and page identity; authenticate a gable pair and at least two matching longitudinal roof outlines; reject dimension, grid, frame and datum lines; retain competing candidates. It must report the native point extents in shadow. Only an existing authority seam may later establish a firm measurement for each axis, with complete viewport and building identity reconciliation. Do not turn the diagnostic ratios or title-block scale into firm authority.

Expected abstentions: unresolved or mixed-scale views; absent or competing outer slope pairs; unverified material/roof identity; only one longitudinal elevation; disagreement between independently owned views; ambiguous relation to the separate toilet block; missing firm scale or figured roof extent. Keep live predictions and commercial rows unchanged in this phase.

## Benchmark firewall and untouched files

The development benchmark expects `LMU-E4-A` at 172 m². That value is **evaluation only** and did not select lines, thresholds, dimensions or formula. Do not change `benchmarks/**`, source hashes, scoring, mappings, tolerances or denominator. This diagnostic must not edit `pb_planreader_pdf_extractor.py`, JobHub, W10 or live opening and net-wall gates. Validation requires positive, look-alike, ambiguity, translation/scale/input-order, viewport and no-mutation tests before a separate authority review considers publication.
