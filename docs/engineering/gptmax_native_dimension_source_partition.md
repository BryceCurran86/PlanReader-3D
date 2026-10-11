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
uses six supports across two separate dimension chains. The existing
component compiler covers four supports. It leaves these two on the lower
chain uncovered:

- `source_observation_365be490820455db4ed5a612e88775fe`
- `source_observation_d118d71458996fc12c8808f6593fb0d1`

The lower native word is `90450`, owned by
`source_observation_f7fc0125971b2b0d833b7c8a68168dd7`.
Its original text-integrity receipt is ABSTAINED with
`text_trace_unavailable`. Original text paint command 954 contains `90`;
command 956 contains `450`. Between them, command 955 is a fill path with
source bbox `[1016.8800048828125,584.760009765625,
1028.6400146484375,593.6400146484375]`.

The audit retains that exact partition and negative receipt. Neither raw
numeric text nor the paint partition enters the component compiler without
the existing text authority. Both supports remain uncovered, complete shadow
opposition is false, and the original live hypothesis is unchanged. This
case is **not closed** by the new diagnostic.

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

Fresh local head source replay retained all 23 opening claims, all 14 host
receipts and all nine frame receipts from the independently recorded
unchanged `9dc7125` source report. The unchanged strict comparator passed
with zero lost or changed host/frame proofs. Provider isolation, V2 integrity,
Ruff F821/F823 and workflow YAML/inline Python checks passed.

The original-source CI gate replays the exact PR-base and head opening
reports, uses the unchanged strict retention comparator, and requires exact
old opening, host and frame payloads. It pins the original PDF digest and
retains the original 23/14/9 control. It separately requires the exact
negative text receipt, two uncovered supports and original intervening paint.
Keep this PR draft until exact-head source and ordinary CI pass.

The source-opposition branch's full-suite result was 11,190 passes, 51 skips,
13 expected failures and one schedule-identity failure independently
reproduced on unchanged `9dc7125`. That result does not certify this branch
or waive any required CI check.
