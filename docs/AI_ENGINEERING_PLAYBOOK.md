# AI engineering playbook

Repository study for PlanReader-3D. Read this after `AGENTS.md`. Do not treat
this as permission to change production or commercial output.

W-numbers below follow the **adopted observability stack** in
`docs/wall_topology_observability_architecture.md`. They are **not** the
historical PR sequence in `docs/planreader_wall_room_topology_spec.md` §18.

Labels used here:

- **OBSERVED** — verified in current functions
- **INFERRED** — caller-wiring or tests, not a single production orchestrator
- **PROPOSED** — not this document; belongs in a task report
- **BENCHMARK** — score/holdout facts that must not set algorithms or thresholds

---

## 1. Start every task with this brief

Copy, fill, and paste at the top of the task:

```
You are working in BrycePremierBW/PlanReader-3D.
Before proposing or changing code, study the repository itself.

READ FIRST
1. AGENTS.md
2. docs/AI_ENGINEERING_PLAYBOOK.md
3. docs/wall_topology_observability_architecture.md
4. docs/planreader_wall_room_topology_spec.md
5. docs/planreader_public_tender_benchmarks.md
6. .github/workflows/ci.yml

TASK
<one quantity or hypothesis>

COMPLIANCE (first reply)
- Files actually read
- Exact functions traced (file + name)
- Authority boundaries crossed
- Expected abstentions before any tests
- Files that will remain untouched

RULES
Follow AGENTS.md. Detection is not measurement authority.
Reuse EvidenceResolutionStatus, QuantityEvidence, stable_contract_id,
and existing authority modules. Unknown/conflicting/stale/ambiguous
evidence must abstain. Retain all plausible candidates. Never resolve
ties with nearest/first/smallest. Never use filenames, project names,
benchmark IDs, or expected BOQ values as prediction inputs. Never
change production code and benchmark-defining files in the same PR.
New work starts in shadow mode.

FIRST DELIVERABLE
Do not change code yet. Write the architecture report required by
AGENTS.md. Stop for review.
```

A report that only restates documentation, without file-and-function traces,
is rejected.

---

## 2. Required reading

| File | Why |
|---|---|
| `AGENTS.md` | Permanent rules |
| `docs/wall_topology_observability_architecture.md` | Adopted W1–W10 call graph |
| `docs/planreader_wall_room_topology_spec.md` | Candidate schema, fusion, abstention, test matrices |
| `docs/planreader_public_tender_benchmarks.md` | Extractor/evaluator firewall; gold must not enter prediction |
| `.github/workflows/ci.yml` | Gold/production separation + provider isolation |

---

## 3. Observed wall-length path

Learn by tracing one wall, not by listing modules.

```
PDF page
  extract_native_page                         pb_vector_geometry_v130
  segment_page_viewports                      pb_viewport_segmentation   [F.07]
  collect_topology_from_page                  pb_wall_topology_diagnostics
    └ scoped segments/words (both endpoints inside bbox)
  collect_topology_from_segments              same file; orchestrator only
    W2  build_wall_graph_for_viewport         pb_wall_room_topology_stage_a
    W3  classify_junctions                    pb_wall_room_topology_junction_classifier
    W4  assemble_wall_candidates              pb_wall_room_topology_wall_assembly
        rekey_junctions_to_wall_candidates
    W5  reconstruct_room_candidates           pb_wall_room_topology_room_faces
    W6  derive_room_wall_relationships        pb_wall_room_topology_room_wall_relationships
    W8  bind_room_labels_from_words           pb_wall_room_topology_room_label_binding
    W7  detect_opening_host_candidates        pb_wall_room_topology_opening_host_binding
  reconcile_topology                          pb_wall_room_topology_reconciliation   [report only]
  adapt_topology_to_canonical_level           pb_wall_room_topology_canonical_adapter [W10]

  bind_viewport_scale                         pb_viewport_scale_binding
    → resolve_page_scale_calibration          pb_page_scale_calibration_authority

  EntityEvidence                              caller-built; W2–W10 do not emit it
  build_wall_length_quantity                  pb_wall_length_quantity
    → resolve_linear_measurement_input        pb_measurement_input_authority
    → QuantityEvidence

  GoldFreeShadowRunner / MigrationExtractPipeline
    compare_shadow_quantities                 pb_gold_free_shadow_runner
    GoldJoinEvaluator after seal only         pb_migration_gold_join_boundary

  quantity_evidence_to_takeoff_output_row     pb_quantity_takeoff_adapter
  run_jobhub_publish_preflight                pb_planreader_jobhub_publish_contract
  build_jobhub_payload
```

