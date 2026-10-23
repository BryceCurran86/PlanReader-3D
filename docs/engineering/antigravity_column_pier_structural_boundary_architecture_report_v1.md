# Architecture Report: Source Structural Column and Isolated Pier Boundary Shadow Authority (v1)

## Executive Summary
In architectural structural drafting, columns and piers provide critical vertical loadbearing support. When extracted naively by wall-run algorithms:
1. Isolated columns (e.g., circular concrete columns in open parking or retail areas) are either discarded as stray loops or erroneously joined to distant walls, creating fake "phantom walls" across open spaces.
2. Embedded columns and engaged pilasters are double-counted with wall volumes and distort interior room boundary polygons.

This authority explicitly recovers and classifies structural columns and piers (circular, rectangular, steel universal columns, masonry piers) with exact boundary polygon geometry, placement relationship (isolated, embedded, engaged), cross-sectional area, and volume.

## Workstream Reference
- **Workstream A Items 1 & 4:** Structural wall and opening continuity, isolated vertical elements.

## Subsystems & Classification
1. **Profile Types:**
   - `CIRCULAR`: Defined by center and diameter/radius (e.g. 450mm DIA concrete column).
   - `RECTANGULAR`: Defined by oriented bounding polygon (e.g. 400x400 concrete column).
   - `UNIVERSAL_COLUMN_STEEL`: Steel H/I-section with flanges and web.
   - `MASONRY_PIER`: Standalone or engaged brick/block pier.

2. **Placement Classification:**
   - `ISOLATED_IN_ROOM`: Completely detached from walls (minimum distance > snap_tolerance_pt). Deducts floor finish area from parent room.
   - `EMBEDDED_IN_WALL`: Intersects wall centerline/thickness. Prevents double-counting of structural volume.
   - `ENGAGED_PIER`: Extends outwards from a wall face (pilaster).

3. **Invariants & Safety:**
   - Candidate shadow mode only (`status = EvidenceResolutionStatus.CANDIDATE`).
   - `commercial_projection_allowed = False`, `takeoff_eligible = False`.
   - Global 2.5 pt snap tolerance.
   - Byte-for-byte customer retention preserved.
