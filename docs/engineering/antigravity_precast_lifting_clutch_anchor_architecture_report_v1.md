# Architecture Report: Source Precast Concrete Sandwich Panel Lifting Clutch & Tilt Anchor Shadow Authority (v1)

## 1. Executive Summary
Precast and site-cast tilt-up concrete wall panels and spandrel panels require engineered lifting inserts cast into panel edges or faces. These proprietary lifting clutches and anchors (e.g. 2.5T, 5.0T, 10.0T spherical head foot or edge lift anchors complying with AS 3850) enable safe de-moulding, tilting, rigging, and crane erection. Embedded recess formers, minimum edge distances, and supplementary shear/tension bar reinforcers dictate edge and face geometry. Parsing these lifting provisions provides essential structural verification without impacting customer baseline takeoffs.

## 2. Geometry & Extraction Model
- **Working Load Limit (WLL)**: Rated capacity in metric tonnes (e.g. 1.3T, 2.5T, 5.0T, 10.0T).
- **Anchor Application Type**:
  - `EDGE_LIFT_ERECTION`: Installed in the top/side edges of panels for vertical lifting and erection.
  - `FACE_LIFT_TILT_UP`: Installed in the horizontal panel face for initial tilting from the casting bed.
  - `SPHERICAL_HEAD_FOOT`: Spread or plate foot anchor for direct tension loading.
- **Recess Void Formers**: Hemispherical rubber void formers create the clutch clearance pocket.
- **Supplementary Reinforcement**: N12/N16 hairpin tension bars, shear loops, or perimeter bursting reinforcement.
- **Minimum Edge Clearances**: Critical edge and corner distance constraints to prevent edge breakout failure.

## 3. Safe Shadow Architecture & Non-Negotiables
- Strict candidate shadow isolation: `status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`.
- Hard safety cap enforced at 20,000 primitives.
- Geometric coordinate snapping at `SNAP_TOLERANCE_PT = 2.5`.
- Preserves customer retention baseline `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb` byte-for-byte.
