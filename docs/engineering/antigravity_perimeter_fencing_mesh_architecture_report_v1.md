# Architecture Report: Source Perimeter Security Fencing Post & Anti-Climb Mesh Shadow Authority (v1)

## 1. Executive Summary & Problem Formulation
Civil site security, infrastructure perimeters, and industrial boundaries require robust fencing takeoffs encompassing mesh fabric types (358 anti-climb, chain link, palisade), post structural profiles, footing excavations/concrete volumes, and security toppings (barbed/razor wire).
Manual takeoffs often neglect post density, corner/end bracing posts, and bored pier concrete footings for fence posts.
This shadow authority extracts and quantifies boundary fence centerlines, post counts, footing concrete volumes, and mesh elevation areas directly from civil and landscape site plans.

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
class SecurityFencingType(str, Enum):
    ANTI_CLIMB_358_WELDED_MESH = "ANTI_CLIMB_358_WELDED_MESH"
    CHAIN_LINK_FABRIC = "CHAIN_LINK_FABRIC"
    STEEL_PALISADE = "STEEL_PALISADE"
    EXPANDED_METAL_MESH = "EXPANDED_METAL_MESH"
    TUBULAR_PICKET = "TUBULAR_PICKET"

class FencingToppingType(str, Enum):
    BARBED_WIRE_3_STRANDS = "BARBED_WIRE_3_STRANDS"
    RAZOR_WIRE_CONCERTINA = "RAZOR_WIRE_CONCERTINA"
    NO_TOPPING = "NO_TOPPING"
```

## 4. Geometric & Analytical Engine
1. **Callout Parsing:** Regex parsing for fence height ($H_m$), post section (SHS/CHS), post spacing ($S_m$), footing size, and security toppings.
2. **Polyline Snapping & Length:** Centerline snapping with $2.5\text{ pt}$ tolerance, evaluating exact linear meters of fencing runs.
3. **Post & Footing Quantities:**
   - $N_{posts} = \lceil L / S \rceil + 1$
   - $V_{footing} = N_{posts} \times \pi \times (D/2)^2 \times d_{depth}$
   - $A_{mesh} = L \times H$

## 5. Verification Plan
- Unit test suite: `tests/test_source_perimeter_fencing_mesh_shadow.py` testing callout regex, snapping, post counts, footing concrete volume, mesh area, and invariant flags.
- Full regression verification: `tests/test_gptmax_original_eight_customer_retention.py`.
