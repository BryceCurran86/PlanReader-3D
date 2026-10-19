# Opening source-proof repairs

Delivery ledger: GitHub issue #3161, items 02–12. This report records a repair
batch, not completed merges or authority promotion.

## Repository trace

Read AGENTS.md, the AI engineering playbook and its required topology,
benchmark-separation and CI documents, and the accuracy-levers agreement.
The affected path is `compose_live_wall_opening_authority` →
`OpeningHostBindingProducer.publish` → `OpeningHostFrameProducer.publish` →
physical-opening composition. Local source frames are separate CANDIDATE
review projections; they never enter the positive frame authority.

## Observed behavior

Main #3151 accepted an unusable, source-unmapped perpendicular candidate in
place of a missing solid flank. Its single-member frame fallback accepted a
local binding after whole-wall reproof failed and expanded the wall extent to
contain the opening. Existing frame tests regressed from 15 passes to 13
failures. Missing type imports also failed F821 checks.

The image-placement fallback extrapolated a transform from a partial overlap.
Supplemental record merging selected an ordinary record first when the same
wall ID described conflicting geometry. Pair lookup selected the final
classification; equivalence lookup selected the first overlapping group;
graph sets collapsed distinct opening edges sharing the same flank nodes.
Local review-frame validation omitted parts of selector lineage and the
orthonormal-basis check used by the positive frame publisher.

An original-source replay on #3143 produced two Lot16 quantities. With the same
pinned dependencies, historical producer 4e5aedf reproduced the archived eight
and exact archived fingerprint. Disabling the newly unconditional double-face
negative in a diagnostic experiment restored the historical opening universe.
That predicate had entered the default path without a separate source policy.

## Inference and implemented boundary

A candidate return cannot establish missing source ownership. A local binding
cannot establish whole-wall completeness. Two agreeing image scales cannot
establish coverage over unpainted image-placement space. Conflicting evidence
cannot be resolved by input order.

The batch restores independently reproved whole-wall bounds and both solid
flank owners. It isolates double-face negatives behind an explicit default-off
source policy, checks policy immutability, and preserves this isolation across
native source forks. The original production capture continues to require an
owned area; single-axis supplemental materialization and supplemental frame
wiring stay in their explicit unmeasured source shadow.

New tile-union coverage and strict collinearity analysis are opt-in shadows.
Strict projection may use the existing authenticated source-edge projection to
explain raster snap drift; it never fabricates a span. Scope, duplicate-record,
equivalence, graph and local-frame checks retain conflicts or withhold frames.

Expected abstentions: unmapped return, truncated/off-center host, uncovered
tile strip, competing transforms, incompatible source scopes, conflicting wall
records, overlapping equivalence groups, contradictory pair classifications,
parallel graph edges with distinct openings, stale selector, invalid basis.

## Validation and release status

Synthetic cases include positive controls, look-alike negatives, order and
translation checks, exact replay, no-mutation checks, and retained source-edge
recovery. Existing negative assertions remain; double-face tests explicitly
enable their experimental source policy.

The repaired default source policy reproduced the Lot16 archived
`source_sealed_run.json` and `verified_customer_rows.json` byte for byte, with
fingerprint ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb.
This is an intermediate working-tree replay. Final-head CI and source retention
must be recorded separately. Maryborough source retention is still under
investigation; it is not claimed passed.

No source PDF, frozen truth, identity map, scorer, tolerance, archived signed
receipt, 20,000-primitive cap, global 2.5pt snap, W10 eligibility or JobHub gate
is edited. Source counts and fingerprints above are post-producer retention
observations, never detector inputs or algorithm thresholds.
