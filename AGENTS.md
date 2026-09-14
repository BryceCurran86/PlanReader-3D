# PlanReader-3D agent contract

This file is the permanent engineering contract. Conversation memory is not a contract.
If this file conflicts with a chat, this file wins.

## Before proposing or changing code

1. Read `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, and the docs listed there.
2. Trace the affected quantity through the real call path in the playbook.
3. Prove compliance in the first reply: files read, functions traced, authority boundaries crossed, files that will stay untouched.
4. Do not start from module names, prior chat claims, or benchmark scores.

Loop for every task: **trace → propose → synthetic proof → shadow run → authority review**.

Next engineering phase: the six evidence-compiler priorities in
`docs/AI_ENGINEERING_PLAYBOOK.md` §13. Supporting research may inform
them; this file still wins if wording conflicts. Typed negatives are
evidence against promotion, not deletion before W2.

## Non-negotiable rules

- Detection is not measurement authority. A plausible value is not an authoritative value.
- Preserve document, source hash, revision, page, viewport, entity, and evidence ownership.
- Reuse `EvidenceResolutionStatus`, `QuantityEvidence`, `stable_contract_id`, and the existing authority modules. Do not invent a second vocabulary.
- Unknown, conflicting, stale, or ambiguous evidence must abstain.
- Retain all plausible candidates. Never resolve ties with nearest, first, or smallest.
- Never use filenames, project names, benchmark IDs, or expected BOQ values as prediction inputs.
- Never change production code and benchmark-defining files in the same PR. CI enforces this via `scripts/check_benchmark_gold_separation.py`.
- Do not introduce a second scale resolver, evidence vocabulary, quantity schema, or canonical graph.
- Do not give AI output, defaults, title-block scale text, geometric gap width, or empty detector results firm authority.
- New topology and extraction work begins in shadow mode.
- Do not modify commercial output until a separate authority-promotion review approves it.
- W10 `adapt_topology_to_canonical_level` must keep `takeoff_eligible=False` and `deduction_authority=False`.
- Do not treat `#273` ranking `CORROBORATED` / non-abstained tiers as wall authority. Hosted-opening consumption of that ranking remains blocked.

## Authority that may become firm

Only existing seams may raise firm measurement authority:

- `pb_page_scale_calibration_authority.resolve_page_scale_calibration` / `measurement_authority_for_page_scale`
- `pb_viewport_scale_binding.bind_viewport_scale`
- `pb_measurement_input_authority.resolve_linear_measurement_input`
- `pb_figured_dimension_authority.resolve_measurement_authority`
- `pb_wall_length_quantity.build_wall_length_quantity` (requires `EntityEvidence.status == CORROBORATED` from `adapt_wall_candidate_to_entity_evidence` / `wall_physical_existence_status`, **and** a firm measurement input; `WallCandidate.status` is not existence authority)
- `pb_wall_height_authority.build_wall_height_quantity` (explicit owned height or corroborated datum pair only)

## Authority that must not become firm

- Title-block scale text alone
- Geometric gap width, hatch ticks, furniture loops, or W5 room faces
- One-hop connectivity or `#273` evidence ranking
- AI / default / assumed / 2.8 m / empty-detector results
- Legacy `pb_vector_geometry_v130.solve_scale` as a competing authority
- W7 `detect_opening_host_candidates` (always `ambiguous_host`)
- `pb_hosted_opening_geometry` / `pb_hosted_opening_wall_binding` (unwired; diagnostic only)
- W10 canonical translation
- Benchmark gold, mappings, scorer tolerances, or development-project scores

## Required tests for every geometric hypothesis

Synthetic positives; look-alike negatives; ambiguity/conflict; translation/rotation/scale metamorphic tests; input-order and segment-splitting invariance; unrelated-content and viewport-expansion invariance; deterministic replay and stable-ID checks; no-mutation checks; proof that live predictions and commercial quantities stay unchanged in shadow mode.

Real development drawings may reveal failure modes. Expected benchmark quantities must not determine algorithms or thresholds.

## First deliverable on a new change

Do not change code first. Produce a short architecture report that distinguishes **observed repository behavior**, **inference**, **proposed change**, and **benchmark observations that must not influence implementation**. Stop for review.
