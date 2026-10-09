# Conflicting raster aperture identities

Observed: `_prove_raster_framed_existence` checks shared support membership but originally did not compare unequal aperture extents between independently supported candidates. Raster physical IDs hash exact gap boxes. In a negative detector-output experiment over a real two-opening synthetic PDF, changing one derived detector extent to overlap the other yielded two CORROBORATED records and `physical_opening_identities_distinct`. Immutable source observations/receipts remained unchanged. This experiment is not evidence that the original drawing contains overlapping openings, nor an assertion of a duplicate in Lot16.

Inference: different hashes are not positive proof that overlapping local aperture claims represent distinct physical objects. No approximation should choose a winning extent or merge them.

Change: before minting a raster physical existence record, retain unequal source-scoped aperture candidates with positive two-dimensional overlap as CONFLICT using the existing ambiguity vocabulary. Both candidate hypotheses and raw audit supports remain retained. Exact-equal apertures retain the existing stable-ID path; separated apertures remain unaffected. No search radius, cap, metric scale, count or quantity changes.

Trace: authenticated source receipts -> registered candidate generation -> authenticated viewport filtering -> physical existence -> semantic closure -> host/frame composition -> canonical opening. Only the first physical-existence boundary changes. Quantity, material/RCP, reconciliation, benchmark truth/tolerances/denominators and the 20,000 primitive limit remain untouched. This is a conservative authority guard with no commercial promotion.

Tests: partial/nested overlap, transformed/reversed replay, retained candidate provenance, unchanged derived support inventory, no false DISTINCT identity, and incomplete count closure; positive separated apertures retain two stable IDs and exact SHA/snapshot ownership. Real Lot16 must preserve exact original binding and positive frame records before publication; Maryborough and full Python 3.13/3.14 remain independent required CI gates. Keep draft until all latest-head checks pass.

Benchmark expected objects/quantities do not inform implementation. No additional extracted object or accuracy improvement is claimed.
