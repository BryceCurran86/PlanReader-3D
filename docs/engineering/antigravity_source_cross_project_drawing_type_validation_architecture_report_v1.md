# Architecture Report: Producer-Owned Cross-Project Drawing Type Validation Shadow Authority (Item 29)

## Executive Summary
This document establishes the architecture for the **Producer-Owned Cross-Project Drawing Type Validation Shadow Authority** (`pb_source_cross_project_drawing_type_validation_shadow.py`), resolving Workstream C, Item 29 of the Autonomous Core Accuracy Engineering Mission: "Validate the same algorithms on multiple drawing types, not project-specific hacks."

The primary blockers addressed are:
1. **Risk of Project-Specific Heuristics and Benchmarking Overfitting:** In multi-agent engineering workflows, algorithms can accidentally incorporate project-specific assumptions (e.g. conditional logic branching on strings like `"maryborough"`, `"lot16"`, or `"q5446"`, or altering geometric tolerances to match expected benchmark figures).
2. **Diverse Architectural Drafting Archetypes:** Construction drawings span radically different drafting styles: residential housing (cavity brick, timber frames, raked roofs), commercial service stations (portal frames, acoustic ceiling grids, cold rooms), standard multi-unit plans (dense vector-stroked font outlines), and industrial buildings (large clear spans). The geometry engine must process all of these using uniform mathematical and topological principles.
3. **Producer-Owned Invariant Verification:** This module establishes an immutable producer/authority contract that validates algorithm execution across all four core drawing archetypes (`DRAWING_TYPE_RESIDENTIAL`, `DRAWING_TYPE_COMMERCIAL`, `DRAWING_TYPE_STANDARDS_OUTLINED`, and `DRAWING_TYPE_INDUSTRIAL`), verifying zero project-name dependencies, strict enforcement of the global 2.5 pt snap tolerance, the 20,000 primitive safety cap, topological 2D Jordan curve closure, and role segregation.

---

## Technical Architecture & Invariants

### 1. Sealed Producer / Authority Pattern
- Standard `_PRODUCER_SEAL`, `_AUTHORITY_SEAL`, and `_RECORD_SEAL` internal singletons ensure immutable writer boundaries.
- Factory method `SourceCrossProjectDrawingTypeValidationProducer.create()` produces the mutable producer.
- Calling `.authority()` returns a frozen `SourceCrossProjectDrawingTypeValidationAuthority` mapping selectors to results.
- Direct instantiation of records or authorities raises `PermissionError`.

### 2. Cross-Project Invariant Gates
- **Drawing Archetype Coverage:**
  - Evaluates four primary architectural typologies:
    - `DRAWING_TYPE_RESIDENTIAL`
    - `DRAWING_TYPE_COMMERCIAL`
    - `DRAWING_TYPE_STANDARDS_OUTLINED`
    - `DRAWING_TYPE_INDUSTRIAL`
  - Unrecognized types fail closed with `UNAUTHENTICATED_DRAWING_TYPE`.
- **Zero Project-Name Bias Gate:**
  - Any attempt to introduce project-specific branching or heuristics fails immediately with `PROJECT_NAME_BIAS_VETOED` (`status = ABSTAINED`).
- **Global Invariant Gates:**
  - Snap tolerance must strictly equal $2.5$ pt (`SNAP_TOLERANCE_INVARIANT_VERIFIED`). Any relaxation fails with `snap_tolerance_invariant_violation`.
  - Primitive safety cap must strictly equal 20,000 (`PRIMITIVE_CAP_INVARIANT_VERIFIED`). Any weakening fails with `primitive_cap_invariant_violation`.
  - Topological closure and material role segregation must be verified across all drawing archetypes (`TOPOLOGICAL_CLOSURE_INVARIANT_VERIFIED`, `ROLE_SEGREGATION_INVARIANT_VERIFIED`).

### 3. Shadow Mode Guards
- Record `status = CANDIDATE`.
- Explicit flags: `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Preserves all 8 holdout customer quantities and SHA-256 fingerprint (`ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`).
