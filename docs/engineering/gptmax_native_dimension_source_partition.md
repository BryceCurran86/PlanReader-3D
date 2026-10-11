# Native dimension text paint partitions: source ownership audit

## Architecture and authority boundary

Observed: `SourceVisibilityProducer.native_dimension_cap_evidence` authenticates
native geometry and text receipts before calling
`compile_native_dimension_cap_components`. The latter requires owned numeric
text, paired ticks at both terminators and perpendicular witnesses covering
every selected opening support. Partial coverage cannot oppose an opening.

`PdfTextIntegrityAuthority.resolve_text` preserves failed source receipts as
ABSTAINED. In `pb_pdf_text_integrity_authority._owned_span_chain`, a word
assembled from separate text spans requires consecutive paint sequence
numbers. An intervening paint prevents that complete word receipt from
becoming trusted. Geometry proximity cannot repair this boundary.

The proposed diagnostic reads the same original PDF bytes, authenticates
visible native supports and every text observation, and independently maps
original raw glyph origins to complete text paint commands. Commands must
own consecutive characters, with every original character covered exactly
once. It retains all complete partitions and their intervening paint
commands. It neither guesses a numeric substring nor changes a text receipt.

Only partitions whose word already has CORROBORATED text integrity and whose
complete paint command sequence exactly matches that receipt may enter the
existing component compiler in shadow. Untrusted partitions stay explicit
negative audit records. The diagnostic proves no physical nonexistence,
deletes no hypothesis and supplies no live host, scale, count or quantity.
It reruns the live candidate before and after the audit and rejects any
change. Production modules and the strict source comparator are unchanged.

An inference from the source trace is that a future text-authority task could
examine whether an intervening command is proven disjoint from all earlier
owned glyphs. This diagnostic grants no such authority and does not relax
the consecutive-command rule or any clipping/font/visibility check.

Drawing names, physical IDs, observed counts and benchmark quantities occur
only in the source gate and this report, never in the partition algorithm.
Frozen V2 truth, evaluator, denominator, tolerances and the 20,000 input
primitive cap remain unchanged.

## Original-source observation

Original PDF SHA:
`10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`,
page 3. Source baseline: `5de14446b5909cd6f2982e8691525bda0568a9b6`.

The original hostless native hypothesis
`physical_opening_existence_415d34ddc0c7591b181ddadc11aefe1d`
uses six supports across two separate dimension chains. The earlier historical compiler snapshot covered only four supports and
left these two on the lower chain uncovered (this is **not** the current
source-authenticated producer state):

- `source_observation_365be490820455db4ed5a612e88775fe`
- `source_observation_d118d71458996fc12c8808f6593fb0d1`

The lower native word is `90450`, owned by
`source_observation_f7fc0125971b2b0d833b7c8a68168dd7`.
Its original text-integrity receipt is ABSTAINED with
`text_trace_unavailable`. Original text paint command 954 contains `90`;
command 956 contains `450`. Between them, command 955 is a fill path with
source bbox `[1016.8800048828125,584.760009765625,
1028.6400146484375,593.6400146484375]`.

The audit retains the exact raw partition and negative text-integrity receipt.
Neither the raw `90450` word nor its separate paint commands acquire a
corroborated numeric receipt. However, **current original-source replay**
[run 38149315040](https://github.com/BryceCurran86/PlanReader-3D/actions/runs/38149315040)
found a *different complete source-owned dimension-opposition path* using
already trusted text and real line/tick topology: 254 unique **CANDIDATE**
dimension-opposition atoms cover all six original supports. Both historically
uncovered supports are now covered in the shadow diagnostic. The original
live producer had already abstained from publishing an opening for this
native look-alike; `existence_record_id` is null, and the live producer state
remains unchanged. Candidate opposition is **not physical nonexistence proof**,
a wall host, an opening count, a quantity, or a V2 scoring result. The audit
itself is nonpublishing and must never upgrade the untrusted `90450` text.

There are 1,727 authenticated native visible segments in this page scope;
that is a source observation count, not a wall or opening count.

## Verification

152 new audit, existing dimension and PDF text-integrity regressions passed
(86 in the initial focused audit/dimension run). Tests cover
fresh synthetic PDFs with trusted consecutive numeric paint commands and
untrusted intervening fill paint; exact glyph and receipt ownership; partial
coverage; overprint and competing command ambiguity; cross-word source;
invisible, translucent and mismatched direction; numeric look-alikes;
translation, scaling, rotation, input order, unrelated content; deterministic
IDs; no input mutation; and unchanged live candidate state. The trusted
synthetic positive can nominate complete CANDIDATE opposition in shadow;
the untrusted source case cannot.

The earlier 23-positive G17 claim snapshot applied before source-authenticated
native false-positive opposition was merged. The current original source run
retains **21 positive opening hypotheses, 14 authenticated hosts and nine
frames**, with the original PR-base and candidate reports identical and strict
retention passing with zero changed or lost host/frame proof. Existing paint
partition tests still require exact glyph/paint provenance and no change to
live production claims.

The original-source CI gate replays the exact PR-base and head opening
reports, uses the unchanged strict retention comparator, and requires exact
opening, host and frame payloads, original PDF SHA and the original **14
authenticated hosts / nine frames**. It retains the exact negative raw `90450`
paint receipt and intervening paint, but separately requires the current
source-authenticated complete *candidate* dimension opposition and six-source
support ownership. Keep draft until latest-head original source, focused and
full CI pass.

The source-opposition branch's full-suite result was 11,190 passes, 51 skips,
13 expected failures and one schedule-identity failure independently
reproduced on unchanged `9dc7125`. That result does not certify this branch
or waive any required CI check.
