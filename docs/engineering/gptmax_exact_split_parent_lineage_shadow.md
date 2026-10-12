# Exact split-parent lineage in shadow — architecture review

Observed on main 8df13e08: `split_segments_at_intersections` emits each fragment
inside its original source segment's loop, but returns geometry pairs alone.
W2 `_point_pairs_to_segment_dicts` therefore asks
`attach_lineage_to_split_fragments` to reconstruct all source parents by
containment. `fragment_contained_in_segment` deliberately rejects fragments
at or below the existing 1e-5 pt containment allowance. Ten positive splitter
slivers in the independently replayed exact-endpoint W2/W4 shadow consequently
have no source parent and keep ten actual assembly records abstained. Geometry
and original source bytes are retained; no nearest source is admissible.

Inference: the splitter's own emitter index is original derivation ancestry,
not a geometric nearest-parent hypothesis. Capturing that index at emission
can preserve known source ownership without changing the containment predicate,
snap allowances, geometry, graph connectivity or W4 constructor guard.

Proposed: an optional empty output list on the existing splitter, recording the
exact source input index for each emitted pair. Only an explicit W2 shadow flag
may union that original emitter's existing primitive_lineage into the fragment.
Validate count/index/type, positive finite geometry and original endpoint
containment with the existing allowance. Existing plural geometric parents
remain retained. Default splitter/W2 callers remain byte-identical. The source
shadow orchestrator exposes this opt-in separately; it does not enter live
physical wall/opening/quantity composition.

Expected abstentions: original source bytes and view/structural wall meaning
remain independent prerequisites. Derived ownership does not establish wall
role, physical equivalence, opening host, metric dimension or candidate-universe
completeness. Ambiguous/non-simple W4 chains remain explicitly abstained.

Validation: focused positive/negative, sub-tolerance, plural-parent, corrupt
provenance, metamorphic, deterministic and no-mutation checks; original source
replay must retain the entire default 21/14/9 production receipt and exact shadow
nodes/edges/assembly partition while reauthenticating each recovered source
parent from the original input. Frozen V2 truth/scoring/denominators/tolerances,
W10, commercial writers and the 20,000-input primitive bound remain untouched.
No benchmark quantity or source coordinate defines implementation behavior.
