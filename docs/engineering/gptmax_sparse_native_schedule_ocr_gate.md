# Sparse native schedule and redundant OCR claims

Observed on unchanged main `6b7908c`: the W21 source mutation test produces a
complete native schedule row with count 5 and documented dimensions. Its page
contains fewer than 150 native text characters. In
`GenericPlanReaderExtractor.extract_from_pdf`, `has_complete_native_openings`
is true, but the unconditional `is_scanned_or_raster` term makes
`native_insufficient` true. OCR reconciliation rebuilds the same original row
with a different raw evidence reference. `merge_extracted_prediction` properly
blocks the unresolved duplicate claim; it must not be weakened.

Trace: native schedule rows → `has_complete_native_openings` →
`DrawingOCREngine.recognize_page_rect` → `EvidenceReconciler.reconcile` →
`merge_extracted_prediction`. The existing native-first comments require OCR
only when native evidence is insufficient, and the other raster/schedule
trigger terms already enforce that condition.

Proposed: gate the sparse-native-text trigger with the same complete-native
predicate. Keep OCR active for genuinely sparse pages without complete native
opening quantities and for existing raster/schedule fallback cases. Do not
change native schedule authority, source claim equivalence, count/dimension
parsing, ambiguity, conflicts, quantity publication or benchmark behavior.

Expected: complete native schedules retain their original source row and skip
redundant OCR; incomplete native schedules still request OCR and retain all
existing abstention rules. Unlabelled source rows cannot invent an opening
identity. The original failure must pass without changing its expectation.
Source PDFs, physical hosts, frozen V2 and the 20,000 input bound are untouched.

Validation: the unchanged W21 source mutation now passes. 71 focused live
schedule conflict, tag normalization, opening reconciliation and generic
binding tests pass. A complete short native PDF skips only redundant 150-DPI
schedule reconciliation; the separate 120-DPI drawing collector remains
available. A sparse incomplete native schedule still requests 150-DPI OCR.
The merge-time duplicate source-claim gate is unchanged.
