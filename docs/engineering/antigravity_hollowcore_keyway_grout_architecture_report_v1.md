# Architecture Report: Source Precast Concrete Hollowcore Floor Slab Keyway Joint & Tie Grout Shadow Authority (v1)

## Executive Summary
Precast prestressed hollowcore concrete floor planks are standard structural floor elements across multi-storey framed buildings. Longitudinal shear keyway joints between modular planks (standard 1200mm modular width) transfer vertical shear across adjacent panels and are filled with high-strength non-shrink grout. Transverse tie reinforcement and optional in-situ composite structural screeds/toppings develop comprehensive diaphragm action under seismic and wind loads.
This report defines the candidate shadow authority for parsing and extracting hollowcore slab layouts, longitudinal keyway joints, and tie grout specifications from structural framing drawings.

## Domain Model & Extraction Rules
1. **Callout Recognition**:
   - Matches callouts including `HOLLOWCORE`, `HOLLOW CORE`, `PRECAST SLAB KEYWAY`, `SHEAR KEY GROUT`, `HOLLOWCORE TIE`, `LONGITUDINAL KEYWAY`, `HOLLOWCORE PLANK`.
2. **Key Physical Parameters**:
   - `slab_depth_mm`: Extruded slab thickness (e.g. `150`, `200`, `250`, `300`, `350`, `400`).
   - `plank_width_mm`: Modular plank width (default `1200`).
   - `grout_strength_mpa`: Keyway filling compressive strength (e.g. `30`, `40`, `50`).
   - `tie_bar_spec`: Tie bar designation (e.g. `N12`, `N16`, `R10`).
   - `has_structural_topping`: Indicates composite in-situ concrete screed.
   - `topping_thickness_mm`: Screed depth (e.g. `65MM`, `75MM`).
3. **Geometric Snapping & Polyline Representation**:
   - Keyway joints and plank boundaries snapped within global `SNAP_TOLERANCE_PT = 2.5` pt.
   - Computes total joint length.
4. **Governance Invariants**:
   - `status="CANDIDATE"`
   - `commercial_projection_allowed=False`
   - `takeoff_eligible=False`
   - Safety cap: 20,000 primitives
   - Byte-for-byte baseline integrity for `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
