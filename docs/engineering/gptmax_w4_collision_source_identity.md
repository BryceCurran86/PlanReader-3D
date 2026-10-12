# W4 identity collision — source-first repair proposal

## Observed (2026-10-11)
Read AGENTS.md, docs/AI_ENGINEERING_PLAYBOOK.md, docs/wall_topology_observability_architecture.md, docs/planreader_wall_room_topology_spec.md, docs/planreader_public_tender_benchmarks.md, .github/workflows/ci.yml, pb_wall_room_topology_wall_assembly.py, pb_physical_wall_identity.py, pb_physical_wall_candidate_authority.py and pb_opening_host_binding_authority.py.

Producer authority path: immutable source visibility → W2 build_wall_graph_for_viewport → W3 classify_junctions → W4 assemble_wall_topology / assemble_wall_candidates (first wall candidate IDs) → collect_physical_wall_identities (keyed by wall_candidate_id) → _assemble_scope_result → resolve_physical_wall_equivalence → source-local host binding.

The current W4 ID intentionally hashes geometry but not U1 source ancestry. Real original Maryborough source SHA b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007, page 7, produces 3,737 W4 records and 3,736 unique IDs: wall_6d948b1b47258597fa66 represents *two different raw W2 edges* split_2296 and split_9744, with different endpoint W3 junction IDs. Current collect_physical_wall_identities dict comprehension silently assigns the later physical identity to both records. Three previously hosted openings do not include this candidate ID in their member wall lists; absence from those members alone is not host safety proof.

## Inference / authority boundary
An equality of unscaled, rounded W4 path fingerprints proves neither equal underlying W2 source lineage nor physical-wall equivalence. W4 may need *distinct candidate addresses* to preserve competing evidence. This must not promote two candidates as physically distinct or grant a count/measurement/host/QuantityEvidence. Any new identifier must be conditional only on actual same-ID conflict and source-owned evidence, not PDF filename, project, benchmark expected values or a tolerance relaxed to change outcomes.

## Proposed narrow change
Before returning assembled W4 candidates, scan *all* candidate IDs. Leave every non-colliding wall and edge map byte-for-byte unchanged. For a collided group, derive an additional deterministic candidate discriminator from existing source primitive lineage, original W2 edge geometry and W3 endpoint junction provenance; distinguish original candidate addresses only if every source-owned discriminator is valid and unique. Recompute only those collided candidate IDs and the edge→candidate map; preserve the original geometric ID in candidate metadata and reason codes. No physical SAME/DISTINCT resolution or host selection happens here. If source support is absent, foreign, nonfinite or still collides, fail closed instead of arbitrarily choosing one wall. Separately guard keyed identity collection against silent same-ID collision.

## Tests / expected negatives
- Same centerline/endpoints with independently evidenced source edges and junction ownership produces two unique, order-stable candidate **addresses**.
- Reversed path, arbitrary edge-list order, rotation/translation, unchanged legitimate collinear rechunking and unrelated content do not rekey unaffected candidates.
- Duplicated/foreign/missing source ancestry and nonfinite edge coordinates must not create fallback identities.
- Original source guard: exact SHA, 20k cap, an **exact PR-base vs PR-head positive-opening universe comparison** (native source-role opposition can legitimately change the baseline across merges), with the independently established Lot16 14 hosts / 9 frames and Maryborough 3 hosts / 0 frames held fixed, and strict original opening/host/frame receipt retention, Python 3.13 and 3.14 suites, provider isolation and frozen V2 integrity.
- Real positive diagnostics and synthetic geometry are not permission to merge if the source host/frame identities change.

## Unchanged
Source PDFs, W2 snapping and thresholds, W3 junction classification, W4 same/different physical equivalence rules, output publishers, dimensions/scale, all frozen V2 truth/evaluator files.
# Continuation design, 2026-10-11

Observed: duplicate physical-identity collection raises a generic `ValueError`
and the production helper catches that error by prefix text across both
assembly and collection calls. An unrelated exception with the same prefix can
be hidden. One corruption regression also asserts text rather than the new
typed source-address exception.

Proposed: a dedicated duplicate-address exception from the existing physical
identity collector; catch only the two producer-owned exception types. Assert
the typed collision for corruption and independently test misleading generic
errors from both call sites. Preserve normal return objects and original source
receipts. This changes failure handling only, never physical equivalence,
geometry, quantities, the 20k cap or frozen truth.

## Corrected source workflow gate — 2026-10-11

The original W4-source CI used fixed historical existence-hypothesis counts (Lot16 23 and Maryborough 180). The live original Lot16 SHA-verified base and candidate both produced **22** after an independent merged native dimension annotation opposition; they retained all 14 authenticated hosts and nine frames, with zero changed/lost source proofs. The earlier fixed 23 assertion therefore failed even though the W4 integrity retention comparator passed. This is a stale test expectation, not new host proof.

The workflow now independently re-extracts the exact original PR base and exact PR head, requires an **equal complete positive-opening hypothesis count** across them, preserves its host/frame counts (Lot16 14/9, Maryborough 3/0), exact original SHA and 20,000 cap, and still runs strict authenticated-host/frame retention and the full per-scope W4 collision ownership census. No fixed number from an older native source classifier enters the W4 test. Do not merge unless the corrected exact-head original source CI and all production regressions pass. No physical identity, source line, host, benchmark, score, wall-equivalence or quantity is promoted by this test fix.

## Original W2 source-coordinate type integrity

