# PlanReader Audit & Deprecation Report: Retired Legacy Percentage Benchmark

**Date:** 2026-10-02  
**Status:** COMPLETE & ENFORCED  
**Directive Authority:** Permanent Project Directive — Old Benchmark Retired  

---

## Executive Summary

Per permanent project directive, the previous canonical-five / legacy percentage benchmark (KSTVET, Murera, Ghazi, Umma, Lamu) is **COMPLETELY RETIRED**. It is no longer executed, reported, compared against, used as a gate, or coupled into production runtime.

The single active validation authority is now the **V2 full-plan, independently source-closed truth framework** (`benchmarks/frozen_holdout/full_plan_v2/`):
```
SOURCE DOCUMENT
→ SOURCE EVIDENCE
→ PHYSICAL OBJECT
→ CANONICAL OBJECT
→ VERIFIED GEOMETRY
→ VERIFIED QUANTITY
→ CUSTOMER OUTPUT
```

---

## 8-Part Repository Audit & Classification

### 1. HISTORICAL (Retained for Git/Project Traceability Only)
The following assets are classified as historical records. They are retained only for git log traceability and are not executed or referenced by active workflows:
- `review_patches/from-2dc24ab-to-6a57d7e/` (historical patch set)
- `benchmark_results/` historical run artifacts and JSON outputs
- Historical commit messages and PR audit references

### 2. ACTIVE CODE (Removed from Execution)
The legacy benchmark modules have been made completely inert:
- `pb_accuracy_benchmark_v130.py`: Marked RETIRED. `apply(app)` no longer creates legacy sqlite tables or mounts prediction recording onto `app`.
- `pb_accuracy_ui_v130.py`: Marked RETIRED. `apply(app)` no longer wraps the customer sidebar workspace selector with the legacy "Accuracy Lab" expander.
- `pb_benchmark_accuracy_engine.py`: Marked RETIRED. Retained only as non-headline evaluator definition; decoupled from production execution.
- `pb_planreader_v126_app.py`: Deactivated active calls to legacy accuracy benchmark/UI.

### 3. CI (Removed from Active Gates/Workflows)
- Historical KSTVET probe workflows (`item19b_kstvet_wall_shadow.yml`, `item19b_kstvet_wall_provenance_probe.yml`) were previously pinned to historical PR #898 and are retired from active gates.
- Active CI (`.github/workflows/ci.yml`) enforces the V2 frozen holdout integrity and benchmark/production separation without invoking legacy percentage benchmarks.

### 4. DOCUMENTATION (Marked Retired)
- `docs/planreader_public_tender_benchmarks.md`: Updated with prominent RETIRED banner.
- `docs/planreader_accuracy_benchmarking.md`: Updated with RETIRED banner, directing all coverage work to V2.
- `docs/full_plan_takeoff_benchmark_v2_architecture.md`: Confirms replacement of the historical Kenyan canonical five with the Australian V2 projects (`au_qld_lot16_power`, `au_qld_3laurel`, `au_qld_maryborough_service_station`, `au_qld_q5446_armstrong32_harlequin`).

### 5. DASHBOARD / UI (Removed Old Percentage / Headline)
- The legacy "Accuracy Lab v1.3.0" sidebar UI panel in `pb_accuracy_ui_v130.py` has been deactivated.
- Customer workspace navigation no longer displays or computes legacy global percentage accuracy scores.
- Scoreboard displays are converted to V2 physical metrics: source-closed truth coverage, object detection coverage, canonicalization coverage, geometry correctness, and quantity correctness.

### 6. AUTONOMOUS TASKS (Replaced with V2 Terminology)
All autonomous engineering queues operate strictly under the V2 canonical building model paradigm:
```
UPLOAD PLANS
→ AUTHENTICATED EVIDENCE
→ CANONICAL BUILDING MODEL
→ TRADE QUANTITIES
→ CUSTOMER RATES
→ LIVE COST
→ 3D/VR
→ CONSTRUCTABILITY CHECKS
→ ARCHITECTURAL DRAWING SET
→ JOB HUB
```

### 7. TEST HELPERS (Isolated & Non-Interfering)
- `tests/test_accuracy_engine_v130.py` continues to verify core vector geometry (`snap_geometry`, `detect_wall_pairs`, `solve_scale`, `extract_native_page`) while its legacy benchmark assertions are isolated.
- V2 benchmark suites (`tests/benchmarks/test_full_plan_takeoff_v2_*.py`) are the sole authoritative benchmark test suites.

### 8. PRODUCTION DEPENDENCY INVESTIGATION (Preserved Reusable Capabilities)
Before removing legacy benchmark coupling, all shared dependencies were thoroughly investigated:
- `pb_vector_geometry_v130.py`: Pure vector linework, snapping, and scale solver. **PRESERVED** — core production dependency.
- `pb_accuracy_v13_engines_v145.py`: `split_segments_at_intersections`, `segment_length`, line intersection mathematics. **PRESERVED** — core production dependency for CAD linework.
- `pb_provider_gold_isolation.py` and `pb_provider_runtime_isolation.py`: Enforces strict isolation of benchmark code from production code. **PRESERVED**.

---

## Verified Scoreboard Metrics (V2 Framework)
1. **Source-Closed Truth Coverage:** Verified denominator items against sealed contract documents.
2. **Physical Object Detection:** 1:1 mapped physical building elements (walls, slabs, openings, roofs).
3. **Canonicalization Coverage:** Elements represented in `CanonicalProject` / `CanonicalBuilding` / `CanonicalLevel`.
4. **Geometry & Quantity Correctness:** Millimeter-exact and meter-exact metric dimensions without guessed defaults.
5. **Customer Runtime Publication:** Directly published to customer `takeoff_rows` with complete 5-link provenance.
