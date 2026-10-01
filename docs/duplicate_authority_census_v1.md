# Duplicate Authority Census & Canonical Mapping (v1.0)
**Task Reference:** AG-17 — DUPLICATE AUTHORITY CENSUS  
**Authority:** PlanReader Autonomous Integration Authority  
**Repository:** `PlanReader-3D`  
**Date:** 2026-10-01  

---

## 1. Executive Summary

This census audits and maps all parallel and overlapping modules across nine core functional extraction domains in `PlanReader-3D`. The objective is to identify the single canonical authority for each domain, distinguish intentional wrappers and adapters from obsolete legacy code, and establish clear convergence rules.

Per the global instructions:
- Broad deletions or replacements are strictly avoided unless rigorous equivalence is proven.
- Callers must be progressively bridged to the canonical authority.

---

## 2. Comprehensive Domain-by-Domain Authority Map

### 2.1 Wall Identity
| Module | Role | Status | Description & Caller Precedence |
|---|---|---|---|
| `pb_wall_room_topology_wall_identity_v2.py` | **CANONICAL** | Live | Direction-invariant, collinear-collapsed centerline path fingerprinting (`canonical_path_fingerprint`). |
| `pb_physical_wall_identity.py` | **CANONICAL** | Live | Cross-observation physical wall identity comparison authority. |
| `pb_physical_wall_existence_authority.py` | **PRODUCER** | Live | Proves physical wall existence from native vector pairs. |
| `pb_wall_room_topology_wall_assembly.py` | **WRAPPER** | Live | Topology assembly stage grouping raw vector segments into candidates. |

### 2.2 Opening Identity & Host Binding
| Module | Role | Status | Description & Caller Precedence |
|---|---|---|---|
| `pb_physical_opening_authority.py` | **CANONICAL** | Live | Physical opening instance existence, visible geometry proof, and identity comparison. |
| `pb_opening_detail_definition_authority.py`| **CANONICAL** | Live | Opening schedule/detail type definitions with immutable dimensions and materials. |
| `pb_opening_detail_definition_bridge.py` | **BRIDGE** | Live (AG-06, AG-11) | Customer-runtime bridge consolidating multi-sheet appearances without instance collapsing. |
| `pb_opening_host_binding_authority.py` | **CANONICAL** | Live | Host wall binding authority for opening instances. |
| `pb_wall_room_topology_opening_host_binding.py` | **LEGACY/SHADOW** | Historical | Early heuristic candidate host binder; superseded by `pb_opening_host_binding_authority`. |

### 2.3 Schedule Matching
| Module | Role | Status | Description & Caller Precedence |
|---|---|---|---|
| `pb_schedule_opening_instance_binding_authority.py` | **CANONICAL** | Live | Binds table schedule rows to physical plan opening instances. |
| `pb_schedule_row_quantity_authority.py` | **CANONICAL** | Live | Extracts and normalizes quantities from door/window schedule tables. |
| `pb_opening_schedule_v171.py` | **WRAPPER** | Live | Schedule table parser and ScheduleEntry data structure. |
| `pb_schedule_row_quantity_binding_adapter.py` | **ADAPTER** | Live | Bridges schedule quantity records into downstream takeoff structures. |

### 2.4 Dimensions & Calibration Precedence
| Module | Role | Status | Description & Caller Precedence |
|---|---|---|---|
| `pb_raster_plan_dimension_bridge.py` | **CANONICAL BRIDGE** | Live (AG-07) | Enforces 4-tier calibration precedence: Explicit > Vector > Calibrated Raster > Fallback. |
| `pb_raster_plan_dimension_authority.py` | **CANONICAL** | Live | Calibrated OCR dimension measurement engine. |
| `pb_physical_scale_authority.py` | **CANONICAL** | Live | Physical drawing sheet scale detection from text annotations and title blocks. |
| `pb_figured_span_scale_shadow.py` | **SHADOW** | Test Only | Shadow authority cross-checking figured spans. |
| `pb_dimension_graph_constraint_engine.py` | **LEGACY** | Test Only | Geometric constraint solver; superseded by direct dimension reconciliation. |

