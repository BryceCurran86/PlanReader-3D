# Variable Air Volume (VAV) Terminal Unit & Electric Reheat Coil Shadow Authority Architecture Report (v1)

## Executive Summary
This authority module implements deterministic, candidate-only shadow extraction for commercial HVAC Variable Air Volume (VAV) terminal units, fan powered boxes (FPB), electric reheat coils, hydronic hot water reheat coils, and integral discharge sound attenuators.

## Scope & Classification
- **Unit Configurations**:
  - `SINGLE_DUCT_VAV`: Pressure-independent single duct throttling terminal boxes.
  - `FAN_POWERED_PARALLEL`: Parallel fan powered induction boxes.
  - `FAN_POWERED_SERIES`: Series continuous fan powered terminal units.
  - `DUAL_DUCT_VAV`: Dual duct mixing terminal boxes.
- **Reheat System**:
  - `ELECTRIC_REHEAT`: SCR modulating or staged electric heating element with capacity (kW).
  - `HOT_WATER_REHEAT`: LTHW hydronic heating coil (1-row or 2-row).
  - `NO_REHEAT`: Cooling-only throttling boxes.
- **Dimensional & Airflow Metrics**:
  - Primary inlet spigot collar diameter (e.g., 150mm to 400mm).
  - Design supply airflow (L/s).
  - Discharge acoustic attenuation module detection.

## Safety & Governance
- Strictly candidate shadow mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`).
- Deterministic 2D coordinate grid snapping (default `2.5 pt`).
- Safety primitive ceiling (`MAX_SAFETY_CAP_PRIMITIVES = 20_000`).
