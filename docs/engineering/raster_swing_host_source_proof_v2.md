# Raster swing host source proof

Read: AGENTS.md; AI_ENGINEERING_PLAYBOOK; wall_topology_observability_architecture;
planreader_wall_room_topology_spec; planreader_public_tender_benchmarks; ci.yml.

Observed: OpeningHostBindingProducer.publish re-proves G17 existence/identity,
resolves the producer-owned complete W4 scope, then tries _resolve_host_bands,
_resolve_raster_whole_wall_host, _resolve_raster_split_centerline_host and
_resolve_raster_source_primitive_host. Six of seven real raster swings have no
band. Three have separate left/right source primitives, so shared-primitive
split resolution cannot establish their host; remaining cases need source
flank mapping. Existing tests: 51 passed. The missing 5.67 area survives
_canonical_opening_area but publish_live_opening_area_quantities rejects its
CONFLICT host (opening_two_face_wall_lineage_ambiguous).

Inference: positive G17 solid-band face/end membership can prove which distinct
W4 fragments form a local interrupted host; equality to a single centerline or
one shared source primitive is an incomplete representation contract.

Proposed: add a final fallback that re-reads the exact authenticated G17 raster
wall-band faces and ends, binds each flank only through an exact authenticated
raster primitive carried by a usable W4 identity, and requires that candidate's
own local chain to reach that same flank end. Retain all alternatives;
competing equivalence groups conflict. Reuse existing pixel equality and W4
snap allowances. Never infer global wall identity, metric dimensions, or count.
Boundary-incomplete scopes abstain in this initial implementation.

Authority boundaries: sealed G17 support -> exact raster primitive/W4 identity
membership -> local host binding. Width/height, whole-wall frame, quantity and
commercial gates remain independently enforced. No changes to frozen truth,
scoring, tolerances, denominator, W10 or other agent lanes.

Benchmark observation: seven swings and the historical eight-area list locate
failures only; they do not set thresholds or dimensions. Single numeric labels
do not prove width role. FSL/JL subtraction does not prove door ownership.

User's handoff authorizes generic implementation and source-proof reruns without
another checkpoint; no commercial authority boundary is bypassed.

## Source proof results

Source SHA: 10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844.
Candidate base: 1d3a0b5fa0c6a631a6a5afd3201235746dd06819 (#1945).
Independent main comparator: 925c33d292f452cd7b22b53019614e87aa6f7812.

Real complete W4 universe: 2094 usable candidate records, scope_complete=true.
G17: 14 framed + 7 swings, unchanged. Framed host binding remains 10/14.
Swing host binding improves 1/7 -> 4/7. No thresholds or detector changes.

| Swing physical identity suffix | First host failure / result |
| --- | --- |
| 33d277d4c6b6ce758b0594f9d47ce4d8 | Left solid flank has no mapped authenticated local W4 raster primitive |
| 4b8c096b603c87f06f2692aa00494ab8 | Source-band host resolved |
| 8ecb81b6524804c80710ec323050be6b | Existing whole-wall host preserved |
| ab431bf4eca30b24da97e2fe3b0f424b | Source-band host resolved |
| ba7f75a2e5f68bcce87cd00ac1acf90b | No left source primitive within authenticated band; right local W4 owner also unavailable |
| c3c1e04acd78419e4f707dfcd89c7096 | Source-band host resolved |
| f819752382d44a00d9f28feca4b00787 | Left solid flank has no mapped authenticated local W4 raster primitive; figured label is independently ambiguous |

For 33d277..., G17's left solid flank is only 3.84 pt long, whereas the visible
raster detector has a 4.0 pt minimum. This is a diagnostic hypothesis about the
missing W4 representation, not permission to lower a global threshold. For
ba7f..., the visible raw line lies outside the actual G17 solid flank's bounded
cross-render equality allowance. No distance budget was widened to force it.

The three newly host-bound swings stop at whole-wall frame authority:
The existing frame routes are incompatible with this two-member representation:
_raster_whole_wall_frame admits one member; _binding_nodes requires four face
members. Scope discovery can also abstain before reaching those checks.
Authenticated raster centreline-flank bindings have two members. Local host ownership
does not establish a complete whole-wall frame, so frame publication remains
ABSTAIN rather than inventing whole-wall extent.

### Width and height

All six corroborated swing labels are a single bare `870` token. Their source
ownership is proven, but neither axis role nor a door-height convention is
proven by that token. Canonical width/height remain 0/7.
OpeningDimensionAuthority._visible_records reads ordinary visible observations,
while raster-opening support lives in resolve_raster_opening_primitive. It
originally stopped at opening_dimension_existence_required before jamb/witness
evaluation. This patch re-reads the exact isolated raster receipts only when the
ordinary namespace abstains and G17 already proves a raster opening. A synthetic
real-producer proof confirms the support is recovered while width still
abstains without jamb/witness authority; stale and unowned IDs stay blocked.
This does not authenticate `870` as width or supply missing witness topology.

OpeningHeightProducer publishes only an exact schedule-instance binding plus
an authenticated height-basis schedule row. The actual first gate here is
schedule_opening_instance_binding_partial_source_coverage. Independent PDF text
contains FSL 68560 / JL 70660 and explicit 2100 dimensions on elevation sheets,
but no source-proven ownership relationship from those exterior/detail views
to each of these interior raster swing identities was established. No default
height, axis inference or cross-view identity inference was added.

### Existing area regression isolation

Both independent current-main and #1945 source runs produce exactly:
0.54, 0.90, 1.26, 1.80, 2.16, 2.16, 10.08 m².
The fix preserves this exact set. The missing historical 5.67 m² opening is
physical_opening_existence_febefbc9ba308c7fc5eb09d57dbdd7d2 in BOTH runs, with
area_basis=figured_opening_label, area_m2=5.67, opening_kind=door, host_wall_id=null.
Both resolve to opening_two_face_wall_lineage_ambiguous plus
ambiguous_physical_wall_equivalence_for_host. Its quantity is correctly blocked
by the existing host requirement. This regression pre-exists #1945, belongs to
the vector two-face authority path, and must not be restored by weakening
publication or matching a benchmark value.

### Validation and reconciliation

122 focused tests passed (including 19 new positive/negative/conflict,
translation/rotation/scaling, source ancestry, segment-splitting, replay,
input-order and no-mutation checks). Provider/gold isolation and frozen V2
integrity passed. Python compilation and whitespace validation passed.
A single scoped GitHub proof workflow repeats the source run and seals all
seven publishable opening areas for review; no runner fan-out is added.

The source-closed opening-only run contains seven quantities with no invented
width, height or count. Exact Lot16 V2 reconciliation is not complete: this
checkout contains no independently frozen V2 production-identity map, and this
opening-only proof is not a complete all-family project handoff. Denominator
remains 27. Matched/missed/partial/unresolved/unsupported and accuracy fields
are unavailable until those exact inputs exist; no numeric/label join or empty
fabricated identity map was substituted.

Keep this change draft. The historical eight-area restoration and remaining
whole-wall/dimension/reconciliation capabilities are still outstanding.
