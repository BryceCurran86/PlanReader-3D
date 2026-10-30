# Commercial Kitchen Exhaust Hood Grease Filter & Ansul Fire Suppression Shadow Authority Architecture Report (v1)

## Executive Summary
This authority module implements deterministic, candidate-only shadow extraction for commercial kitchen exhaust canopies, stainless steel baffle grease filters, UV-C grease destruction systems, wet chemical fire suppression systems (Ansul R-102), detection fusible links, and gas solenoid safety interlocks.

## Scope & Classification
- **Hood Configurations**:
  - `TYPE_1_GREASE_HOOD`: Heavy-duty cooking exhaust canopy with fire suppression.
  - `TYPE_2_CONDENSATE_HOOD`: Steam, heat, and vapour capture canopy (e.g., dishwashers).
  - `ISLAND_CANOPY` & `WALL_MOUNTED_CANOPY`.
- **Grease Extraction Technology**:
  - Centrifugal stainless steel baffle filters (UL 1046 compliant).
  - UV-C photochemical ozone grease breakdown cassettes.
  - Water-wash automated manifold cleaning.
- **Fire Life Safety Integration**:
  - Pre-engineered wet chemical fire extinguishing system (Ansul R-102 / Amerex KP).
  - Appliance, plenum, and duct exhaust protection nozzles.
  - Gas supply emergency shut-off valve interlock.
  - Remote manual actuation pull station.

## Safety & Governance
- Strictly candidate shadow mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`).
- Deterministic 2D coordinate grid snapping (default `2.5 pt`).
- Safety primitive ceiling (`MAX_SAFETY_CAP_PRIMITIVES = 20_000`).
