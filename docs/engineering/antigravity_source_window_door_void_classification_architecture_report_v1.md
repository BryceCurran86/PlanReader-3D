# Architecture Report: Producer-Owned Window vs Door Physical Void Classification Shadow Authority (Item 61)

## Executive Summary
This document establishes the architecture for the **Producer-Owned Window vs Door Physical Void Classification Shadow Authority** (`pb_source_window_door_void_classification_shadow.py`), resolving a core blocker across Workstream A and Workstream C: "Differentiate door voids from window voids using source-authenticated physical geometry, sill line presence, floor finish continuity, and schedule evidence."

The primary blockers addressed are:
1. **Misclassification of Fenestration vs Walk-Through Voids:** In CAD linework, wall openings are often drawn with ambiguous 2D linework. Naive parsers frequently misclassify doors as windows (or vice versa), leading to incorrect floor deductions, incorrect wall deduction heights, and corrupted quantity takeoffs.
2. **Missing Floor Continuity Distinction:** In physical construction, window openings have unbroken floor finish beneath them (as the structural wall continues up to the windowsill), whereas door openings interrupt or transition the floor finish at the door threshold line.
3. **Producer-Owned Multi-Evidence Cross-Checking:** This module establishes an immutable producer/authority contract that evaluates physical sill lines, floor continuity/interruption, swing arcs, and schedule codes (`Dxx` vs `Wxx`), failing closed on conflicting evidence (`OPENING_EVIDENCE_CONFLICT`), and outputting validated physical parameters and OGC WKB LineString geometries.

---

## Technical Architecture & Invariants

### 1. Sealed Producer / Authority Pattern
- Standard `_PRODUCER_SEAL`, `_AUTHORITY_SEAL`, and `_RECORD_SEAL` internal singletons ensure immutable writer boundaries.
- Factory method `SourceWindowDoorVoidClassificationProducer.create()` produces the mutable producer.
- Calling `.authority()` returns a frozen `SourceWindowDoorVoidClassificationAuthority` mapping selectors to results.
- Direct instantiation of records or authorities raises `PermissionError`.

### 2. Multi-Evidence Geometric Gates
- **Floor Continuity / Interruption:**
  - `FLOOR_INTERRUPTION_PROVEN`: Floor finish terminates or transitions at opening chord $\to$ door evidence (+2).
  - `FLOOR_CONTINUITY_PROVEN`: Floor finish continues unbroken across opening $\to$ window evidence (+2).
- **Physical Sill Lines:**
  - `WINDOW_SILL_LINE_PROVEN`: 1 or 2 sill lines spanning jambs $\to$ window evidence (+2).
  - `DOOR_THRESHOLD_LINE_PROVEN`: Sill lines absent $\to$ door evidence (+1).
- **Door Swing Arc Presence:**
  - `DOOR_SWING_ARC_PROVEN`: Authentic swing arc attached to jamb $\to$ door evidence (+3).
- **Schedule Code Match:**
  - `SCHEDULE_TAG_DOOR_MATCH`: Schedule code starts with 'D' $\to$ door evidence (+2).
  - `SCHEDULE_TAG_WINDOW_MATCH`: Schedule code starts with 'W' $\to$ window evidence (+2).
- **Conflict Resolution:**
  - If votes for both door and window are substantial, marks `OPENING_KIND_AMBIGUOUS` with `OPENING_EVIDENCE_CONFLICT` and fails closed (`status = ABSTAINED`).
  - Clear winners are corroborated as `OPENING_KIND_DOOR` or `OPENING_KIND_WINDOW`.

### 3. Shadow Mode Guards
- Record `status = CANDIDATE`.
- Explicit flags: `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Preserves all 8 holdout customer quantities and SHA-256 fingerprint (`ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`).
