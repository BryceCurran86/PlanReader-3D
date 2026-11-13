# Original-source clipped rendering reuse — 11 November 2026

Observed on the genuine Maryborough Office production floor run: per-word two-DPI raster corroboration repeatedly enters PyMuPDF's fz_new_display_list_from_page through SourceObservationProducer.render_native_page_png. The original baseline remained in source-semantic recovery after more than 25 minutes. This is an execution bottleneck, not source unavailability or evidence for a new quantity.

The change retains at most two annotation-inclusive page display lists within one producer's retained immutable PDF. Every call still validates the current revision, stored source hash, requested snapshot, native page parent/partition, decoded-page membership, native clip and native/display coordinate frame. Each DPI renders its own exact clip. Different source bytes clear the cache before closing the old document. Dirty retained PDFs and modified renderer methods take the original Page.get_pixmap path. Full-page and images-only rendering remain unchanged.

The display list is the same one PyMuPDF creates internally for an ordinary clipped get_pixmap call. It carries no measurement, host, scale or physical-wall authority. No OCR decision, input bytes, evidence IDs, primitive cap, snap, quantity or customer schema changes.

Validation covers exact PNG bytes and defensive parent lineage at 144/300/450 DPI, annotations, supported native rotations (0/90 degrees), preservation of existing unresolved-frame rejection for 180/270 degrees, independent DPI output, source/page/producer isolation, source-byte substitution, stale revisions, bounded eviction, dirty pages and renderer-hook failures. Three pre-change performance regressions establish repeated native display-list construction; existing native-frame refusals are preserved rather than broadened.

This is a dependency of the pending original Maryborough source-to-customer acceptance, layered on PR #4287. Full exact-head CI, original-source raster parity and genuine customer results must be recorded before release. No benchmark score or successful original quantity is inferred from synthetic rendering tests.
