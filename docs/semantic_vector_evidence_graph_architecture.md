# Semantic vector evidence graph — architecture note (Phase D, research)

Status: **research / shadow only**. Nothing described here is wired into any
production, authority, or benchmark-scoring path. This is a short design
note for the long-run structure that `pb_semantic_vector_evidence_graph.py`
is the first rung of, per the standing architecture principle:

> perception nominates → geometry relates → authority contract publishes.
> Detection is not measurement authority.

## The intended long-run chain

```
PDF primitive
  -> semantic primitive              (THIS PHASE: pb_semantic_vector_evidence_graph.py)
  -> wall / room / opening / slab / roof object   (existing W2-W9 stages, unchanged)
  -> dimension / spec / schedule evidence          (existing figured-dimension /
                                                     opening-schedule evidence, unchanged)
  -> QuantityEvidence
  -> BOQ quantity                                   (existing W10 publication authority, unchanged)
```

Every edge in this chain must preserve provenance back to the native PDF
primitive(s) that produced it. If any single edge's relationship is
ambiguous, the correct behavior is to **abstain**, not to guess — the same
fail-closed posture already governing every existing authority stage in
this repository (W4 identity, W10 publication, F.9).

This is deliberately the opposite of a pipeline shaped

```
PDF primitive -> BOQ quantity
```

i.e. a single opaque model or hand-tuned formula guessing a quantity
directly from raw geometry. The whole point of routing through explicit
semantic primitives, then explicit objects, then explicit evidence, is that
every intermediate hop is independently inspectable, testable, and
falsifiable against a real drawing — the same reason U1's primitive lineage
exists, and the same reason this repository's benchmark scorer treats
detection as evidence, never as measurement authority.

## What exists today (this phase)

`pb_semantic_vector_evidence_graph.py` implements only the first hop:

```
PDF primitive -> semantic primitive
```

as a deterministic, rule-based, read-only pass over an already-built
Stage-A wall graph (`pb_wall_room_topology_stage_a.build_wall_graph_for_
viewport`'s own output) and its `excluded_segments` population. For every
primitive it produces a `SemanticEvidence` bundle: a candidate class
(`SemanticClass` — `PHYSICAL_WALL_PROBABLE`, `OPENING_GEOMETRY_PROBABLE`,
`DIMENSION_ANNOTATION`, `HATCH`, `GLAZING`, `FURNITURE`, `GRID`, `SYMBOL`,
`TABLE_OR_SCHEDULE`, `UNKNOWN`), an explicit strength tag (`STRONG` / `WEAK`
/ `ABSTAIN` — never a bare probability presented as truth), and the names of
every rule that matched, so every label is explainable back to the specific
generic geometric or metadata signal that produced it.

Provenance is preserved throughout: each `SemanticEvidence.primitive_id`
traces back to a Stage-A graph edge id (itself carrying U1's own
`primitive_lineage` — the merged W2 lineage work — back to native PDF
primitive ids) or to an `excluded_segments` entry (native id + `reason_
codes`, unchanged from Stage A's own Section 6.11 pre-filter). Nothing in
this module invents a new identity or collapses multiple primitives into
one without keeping the union.

Features used are all generic and project-agnostic: segment length,
direction-agnostic orientation, native layer/dash/width metadata (read
through U1 lineage's own per-source records where present, falling back to
the edge's own fields when lineage is absent), Stage-A's own already-
computed graph junction degree, and two purely-local geometric measures
computed by this module — a bounded-radius repetition-neighbor count (a
generic proxy for "this looks like part of a repeated pattern": hatching,
grid lines, glazing mullions, or repeated furniture/fixture symbols all
show local repetition that an individual wall face usually does not) and a
nearby-parallel-partner search (a generic "paired face" proxy for wall
thickness, with no project-specific thickness number hard-coded). No
filename, project name, benchmark ID, or hand-tuned per-project threshold
is used anywhere.

## Validation stance

Real benchmark drawings (Baghau, Dungicha — the two with committed,
CI-reproducible native-vector snapshots) are used **only** for qualitative
development validation, never as training data, never to fit a threshold,
and never converted into a benchmark pass/fail claim. The validation this
phase actually produced: on both real drawings, at least one edge receives
`PHYSICAL_WALL_PROBABLE`, at least one receives `UNKNOWN`/`ABSTAIN`, and
critically, short/densely-repeated real edges (Baghau's documented
solid, untagged 45°-hatch-tick convention, which Stage A's own metadata-only
pre-filter does **not** catch, since the ticks are solid and carry no
identifiable layer name) never receive `PHYSICAL_WALL_PROBABLE` — a genuine,
non-circular cross-check, since it uses only geometric repetition, never the
same layer/dash metadata the existing production filter already uses, and
catches a class of primitive the existing filter is documented to miss.

## What is deliberately NOT built yet

- The second hop (`semantic primitive -> wall/room/opening/slab/roof
  object`) — this phase's `PHYSICAL_WALL_PROBABLE` etc. remain evidence
  labels on individual primitives; nothing here assembles them into a
  canonical `WallCandidate`/`RoomCandidate`/opening object, and nothing here
  changes what those existing stages already do.
- Any ML classifier. Per the standing instruction, a deterministic feature
  graph + shadow evidence interface comes first; only after that should a
  learned classifier's value be assessed. If that assessment ever happens,
  training data must come from public/synthetic/procedural sources only —
  never the five development benchmark projects, which stay
  validation-only — and every external dataset's license must be recorded
  before use.
- Any quantity publication, commercial adapter change, or benchmark scoring
  change. This phase cannot move the benchmark score by construction:
  nothing in the existing pipeline imports this module.

## Why this shape avoids "independent formula-specific geometry guessers"

A common failure mode in this problem domain is a proliferation of narrow,
one-off heuristics — one bespoke rule for wall length, another unrelated one
for DPC, another for gross wall area, another for opening deduction — each
independently guessing from raw geometry with no shared representation and
no shared provenance trail. Routing every quantity through one shared
semantic-evidence graph instead means a wall-length rule, a DPC rule, and a
paint-area rule can all consume the *same* `PHYSICAL_WALL_PROBABLE` semantic
primitives and the *same* provenance chain back to native geometry, rather
than each re-deriving "is this a wall" from scratch in its own inconsistent
way. Future quantity-evidence stages (wall length, DPC, gross/net wall area,
plaster, paint, opening deductions) should consume this graph's output, not
re-implement their own primitive classification.
