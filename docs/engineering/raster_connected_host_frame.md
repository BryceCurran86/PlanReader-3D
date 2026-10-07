# Connected raster host-frame continuation

Read AGENTS, AI_ENGINEERING_PLAYBOOK, wall_topology_observability_architecture,
planreader_wall_room_topology_spec, planreader_public_tender_benchmarks and CI.

Observed: `OpeningHostFrameProducer.publish` first tries a one-member raster
whole-wall frame, then `_shared_host_frame`. `_scope_bindings` discovers openings
only through ordinary W4 visible IDs; isolated G17 raster receipts are absent.
`_binding_nodes` accepts four face members. Three source-band-bound openings in
the pinned production proof share consecutive W4 fragments but have two members.
The existing connected-component algorithm and its positive DISTINCT exclusion
gate are suitable; raster centerlines do not supply two wall-face offsets.

Inference: a raster frame can reuse that graph only after each edge is re-proved
from exact authenticated G17 support and its local W4 primitive owners. Uniform
sealed G17 band geometry supplies source-space center/thickness, while the
connected W4 component supplies extent. Neither local ownership nor geometric
alignment alone establishes whole-wall completeness.

Proposed: expose a snapshot addressing index for isolated raster receipts;
re-authenticate them before discovery; admit two-member graph edges only after
the existing source-band resolver independently reproduces the exact binding.
Require a simple connected path, matching band geometry, complete sealed W4
scope, and positive DISTINCT proof for every excluded aligned candidate against
every component member. Otherwise retain ABSTAIN with an exact first-failure
reason. Reuse the existing frame, status and stable-ID contracts. Vector frame
behavior and the one-member raster route remain unchanged.

Expected abstentions: stale/tampered receipts, incomplete scopes, unbound aligned
openings, unreproven source membership, branches/cycles, inconsistent band
geometry, and aligned fragments without positive DISTINCT evidence.

Benchmark observations: the recovered swing count and area values locate the
failure only. They do not set algorithm parameters, frame bounds, dimensions,
quantity counts or joins. V2 truth, scoring, tolerances, source manifests,
measurement and commercial publication gates, and other agent lanes are not
changed. The user's handoff authorizes continuing implementation and proof.

## Source proof

144 focused tests pass: the complete sealed-producer synthetic chain resolves
two openings on one shared three-fragment frame. Translation, rotation, scale,
unrelated content, source receipt integrity, incomplete scope, branch/cycle,
competing aligned fragments, replay, order, segment splitting and no-mutation
checks pass. Source-space frame proof supplies no metric quantity.

The exact Lot16 source replay verifies SHA
10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844.
Hosts remain 4/7; whole-wall frames remain 1/7. The three two-member bindings
now reach opening_host_frame_aligned_band_geometry_inconsistent. Ordinary
G17 openings aligned with the raster component have incompatible thickness;
their physical relationship cannot be excluded merely by structural pattern,
distance, or detector namespace. ABSTAIN is retained. The diagnostic records
the exact competing source identities and geometry for the next ownership step.

Widths/heights remain 0/7 at witness topology and schedule-instance coverage.
The seven sealed areas remain 0.54, 0.90, 1.26, 1.80, 2.16, 2.16, 10.08 m².
Provider isolation, V2 truth integrity, compilation and whitespace checks pass.
The missing 5.67 m² two-face host conflict and exact V2 reconciliation inputs
remain as documented in raster_swing_host_source_proof_v2.md. Keep draft.
