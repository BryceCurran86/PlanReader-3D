# Original floor-finish coverage forwarding

Observed: `GenericPlanReaderExtractor.extract_from_pdf` collects original physical claims, appends wall/opening/count/room-area quantities to `_coverage_quantities`, then sends the list to `collect_live_canonical_coverage`. The claim's `floor_finish_quantity_evidence` is omitted. The workspace path already passes that field. A separate ceiling collector supplies its own quantities later.

Inference: existing floor-finish evidence is absent from the extractor's diagnostic inventory. This is not evidence of a missing issued customer quantity; original Office and Food Prep finish selection is already confirmed by the owner, while automated material text proof remains unresolved.

Change: append the original finish tuple once at the existing sink, preserving its objects, order, duplicate/blocked records and metadata. Keep independent ceiling collection. No filtering, reissue, identity alias, quantity, source-text or measurement promotion is introduced.

Trace: existing physical producer -> original `LivePhysicalNetWallClaim.floor_finish_quantity_evidence` -> extractor coverage sink -> existing typed coverage registry. Source-to-customer issuers and publication contracts remain unchanged. Coverage registry identity joins, including physical/canonical identity differences, remain independently checked; this change does not resolve or hide them.

Proof: test the actual extractor call with the existing typed synthetic source/seal/customer fixture, then spy at the final registry boundary. Check valid/blocked/duplicate/empty inventories, exact-once ceiling forwarding and no input mutation. These are routing regressions, not original-plan or accuracy proof.

Benchmark observations do not guide this patch. Frozen120, original PDFs, signed/customer fixtures, source/metric authorities, snap and primitive limits are untouched. No new floor-finish customer completion is claimed.

Validation: before the patch, the actual-extractor positive routing regression failed with zero forwarded finish quantities instead of one. After the five-line routing patch, all 65 selected extraction-coverage, runtime-coverage and floor-finish customer-veto tests passed on Windows Python 3.13. F821/F823 and diff checks passed. Final-head CI and original sealed/customer replay are recorded separately before release.