**OBSERVED details**

- `extract_native_page` returns native `segments` / `words` / `rects`. It does not own viewports, scale, or walls.
- `segment_page_viewports` returns `SegmentedViewport` with `RESOLVED` / `DERIVED` / `AMBIGUOUS` / `UNSUPPORTED`. Scale is not resolved here.
- `collect_topology_from_page` fail-closes with `safe_floor_plan_viewport_unavailable` unless a floor-plan viewport is `RESOLVED` or explicitly `DERIVED` and has a bbox. It does not invent a box.
- W4 is the first `WallCandidate`. `length_m` and `thickness_m` stay `None`; `status=CANDIDATE`; `thickness_authority=PROVISIONAL`.
- W5 is the first `RoomCandidate`. `floor_area_m2` stays `None`.
- W7 always emits `host_status="ambiguous_host"`. It is not a hosted-opening quantity.
- W9 does not mutate topology.
- W10 copies into `CanonicalWall` / `CanonicalSpace` with `takeoff_eligible=False`, `deduction_authority=False`, `height_m=None`, `openings=[]`.
- `build_wall_length_quantity` abstains unless `wall.status == CORROBORATED` **and** `resolve_linear_measurement_input` returns a firm value. Duplicate wall ids or overlapping source segments abstain in the batch builder.
- `build_wall_height_quantity` accepts only owned explicit height kinds or a corroborated datum pair. Tokens such as `default` / `assumed` / `legacy_default` are forbidden.

**INFERRED:** there is no single production function that runs PDF → JobHub wall length today. `pb_wall_topology_diagnostics` is an observability harness, not live extraction.

**BENCHMARK (must not drive implementation):** development-set scores and the absence of a frozen unseen holdout ≥99.0% within ±5% are evaluation facts, not algorithm inputs.

---

## 4. Observed hosted-opening path

