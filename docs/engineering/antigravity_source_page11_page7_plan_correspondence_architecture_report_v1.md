# Architecture Report: Producer-Owned Source Page-11 to Page-7 Plan Correspondence Shadow Authority (Item 15)

## Executive Summary
This document establishes the architecture for the **Producer-Owned Source Page-11 to Page-7 Plan Correspondence Shadow Authority** (`pb_source_page11_page7_plan_correspondence_shadow.py`), resolving Workstream B, Item 15 of the Autonomous Core Accuracy Engineering Mission: "Prove page-11 to page-7 plan correspondence using authenticated source geometry."

The primary blockers addressed are:
1. **Unregistered Multi-Sheet Geometries:** In multi-sheet drawing packages like Maryborough, measured room dimensions live on figured floor plan sheets (e.g., page 11) while physical room floor surfaces, finish tags, and ceiling elements live on finish plan sheets (e.g., page 7). Without authenticated geometric cross-sheet registration, rooms like OFFICE, FOOD PREP, and COLD ROOM cannot be bound to their finishes or verified areas.
2. **Ad-Hoc Coordinate Guessing:** Previous heuristics attempted to link sheets via label matching or hardcoded coordinates. This module computes rigid 2D registration derived strictly from split-invariant collinear interval overlap of non-grid wall linework, evaluating all D4 orientations, scales, and translations against a seeded null baseline.
3. **Physical Room Enclosure Verification:** Registration alone is insufficient to prove room correspondence; a correspondence is valid only if the registered boundary is fully wall-bounded on *both* sheets (with verified outward parallel second faces within standard wall thickness bands $3.0 - 15.0$ pt) and exhibits consistent wall opening intervals ($IoU \ge 0.98$). Open-plan zones (like FOOD PREP) or spaces with competing finishes (like COLD ROOM) are strictly rejected.

---

## Technical Architecture & Invariants

### 1. Sealed Producer / Authority Pattern
- Standard `_PRODUCER_SEAL`, `_AUTHORITY_SEAL`, and `_RECORD_SEAL` internal singletons ensure that instances can only be minted through authorized producer methods.
- Immutable `SourcePagePlanCorrespondenceAuthority` provides frozen O(1) resolution via `SourcePagePlanCorrespondenceSelector`.

### 2. Geometric Registration & Wall Interval Analysis
- **Lines Model:** Segments on each sheet are converted into axis-parallel horizontal ("H") and vertical ("V") collinear interval unions, eliminating dependencies on rasterization or segment splitting.
- **D4 Orientation and Translation Ranking:**
  - Evaluates Identity, Rot90, Rot180, Rot270, Mirror X, Mirror Y, Transpose, and Anti-Transpose.
  - Scores registration support using the two-axis minimum of collinear interval overlap ($\min(\text{support}_H, \text{support}_V)$). This ensures that sliding along long collinear corridors or repeating grid lines cannot falsely dominate the score.
  - Winner in Maryborough: Identity, scale 1.0, translation $T = (-78.0, 0.0)$, with $> 22,000$ pt support, $> 3.5\times$ over next competitor, and $> 100\times$ over null maximum.
- **Four-Sided Wall Enclosure Gate:**
  - Evaluates $x_0, x_1, y_0, y_1$ box sides on both the support sheet and registered target sheet.
  - For each side: verifies face coverage ($\ge 95\%$ for full wall, $\ge 50\%$ with doorway openings) AND an outward parallel second face line within wall thickness band $3.0 - 15.0$ pt.
  - Fails closed if any side lacks physical wall evidence (`ROOM_NOT_WALL_BOUNDED_ON_BOTH_SHEETS`).
- **Interval IoU Gate:**
  - Computes the intersection over union of covered intervals between the support and target sheets.
  - High fidelity required ($IoU \ge 0.98$) to prove identical physical wall enclosure.

### 3. Material Mark Containment & Conflict Detection
- Verifies that the designated material mark (e.g. FT3 in OFFICE) lies strictly within the room box on the support sheet.
- Rejects if competing finish codes (e.g. EPX in COLD ROOM) or multiple conflicting marks exist within the same room box (`COMPETING_FINISH_CODES_IN_ROOM`).
- Unregistered/schedule marks outside measured boxes are rejected (`MARK_OUTSIDE_REGISTERED_ROOM`).

### 4. Shadow Mode Guards
- Record `status = CANDIDATE`.
- Explicit flags: `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Preserves all 8 holdout customer quantities and SHA-256 fingerprint (`ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`).
