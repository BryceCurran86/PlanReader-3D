# GPT1 — Linear canonical original room ring without source-ID drift (2026-10-30)

## Observed repository behavior

`pb_room_area_quantity._original_pdf_ring` validates native finite PDF-point pairs, rejecting repeated source vertices and malformed coordinates. `_canonical_ring` rounds valid original vertices to eight decimals, then enumerates every cyclic rotation in both directions and chooses Python's lexicographic minimum. That constructs 2N full tuples (quadratic time and memory). `build_room_area_quantity` embeds this exact canonical ring in the original PDF-scaled `stable_contract_id("qty", ...)` payload and `ring_signature`. The actual live floor publisher, source-closed trace, and final customer projector reuse the original source ID; GPT1 draft #4127 also rederives the same ring before a scaled customer row. A changed canonical representation would invalidate genuine source/customer receipts.

## First failing gate and inference

For a geometrically valid, source-owned high-vertex room ring, quadratic rotation allocation can exhaust process memory before the PDF-scaled room-area producer can complete. The unchanged 20,000 input-primitive safety cap is not a quadratic-work budget. This is a resource/completeness defect, not permission to infer area, scale, host, room ownership, or source authority.

## Narrow production correction

Use the lexicographically least cyclic rotation algorithm (Booth's two-index elimination) separately on the forward and reversed eight-decimal original coordinate sequences, then choose the same minimum. It is O(N) time and O(N) additional memory; the old list-of-rotations is removed. The original ring parser, numeric rounding, source contract payload, formula, SHA, revision, viewport, conflict/ABSTAIN rules and all downstream issuers are untouched. No new numeric FIRM evidence is created.

## Validation and authority firewall

Compare the new function against the exact old enumeration oracle for many source-valid rings, including rounded-coordinate ties and signed zeros; assert cyclic and winding invariance, a 20,000-vertex source-identity stress case, original scaled producer ID/ring-signature stability across equivalent vertex orderings, translation's distinct physical identity, deterministic replay, and input immutability. Malformed/ambiguous source vertices remain abstained. Require exact-head full Python 3.13/3.14 CI, technical self-review and trusted original-source replay proving byte-exact preservation of nine Lot16 and three Maryborough signed/customer bodies before merge. No synthetic test can claim new original FIRM or frozen120 accuracy.

## Scope / benchmark observations

This change is disjoint from GPT2 physical FT2/FT3/RCP, GPT MAX/Claude opening hosts, GPT3 signing/scoring and existing GPT1 customer/floor PRs. Do not touch private PDFs/tokens, frozen Full Plan V2 truth/evaluator, 2.5pt snap or the 20,000 primitive cap. Benchmark values are observations only and must not influence the canonical ring algorithm.