**Correction (verified against current main, not the original PR #275 text):**
`pb_opening_provenance_graph.py`, `pb_opening_deduction_readiness.py`, and
`pb_wall_net_area_quantity.py` all **exist** on main — the prior wording
here ("not present") was wrong. More importantly, `resolve_hosted_opening_spans`
itself is **not** a dead end: it is imported and called live, in shadow
scope only, via `pb_hosted_opening_instance_adapter.collect_hosted_opening_shadow_evidence`
→ `pb_planreader_pdf_extractor.py`. `bind_hosted_opening_to_walls` remains
an actual dead end — grep confirms its only callers are its own definition
and its own test file.

```
resolve_hosted_opening_spans                  pb_hosted_opening_geometry
  → HostedOpeningEvidence (found | abstained)
  ↓ (LIVE, shadow-scoped)
collect_hosted_opening_shadow_evidence        pb_hosted_opening_instance_adapter
  → self.hosted_opening_shadow                pb_planreader_pdf_extractor
      "Never appended to F.9 live openings"   (comment at the call site)
  ↓
collect_opening_provenance_shadow_for_doc     pb_opening_provenance_graph
  → self.opening_provenance_shadow            pb_planreader_pdf_extractor
      "Never mutates pred_dict or F.9"        (comment at the call site)

bind_hosted_opening_to_walls                  pb_hosted_opening_wall_binding
  → HostedOpeningWallBinding (bound | ambiguous | unbound)
        ★ true dead end — only callers are its own definition and
          tests/test_hosted_opening_wall_binding.py; NOT reached from
          pb_hosted_opening_instance_adapter, pb_opening_provenance_graph,
          or the PDF extractor
```

**OBSERVED**

- Section H never reads schedules, tags, AI, or title-block scale. `width_m` exists only if the caller supplies `scale_pt_per_m`.
- Binding never picks nearest/first/smallest. Two plausible walls → `ambiguous`.
- `pb_opening_provenance_graph.py` is live-imported (shadow-scoped, both call sites wrapped in `try/except` falling back to an explicit `empty_*_shadow(reason=...)`) — not merely present, actually wired. Its own docstring: "shadow / diagnostics only... never mints W1/W2/D1 from repetition, nearest text, width similarity, or benchmark expectation... bound_wall_id is not assigned here."
- `pb_opening_deduction_readiness.py` and `pb_wall_net_area_quantity.py` exist but have no live (non-test) caller anywhere in the repository — genuinely standalone, development-only readiness layers, consistent with their own "development-only" / "fail-closed... readiness" docstrings.
- Live deductions today use the schedule/tag path: `pb_opening_deduction_v174.apply_deductions` / `passes_eligibility_gate`, `pb_opening_production_v175`, and `GenericOpeningDeductionPipeline` from `pb_planreader_pdf_extractor`. That path is a different axis from hosted spans.
- Opening **counts** in shadow use `ShadowOpeningCountProvider` → `GoldFreeShadowRunner` → `evaluate_opening_count_migration_gate`. Gate state is `new_shadow`. `CanonicalOpening.takeoff_eligible` is False.

W7 topology gaps and Section H hatch/fill spans answer “which wall hosts this opening?” from incompatible evidence and do not reconcile. Do not merge them silently. The shadow chain above collects evidence for later comparison — it still does not resolve that reconciliation, and per AGENTS.md's own authority table, `pb_hosted_opening_geometry` / `pb_hosted_opening_wall_binding` output stays unwired for any firm authority regardless of what shadow-collects it.

---

## 5. What may and may not raise authority

| Evidence | May become firm? | Function |
|---|---|---|
| F.07 viewport ownership (`RESOLVED` / explicit `DERIVED`) | Spatial ownership only | `segment_page_viewports` |
| Page-scale calibration that is already `AuthorityStatus.FIRM` | Yes, as scale | `resolve_page_scale_calibration`, `bind_viewport_scale` |
| Figured dimension that `resolve_measurement_authority` corroborates | Yes, as length | `resolve_linear_measurement_input` |
| Explicit owned height / corroborated datum pair | Yes, as height | `build_wall_height_quantity` |
| Native segment geometry | Detection / candidate geometry only | `extract_native_page` |
| W2–W6 topology | Candidate identity / faces only | see §3 |
| Title-block scale text alone | No | capped provisional in page-scale authority |
| Geometric gap, hatch tick, furniture loop, W5 face | No | W5 / `#273` ranking |
| One-hop connectivity | No | `rank_wall_candidates` |
| `#273` `CORROBORATED` | No — not wall-precise | `rank_wall_candidates` |
| AI, defaults, 2.8 m, empty detector | No | `build_wall_height_quantity` forbids default tokens |
| Benchmark gold / expected BOQ | Never as prediction | extractor/evaluator firewall |
| W10 canonical copy | No | `adapt_topology_to_canonical_level` |

`#273` `rank_wall_candidates` reissues every W4 candidate and may write `thickness_m` when a **caller-supplied** `scale_pt_per_m` plus paired-face evidence exists. Independent validation (PR #274) found `candidate_multi == room_boundary + connected`, fill hits `0` on the useful native-vector PDFs, and room-width / frame pairs inside the reused 1.5–40 pt band. That layer remains research-only.

---

## 6. Authority boundaries crossed on the wall-length path

1. **Primitive capture** — page units, no identity.
2. **Viewport ownership** — F.07; fail closed if unsafe.
3. **Candidate geometry** — W2–W6; retain fragments; do not delete ties.
4. **Entity evidence** — caller must construct `EntityEvidence` with matching `candidate_entity_id`.
5. **Measurement input** — ownership + firm scale or figured dimension.
6. **QuantityEvidence** — `stable_contract_id("qty", ...)`; abstain rather than guess.
7. **Shadow compare** — semantic-key join; no gold.
8. **Gold join** — only after `SealedShadowBundle` seal.
9. **Commercial row** — `quantity_evidence_to_takeoff_output_row` returns `None` if abstained.
10. **JobHub gate** — commercial preflight blocks non-publishable / blocked / stale rows.

Crossing a later boundary does not promote an earlier one.

---

## 7. Duplicate or conflicting implementation paths

| Concern | Keep | Do not treat as a second authority |
|---|---|---|
| Scale | `bind_viewport_scale` → `resolve_page_scale_calibration` | `pb_vector_geometry_v130.solve_scale` / `analyse_pdf_page` |
| Wall identity | W4 `assemble_wall_candidates` | `#273` ranking status; legacy envelope detectors |
| Opening host | none live | W7 gaps **and** Section H spans (parallel, unwired) |
| Opening deduction | B5 / v175 / `GenericOpeningDeductionPipeline` | hosted-opening geometry |
| Gross/net wall area | `pb_geometry_takeoff_model.calculate_wall_takeoff`; editable-3D / v174 helpers | missing `pb_wall_*_area_quantity.py` |
| Room faces | W5 `reconstruct_room_candidates` | older `pb_room_face_takeoff` as a second room graph |

---

## 8. Current abstention points (predict these before writing tests)

- No safe F.07 floor-plan viewport → no W2–W9.
- Dashed / hatch-layer / dimension-layer / text-frame segments excluded in W2 (metadata only; length is never a discard reason).
- W3 `UNRESOLVED` / `NEAR_JUNCTION_REVIEW` / rejected crossings → junction `ABSTAINED`.
- W4 will not chain across `L_CORNER`, `ENDPOINT`, `AMBIGUOUS`, or review junctions.
- W5 untraceable or tiny loops → room `ABSTAINED` (kept).
- W7 unpaired dangling ends omitted; reported hosts stay `ambiguous_host`.
- Scale binding abstains unless measurement authority is `FIRM`.
- Wall length abstains if topology is not `CORROBORATED`, identities mismatch, centerline is invalid, measurement input abstains, or two walls share source segments.
- Height abstains without owned explicit evidence.
- Hosted spans abstain on orientation conflict, missing jamb proof, or empty detector.
- Hosted binding abstains on two walls or one-sided adjacency.
- Commercial adapter drops abstained quantities. JobHub commercial mode refuses blocked rows.

---

## 9. Required tests (before implementation)

For every geometric hypothesis:

- synthetic positive cases
- synthetic look-alike negatives (furniture, glazing, dimension ticks, title-block frames, hatch lattice)
- ambiguity and conflict cases (two hosts, two scales, two thicknesses)
- translation, rotation, and scale metamorphic tests
- input-order and segment-splitting invariance
- unrelated-content and viewport-expansion invariance
- deterministic replay and `stable_contract_id` checks
- no-mutation checks on inputs
- proof that live predictions and commercial quantities are unchanged in shadow mode

Do not tune thresholds against known development projects. Do not change gold, mappings, or scorer tolerances to make a hypothesis look better.

---

## 10. Review checklist (teach through review)

Reject the work if any of these fail:

- Report only repeats documentation and does not cite functions.
- Recommendation lacks `file` + `function`.
- Evidence that cannot raise authority is used as if it could.
- Expected abstentions were not predicted before tests were written.
- Production code and benchmark-defining files (`expected_*.json`, `tolerances.json`, `benchmark_rules.json`, manifests under `benchmarks/public_tenders/` or `benchmarks/plans/`) appear in one PR.
- A second scale resolver, quantity schema, evidence enum, or canonical graph was added.
- Commercial rows, JobHub payload, or `takeoff_eligible=True` changed without an authority-promotion review.
- After implementation, an independent pass must inspect for leakage, duplicated authority, and hidden project/filename special cases.

---

## 11. Files that must remain untouched unless a later review says otherwise

- `pb_planreader_pdf_extractor.py` and other live commercial writers
- `pb_planreader_jobhub_publish_contract.py` production payload behavior
- `pb_opening_production_v175.py` / `pb_opening_deduction_pipeline.py` live deduction gates
- `benchmarks/**` gold, mappings, tolerances, manifests
- `pb_benchmark_accuracy_engine.py` scoring rules
- W10 `takeoff_eligible` / `deduction_authority` defaults
- `#273` ranking thresholds, unless a later research task is explicitly about those constants

Safe first homes for new topology work: diagnostic harnesses, shadow providers, and new modules that reissue existing records without deleting them.

---

## 12. Smallest safe place for new wall/opening work

**OBSERVED:** W1–W10 are not live-wired into `pb_planreader_pdf_extractor`. Wall length/height quantity modules exist but require caller-built `EntityEvidence` and firm measurement input. Hosted-opening geometry is diagnostic only.

**INFERRED smallest next step, not a change order:** keep new signals in shadow. If a later task consumes ranked walls, consume only after an independent validation that the tier means “physical wall,” and still leave W10 `takeoff_eligible=False`. Do not feed `#273` tiers into hosted-opening diagnostics until that review happens.

Governing accuracy target (**BENCHMARK**, not an implementation knob): there is still no frozen unseen project-level holdout showing ≥99.0% within ±5%. Moving a development score is not progress toward that target.

---

## 13. Next engineering phase (evidence compiler)

PlanReader is a conservative **evidence compiler**, not an image-to-quantity
predictor. Perception may nominate evidence. Geometry may establish
relationships. Only an authority contract may publish a quantity.

IFC-style separation is required and already matches the unused opening
stack: **host wall**, **physical opening (void)**, **door/window filling**,
and **schedule/type identity** are four objects. Do not let a gap, arc, or
tag fabricate the others.

Supporting research may inform this list. `AGENTS.md` remains repository
authority. Do not rewrite the external study.

Implement in this order, **shadow first**. Do not publish through
`extract_from_pdf`, W10, or JobHub.

| Priority | Contract-correct reading | First functions | Must not do |
|---|---|---|---|
| 1. Lossless vector-primitive provenance | Keep path index, stroke, dash, layer, clip, and page coordinates through every split/snap/merge | `extract_native_page`, `split_segments_at_intersections`, `build_wall_graph_for_viewport` | Invent geometry; drop graphic state at split |
| 2. W4 wall-id and duplicate-geometry consolidation | Stop endpoint-only id collisions (`_canonical_wall_candidate_id`); reuse one pair/fill/overlap predicate (`detect_wall_pairs`) | `assemble_wall_candidates`, `detect_wall_pairs` | Delete “ghosts”; treat `#273` status as wall authority |
| 3. Typed negative evidence | Codify dimension, glazing, furniture, table, grid roles as **opposing evidence atoms** on retained candidates | W2 metadata prefilter stays metadata-only; ranking/diagnostics consume negatives | Reject/delete noise **before** topological assembly; nearest-role wins |
| 4. Joint hosted-opening and schedule graph | Unify span, host, fill, tag, and schedule row by explicit tag/leader/coordinate ownership | `resolve_hosted_opening_spans`, `bind_hosted_opening_to_walls`, existing tag/schedule extractors | Proximity / first-bbox / single-envelope bind (`bind_openings_to_walls` steps 2–3) |
| 5. Figured-dimension and vertical binding | Bind witness bundles and FFL/storey datums to entities; height only from owned evidence | `extract_dimension_evidence_bundle`, `resolve_linear_measurement_input`, `build_wall_height_quantity` | Typical door width as scale; `default_ceiling_height_m` as firm |
| 6. Stage-wise accuracy and abstention metrics | Precision, coverage, and blocker rates at each boundary in §6 | diagnostic harness / shadow runner | Tune gold or thresholds to move 24/61 |

**Expected abstentions** stay those in §8. First implementation task, when
authorized: priority 1 only, with the test matrix in §9, and proof that
live predictions are unchanged.
