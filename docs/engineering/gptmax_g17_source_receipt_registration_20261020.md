# G17 original render and pixel registration

The source reader previously accepted a replaced raster-opening receipt with a
foreign render hash, wrong DPI or unrelated pixel coordinates as CORROBORATED
when the immutable PDF-point parent was unchanged. A generated raster PDF
reproduced all three failures before implementation. The new regression failed
on the unchanged main reader before the patch.

`SourceVisibilityAuthority.resolve_raster_opening_primitive` now validates the
original `raster_opening_primitive` parent reference, render SHA, identity
version, primitive kind, fixed producer DPI, finite nonnegative half-pixel
coordinates, exact existing pixel-to-PDF quantization, and both original stable
observation IDs. It reuses the existing CONFLICT boundary. Ordinary W4 source
IDs remain distinct. No detector, source geometry, host, measurement or count
authority is created.

## Verification

- 194 focused source, tampering, G17/frame, transformed-geometry and archived
  signed-eight tests passed locally (Python 3.12.14, PyMuPDF 1.28.0, OpenCV
  4.14.0). Public Python 3.13/3.14 CI remains a separate required result.
- Provider isolation, V2 integrity, V2 separation, undefined-name lint and
  whitespace checks passed.
- Fresh original Lot16 PDF SHA:
  `10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`.
- Original p3 selected root remains
  `source_snapshot_3fcb6bc5c44b51d930e9600080501d27`.
- Exact baseline `dffce8bc13ed292271ce7c3f7be4690dfb2b7208` and patched source
  receipt reports are equal in their entirety: 21 physical openings, 15 hosts,
  nine frames and eight issued areas. Complete original production receipt
  bundle canonical JSON SHA-256 is
  `1b4d56abd1c8f2c06e072524f8e7b052b22f084f2a1db05a41fd7a4e43fc8a99`
  on both trees. This includes all wall, host, frame, canonical, raw quantity,
  audit seal, audit customer and customer-verification bodies.
- A separately project-scoped source replay exactly retains the archived
  signed run and fingerprint
  `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
  The general `_retention` helper uses simplified measurement-authority metadata;
  its audit customer rows are not the historical production-customer writer.
  Do not confuse that harness difference with a source or signed-row change.

## Remaining boundaries

This is a source-integrity repair, not a recovered opening, host or benchmark
match. Exact-current-head CI, Maryborough parity, independent authority review
and owner approval remain necessary before merge. The baseline missing
`_axis_values_match_figured_pair` helper is separately fixed in unmerged #3373;
do not silently absorb that dependency or call failing full CI green.

Follow-up: a warmed physical-opening existence cache can retain a positive
after a different supporting receipt is damaged. That is a separate cache
invalidation defect; this reader repair alone must not claim to fix it.
