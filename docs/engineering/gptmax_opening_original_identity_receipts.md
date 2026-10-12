# Original opening identity receipts — architecture report

Observed on main 63fe8706: `SourceVisibilityProducer.ingest_native_pdf_bytes`
owns original native/raster observations. `compose_live_wall_opening_authority`
proves physical opening representatives and hosts; `OpeningLabelDimensionProducer.publish_scope`
proves exact label text ownership through `source.text_integrity_authority().resolve_text`.
`compose_live_physical_opening_voids` retains the figured-label evidence ID in
canonical openings. `seal_live_opening_area_claim_run` preserves that ID and all
quantity source evidence. Its signed schema does not carry the original label
text boxes; `project_live_opening_customer_rows` therefore exposes no such box.
The unchanged exact-project reconciler requires independent physical identity
bindings after sealing and never joins by quantities, names or order.

Inference: source-native label receipts, including exact observation IDs,
original boxes, page and snapshot ancestry, can recover location evidence
without reissuing any quantity or altering the signed customer artifact.

Proposed: opt-in, read-only source identity detail in the existing source-stage
report. Re-resolve every text observation named by a corroborated figured-label
receipt using the existing text integrity authority. Reject missing/untrusted
or foreign-page/snapshot source receipts. Retain canonical opening geometry,
source parents, host/frame and figured-label evidence unchanged. The default
report must remain identical. This does not resolve plan viewport ownership,
source completeness, physical equivalence, missing hosts, width or height.

Benchmark observation excluded from implementation: seven sealed areas exist
in the original Lot16 run, including two equal values. No numeric or name
matching is admissible. Source-only detail knows no frozen IDs or quantities.
Any later benchmark-side crosswalk must justify each pair independently from
original observation ancestry and exact frozen source-location evidence.

Expected abstentions: unmeasured/hostless objects remain unchanged; failed text
integrity cannot supply location authority. Frozen V2 truth, evaluator, scoring,
tolerances, denominators, W10, 20,000-input cap and commercial writers remain
untouched. Focused negative/opt-in tests plus original SHA replay verify this
read-only change; applicable CI remains a merge gate.
