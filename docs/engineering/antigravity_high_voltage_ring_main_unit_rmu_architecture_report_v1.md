# High-Voltage Electrical Ring Main Unit (RMU) & SF6/Dry Air Switchgear Shadow Authority Architecture Report (v1)

## Executive Summary
This authority module implements deterministic, candidate-only shadow extraction for medium/high-voltage electrical Ring Main Units (RMU), gas-insulated switchgear (GIS), vacuum circuit breakers (VCB), SF6 and dry air insulation chambers, and internal arc classified (IAC) substation enclosures.

## Scope & Classification
- **Switchgear Configurations**:
  - `RING_MAIN_UNIT`: Compact multi-way switchgear (e.g., 3-way CCV or 4-way CCVV arrangements).
  - `CIRCUIT_BREAKER_UNIT`: Dedicated tee-off vacuum circuit breaker unit for transformer protection.
  - `METERING_UNIT`: High-voltage revenue CT/VT metering panel.
  - `EXTENSIBLE_SWITCHGEAR`: Modular extensible busbar switchboard panels.
- **Electrical & Thermal Parameters**:
  - Operational voltage ratings: 11kV, 22kV, 33kV.
  - Short-circuit breaking withstand: 16kA, 20kA, 21kA, 25kA (1s/3s).
  - Insulation technology: SF6 gas-insulated sealed stainless steel tank vs eco Dry Air (SF6-free).
  - Internal Arc Classification (IAC AFLR).

## Safety & Governance
- Strictly candidate shadow mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`).
- Deterministic 2D coordinate grid snapping (default `2.5 pt`).
- Safety primitive ceiling (`MAX_SAFETY_CAP_PRIMITIVES = 20_000`).
