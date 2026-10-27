# Underground Water Main Fire Hydrant Booster Assembly & Storz Connections Shadow Authority Architecture Report (v1)

## Executive Summary
This authority module implements deterministic, candidate-only shadow extraction for external fire hydrant booster assemblies, Storz fire service connections, cabinet enclosures, and backflow prevention valves from civil and wet fire protection plans.

## Scope & Classification
- **Assembly Types**:
  - `CABINET_ENCLOSURE`: Freestanding metal kiosk/cabinet or brick masonry booster cabinet at property boundary.
  - `WALL_MOUNTED`: Facade-recessed booster manifold assembly.
  - `PILLAR_HYDRANT`: Standalone external pillar or street hydrant.
  - `TANK_INLET`: Fire water storage tank refill/suction booster.
- **Coupling & Manifold Config**:
  - Inlets count (2-way, 3-way, 4-way, 6-way Storz fittings).
  - Coupling standard (`STORZ` 65mm/100mm, `BIC`, `NST`, `THREADED`).
  - Main feeder pipe diameter (e.g., 100mm, 150mm, 200mm).
- **Ancillary Valving**:
  - Backflow prevention (`RPZD`, `DCV`).
  - Hydrostatic test drain valve, pressure gauge, non-return check valves.

## Safety & Governance
- Strictly candidate shadow mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`).
- Deterministic 2D coordinate grid snapping (default `2.5 pt`).
- Safety primitive ceiling (`MAX_SAFETY_CAP_PRIMITIVES = 20_000`).
