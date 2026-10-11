# Zero-endpoint indexing shadow

## Architecture report before implementation

Read `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md` (including §13),
`docs/wall_topology_observability_architecture.md`,
`docs/planreader_wall_room_topology_spec.md`,
`docs/planreader_public_tender_benchmarks.md` and `.github/workflows/ci.yml`.

Observed repository behavior: the original byte-authenticated source reader
feeds `_trace_sources`, then `build_wall_graph_for_viewport`, intersection
splitting and source-parent attachment, `_snap_geometry_indexed`, collinear
merging, W3 deduplication/classification and W4 assembly. Positive endpoint
tolerances use the existing spatial index. Zero/negative tolerances delegate
to `pb_vector_geometry_v130.snap_geometry`, whose endpoint lookup scans every
current node. A bounded, stage-instrumented full-page legacy replay is being
run to distinguish source attachment cost from endpoint lookup cost.

Inference: the zero-tolerance full-node scan may prevent a practical full-page
control for the local fragment-bundle hypothesis. Local survival does not
prove full-page survival; full-page topology does not prove a physical wall.

Proposed change: an explicit boolean **shadow-only** opt-in reuses the existing
endpoint spatial index at tolerance zero. An index bin is only a lookup aid;
the unchanged distance predicate still requires distance exactly zero. Keep
ascending existing node IDs, strict distance comparison, running-centroid
arithmetic, original segment traversal, collapsed-edge behavior and all
lineage. This is not a second snapper, splitter, graph or scale resolver.
The default zero-tolerance path and every positive/negative tolerance path
remain unchanged. Nonfinite zero-mode inputs retain the historical fallback;
overflowed centroids cannot match finite endpoints and must leave the index
without changing their graph records. Preserve the legacy zero-mode absence
of endpoint-assignment metadata, including when that audit was requested.

Synthetic proof must compare the entire graph directly against the existing
legacy snapper, including decimal centroid drift, signed zero, subnormal and
huge coordinates, duplicate/coincident inputs, metadata, permutations,
splitting, transformations, unrelated content, replay and no mutation.
A sparse-distance-call test will establish bounded lookup work rather than
asserting a machine-dependent runtime. Invalid opt-ins must fail explicitly.

Original-source shadow replay will freshly authenticate PDF bytes and all
ordinary/positive-pixel observations, retain identical full-page inputs for
default and indexed-zero controls, and repeat the established production
opening census before/after with exact whole-report equality. Reuse existing
flank/contact/interval diagnostics. Full-page legacy-zero equality must stay
explicitly unproved unless an entire legacy-zero replay actually completes;
synthetic/local equality is not a substitute for that claim.

Authority review: every new source graph, fragment bundle and W4 alternative
remains nonpublishing. Structural role, authenticated floor-plan scope and
physical equivalence must still abstain. No production caller opts in. All
measurement/publication modules, W10 eligibility, frozen V2 truth, evaluator,
denominators, tolerances and the 20,000-input-source limit stay untouched.

Benchmark/source observations excluded from implementation: original source
SHA, opening identities, fragment counts and drawing names are validation
controls only. None may tune lookup eligibility or select a representative.

## Bounded original-source profile

The untouched legacy-zero full-page trace was stopped by its explicit
60-second profiling budget, not interpreted as absent geometry. Intersection
splitting completed in 0.43 s (10,099 inputs → 62,732 fragments); source-parent
attachment completed in 12.88 s. Endpoint snapping had not completed after
46.67 additional seconds when the budget expired. These local timings identify
the active stage, not a universal speed claim or whole-page legacy result.

## Initial synthetic evidence

173 new/related regressions pass locally. The zero-index option preserves
exact complete legacy snap output under seeded duplicate/decimal mixtures,
input permutations, transformations, graph splitting, subnormals, signed zero
and arithmetic overflow. In particular, repeated `0.1` endpoints still create
the historical extra node when the running mean drifts; ideal coordinate
hashing would change that result and is not used. Nonfinite input falls back
to the actual legacy callable, and existing zero callers remain on legacy
unless explicitly opted in. Sparse 5,000-segment verification counts distance
calls instead of asserting a hardware-dependent elapsed time.

Original-source replay and exact-head CI are required additional gates. This
change cannot publish physical hosts even if fragment geometry survives.
