# Exact source fragment bundles — architecture review

## Observed repository behavior

Read AGENTS.md, AI_ENGINEERING_PLAYBOOK.md, wall_topology_observability_architecture.md,
planreader_wall_room_topology_spec.md, planreader_public_tender_benchmarks.md and
the general CI workflow before this change.

`scripts/gptmax_source_graphic_state_shadow.original_graphic_state_report`
reauthenticates original PDF bytes, calls `_source_page_segments` for literal
native paint, and calls `tools/diag_gptmax_full_foreground_run_source._trace_sources`
for the existing W2/W3/W4 shadow. `_trace_sources` calls
`build_wall_graph_for_viewport`, `deduplicate_coincident_edges`,
`classify_junctions` and `assemble_wall_candidates`. Its actual W4 record list
retains repeated candidate IDs. The per-edge field
`experimental_w4_candidate_ids` is therefore an address list, not a unique
assembly-record join. Candidate and abstained edges are separately retained.

`scripts/gptmax_exact_endpoint_flank_shadow.source_interval_coverage` proves
axis-aligned original span coverage from actual retained fragments without
combining graph edges. `_flank_stage_rows` currently retrieves every assembly
record sharing an address, including records that do not own the queried edge.
It preserves alternatives and grants no host authority.

`pb_viewport_segmentation.segment_page_viewports` independently establishes
spatial ownership. An original-source inspection finds an unsupported legend
on the current drawing; a title-block drawing title and sheet-wide raster tiles
do not authenticate a floor-plan viewport.

## Inference

A shared candidate address across all source intervals does not prove that a
single actual assembly record contains those intervals. An exact fragment
membership join can resolve this diagnostic ambiguity while physical wall
equivalence, structural role and drawing-view ownership remain unproved.

## Proposed change

Add a separate read-only script that consumes the freshly reproduced graphic
state report. Derive stable diagnostic record IDs from the complete existing
candidate address, centerline and owned fragment inventory. Validate an exact
partition of retained W3 edges between actual candidate records and explicitly
abstained chains. Join each original source span to all owning actual records,
retaining disconnected alternatives and uncovered intervals. Report common
actual assembly records separately from common candidate addresses.

Reuse stable_contract_id and EvidenceResolutionStatus. Do not alter W4 IDs,
graph nodes/edges, source ancestry, physical identity or any existing default
caller. No nearest/first record selection, gap bridging or synthetic merged
edge. The read-only join cannot authenticate source bytes by itself; the
original-source wrapper must independently reproduce its inputs.

## Expected abstentions and focused proof

Parentless derived fragments, explicitly abstained W4 chains, incomplete spans,
and spans spread across different actual assembly records remain visible and
nonpublishing. Duplicate/foreign fragment ownership or contradictory membership
must reject the report. Test the exact record-address collision, ownership
tampering, source span gaps and deterministic nonmutation. One original PDF
replay verifies unchanged production and source graph. Required remote CI and
original-source checks remain merge gates.

## Authority boundaries and benchmark observations

This crosses source-observation -> candidate-geometry -> diagnostic membership
only. It does not cross physical-wall, viewport, measurement, count, seal or
commercial publication authority. Observed drawing counts and quantities must
not influence implementation or thresholds. Frozen Full Plan V2, its evaluator,
tolerances and denominators, the 20,000 source-input cap, W10 and all commercial
writers remain untouched.

## Original-source checkpoint

Local original-PDF replay uses the repository-pinned PyMuPDF 1.28.0 and numpy
2.3.5. All 10,099 original source inputs are independently reauthenticated.
The replay retains the exact production receipts: 21 opening hypotheses,
14 authenticated hosts and nine complete frames. The separately reproduced
source input manifest and entire shadow graph have identical SHA-256 values.

The actual graph contains 60,929 retained fragments, 10,788 assembly records,
42 reused candidate addresses and 27 fragments in eight abstained chains.
Ten parentless actual assembly records retain their ten fragments as explicitly
ABSTAINED, without borrowed ancestry. Of the previously recorded 81 required
associations (72 distinct source IDs), all retain complete W3 source spans;
78 share an actual assembly record, and three do not. The three are 33d277
right/source ce6fc8cb..., 81a45c left/source 0141bee1..., and f81975
right/source 1f3529e3.... Exact IDs are retained in the accompanying JSON.

These are assembly membership observations, not recovered physical walls.
The seven raster hosts, drawing-view ownership, structural roles, physical
equivalence, frame/measurement/count gates remain open. No benchmark increase
is claimed. Twelve focused tests pass in 0.99 seconds; undefined-name lint,
workflow/embedded Python parsing, provider isolation and frozen V2 integrity
pass locally. Remote CI/source gates have not run for this new branch.
