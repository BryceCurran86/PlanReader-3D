# GPT1 — Bound per-primitive native-ingest allocation (2026-11-06)

## Observed call path and first failure
Private original-source replay reported `SOURCE_ROLES_INCOMPLETE` with child `MEMORY_LIMIT`; its allocation hotspot is **not** established. The public collector `pb_live_physical_net_wall_integration._collect_live_physical_net_wall_claim` retains the original PDF bytes and calls `SourceVisibilityProducer.ingest_native_pdf_bytes`, which delegates to `SourceObservationProducer.ingest_native_pdf_bytes`. `_decode_native_page_for_cache` already returns immutable six-field tuples for each native page/word/segment/rect, while ingestion formerly expanded these tuples to a second list of seven-key dictionaries before creating producer-owned `SourceObservationRecord` objects. That per-primitive mutable dict stage was redundant.

## Bounded implementation
Consume the existing cached native `pending_items` tuples directly and retain only a list of tuple references until final records are constructed. Remove the unused list-of-dicts materializer. The final `identity` mapping, stable observation ID, content fingerprint, source SHA, record ordering, decode coverage, page scope and immutable commit sequence are unchanged. This avoids transient allocations; there is no original-source performance or memory-limit success claim.

## Synthetic evidence and mandatory release
`tests/test_scoped_source_ingestion_v1.py` independently recomputes every native observation ID on a synthetic multi-page PDF from exact tuple fields and source revision, confirms scoped page coverage and idempotent replay. Existing visibility, scoped, customer-retention and adversarial source-integrity tests remain required. Before merge: full exact-head Python 3.13/3.14 CI, protected original-source replay reproducing all historical signed/customer quantities, and (for any memory-limit claim) the protected Maryborough source-role execution at the exact head. No `FIRM` quantity or frozen four-project score is added.

## Authority boundaries and untouched files
Original PDF SHA, revision/page/primitive identity, source snapshot, existing `QuantityEvidence`, customer rows, frozen120 definitions/gold/scorer, private PDF source repository, geometry limits (20k primitives, 2.5pt snap), W4/host/frame, floor/ceiling source interpretations, original retained outputs, and other agents' branches are not changed.
