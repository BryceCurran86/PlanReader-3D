# GPT MAX — terminal source span preview, isolated hypothesis

Observed functions: `_snap_geometry_indexed` collapses the two original
endpoints into one node; `assemble_wall_candidates` retains surviving edges;
`resolve_physical_wall_identity` and `_path_from_edges` derive a physical
candidate source path from those edges. The endpoint audit in PR #2182 exposes
the actual lost source geometry and node associations without graph mutation.

Inference: a lost terminal fragment with one exact same-source adjacent owner
can reproduce the old source candidate path. That is a candidate-identity
hypothesis, not authority to merge walls, extend a host or recover a frame.

This isolated pure preview requires an exact connected nonbranching raw path,
one source ancestor, one owner and exactly one shared terminal endpoint. The
extension must continue an exactly straight monotonic path outward; a tiny
off-axis deviation is skipped conservatively, without choosing a tolerance.
Missing node assignments, duplicate identities, competing owners, internal
gaps, disconnected paths, turns, overlaps and near endpoints cannot supply a preview. It uses
the existing path fingerprint and stable candidate identity function. It does
not read a benchmark, alter W2/W4 or return an authoritative wall object.

Caller must independently authenticate that the W2 trace and wall records
belong to one source scope. Serialized diagnostic fields alone do not prove
that association. The preview explicitly grants no physical-equivalence,
graph, host, opening-count, frame, measurement or quantity authority.

Original source inspection of archived experiment `1ca637b3`, PDF SHA
`10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`,
finds one exact endpoint owner for each motivating terminal fragment.
Reconstructing these exact source paths with the existing identity function
reproduces `wall2_7d5ea2aeef89c298a272` and
`wall2_3eab70ec4af1a6110deb`. Those comparisons occur after derivation and never
choose an owner or algorithm threshold. The 2pt interior snap-loss interval
at source `:1567` is intentionally ineligible for a terminal preview.

This hypothesis remains separate from the proposed production diagnostic
#2182 and the blocked compact-capture #2161. Any subsequent W4/source-host
change needs synthetic/metamorphic tests, actual source revalidation,
strict original host/frame retention and a separate authority review.
Frozen V2 truth, quantities, default geometry and the 20k primitive cap stay
unchanged. The preview is not an accuracy improvement or a DONE milestone.

## Validation of the isolated preview

46 focused tests pass locally on Python 3.12.14. They cover exact ownership,
competing unresolved owners, same-parent conflicts, overlap, backtracking,
turns, disconnected and cyclic paths, invalid actual endpoint assignments,
mixed viewports, nonfinite and oversized geometry, replay without mutation,
orientation and order invariance, exact collinear rechunking, rotation,
reflection, translation, scaling, unrelated content and viewport expansion.
Undefined-name and whitespace checks pass.

Applying the pure preview to the independently re-executed archived source
trace reproduces these two original identities after derivation:

| Lost source fragment | Current source candidate | Derived original source candidate |
| --- | --- | --- |
| `split_1462` (`:1585`, 1.22pt terminal span) | `wall2_544ebbb9d0acaaab0a51` | `wall2_7d5ea2aeef89c298a272` |
| `split_1732` (`:324`, 1.90pt terminal span) | `wall2_87c9674a639061b3cf45` | `wall2_3eab70ec4af1a6110deb` |

Trace SHA-256: `e1cb84cab9813d2e1280c7a3c98f68fad78298362a4eb7de92f0c96064034ce4`.
The original paired reference is Actions run `38068100685`, artifact
`11675407730`. These identifiers are review evidence only; the preview module
and its tests contain no project-specific IDs or expected benchmark values.

The generic preview emits 134 independent path hypotheses across this scope.
It skips 45 disconnected source paths, 50 nonstraight/outward extensions,
69 noncollapsed fragments, 218 unavailable/ambiguous endpoint owners and
87 owners without corroborated single-parent lineage. No preview is emitted
for the motivating interior interval at `:1567`. These census values describe
the diagnostic, not recovered walls, hosts, frames or accuracy.

This broader census also prevents shipping a selective two-ID patch: changing
the identity authority generically would affect other source candidates and
must be validated against the complete original retention gate in a separate
shadow experiment.

## Proposed runtime association check before implementation

Observed: the physical-wall producer's `_assemble_scope_result` passes its
actual W2 graph and assembled walls into `collect_physical_wall_identities`,
then writes those original identities and edge geometries into the scope's
records. The scope's `decision_scope_id` equals the wall identity viewport;
its source SHA, revision and snapshot identify the original published source.

Inference: a read-only wrapper at that existing call can link the endpoint
trace and wall records without pairing unrelated serialized files. Proposed
shadow diagnostic: observe the real graph object and its identity-collection
call; derive previews from copies; return every original graph and identity
object; verify the resulting scope's source/page/revision/snapshot and exact
candidate records before exposing the preview. Missing, duplicate or foreign
associations fail closed. The wrapper cannot grant physical equivalence or
host/frame/quantity authority. Benchmark IDs and expected counts never choose
an association. Default prediction and complete source-report parity remain
required in the real PDF run.

## Runtime association validation

20 additional runtime tests pass (66 tests with the pure preview suite).
Missing graph calls, reused graph objects, duplicate identity calls, changed
source geometry, foreign candidate records, documents, pages, revisions and
snapshots fail closed. Original graph/identity objects and environment state
are retained on both successful and failing diagnostic calls.

The actual Lot16 run observes one producer assembly call with all 2,094
original candidate identities. The complete source report equals the default
published-tree report; the unchanged strict retention checker passes, with
23 openings, 14 hosts and nine frames. All source document, hash, page,
revision and snapshot fields agree. Its ordinary W2 graph fingerprint equals
the endpoint-only trace: `b813c6aa609139c783db09477f4a068e1c2198c14e3821eda48a91817a31d334`.
It produces 126 independent terminal hypotheses on the unchanged baseline,
without replacing any candidate or granting authority.

The archived blocked experiment was independently replayed through the same
runtime observer, with actual indexed-snap graph equality asserted before
attaching the observational sidecar. Its one producer assembly call contains
2,101 original identities and 134 terminal hypotheses. Both motivating
fragments reproduce their original IDs inside that actual source scope.
All source-report fields reproduce the archived experimental result
(23 openings, 18 hosts, nine frames), while strict original retention still
fails. Original graph, assembly and identity objects were never repaired.
The interior `:1567` interval still emits no terminal preview.

Archived ordinary graph SHA-256:
`44e1596327c0ca01d2fef98e026d4db2f03f369e7fb32ffcf0fdbef58d331c55`.
Runtime diagnostic report SHA-256:
`19348c33f885e12436d5c75c5a498e59c537633a628c4459fd764ab9f59c90d9`.
The source association is observed and checked; physical equivalence, receipt
migration, graph extension and commercial publication remain unauthorized.

Current main's newly merged read-only source-host rekey ledger (#2178) was
also run against the original archived pair. It classifies ten old hosts as
unchanged W4/frame source with unapproved receipt rekeys, and four as source
proof requiring review: three changed W4 membership groups and one changed
ABSTAIN frame reason. Neither this ledger nor the source-path preview accepts
those receipts. This preserves the interior-gap negative for separate review.
