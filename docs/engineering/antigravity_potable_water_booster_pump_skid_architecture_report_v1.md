# Cold Water Pressure Booster Pump Hydro-Pneumatic Variable Speed Skid Shadow Authority Architecture Report (v1)

## Executive Summary
This authority module implements deterministic, candidate-only shadow extraction for domestic cold water pressure booster pump skids, variable frequency drives (VFD), hydro-pneumatic diaphragm expansion tanks, stainless steel header manifolds, and anti-vibration inertia bases.

## Scope & Classification
- **Skid Configurations**:
  - `DUPLEX`: 2-pump Duty/Standby or Duty/Assist skid.
  - `TRIPLEX`: 3-pump Duty/Assist/Standby commercial skid.
  - `QUADRUPLEX`: 4-pump high-rise institutional booster set.
  - `SIMPLEX`: Single pump package booster.
- **Hydraulic Performance Parameters**:
  - Design flow rate in litres per second (L/s).
  - Rated delivery head in meters (m) or pressure in kPa.
  - Diaphragm expansion vessel capacity in litres (e.g., 50L to 500L).
- **Control & Material Architecture**:
  - Frequency converter (VFD) inverter control.
  - Stainless steel suction and discharge manifolds (304 or 316).
  - Spring or neoprene anti-vibration isolators.

## Safety & Governance
- Strictly candidate shadow mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`).
- Deterministic 2D coordinate grid snapping (default `2.5 pt`).
- Safety primitive ceiling (`MAX_SAFETY_CAP_PRIMITIVES = 20_000`).
