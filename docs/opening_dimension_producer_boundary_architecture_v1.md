# Opening Dimension Producer Boundary — Architecture (v1)

**Status:** test-first architecture only. No production implementation or dimension publication is authorized by this document.

**Exact base:** post-#331 `main` at `507c57db16be515e2432c695341bdea1e71b3fd7`.

**Related gates:** #333 independently validates merged physical-opening identity. #336 refreshes the broader dimension attack matrix onto post-identity main. This document closes a narrower producer/query boundary discovered while reviewing #336.

## 1. Decision

A future opening-dimension authority must not be constructed from `SourceVisibilityAuthority` alone and then reach through its private `_source_authority` to obtain figured text.

The producer/query boundary must bind all of the following before a positive dimension can be returned:

1. producer-owned native text observations;
2. producer-receipted visible vector observations;
3. the exact source revision/hash/snapshot/page scope;
4. a G17 physical-opening existence proof re-derived from an `ObservationSelector`;
5. merged #331 local physical-opening identity semantics where identity comparison is required; and
6. the figured-dimension/witness relationship itself.

Ordinary consumers submit selectors. They do not submit authoritative dimension values, source-observation bodies, existence-record bodies, producer snapshots, or candidate universes.

## 2. Observed current boundary

`SourceVisibilityProducer` owns a private `SourceObservationProducer` and returns a sealed `SourceVisibilityAuthority`.

The underlying source producer records native PDF pages, segments, words and rectangles. Native words retain `raw_text` and bbox geometry. The visibility wrapper additionally publishes receipted `native_pdf_visible_segment` observations.

However, the public `SourceVisibilityAuthority` query surface resolves only receipted visible observations. A raw `native_pdf_word` snapshot member has no visibility receipt and therefore cannot be retrieved through `resolve_visible()` as figured text evidence.

This is deliberate and correct for G17 visibility authority. It means a consumer built only from `SourceVisibilityAuthority` cannot securely resolve a printed `900` dimension without either:

- reaching through private state; or
- receiving a producer-bound typed dimension authority that has read access to the same producer-owned raw observations and visibility receipts.

Private attribute reach-through is rejected as an authority design because it bypasses the reviewed query boundary and makes same-store binding implicit rather than contractual.

## 3. Required composition model

The trusted composition root should create the dimension authority from the same producer that owns source observations and visibility receipts. An illustrative in-process API is:

```python
dimension_authority = source_visibility_producer.opening_dimension_authority()
```

The exact class name is less important than the boundary:

- the producer performs the binding;
- ordinary consumers receive only a read-only dimension authority;
- the consumer cannot combine arbitrary source and visibility readers and call them one authority;
- the returned authority exposes query methods, not ingestion/publish methods.

A future separate-process deployment may implement the same contract behind a service boundary rather than a Python factory.

## 4. Required consumer query shape

The preferred public query is selector-based:

```python
width = dimension_authority.resolve_width(opening_selector)
height = dimension_authority.resolve_height(opening_selector)
```

The authority must independently:

1. call the producer-bound physical-opening authority for the selector;
2. fail closed if G17 existence is unavailable/conflicted;
3. obtain raw text/vector observations from the producer-owned store for the authenticated source scope;
4. require a valid figured-dimension relationship such as witness-bound geometry;
5. preserve competing figured candidates as conflict rather than choosing nearest/first/smallest;
6. keep width and height independent; and
7. return an inspectable result with producer-owned evidence identifiers and reason codes.

The public resolve methods must not accept caller-provided `width_mm`, `height_mm`, `figured_text`, `PhysicalOpeningExistenceRecord`, `SourceObservationRecord`, or an already-assembled evidence list as the object that proves its own authority.

## 5. Figured text and geometry

Reuse the adopted dimension machinery rather than creating a parallel parser/binder:

- `pb_figured_dimension_evidence` for typed text, line/witness association and ambiguity handling;
- `pb_figured_dimension_authority` for figured-value measurement resolution semantics;
- existing source observation / visibility records for immutable provenance.

A dimension string near an opening is not enough. Positive width requires the producer-owned relationship between the dimension observation and the physical opening geometry. Text-only, OCR-only without an authenticated transform, and unmatched witness geometry remain non-authoritative.

## 6. Height remains independently gated

Plan width authority does not imply height authority.

Height may remain unresolved when only a plan figured width is proven. Cross-view elevation height must not be attached to the plan opening unless a separate authority proves the required cross-view physical identity/equivalence. Schedule/type height likewise requires independently proven instance/type binding.

Merged #331 deliberately abstains across source/page/view scopes without separate equivalence authority. This document does not weaken that rule.

## 7. Downstream firewall

Even after a width resolves, all of the following remain separate and closed unless independently authorized:

- opening-universe completeness;
- host identity / host binding;
- physical void;
- opening deductions;
- net wall area;
- FIRM/commercial publication; and
- JobHub publication.

`PhysicalOpeningAuthority.capabilities()["opening_dimensions"]` remains false on this test-only base. A later typed dimension authority may expose its own capabilities without converting physical-opening existence/identity into dimension authority.

## 8. Test-first gate

The companion red-team suite must prove:

- current visibility authority cannot publicly read raw figured-text observations;
- raw native words do exist in the producer-owned source observation substrate;
- equal source hash/revision from two independent producers does not itself prove one producer binding;
- future dimension authority is created by the trusted producer boundary;
- its public resolve API is selector-based and read-only;
- a witnessed `900` can resolve width only through the producer-bound authority;
- schedule/text-only selectors cannot mint physical opening dimensions;
- plan height remains unresolved when only width evidence exists; and
- downstream capabilities stay closed.

## 9. Merge policy

**DO NOT MERGE production from this branch.** Keep the gate draft/test-only. A production implementation must be a separate PR and must pass the producer-boundary attacks unchanged before broader #336 dimension attacks can be treated as an implementation gate.

No benchmark gold/scorer/mapping/tolerance/denominator/holdout changes are permitted here. Development benchmark remains an observation only: `31/61 = 50.82%`.
