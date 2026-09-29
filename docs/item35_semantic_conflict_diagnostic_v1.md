# Item 35 semantic conflict diagnostic — v1

Shadow / diagnostic only. It changes no authority behaviour, no extractor
prediction, no commercial output and no benchmark-defining file, and it starts
no cross-scope identity work.

- Module: `pb_semantic_conflict_diagnostic.py`
- Script: `scripts/semantic_conflict_report.py`
- Tests: `tests/test_semantic_conflict_diagnostic_v1.py`

## Why

The real-source Item 35 funnel run (57 scopes over six SHA-verified sources)
was blocked at `semantic_opening_enumeration` with `CONFLICT` every time, on
`semantic_opening_physical_conflict`. The semantic record stores *which*
observations conflict (`conflict_observation_ids`) but not *why*, and the
funnel cannot see inside it. This diagnostic explains each conflicting and
residual observation from the authorities' public results.

## OBSERVED (main `fbe9448`)

`SemanticOpeningEnumerationProducer._publish_scope` adds an observation to
`conflict_observation_ids` on exactly these paths:

| # | Condition | Label used here |
|---|---|---|
| 1 | document scope: `resolve_visible` status is `CONFLICT` | `source_observation_failure` |
| 2 | observation lineage differs from the scope | `lineage_mismatch` |
| 3 | proven-opening record lineage / page differs | `lineage_mismatch` |
| 4a | `classify_disposition` is `CONFLICT` with `ambiguous_physical_opening_candidates` (the observation belongs to more than one candidate) | `ambiguous_physical_opening_candidates` |
| 4b | `classify_disposition` is `CONFLICT` with `snapshot_observation_integrity_failure`. This reason comes from resolving EVERY observation of the snapshot and collecting failures, so one failed observation makes every observation's disposition a conflict | `snapshot_observation_integrity_failure` (its own label: a snapshot-wide cause, not one observation's) |
| 4c | any other `CONFLICT` disposition | `disposition_conflict_other` |
| 5 | page candidate closure incomplete, and the observation is both closure-unresolved and support of a proven opening | `closure_unresolved_overlap_with_proven_opening` |
| 6 | two proven-opening records share a record id but are not equal (record ids are content hashes, so this is unreachable in practice) | not reproduced; the observation is reported `unattributed` |

The record does not keep the path. The "source-observation failure" family the
investigation asks about is paths 1 and 4b; aggregation reports both labels and
also the three families (`ambiguous_physical_opening_candidates`,
`source_observation_failure`, `closure_unresolved_overlap_with_proven_opening`)
with ties preserved.

## What the diagnostic exposes

Per conflicting observation: id; page, viewport, kind, `source_primitive_ref`,
derivation parents, geometry; `resolve_visible` status and reason codes; the
`classify_disposition` status / disposition / reason codes / candidate ids;
whether it is support of a proven opening and which proven openings list it;
whether it is closure-unresolved; and the path label(s). Per scope: semantic
record id and status, the full authenticated identity (document, revision,
source hash, snapshot, decision scope, pages), per-page closure results,
residual observations with the same detail, ambiguity clusters (observations
linked only by shared candidate ids), and the proven openings whose recorded
representative cannot re-prove existence.

Derived relation for an ambiguous observation, from each proven opening's public
support set: `shared_between_proven_openings` (two or more proven openings list
it), `one_proven_opening_plus_competitor` (one does), `no_proven_opening`.

## Scope of what is assessed

* Page closure is assessed only for pages that contain a diagnosed (conflicting
  or residual) observation, seeded by the smallest diagnosed observation on the
  page. The producer seeds it with the first visible observation; closure depends
  only on the seed's page and lineage, and a test checks that the result is
  seed-independent. `closure.pages_assessed` counts those pages, not every scoped
  page.
* The diagnostic builds its own private `PhysicalOpeningAuthority` over the
  producer's visibility authority. A caller cannot substitute an authority, and
  only that private object's memo caches are filled; no producer or shared
  authority is touched (a test compares the semantic producer's state before and
  after).
* A scope whose semantic authority published no record keeps that result's
  status and reason codes and is reported `semantic_record_absent`, not as a
  clean scope. `scripts/semantic_conflict_report.py` adds a `coverage` block
  (entries with/without a semantic record, errors, unreadable sources) and exits
  non-zero when an entry errored or could not be read.

## Rules

* Read-only. Only public seams are called (`resolve_visible`,
  `classify_disposition`, `prove_existence`, `assess_visible_candidate_closure`);
  a test forbids private accessors. No authority module is edited or patched.
* Paths are RE-DERIVED from the same public results on the same snapshot. An
  observation whose path does not reproduce is `unattributed` and
  `rederivation_consistent` becomes false. Nothing is guessed.
* The collector mirrors the shadow's source -> semantic steps exactly, and a
  test asserts its `semantic_record_id` equals the shadow's, so both describe
  the same authenticated scope.
* Unavailable, not inferred: a candidate's structural pattern and member
  observations (`prove_existence` returns no candidate on a conflict), the
  relation between closure candidate ids and disposition candidate ids, the
  view kind (resolved later, by the count stage), and the recorded path itself.
* No identity is inferred from counts, similarity, proximity or adjacency. The
  relations above describe how public support sets overlap; they do not claim
  two candidates are the same opening.
* `commercial_authority_granted` is a constant `False`; production code must
  not import this module (tested).
* Aggregation reports conflict-path counts (observations and scopes),
  disposition and visibility reason-code counts, observations involved,
  candidates per conflict, cluster sizes, candidate-pair overlap, closure totals
  and unavailable counts; ties for the dominant path are all reported.

## Side findings (not changed here)

* A proven opening's recorded representative is `min(support observation ids)`.
  If that observation is itself ambiguous, `prove_existence(representative)` is a
  conflict, and consumers that re-prove existence from the representative (the
  generic count, the live composition) cannot. Whether it happens depends on
  observation-id order. The diagnostic lists these openings.
* `GenericOpeningCountProducer.publish` raises for a complete universe with zero
  proven openings (queued as a separate task).

Run:

```
PYTHONPATH=. python scripts/semantic_conflict_report.py PDF_OR_DIR [...] \
    [--pages 0,1] [--output report.json] [--detail full]
```
