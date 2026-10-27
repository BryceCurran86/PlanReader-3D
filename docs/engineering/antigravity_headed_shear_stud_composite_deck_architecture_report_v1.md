# Structural Steel Welded Headed Shear Stud Connector & Composite Decking Shadow Authority Architecture Report (v1)

## Executive Summary
This authority module implements deterministic, candidate-only shadow extraction for structural steel welded headed shear stud connectors (Nelson studs), through-deck drawn-arc stud welding, composite metal decking profiles (trapezoidal and re-entrant), and edge form pour stops.

## Scope & Classification
- **Element Configurations**:
  - `SHEAR_STUD_GROUP`: Headed shear studs welded to composite steel beam top flanges.
  - `COMPOSITE_DECK`: Profiled metal decking acting as permanent formwork and tensile reinforcement.
  - `EDGE_FORM_TRIM`: Galvanized sheet steel slab edge closure trim / pour stop.
- **Stud & Layout Attributes**:
  - Stud metric dimensions: Standard 19x100mm, 19x125mm, 22x150mm.
  - Welding process: Drawn-arc through-deck welding with ceramic arc shield vs bare flange shop welding.
  - Pitch distribution: 1 per trough, 2 per trough, or staggered pairs.
  - Deck profile: Trapezoidal (deep rib) vs Re-entrant (dovetail).

## Safety & Governance
- Strictly candidate shadow mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`).
- Deterministic 2D coordinate grid snapping (default `2.5 pt`).
- Safety primitive ceiling (`MAX_SAFETY_CAP_PRIMITIVES = 20_000`).
