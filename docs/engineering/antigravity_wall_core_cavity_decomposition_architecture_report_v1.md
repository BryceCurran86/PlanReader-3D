# Architecture Report: Source Wall Core Thickness & Multi-Leaf Cavity Wall Decomposition Shadow Authority (v1)

## Executive Summary
In architectural building construction, exterior envelopes and acoustic partitions often consist of multi-leaf composite assemblies (such as cavity brickwork, brick veneer, and twin stud acoustics).
Naive geometry algorithms suffer from two failure modes:
1. Treating the composite as a single monolithic block, distorting structural core engineering sizing.
2. Treating the air gap / insulation cavity between leaves as an enclosed internal "room" or skinny corridor, creating spurious room objects.

This authority decomposes composite wall runs into typed leaves (`STRUCTURAL_INNER_CORE`, `INSULATED_OR_AIR_CAVITY`, `ARCHITECTURAL_OUTER_VENEER`), determining the exact structural loadbearing core thickness while explicitly suppressing the cavity from room formation algorithms.

## Workstream Reference
- **Workstream A Items 2, 4 & 5:** Structural wall identification, physical continuity, and leaf thickness.

## Subsystems & Assembly Classification
1. **Wall Assembly Types:**
   - `SOLID_MONOLITHIC`: Single leaf wall (concrete panel, solid masonry).
   - `CAVITY_BRICK`: Inner structural brick leaf, 50mm air/insulation cavity, outer face brick leaf.
   - `BRICK_VENEER`: Structural timber/steel stud core, air cavity, outer masonry veneer.
   - `DOUBLE_STUD_ACOUSTIC`: Dual stud wall leaves with isolation gap.

2. **Leaf Roles & Cavity Suppression:**
   - `STRUCTURAL_INNER_CORE`: Carries structural loads (`is_loadbearing = True`).
   - `INSULATED_OR_AIR_CAVITY`: Non-loadbearing void (`is_loadbearing = False`), flagged to prevent room polygon generation.
   - `ARCHITECTURAL_OUTER_VENEER`: Cladding/facade protection (`is_loadbearing = False`).

3. **Invariants & Safety:**
   - Candidate shadow mode only (`status = EvidenceResolutionStatus.CANDIDATE`).
   - `commercial_projection_allowed = False`, `takeoff_eligible = False`.
   - Global 2.5 pt snap tolerance.
   - Preserves byte-for-byte customer retention.
