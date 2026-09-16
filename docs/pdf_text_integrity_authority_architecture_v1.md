# PDF Text Integrity Authority — architecture report (test-first)

**Status:** architecture + adversarial tests only. No production implementation authorized.

**Exact base:** post-#331 `main` `507c57db16be515e2432c695341bdea1e71b3fd7`.

**Issue:** #330 — authenticate PDF text encoding and fail closed on broken CMaps.

## 1. Decision

A native PDF word existing in producer-owned source is **not yet equivalent to trusted semantic text**.

The authority chain must keep these propositions separate:

`source bytes exist ≠ native word object exists ≠ text decoded correctly ≠ text is visible ≠ text is semantically authoritative ≠ opening dimension is authoritative`.

Until a reviewed producer-owned text-integrity/visibility authority exists, figured text such as `900` must not become FIRM opening-dimension evidence merely because PyMuPDF returned it from `get_text("words")`.

## 2. OBSERVED on current main

### 2.1 Source observation producer already owns the source boundary

`SourceObservationProducer.ingest_native_pdf_bytes()`:

- hashes the exact immutable PDF byte buffer;
- owns document/revision/source-SHA identity;
- stores the immutable source bytes internally;
- creates producer-owned snapshots;
- emits `native_pdf_word` observations containing raw text and bounding boxes;
- validates snapshot membership and observation payload fingerprints on read.

`SourceObservationAuthority.resolve()` can therefore prove that a native word observation exists in the authenticated source snapshot. It does **not** prove that the Unicode decoding is correct or that the word is visible.

### 2.2 Source visibility currently authenticates vector segments only

`SourceVisibilityProducer` reopens the same immutable bytes and publishes visibility receipts for eligible vector segments as `native_pdf_visible_segment` observations.

`SourceVisibilityAuthority.resolve_visible()` validates those producer-owned segment receipts and their native parents.

There is no corresponding producer-owned trusted/visible-text receipt or public text resolver on current main.

### 2.3 Native vector extractor returns raw words

Current-main `pb_vector_geometry_v130.extract_native_page()` returns `words` directly from `pdf_page.get_text("words")`.

It does not expose the stale-branch concepts `authority_words` or `text_visibility_diagnostics` on current main.

### 2.4 Figured-dimension parsing is intentionally generic, not a text-integrity gate

`pb_figured_dimension_authority.parse_figured_dimension_mm("900")` correctly parses to `900.0` mm. `pb_figured_dimension_evidence` can also classify native text and bind it to vector witness geometry.

Those modules answer measurement grammar/binding questions. They do not independently authenticate PDF font encoding, `/ToUnicode`, glyph semantics, or text visibility.

### 2.5 OCR remains a separate provenance route

`pb_drawing_ocr_evidence_layer` distinguishes native text from raster OCR and keeps uncertain OCR provisional/unresolved. OCR must not be relabeled as native text or silently used to repair native decoding without retaining separate provenance.

## 3. Authority gap

Issue #330 is the missing boundary between source-word existence and semantic use.

A future positive text result needs producer-owned evidence sufficient to establish, for the exact document/revision/source/snapshot/page:

1. the word came from the authenticated immutable PDF bytes;
2. text decoding is trustworthy for the relevant font/glyph run;
3. malformed or unsupported character maps did not fabricate the Unicode string;
4. Type-3/vector-glyph content is not mistaken for ordinary trustworthy text;
5. text is not proven occluded and visibility is not unresolved;
6. OCR fallback, if used, retains independent raster provenance and confidence;
7. native/OCR contradiction cannot strengthen authority.

## 4. Required fail-closed cases

The producer-owned text authority must explicitly handle:

- missing `/ToUnicode` or otherwise insufficient decoding evidence;
- malformed CMap / invalid mapping data;
- control/unprintable/replacement-character output;
- visual glyph versus encoded-Unicode disagreement;
- Type-3/vector-glyph text;
- text hidden or occluded by later opaque drawing operations;
- unresolved clip/visibility state;
- OCR/native provenance separation;
- low-confidence OCR fallback;
- native-versus-OCR conflict;
- document/page/revision/source-SHA/snapshot laundering;
- deterministic replay under identical immutable source bytes.

Absence of a trusted text result must remain `ABSTAINED`/`BLOCKED`; contradiction must remain `CONFLICT`. Neither may fall back to a guessed dimension.

## 5. Preferred production shape — not implemented here

Reuse the existing source producer/query boundary. Do not introduce a caller-certifiable parallel framework.

A reviewed implementation may extend the current source-visibility pipeline with producer-owned text-integrity receipts and a read-only resolver (exact API name to be reviewed). The producer must derive those receipts from the same immutable source bytes already owned by `SourceObservationProducer` / `SourceVisibilityProducer`.

The consumer-facing result should carry at least:

- exact source scope (document, revision, source SHA, snapshot, page);
- source word observation identity;
- trusted decoded text only when proven;
- decoding/integrity state;
- visibility state;
- provenance route (`native` versus `ocr`);
- conflict/blocking reason codes.

Caller booleans such as `trusted_text=True`, caller hashes, caller font names, caller-supplied decoded strings, or caller OCR confidence must not mint authority.

## 6. Relationship to opening dimensions

This lane is a prerequisite only. Even a trusted text receipt does not prove:

- that the text is a dimension;
- that it is width versus height;
- that it belongs to a particular opening;
- that witness geometry binds it to opening jambs;
- host wall identity/binding;
- opening-universe completeness;
- physical void;
- deductions, FIRM/commercial output, or JobHub publication.

The post-#331 dimension validator is PR #336. It must remain DRAFT/test-only while this text-integrity prerequisite is unresolved.

## 7. Reuse of stale PDF visibility research

Draft PR #295 contains useful test-first ideas for:

- Type-3 glyph-vector quarantine;
- text occlusion by later opaque fills;
- clip-aware visible geometry;
- Form/XObject transform diagnostics.

Those tests are on a stale non-main base and are not current authority. This lane may reuse their adversarial concepts, but must replay them from current `main` and must not assume their unmerged production surfaces exist.

## 8. Benchmark firewall

Development telemetry remains **31/61 = 50.82%**.

This lane must not change benchmark gold, scorer, mappings, tolerances, denominator, frozen holdouts, live prediction outputs, commercial publishing, or JobHub.

## 9. Merge policy

**DRAFT / TEST-ONLY / DO NOT MERGE.**

Production remediation belongs in a separate reviewed branch after this gate is validated. No opening-dimension production code is authorized by this document.