W4 candidate-address disambiguation now requires all four underlying W2 edge
coordinates to be genuine integer/float numerical observations (never
`True`, `False`, a numeric string or an object whose `float()` coercion
could fabricate source geometry). The already existing canonical float
conversion remains unchanged for legitimate numeric inputs, including integers.
Overlarge integers that overflow conversion, NaN, infinities and zero-length
edges fail closed with `W4SourceCandidateAddressCollision`. Adversarial
regressions cover each negative and verify equivalent canonical IDs for
authentic integral values. No wall role, opening host, physical equivalence,
benchmark quantity, safety cap or tolerance is changed.

## Current-main replay proposal — 2026-10-13

Observed: main `a0f5e98c` retains the W4 raw-node incidence/constructor-abstention
shadow and exact splitter-emitter ancestry shadow added since the held #2420
branch. Default assembly still hashes candidate path geometry, and
`collect_physical_wall_identities` still keys by candidate address without a
unique-address guard. Today’s original Maryborough grid workflow has passed its
three source-measured room controls, so the historical upstream failure must be
re-tested rather than assumed permanent.

Inference: the narrow source-owned address correction can be replayed while
preserving all newer shadow behavior. It distinguishes evidence addresses only;
no structural wall role, viewport, SAME/DISTINCT relation, opening host, quantity
or source completeness follows from a unique address.

Proposed: replay only #2420’s three authority-file deltas, original regression
file and source workflow onto current main. Preserve the current graph’s raw-node
incidence shadow and exact emitted parents. Independently compare current base
and candidate original-PDF source receipts, require unchanged geometry/membership
for every retained source candidate and exact existing host/frame receipts, then
run all applicable current-head CI including the unchanged Maryborough grid gate.
Leave the change draft if any source parity or room control fails. The historical
branch remains preserved until verified successor integration.

Benchmark observations are excluded from prediction: the identity-ready 1215
window is an engineering priority only; its label/area cannot select a wall or
set a geometry threshold. Frozen V2 files, commercial writers, W10 flags, the
20,000 source cap, snapping and physical-equivalence predicates stay unchanged.

### Actual assembly-membership collision found in the full-source fixture

Observed: the complete retained source-record fixture reaches two different W4
chains with identical parent/geometry/rounded-junction discriminator payloads.
The proposed address helper therefore raises its typed unavailable exception.
This fixture check does not itself reauthenticate the original PDF. The actual
chains own disjoint W2 edge addresses, which are already retained by the graph
and used in the existing source-fragment bundle record identity.

Inference: matching source parents, geometry and rounded junction names does
not erase distinct assembly memberships. An evidence address can name the
actual owned edge inventory without asserting separate physical walls.

Proposed: include the original owned W2 edge addresses in the collision-only
address payload; independently require each edge dictionary's original `id` to
match its map address. Retain the shared original parents, geometry and terminal
IDs in the payload. Preserve the duplicate-edge ownership and missing ancestry
abstentions. Add positive coverage for two separately owned chains with identical
parent/geometry/junction facts, and a contradictory edge-address negative. No
SAME/DISTINCT, viewport, role, host, count or metric authority is added. Repeat
applicable exact-head source and CI gates after this correction.

### Exact duplicate-edge ownership regression — required gate remains held

Observed: corrected-head Maryborough grid CI failed with zero canonical rooms
and floors. Unchanged main locally retains 687 room/floor candidates; the changed
head retains none. No typed W4 collision exception occurs. The source room-face
compiler `_derive_scope_outcome` in `pb_source_room_face_authority.py` returns a
whole-scope `source_room_face_duplicate_edge` negative when two unique candidate
addresses own the same normalized edge. The earlier reused address hid that
competition. Its existing collinear-overlap path already localizes ambiguity to
faces whose boundary shares the actual competing span. The shadow ownership
evaluator has the same early whole-scope duplicate-edge return.

Inference: preserving both source owners must not elect either one. It also
must not erase unrelated independently owned rings. Exact duplicate-edge
competition can use the same existing competing-span taint as other collinear
ownership ambiguity. Geometry-only planarization may collapse repeated identical
edge coordinates while the complete source-owner alternatives remain explicit.

Proposed: remove exact duplicate keys from the unique-owner lookup; retain all
candidate owners through the existing containment lookup; planarize unique
geometric edges using the current face extractor; seed the existing competing
span inventory with each exact duplicated edge and all its source-owner IDs.
Apply the unchanged positive collinear-overlap predicate to withhold every
adjacent affected face. Keep source-universe completeness false whenever duplicate
ownership exists, even if the span does not bound a surviving ring. Make the
shadow ownership census use the same unique-owner lookup, rather than returning
before it can report affected faces. No source owner, physical equivalence or
geometric tolerance is selected or changed.

Required proof: a duplicated room boundary remains withheld; unrelated owned
rooms keep exact original rings and IDs; order/reversal/transformation/rechunking
and no-mutation checks; complete source-owner alternatives and incomplete
universe retained; actual original Maryborough Food Prep, Cold Room and Office
controls and canonical floors preserved by new exact-head CI. Do not merge this
PR or weaken the existing source metric controls if those gates still fail.

The focused proof found an additional legacy exact-match ambiguity: rechunking
an alternate source edge could make its short fragment an exact lookup winner,
masking the other wall that contains it. The live competing-span inventory now
also retains all source edges with multiple containing owners before face
subdivision. This is a stricter negative, and uses the same containment predicate
and spatial index. It neither broadens tolerances nor accepts a face formerly
blocked by contamination. The diagnostic per-edge audit remains descriptive;
its exact-key findings cannot override the live full-span abstention.

The one pollution fixture whose specks overlap a real room boundary still
publishes nothing; its correctly identified first reason changes from generic
degenerate cells to source boundary competition. The half/majority pollution,
missing ownership, component, boundary-taint and completeness guards are intact.
