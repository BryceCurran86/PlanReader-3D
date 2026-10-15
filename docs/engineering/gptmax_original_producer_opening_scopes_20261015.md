# Original producer opening-scope handoff

Tracking: #2396, upstream evidence for GPT3 #2297. Architecture was posted
before code at #2396 comment 6184862360. No source authority is promoted.

## Observed call path

Read AGENTS.md, the engineering playbook, W1–W10 architecture and specification,
public tender benchmark firewall and CI. Traced original
`SourceVisibilityProducer.ingest_native_pdf_bytes` →
`compose_live_wall_opening_authority` →
`PhysicalOpeningAuthority.prove_existence` →
`OpeningHostBindingAuthority.resolve` / `OpeningHostFrameAuthority.resolve` →
`compose_live_physical_opening_voids` →
`publish_live_opening_area_quantities` → existing source export and seal.

The actual host record owns snapshot and decision-scope IDs. A host selector
may exist without a positive host record; that attempted scope is not a
source-positive host receipt. Existing V1 sealing omits these scope fields.
Matching JSON metadata is not independent authentication and cannot silently
change a V1 fingerprint.

## Proposed and implemented source-only boundary

`tools/diag_gptmax_producer_opening_scope_receipts.py` accepts only PDF bytes
and canonical source page selectors. It creates an isolated real source root,
composes existing authorities, re-proves original physical existence, and reads
host and frame records through the real producer-issued selectors. It checks
root, physical identity, host, frame and full inventory agreement. Original
figured-label measurements are independently reissued through
`OpeningLabelDimensionProducer` and checked against existing figured quantities.
All missing hosts, frames and metric axes retain their actual negative traces.

The output copies actual original record bodies plus canonical/quantity IDs.
It retains attempted selectors separately, and returns no positive scope ID
for a hostless object. Recomposition must preserve every original wall, host,
frame, canonical object, quantity, seal and customer row. The observer repeats
its source/record checks after recomposition; source byte replacement, changed
snapshots, duplicate objects or incomplete producer inventories fail closed.

This is **UNSIGNED and UNPUBLISHED**, including when a positive host scope was
replayed. It is not the versioned signed sidecar required by #2297. GPT3 must
independently verify the originating source/code artifact, agree a versioned
consumer/signature contract and match exact roots before accepting any portable
scope data. A different decoded-page universe can issue a different snapshot
for the same PDF SHA. The tool exposes both decode/topology page selectors and
never aliases those roots.

## Original endpoint source result reviewed independently

Read exact-head #2765 original-source artifact 11950095147 from successful
Actions run 38684640994, head 9652f1ae998d86eb131cf1e1af0a74c4a2024231.
Its immutable original Lot16 SHA is
`10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`;
snapshot `source_snapshot_7ad8bf09e3ebbec9797df89842574683`.
Raw group `7c32fd8f` retains the whole-source negative (41/43 painted cells)
and separately proves 41 contiguous original endpoint cells spanning 9.60pt
from the original maximum endpoint. This resolves that terminal-paint question
only. It does not restore snap-collapsed caps, establish structural wall role,
physical opening existence, host, height or quantity. Page-wide closure stays
30 raw / 21 resolved / 9 unresolved; count completeness remains false. The
original eight signed customer rows were exactly retained in that workflow.

## Validation and protected boundaries

Real synthetic PDF tests cover issued scope/quantity association, foreign
document/revision/SHA/snapshot/page and unissued scope, duplicate or missing
producer inventory, source changes during a read, nonexistent pages, decode
root differences, deterministic replay and absence of caller evidence inputs.
Dedicated CI independently replays immutable original Lot16 and preserves the
existing 21 physical / 15 hosts / 9 frames / 8 signed rows as controls only.
Exact current-head CI and independent review remain required.

No geometry predicate, source PDF, production module, 2.5pt snap, W3 ambiguity,
W4 membership, host/frame producer, 20,000 input cap, quantity publisher,
signature, frozen truth, denominator, mapping or evaluator is changed. No new
benchmark match is claimed. Each unresolved opening still needs its first
physical source/host/measurement authority before the user's completion gate.
