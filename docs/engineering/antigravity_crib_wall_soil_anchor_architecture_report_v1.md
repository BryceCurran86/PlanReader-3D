# Architecture Report: Source Precast Concrete Retaining Crib Wall & Geotechnical Soil Anchor Shadow Authority (v1)

## 1. Executive Summary & Problem Formulation
In civil site engineering, infrastructure embankments, and earth retention structures, crib walls (precast concrete cellular modular blocks filled with free-draining crushed rock aggregate) and ground anchors prevent slope failure.
Civil takeoffs must resolve wall face elevation area ($m^2$), rockfill aggregate volume ($m^3$), cell header depth (e.g. 1.2m, 1.8m), precast header/stretcher unit counts, subsoil AG drainage lines, and tie-back soil anchor counts.
This shadow authority extracts and quantifies crib retaining wall centerlines, heights, rockfill volume, drainage, and anchors directly from civil retaining wall drawings.

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
class RetainingWallType(str, Enum):
    PRECAST_CONCRETE_CRIB_WALL = "PRECAST_CONCRETE_CRIB_WALL"
    TIMBER_CRIB_WALL = "TIMBER_CRIB_WALL"
    REINFORCED_SOIL_NAIL_WALL = "REINFORCED_SOIL_NAIL_WALL"
    SOLDIER_PILE_PANEL_WALL = "SOLDIER_PILE_PANEL_WALL"

class SoilAnchorType(str, Enum):
    SELF_DRILLING_GROUTED_ANCHOR = "SELF_DRILLING_GROUTED_ANCHOR"
    DRIVEN_HELICAL_TIEBACK = "DRIVEN_HELICAL_TIEBACK"
    NO_ANCHORS = "NO_ANCHORS"
```

## 4. Geometric & Analytical Engine
1. **Callout Parsing:** Regex parsing for wall retention height ($H_{wall}$), cell header depth ($T_{cell}$), batter ratio (1:4, 1:6), soil anchors, and AG drainage pipe.
2. **Dimension & Volume Calculations:**
   - Face elevation area $A_{face} = L_{run} \times H_{wall}$.
   - Rockfill volume: $V_{rock} = L_{run} \times H_{wall} \times T_{cell}$.
   - Precast header/stretcher modular units count: $N_{units} \approx \lceil A_{face} / 0.3\text{m}^2 \rceil$.
   - Subsoil AG drain length: $L_{drain} = L_{run}$.
3. **Point Snapping:** Snaps wall centerline points to $2.5\text{ pt}$ tolerance.

## 5. Verification Plan
- Unit test suite: `tests/test_source_crib_wall_soil_anchor_shadow.py` testing callout regex, snapping, face area, rockfill volume, modular units count, and invariant flags.
- Full regression verification: `tests/test_gptmax_original_eight_customer_retention.py`.
