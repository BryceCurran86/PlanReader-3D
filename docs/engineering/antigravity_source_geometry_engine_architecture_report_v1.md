# Antigravity Source Geometry Engine Shadow Authority Report (v1)

## Compliance & Context

### Files Actually Read
- `AGENTS.md`
- `docs/AI_ENGINEERING_PLAYBOOK.md`
- `pb_source_structural_wall_system_shadow.py`
- `pb_source_window_door_void_classification_shadow.py`
- `pb_source_cavity_slider_pocket_jamb_shadow.py`
- `pb_source_open_passage_connection_shadow.py`
- `pb_source_maryborough_physical_room_boundary_shadow.py`
- `pb_source_floor_finish_occurrence_ownership_shadow.py`
- `pb_source_wet_area_hob_waste_fall_shadow.py`
- `pb_source_rcp_ceiling_region_shadow.py`
- `pb_source_rcp_word_eligibility_shadow.py`
- `pb_source_multilevel_floor_vertical_void_shadow.py`
- `pb_source_wall_junction_corner_mass_deduction_shadow.py`
- PR #3462 (shared coordination hub)

### Exact Functions Traced
- `pb_source_structural_wall_system_shadow.SourceStructuralWallSystemProducer.evaluate_wall_run`
- `pb_source_window_door_void_classification_shadow.WindowDoorVoidClassificationShadowAuthority.evaluate_opening_void`
- `pb_source_cavity_slider_pocket_jamb_shadow.CavitySliderPocketJambShadowAuthority.evaluate_cavity_slider`
- `pb_source_open_passage_connection_shadow.evaluate_source_open_passage_connection_shadow`
- `pb_source_maryborough_physical_room_boundary_shadow.evaluate_maryborough_physical_room_boundary_shadow`
- `pb_source_floor_finish_occurrence_ownership_shadow.evaluate_source_floor_finish_ownership_shadow`
- `pb_source_wet_area_hob_waste_fall_shadow.WetAreaHobWasteFallShadowAuthority.compute_wet_area_takeoff`
- `pb_source_rcp_ceiling_region_shadow.SourceRcpCeilingRegionProducer.evaluate_and_publish`
- `pb_source_multilevel_floor_vertical_void_shadow.MultiLevelFloorVerticalVoidShadowAuthority.compute_level_net_floor_area`
- `pb_source_wall_junction_corner_mass_deduction_shadow.WallJunctionCornerMassDeductionShadowAuthority.evaluate_t_junction`

### Authority Boundaries Crossed
- Coordinates and aggregates all upstream geometric authorities into a unified, authenticated plan compilation receipt.
- Strictly non-publishing shadow authority (`status = CANDIDATE`, `commercial_projection_allowed = False`, `takeoff_eligible = False`).

### Expected Abstentions Before Any Tests
- Any plan set with contradictory wall runs, unaligned doorway thresholds, or overlapping vertical voids fails closed or quarantines affected spaces.
- Downstream commercial projection and takeoff eligibility remain strictly `False`.
- Customer retention baseline preserved byte-for-byte.

### Files That Will Remain Untouched
- All benchmark gold and holdout definitions (`benchmarks/**`).
- Production extractors and commercial writers (`pb_planreader_pdf_extractor.py`, `pb_opening_production_v175.py`).
- 20,000 primitive safety cap and 2.5 pt snap tolerance.

---

## 1. Observed Repository Behavior

PlanReader-3D features sophisticated shadow-first modules for individual geometric subsystems:
- Wall runs and paired faces (`pb_source_structural_wall_system_shadow.py`)
- Walkthrough voids and windows (`pb_source_window_door_void_classification_shadow.py`)
- Pocket sliders and jamb continuity (`pb_source_cavity_slider_pocket_jamb_shadow.py`)
- Room boundaries and floor finish zones (`pb_source_floor_finish_occurrence_ownership_shadow.py`, `pb_source_wet_area_hob_waste_fall_shadow.py`)
- Ceiling linings and soffits (`pb_source_rcp_ceiling_region_shadow.py`, `pb_source_rcp_word_eligibility_shadow.py`)
- Multi-level vertical voids (`pb_source_multilevel_floor_vertical_void_shadow.py`)
- Corner mass deductions (`pb_source_wall_junction_corner_mass_deduction_shadow.py`)

However, downstream agents (GPT1 for area measurement, GPT2 for room takeoff, GPT3 for signing/export, GPT MAX for host binding) previously had to consume and stitch together these individual modules manually, risking inconsistency across boundaries.

---

## 2. Inference

An integration-ready source geometry engine (`pb_source_geometry_engine_shadow.py`) solves this by providing:
1. Unified Ingestion: Clean, type-safe methods to register structural walls, openings, rooms, ceilings, and level datums.
2. Cross-Subsystem Consistency Verification:
   - Verifies that all openings are housed within registered walls without splitting continuous runs.
   - Verifies that room floor finishes terminate at internal wall faces and transition at authenticated door chords.
   - Verifies that vertical voids subtract from upper level floors without inventing phantom slabs.
   - Verifies that wall junction mass deductions partition 3D volume disjointly.
3. Immutable Compilation Receipt:
   - Produces `CompiledSourcePlanGeometryReceipt` sealed with `_ENGINE_SEAL`.
   - Maintains complete provenance, SHA lineage, and zero commercial projection.

---

## 3. Proposed Change

Implement `pb_source_geometry_engine_shadow.py` with:
- `SourceGeometryEngine` class:
  - `register_wall_system(system: WallSystemEvidence)`
  - `register_opening(opening: Any)`
  - `register_room(room: Any)`
  - `register_ceiling_region(ceiling: Any)`
  - `register_vertical_void(void: Any)`
  - `compile_plan_geometry(document_id, revision_id, source_sha256, page_id) -> CompiledSourcePlanGeometryReceipt`
- Invariants:
  - Strict shadow mode (`commercial_projection_allowed = False`, `takeoff_eligible = False`).
  - Fail-closed on contradictory or uncorroborated geometry.
  - Complete OGC WKB export capability for 2D footprints and 3D bounding prisms.

---

## 4. Benchmark Observations That Must Not Influence Implementation

- No project IDs (Lot16, Maryborough, 3Laurel, Q5446) or expected quantities are referenced.
- All relationships are derived from authenticated geometric coordinates, snap tolerances, and topological constraints.
