# Registered G17 source parent verification — 2026-10-17

## Observed repository behavior

Trace: SourceVisibilityProducer._augment_with_raster_visible_segments_source_impl
emits original_g17_one_end_paint_v1 and original_g17_jamb_partial_paint_v1
parent/visible primitives with exact source-render receipts. SourceVisibilityAuthority
authenticated_visible_observations and resolve_visible both call
_raster_segment_receipt_matches_parent. Its five-field grammar accepted only
UNCHANGED_BAND_IDENTITY_VERSION, so it rejected the new producer-issued families.

Original Lot16 SHA-pinned changed-policy replay reached
visibility_parent_mismatch -> physical_wall_candidate_source_integrity_failure
before W4 source reconstruction. A separate synthetic image-only PDF reproduces
the same failure through the real one-ended source publisher and both readers.
The original-source failure is not evidence of a missing physical wall.

## Inference and correction

Accept only the two already registered new family constants beside the historical
unchanged-band family. All existing source-render SHA, full-render SHA, DPI,
pixel-to-page geometry, canonical primitive grammar and stable parent observation
ID checks remain mandatory. Unknown, similar or future family versions abstain.

This corrects source visibility registration, not structural wall role, physical
equivalence, host selection, frame geometry, measurement, count or customer
publication. Existing opening-local isolation still keeps these source families
out of ordinary page/F.07 W4 and in incomplete supplemental scopes.

## Synthetic proof

Before correction: 17 failed / 35 passed in the new registration test.
After correction: new registration tests plus existing unchanged-band and raster
source visibility tests: 77 passed (Python 3.12.14, PyMuPDF 1.28.0, OpenCV 4.14.0).
Coverage includes every exact registered family; half-cell, translated, rotated
and alternate spans; similar/unknown namespaces; borrowed document/revision/page/
partition/geometry; real publisher/reader round trip; and altered render hashes,
DPI and pixels after cold or warm authenticated reads.

The prerequisite test repairs restore the viewport-isolation test syntax and the
paired-policy test fixture, without modifying production behavior. The preceding
integrated tree passed 1,970 GPT MAX tests, original-PDF ink checks, compile and
provider/truth integrity gates. Final-tree results and original-source retention
must be recorded on the PR; those earlier passes do not verify this final head.

## Authority boundaries and untouched files

No benchmark values, mappings, tolerances or expected quantities informed this
registration correction. Source PDFs, frozen truth/evaluator, W2 2.5pt snap,
4pt printed-ink threshold, 20,000 primitive cap, physical opening existence,
host/frame producers, quantity schemas and customer writers are unchanged.
No new host, frame, signed area, complete opening count or accuracy gain is
granted. Strict original W4/host/frame/customer retention remains a release gate.

