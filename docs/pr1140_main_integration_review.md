# PR #1140 integration review

## Observed repository behavior

Current main was fetched at `882c53eca59a16323f30a921ba6b4441abd80577`.
The existing PR head is `0d03f704b045cdf261d4a4c10b4cbf1e96981704`.
Merging main produces two conflicts in `pb_planreader_pdf_extractor.py`:
extractor initialization and per-document state reset. The PR adds declared-area
diagnostics; main adds canonical family state and original coverage quantities.
Both additions are required and are independent of each other.

The existing authority correction follows
`GenericPlanReaderExtractor.extract_from_pdf` ->
`extract_explicit_floor_area_evidence` -> `declared_floor_area_claims`.
`resolve_explicit_floor_area_evidence` resolves repeated declared values only.
Physical dimensions continue through `_detect_outer_envelope` and
`MultiSpaceFootprintBuilder`. The original PR's
`reconcile_orthogonal_envelope_against_declared_area` runs after that producer;
its declared-area result does not select dimensions or replace the reconstructed
structural bed area. The former `resolve_orthogonal_envelope_evidence` selector
returns no geometry. Current main's typed canonical producers and AG-09 original
quantity sink must remain present after this merge.

## Inference

The conflicts are adjacent state additions, not competing quantity algorithms.
Combining both sides should preserve the authority correction and current
canonical coverage, but targeted tests and final-head regression must prove it.
The private source runtime gate is still outstanding; earlier CI cannot replace
that gate.

## Proposed narrow integration

Keep declared-area diagnostics alongside all current canonical fields, and
reset declared claims together with the per-document coverage state. Preserve
the PR's existing eight-file authority scope. Add no source-name branches,
default geometry, new room architecture, scale resolver or quantity path.
Run synthetic authority-boundary tests first, then the hash-verified private
source through the normal extractor and capture completed downstream outputs.
Retain abstentions and discrepancies. Run wider CI and performance gates after
the final tree is committed and published.

## Source and benchmark observations

The review requests an exact private source with SHA-256
`014e9f68b377bef4fb556de61b83a94388792dfa4bfb8ea981644f9c323e9e2e`.
The printed aggregate is an observed declared claim, never an expected input
to extraction. Source names, aggregate values, benchmark identities and scores
must not influence implementation. Benchmark truth, golden files, mappings,
scoring, acceptance rules, VR UI and costing remain outside this integration.

Maryborough room integration is a subsequent task: independently verify source
closure before using its report as customer-publication evidence. Report major
room architecture or accuracy failures rather than redesigning that stack.

## Validation recorded before publication

The integrated tree passed 114 targeted authority-boundary, declared-area,
orthogonal-envelope, DPM, canonical-coverage and customer-source-scope tests.
V2 truth separation/integrity, provider gold isolation, Ruff F821/F823 and diff
checks passed. The comparison against current main retains only the intended
eight implementation/test files plus this integration report; inherited main
truth updates are not new edits by this PR.

An additional 20 canonical-state-reset, extractor-observability, startup,
processing-cache and runtime-rerun performance tests passed.

The exact private PDF was recovered and its required SHA-256 verified, with
5,157,446 bytes and 18 pages. Native text on page 3 exposes a declared FLOOR AREA
claim. The normal full extractor was attempted with diagnostic progress and
stack capture. The host's automatic approval review stopped it for attempted
outbound telemetry while processing the private source, even after using the
dependency's supported telemetry-disable API. No completed result or numeric
downstream quantities exist from this run. A network-isolated user namespace
was also unavailable on this host. This is an execution block, not evidence
that the production geometry/quantity gate passed or failed.

The exact-source acceptance gate remains OPEN. Do not merge or mark full source
runtime parity proven until a permitted offline run completes and its observed
outputs are reviewed. No source PDF, expected quantity, benchmark rule or
authority override is added to production to work around this host block.
