# Precast Concrete Spandrel Panel Tieback & Gravity Bracket Connection Shadow Authority Architecture Report (v1)

## Executive Summary
This authority module implements deterministic, candidate-only shadow extraction for architectural precast concrete spandrel panels, dead load gravity bearing brackets, lateral wind tiebacks with deflection slots, cast-in channels, and alignment dowels.

## Scope & Classification
- **Element Types**:
  - `GRAVITY_BRACKET`: Structural steel dead load bearing shelf bracket at slab edge.
  - `TIEBACK_BRACKET`: Slotted wind restraint connection accommodating inter-story drift and slab deflection.
  - `SPANDREL_PANEL`: Exterior architectural/structural precast spandrel panel.
  - `ALIGNMENT_DOWEL`: Inter-panel shear dowel / locating pin.
  - `SHIM_PACK`: Engineered leveling shim packs.
- **Connection Details**:
  - Fixing methods: Cast-in channels (e.g., Halfen), cast-in weld plates, chemical anchor studs, through-bolts.
  - Fastener sizes (M16, M20, M24, M30).
  - Material coatings (Hot Dip Galvanized HDG, Stainless Steel 316).

## Safety & Governance
- Strictly candidate shadow mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`).
- Deterministic 2D coordinate grid snapping (default `2.5 pt`).
- Safety primitive ceiling (`MAX_SAFETY_CAP_PRIMITIVES = 20_000`).
