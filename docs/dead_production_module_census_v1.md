# Dead Production Module Census Report (v1.0)
**Task Reference:** AG-16 — DEAD PRODUCTION MODULE CENSUS  
**Authority:** PlanReader Autonomous Integration Authority  
**Repository:** `PlanReader-3D`  
**Date:** 2026-10-01  

---

## 1. Executive Summary

A comprehensive AST-based caller census was executed across all 350 root Python modules in the `PlanReader-3D` repository. The audit distinguishes between production consumers (e.g. entrypoint apps, auto-geometry pipeline, database publication routines) and test consumers (`tests/`).

### Overall Census Distribution
- **LIVE:** 277 modules (79.1%) — Imported and executed by both production application code and regression test suites.
- **PARTIALLY LIVE:** 20 modules (5.7%) — Imported by live production code; indirect test coverage via integration suites.
- **TEST ONLY:** 44 modules (12.6%) — Imported only by test suites; contains specialized authorities, shadow pipelines, and benchmarks awaiting customer runtime wiring.
- **DEPRECATED:** 3 modules (0.9%) — Explicitly marked legacy/deprecated adapters preserved for backward compatibility.
- **ORPHANED:** 6 modules (1.7%) — Standalone scripts, utilities, or prototype applications with 0 active imports.

---

## 2. Census Breakdown Table

| Classification | Count | % of Total | Definition | Architectural Action |
|---|---|---|---|---|
| **LIVE** | 277 | 79.1% | Active in production and test suites | Maintain & protect with regression tests |
| **PARTIALLY LIVE**| 20 | 5.7% | Active in production, tested via integration | Add targeted unit tests where appropriate |
| **TEST ONLY** | 44 | 12.6% | Active in test suites / benchmarks only | Candidate authorities for customer runtime wiring |
| **DEPRECATED** | 3 | 0.9% | Legacy wrappers with explicit deprecation notices | Retain for historical backward compatibility |
| **ORPHANED** | 6 | 1.7% | Standalone scripts / zero callers | Preserve; do NOT delete without explicit mandate |

---

## 3. Detailed Audit of ORPHANED Modules (6)

1. **`benchmark_fixtures.py`**
   - **Intent:** Defines reusable benchmark data structures and fixture dictionaries.
   - **Reason for 0 callers:** Benchmarks import fixtures dynamically or define local test fixtures.
   - **Recommendation:** Retain as reference data.

2. **`pb_3d_foundation_app.py`**
   - **Intent:** Standalone Streamlit test application for exploring Three.js / pydeck 3D massing.
   - **Reason for 0 callers:** Interactive utility launched directly via `streamlit run pb_3d_foundation_app.py`.
   - **Recommendation:** Retain as an engineering diagnostic viewer.

3. **`pb_native_text_render_authority.py`**
   - **Intent:** Conservative native-PDF text render evidence and occlusion analyzer.
   - **Reason for 0 callers:** Perception authority whose output was designed for text occlusion auditing; not yet directly wired to customer scale detection.
   - **Recommendation:** High-value candidate for text bounding box validation.

4. **`pb_render_worker.py`**
   - **Intent:** Dedicated background render worker process for headless PDF rasterization.
   - **Reason for 0 callers:** Executed as a standalone sub-process CLI script.
   - **Recommendation:** Retain for background worker orchestration.

5. **`tradereader_trade_templates.py`**
   - **Intent:** Trade template catalog and trade classification dictionary.
   - **Reason for 0 callers:** Part of the specialized TradeReader extension suite.
   - **Recommendation:** High-value reference for Trade Readiness phase (AG-21 to AG-30).

6. **`tradereader_v12_app.py`**
   - **Intent:** Dedicated TradeReader Streamlit user interface application.
   - **Reason for 0 callers:** Standalone entrypoint executed directly via CLI.
   - **Recommendation:** Retain as TradeReader UI prototype.

---

## 4. Key High-Value TEST-ONLY Production Authorities (44)

The 44 `TEST ONLY` modules represent high-value benchmark-proven capabilities that have not yet been wired into the live customer upload-to-takeoff runtime:

1. **Trade & Substructure Authorities:**
   - `pb_dpc_substructure_authority.py`: Damp-proof course and footing substructure extraction. **[PROMOTED TO LIVE via `pb_dpc_substructure_customer_bridge.py` under AG-11]**
   - `pb_paintable_surface_v176.py`: Paintable area computation from wall faces.
   - `pb_structural_member_*.py` (3 modules): Structural steel and timber member framing extractors. Candidate for AG-24.
   - `pb_roof_ceiling_authority.py`: Pitch and ceiling area correlation engine.
2. **JobHub & Commercial Publishing:**
   - `pb_jobhub_publishing_pipeline.py` & `pb_planreader_jobhub_publish_contract.py`: Commercial export pipelines to JobHub.
3. **Spatial Provenance & Diagnostics:**
   - `pb_3d_spatial_provenance_v179.py`: Canonical 3D spatial graph projection.
   - `pb_takeoff_coverage_audit_adapter.py`: 6-stage lifecycle audit adapter.

---

## 5. AG-11 Refresh: Authority Census & Substructure Promotion

Under task **AG-11 (Orphaned Authority Census Refresh)**:
- Re-evaluated caller graphs across all 72 dedicated `pb_*authority*.py` production modules.
- **Classification:**
  - **LIVE (55 modules):** In active use across customer application runtime and regression suites (now includes `pb_dpc_substructure_authority.py`).
  - **PARTIALLY LIVE (1 module):** `pb_mapped_zone_geometry_authority.py` (active in production callers, covered via integration suites).
  - **TEST ONLY / DISCONNECTED (15 modules):** Mature authorities with regression tests awaiting customer runtime wiring.
  - **ORPHANED (1 module):** `pb_native_text_render_authority.py` (perception authority preserved for OCR/text occlusion).
- **Highest-Value Disconnected Authority Bridged:**
  - `pb_dpc_substructure_authority.py` was bridged into customer runtime via `pb_dpc_substructure_customer_bridge.py`.
  - Integrated into `pb_auto_geometry_v1219.py` (`analyse_workspace()`) to automatically extract and publish authoritative DPC and foundation rows into `takeoff_rows` adhering strictly to the 21-field core contract.
  - Preserves fail-closed behavior: drawings without authenticated witness callouts produce zero rows (no hallucinated default values).

---

## 6. Architectural Decision
As required by the global operating instructions:
**DO NOT DELETE MODULES MERELY BECAUSE THEY HAVE ZERO CALLERS.**  
All ORPHANED modules and TEST-ONLY modules are preserved. High-value authorities will be bridged autonomously as each corresponding trade task is reached.