### 2.5 Net Wall & Opening Deductions
| Module | Role | Status | Description & Caller Precedence |
|---|---|---|---|
| `pb_live_physical_net_wall_integration.py` | **CANONICAL BRIDGE** | Live (AG-01) | Primary customer-runtime bridge for live physical net wall claims. |
| `pb_net_wall_boolean_union_authority.py` | **CANONICAL** | Live | Exact 2D polygon boolean subtraction of opening voids from wall faces. |
| `pb_opening_deduction_authority.py` | **CANONICAL** | Live | Evaluates opening deduction eligibility and net area reductions. |
| `pb_opening_deduction_v174.py` | **CANONICAL** | Live | Production opening deduction pipeline. |
| `pb_opening_deductions_v134.py` | **LEGACY** | Partially Live | Early opening deduction fallback; retained as secondary fallback in v175. |

### 2.6 Room & Space Area
| Module | Role | Status | Description & Caller Precedence |
|---|---|---|---|
| `pb_room_area_quantity.py` | **CANONICAL** | Live | Source-owned room area quantity extraction with boundary polygon verification. |
| `pb_source_room_area_bridge.py` | **BRIDGE** | Live | Bridges room area records into customer model. |
| `pb_unit_floor_area_v1221.py` | **WRAPPER** | Live | Customer runtime unit floor area parser. |
| `pb_unit_floor_area_gate_v1221.py` | **GATE** | Live | Sanity check filter preventing spurious text matches from publishing as room areas. |
| `pb_unit_floor_area_textfix_v1221.py` | **LEGACY** | Live | Regex text cleaning helper. |

### 2.7 Facade Area & Building Elevation
| Module | Role | Status | Description & Caller Precedence |
|---|---|---|---|
| `pb_elevation_registration_v135.py` | **CANONICAL** | Live | Registers elevation sheets to horizontal floor plan sides (N, S, E, W). |
| `pb_auto_geometry_v1219._build_facade_rows` | **CUSTOMER RUNTIME** | Live | Customer takeoff builder consuming registered walls and physical net wall claims. |

### 2.8 Floor & Slab Area
| Module | Role | Status | Description & Caller Precedence |
|---|---|---|---|
| `pb_slab_classification_geometry.py` | **CANONICAL** | Live | Classifies slabs (ground-bearing vs suspended) and extracts perimeter geometry. |
| `pb_explicit_floor_area_evidence.py` | **PRODUCER** | Live | Produces authenticated floor polygon evidence from vector boundaries. |
| `pb_cross_trade_geometry_reuse.py` | **CANONICAL (AG-13)** | Live | Derives multi-trade slab quantities (concrete, formwork, mesh, membrane). |

### 2.9 Finish Assignment & Face Binding
| Module | Role | Status | Description & Caller Precedence |
|---|---|---|---|
| `pb_bound_wall_finish_quantity_authority.py` | **CANONICAL** | Live | Authenticated source-bound wall finish quantity authority. |
| `pb_bound_wall_finish_customer_bridge.py` | **BRIDGE (AG-04)** | Live | Customer takeoff bridge for bound finishes adhering to 21-field contract. |
| `pb_wall_finish_callout_wall_authority.py` | **CANONICAL (AG-05)**| Live | Binds drawing finish callouts to specific wall faces with provenance. |
| `pb_wall_finish_face_binding_authority.py` | **CANONICAL** | Live | Binds finish types to room-facing internal vs external wall faces. |
| `pb_room_face_takeoff.py` | **LEGACY** | Partially Live | Early geometric face segmentation; superseded by bound wall finish authority. |
| `pb_surface_evidence_v160.py` | **LEGACY** | Live | Early heuristic surface extractor. |

---

## 3. Convergence & Integration Guidelines

1. **Precedence Hierarchy:**
   - Always prefer the `pb_*_authority.py` (e.g. `pb_bound_wall_finish_quantity_authority`, `pb_opening_deduction_authority`) over legacy `_v134` or `_v160` heuristic scripts.
2. **Safe Bridge Pattern:**
   - When connecting customer runtime to a canonical authority, always use the non-invasive bridge pattern (`pb_*_bridge.py` or dedicated wrapper method in `pb_auto_geometry_v1219.py`).
   - If the canonical authority abstains, fall back safely to registered geometry; never fabricate or guess quantities.
3. **No Breaking Deletions:**
   - Legacy modules remain in place to guarantee backward compatibility for older workspaces. Callers should be gradually routed through canonical bridges.
