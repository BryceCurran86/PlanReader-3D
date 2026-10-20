# Architecture Report: Source Full-Plan Recovery Engine Shadow Authority (Workstream C, Items 27 & 30)

**Status:** Architecture Report v1 for review.
**Author lane:** Antigravity (Lead Geometry & Source Interpretation).
**Workstream:** Workstream C, Item 27 ("Restore full-plan source interpretation after partial pipeline failures") and Item 30 ("Deliver an integration-ready source geometry engine that downstream agents can consume").

---

## 0. Contract Compliance (AGENTS.md)

- **Files Read:**
  - `AGENTS.md`
  - `docs/AI_ENGINEERING_PLAYBOOK.md` (§3, §8, §13)
  - `docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md`
  - `docs/engineering/gpt1_q5446_source_complexity_reporting_20261015.md`
  - `pb_source_room_boundary_doorway_opening_shadow.py`
  - `pb_source_open_passage_connection_shadow.py`
  - `pb_source_room_figured_dimension_witness_shadow.py`
  - `pb_source_floor_finish_occurrence_ownership_shadow.py`
  - `pb_source_wall_junction_continuity_shadow.py`
  - `pb_source_drafting_motif_negative_evidence_shadow.py`
  - `tests/test_gptmax_original_eight_customer_retention.py`
- **Authority Boundaries Crossed:**
  - Strictly **shadow mode** (`EvidenceResolutionStatus.CANDIDATE`).
  - `commercial_projection_allowed = False` and `takeoff_eligible = False`.
  - Never invents wall lengths, heights, room areas, or physical quantities.
  - No existing signed quantity, fingerprint, or customer output is altered.
- **Untouched:**
  - `benchmarks/frozen_holdout/full_plan_v2/` (entire tree untouched).
  - 20,000 raster primitive cap and global 2.5 pt snapping tolerance untouched.
  - Baseline signed eight rows byte-for-byte retention verified.

---

## 1. Observed Repository Behavior

1. **Brittle All-or-Nothing Document Pipelines:**
   - In multi-page plan sets, previous pipeline architectures suffered from cross-page poisoning: if a single secondary sheet (such as a detail or schedule page with vector text outlines in Q5446 or an unscaled elevation) encountered an issue (e.g. `physical_wall_candidate_scope_complexity_exceeded`), the entire document processing stopped or returned an empty universe for all pages.
   - This caused `status: no_sealable_quantities` across all pages, even when primary floor plan pages had valid, authentic source geometry.
2. **Downstream Integration Needs:**
   - Downstream agents (GPT1, GPT2, GPT3, Cursor) require an integration-ready source geometry engine that orchestrates room boundaries across doorway voids, open passages, figured room dimensions, floor finish occurrences, continuous wall junctions, and motif negative filtering with per-page failure isolation.

---

## 2. Inference

- Source evidence is inherently page- and viewport-scoped. A failure on Page $i$ must not invalidate or poison verified source-authority records on Page $j$.
- By providing `pb_source_full_plan_recovery_engine_shadow.py`:
  1. Each page is processed through independent, sealed shadow evaluations.
  2. If Page $i$ encounters an issue, that page is quarantined with its exact typed reason code (e.g. `PAGE_COMPLEXITY_BLOCKED`, `VIEWPORT_SCALE_UNRESOLVED`), while healthy pages produce verified `CANDIDATE` geometry records.
  3. The engine aggregates validated room boundaries, open passages, figured dimensions, floor finishes, and continuous wall systems into an integration-ready manifest for downstream consumption.

---

## 3. Proposed Change

Implement `pb_source_full_plan_recovery_engine_shadow.py`:
- **Selector:** `SourceFullPlanEngineSelector` (document_id, revision_id, source_sha256, snapshot_id).
- **Inputs:**
  - `pages`: sequence of `SourcePagePayload`:
    - `page_id`: str
    - `page_type`: str ("floor_plan", "reflected_ceiling", "elevation", "detail")
    - `candidate_segments`: sequence of linework segments
    - `room_boundary_candidates`: sequence of room polygon candidates
    - `opening_candidates`: sequence of doorway/opening candidates
    - `finish_mark_candidates`: sequence of finish occurrences
    - `is_blocked_by_complexity`: bool = False
    - `block_reason`: str = ""
- **Evaluation Rules:**
  1. Validate document lineage (64-hex lowercase SHA-256, non-empty fields).
  2. Process each page independently with failure isolation:
     - If page is flagged blocked $\to$ record page verdict as `QUARANTINED`, preserving exact reason code, without aborting other pages.
     - Evaluate drafting motif negative filtering.
     - Evaluate room boundaries across doorway opening voids.
     - Evaluate open passages and finish transitions.
     - Evaluate floor finish occurrences and internal wall-face boundaries.
  3. Emit `SourceFullPlanEngineRecord`:
     - `page_verdicts`: mapping of `page_id` to page status and reasons.
     - `total_pages_evaluated`: int.
     - `successful_pages_count`: int.
     - `quarantined_pages_count`: int.
     - `total_rooms_recovered`: int.
     - `total_open_passages`: int.
     - `total_finish_zones`: int.
     - `status = EvidenceResolutionStatus.CANDIDATE`.
     - `commercial_projection_allowed = False`.
     - `takeoff_eligible = False`.

---

## 4. Benchmark Observations That Must Not Influence Implementation

- References to specific project names or numbers are illustrative only.
- Page evaluation and failure isolation operate purely on geometric payloads and typed contracts.

---

## 5. Required Test Matrix (`tests/test_source_full_plan_recovery_engine_shadow.py`)

1. **Positive - Multi-page full recovery:** 2 healthy floor plan pages successfully evaluated with rooms, passages, and finish zones.
2. **Positive - Partial pipeline failure isolation:** 1 healthy floor plan page + 1 page with complexity failure $\to$ healthy page successfully recovers geometry while failing page is safely quarantined (no document-wide abortion!).
3. **Negative - All pages failing closed:** When all pages have defects, engine reports `ABSTAINED` with all reasons.
4. **Negative - Lineage mismatch:** Bad SHA-256 fails closed.
5. **Metamorphic test:** Invariance under page order permutation.
6. **No-mutation test:** Verify caller input data structures are not mutated.
7. **Customer retention test:** Verify byte-identical preservation of customer retention rows.
