# Source edge projection for snapped raster wall frames

## Observed repository behavior

Read the agent contract, engineering playbook, adopted topology architecture,
wall/room specification, retired benchmark notice and CI contract. Traced
`build_wall_graph_for_viewport` → `_snap_geometry_indexed` →
`assemble_wall_topology` → `collect_physical_wall_identities` →
`_build_scope_result` in the physical wall producer, and host publication →
`OpeningHostFrameProducer._raster_binding_nodes` → `_shared_host_frame`.
W2 keeps source geometry on unmerged edges while node centroids can move at
junctions. W4 uses those node centroids for its path. Physical identities retain
edge IDs and primitive ancestry, but the sealed wall records currently omit
the corresponding edge geometry. A locally proven raster host can therefore
fail the frame's segment-direction check despite straight immutable source.

## Inference

The producer's complete edge fragments can establish a separate straight source
projection when every edge is authenticated against its exact visible raster
ancestor. An ancestor's full extent alone cannot establish which part belongs
to a particular wall candidate. Snapped path coordinates alone cannot explain
whether a bend is physical or reconstructed.

## Proposed change and authority boundary

Retain immutable per-candidate graph edge geometry and ancestry in the sealed
wall record. Do not change W2/W4 geometry, identities, equivalence or scope
completeness. For an otherwise rejected raster frame member, require a usable
simple candidate and complete bijective edge-ID coverage. Authenticate every
ancestral raster primitive in the exact document/revision/hash/snapshot/page.
Each edge must be exactly parallel to the opening, lie on every recorded source
ancestor and be contained in that ancestor; all edges must share one exact
normal offset and cover a continuous interval without interpolation. Require
the snapped chain to be monotonic, retain the same extent within the existing
snap bound, and remain within the same source band. Use the owned edge extent,
never a remote ancestor's longer extent. Curves, unknown ancestry, real source
bends, opposing offsets, gaps and damaged receipts retain abstention.

Re-prove this projection at both the local edge and whole-component gates.
Retain the exact visible observation IDs in frame evidence. Complete component,
positive DISTINCT and native-text exclusion gates still apply. This proves
only PDF-point geometry, not metric width, height, scale, counts, deductions or
commercial eligibility. Start with synthetic and source shadow replay, then
review the exact producer-owned promotion. The user's continuous-work instruction
supersedes the routine report review pause; it does not weaken evidence gates.

## Benchmark observations that must not influence implementation

One remaining development-source frame has straight source geometry and a W4
junction deformation. Two others are blocked by independently retained native
aligned opening candidates of different thickness. These observations identify
generic failures, not constants, exclusions or expected outputs. Preserve
frozen truth, scoring, denominator, source files and every unresolved ambiguity.

Required checks include synthetic positives and bent/curved/gapped/foreign-source
negatives; ambiguity, receipt tampering, transformation, input-order and segment
splitting invariance; stable replay and no mutation; unchanged quantities in
shadow; and an independent SHA-pinned source artifact.

## Additional observed source-integrity gap

The frame receipt-damage regression found that the ordinary raster visibility
readers authenticate geometry and parent lineage but accept a damaged render
DPI. The supplemental provenance helper currently returns true without checking
ordinary provenance; the native-text reader already rejects the same damage.
Extend the existing shared reader guard to authenticate the ordinary 144-DPI
detector version and image-hash reference too. Test both readers for missing or
damaged DPI, version, hash and geometry, without regenerating any source identity.
Recompute the existing segment and visible IDs from the receipted pixel/point
geometry, render hash, detector namespace and exact primitive index. This
authenticates those fields against the already-published identities; it creates
no new identity or namespace.

## Source shadow result and authority review

The SHA-pinned drawing shadow proves the six locally owned source fragments
behind the rejected snapped chain. Its local edge and component direction gates
then succeed, but the whole frame correctly abstains at
`opening_host_frame_aligned_fragment_distinctness_unproven`. Ten aligned
alternatives remain retained; pair evidence against the selected members is
absent for those alternatives. Some are remote image fragments and one is a
native fragment inside the aperture. Neither distance nor a plausible text role
is positive physical DISTINCT evidence. No source frame is gained from this
projection alone: swing hosts remain 7/7 and frames 4/7. Both other swing frames
still retain their independently discovered incompatible native opening bands.
All 21 raster physical IDs and seven area values survive the shadow replay.

The frame producer now separately authenticates the edge projection at the
local role and full-component gates and retains every exact visible receipt ID
in successful frame evidence. Existing complete-scope, component/path and
positive DISTINCT/native-text rules remain unchanged. Synthetic source-backed
snapped frames succeed; missing edges, foreign ancestors, source bends, gaps,
multiple offsets, backtracking, curves and damaged receipts abstain. The wall
record adds immutable edge facts without changing candidate geometry or IDs.
Ordinary and supplemental readers authenticate the existing frozen identity
payload and reject provenance damage. Independent published CI/source artifacts
remain required before claiming verified deployment.

Local validation: the expanded focused workflow passes 632 tests. Provider
isolation passes for all three production roots; frozen V2 integrity, compile
and whitespace checks pass. Published CI and source verification are pending.

Full CI exposed two detector-migration regressions in the first publication:
the ordinary reference check used the live detector version where the frozen
identity namespace belongs. Correct that distinction and include the existing
Task-3 identity/wall migration suite in the focused workflow. Render receipts
still verify the actual producer detector version; the namespace and IDs remain
frozen. Re-run full CI and source verification on the corrected head.
