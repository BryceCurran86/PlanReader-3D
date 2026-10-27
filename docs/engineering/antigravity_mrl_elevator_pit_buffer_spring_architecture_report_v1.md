# Vertical Transportation Machine-Room-Less (MRL) Traction Elevator Pit & Buffer Spring Shadow Authority Architecture Report (v1)

## Executive Summary
This authority module implements deterministic, candidate-only shadow extraction for passenger and service Machine-Room-Less (MRL) traction elevator pits, car and counterweight buffer assemblies, guide rail bracket fixings, retractable pit ladders, and pit drainage sumps.

## Scope & Classification
- **Element Configurations**:
  - `ELEVATOR_PIT`: Structural reinforced concrete lift pit enclosure with waterproofing.
  - `CAR_BUFFER`: Energy dissipation oil buffer or accumulation spring buffer under elevator car.
  - `COUNTERWEIGHT_BUFFER`: Buffer assembly aligned with counterweight safety strike plate.
  - `GUIDE_RAIL_BRACKET`: T-rail anchoring brackets fixed to shaft structural walls.
  - `PIT_LADDER`: Permanently installed fixed or retractable ladder with safety contact.
  - `PIT_SUMP`: Waterproof drainage sump box (typically 600x600x600mm).
- **Kinematic & Dimensional Metrics**:
  - Contract speed (m/s) driving buffer type requirements ($> 1.0$ m/s requires hydraulic oil buffers).
  - Rated car payload (kg).
  - Pit structural clear depth (mm).

## Safety & Governance
- Strictly candidate shadow mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`).
- Deterministic 2D coordinate grid snapping (default `2.5 pt`).
- Safety primitive ceiling (`MAX_SAFETY_CAP_PRIMITIVES = 20_000`).
