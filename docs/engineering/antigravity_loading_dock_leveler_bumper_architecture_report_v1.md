# Architecture Report: Source Loading Dock Leveler Pit & Hydraulic Dock Bumper Shadow Authority (v1)

## 1. Executive Summary & Problem Formulation
In logistics facilities, industrial warehouses, distribution centers, and commercial loading docks, dock leveler pits represent recessed structural slab depressions equipped with edge embed angles, hydraulic/mechanical actuators, and heavy-duty impact bumpers.
Accurate shadow quantification requires parsing pit dimensions, depression depths, bumper specifications (laminated vs. molded rubber), embed curb framing, and power/drainage conduit sleeves without human intervention or benchmark hardcoding.

## 2. Invariants & Non-Negotiables
- **Customer Retention Invariance:** Must strictly preserve the baseline fingerprint (`ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`) across all test suites.
- **Strict Evaluator Separation:** Zero project-specific heuristics or hardcoding.
- **Safety Cap & Snap Tolerance:** Coordinate snapping strictly aligned to `SNAP_TOLERANCE_PT = 2.5`.
- **Shadow Mode Isolation:**
  - `status = "CANDIDATE"`
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`

## 3. Typology & Data Contracts
```python
class DockLevelerType(str, Enum):
    HYDRAULIC_DOCK_LEVELER = "HYDRAULIC_DOCK_LEVELER"
    AIR_POWERED_DOCK_LEVELER = "AIR_POWERED_DOCK_LEVELER"
    MECHANICAL_SPRING_LEVELER = "MECHANICAL_SPRING_LEVELER"
    VERTICAL_STORING_LEVELER = "VERTICAL_STORING_LEVELER"
    EDGE_OF_DOCK_LEVELER = "EDGE_OF_DOCK_LEVELER"

class DockBumperType(str, Enum):
    LAMINATED_RUBBER_BUMPER = "LAMINATED_RUBBER_BUMPER"
    MOLDED_RUBBER_BUMPER = "MOLDED_RUBBER_BUMPER"
    STEEL_FACED_BUMPER = "STEEL_FACED_BUMPER"
```

## 4. Geometric & Analytical Engine
1. **Callout Parsing:** Robust regex extraction for pit width, length, depth, bumper count, and curb steel embeds.
2. **Pit Plan Area & Void Volume:** $A = W \times L$; $V = A \times d_{pit}$.
3. **Curb Angle Perimeter:** 3-sided embed curb angle length $L_{curb} = W + 2L$ (front edge open to dock face).
4. **Bumper Takeoff:** Total pair counts per dock position.

## 5. Verification Plan
- Unit test suite: `tests/test_source_loading_dock_leveler_bumper_shadow.py` testing callout regex, snapping, void volume calculations, bumper associations, and invariant flags.
- Full regression verification: `tests/test_gptmax_original_eight_customer_retention.py`.
