# Architecture Report: Producer-Owned Cold-Room Insulated Panel (PIR/EPS) Structural Boundary Shadow Authority (Item 62)

## Executive Summary
This document establishes the architecture for the **Producer-Owned Cold-Room Insulated Panel (PIR/EPS) Structural Boundary Shadow Authority** (`pb_source_cold_room_insulated_panel_shadow.py`), resolving Workstream B & Workstream A Blocker: "Recover authenticated insulated sandwich panel boundaries for refrigerated enclosures (e.g. FREEZER, COLD ROOM) with thermal breaks, panel joint continuity, and door rebates."

The primary blockers addressed are:
1. **Misclassification of Cold Storage Insulated Panels:** Refrigerated spaces (e.g. Maryborough FREEZER / COLD ROOM) are enclosed with specialized polyisocyanurate (PIR) or expanded polystyrene (EPS) insulated panels clad in Colorbond steel. Conventional wall extraction routines mistakenly treat them as standard stud or masonry walls, misattributing panel thickness ($T_{\text{panel}} \in [0.075, 0.200]$ m) and missing thermal envelope integrity.
2. **Thermal Break Boundary Discontinuities:** Cold room doors and panel capping lines create subtle breaks in 2D vector CAD linework. Without an authority proving thermal perimeter continuity, refrigerated room polygons remain open in `abstained_faces`.
3. **Producer-Owned Thermal Perimeter Verification:** This module establishes an immutable producer/authority contract that validates refrigerated room names (`FREEZER`, `COLD_ROOM`, etc.), proves 2D closed panel polygon boundaries, verifies panel thickness within architectural standards, validates cold room door rebates, and derives scale-calibrated refrigerated storage volume ($m^3$) and internal floor area ($m^2$).

---

## Technical Architecture & Invariants

### 1. Sealed Producer / Authority Pattern
- Standard `_PRODUCER_SEAL`, `_AUTHORITY_SEAL`, and `_RECORD_SEAL` internal singletons ensure immutable writer boundaries.
- Factory method `SourceColdRoomInsulatedPanelProducer.create()` produces the mutable producer.
- Calling `.authority()` returns a frozen `SourceColdRoomInsulatedPanelAuthority` mapping selectors to results.
- Direct instantiation of records or authorities raises `PermissionError`.

### 2. Cold-Room Geometric & Material Gates
- **Refrigerated Room Typology Gate:**
  - Room names must match recognized cold storage typologies (`FREEZER`, `COLD_ROOM`, `COOL_ROOM`, `KEG_ROOM`, `CHILLER`). Non-cold room names fail with `NON_COLD_ROOM_NAME_UNAUTHENTICATED`.
- **Panel Thickness Gate:**
  - Panel thickness must fall strictly within cold storage manufacturing bounds ($0.075 \text{ m} \le T_{\text{panel}} \le 0.200 \text{ m}$, e.g. 75mm, 100mm, 150mm PIR panels).
  - Out-of-bounds thickness fails with `PANEL_THICKNESS_OUT_OF_BOUNDS`.
  - Tagged with `COLD_ROOM_PANEL_THICKNESS_CORROBORATED`.
- **Thermal Perimeter Enclosure & Door Rebate Gate:**
  - Polygon boundary must form a simple, non-self-intersecting closed loop (`THERMAL_PERIMETER_ENCLOSED`). Gaps fail with `THERMAL_BREAK_GAP_DEFECT`.
  - Cold room door openings must be verified (`COLD_ROOM_DOOR_REBATE_VERIFIED`).
- **Metric Calibration:**
  - Scale-calibrated internal floor area: $\text{area\_m2} = \text{area\_pt2} / (\text{scale\_px\_per\_m})^2$.
  - Storage volume: $\text{volume\_m3} = \text{area\_m2} \times \text{clear\_height\_m}$.
  - WKB polygon geometry exported for spatial coordination.

### 3. Shadow Mode Guards
- Record `status = CANDIDATE`.
- Explicit flags: `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Preserves all 8 holdout customer quantities and SHA-256 fingerprint (`ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`).
