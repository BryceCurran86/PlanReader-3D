# Emergency Generator Exhaust Flue & Expansion Bellows Compensator Shadow Authority Architecture Report (v1)

## Executive Summary
This authority module implements deterministic, candidate-only shadow extraction for diesel generator exhaust flue networks, flexible stainless steel expansion bellows compensators, acoustic silencers (mufflers), high-velocity discharge terminals, and roof thimbles.

## Scope & Classification
- **Element Types**:
  - `EXHAUST_FLUE`: High-temperature generator engine exhaust stack.
  - `EXPANSION_BELLOWS`: Stainless steel multi-ply expansion joints isolating vibration and thermal expansion.
  - `EXHAUST_SILENCER`: Reactive/absorptive silencers (Industrial, Residential, Critical, Hospital grades).
  - `DISCHARGE_COWL`: High-velocity vertical jet cowl or weather cap terminal.
  - `WALL_THIMBLE`: Insulated and ventilated roof/wall penetration sleeve.
- **Dimensional & Material Specifications**:
  - Pipe nominal diameter (DN150 to DN500).
  - Stainless steel grades (316, 304) or mild steel.
  - Wall construction: Twin-wall factory insulated vs single-wall lagged.
  - Condensate drain point identification.

## Safety & Governance
- Strictly candidate shadow mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`).
- Deterministic 2D coordinate grid snapping (default `2.5 pt`).
- Safety primitive ceiling (`MAX_SAFETY_CAP_PRIMITIVES = 20_000`).
