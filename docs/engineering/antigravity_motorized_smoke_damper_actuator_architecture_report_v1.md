# Architecture Report: Fire Life Safety Smoke Damper Actuator & Modulating Motorized Core Shadow Authority (v1)

## Executive Summary
This document establishes the shadow candidate geometry authority for fire life safety smoke dampers, motorized combination fire/smoke dampers (MFSD), modulating smoke management dampers, and fast-acting spring-return actuators (`pb_source_motorized_smoke_damper_actuator_shadow.py`).

## Scope & Classification
- **Element Types**:
  - `COMBINATION_FIRE_SMOKE_DAMPER`: Motorized combination fire and smoke damper (15-second spring-return + dual temperature cutoff).
  - `LEAKAGE_CLASS_I_SMOKE_DAMPER`: AMCA 500-D Class I ultra-low leakage smoke damper.
  - `MODULATING_SMOKE_CONTROL_DAMPER`: Modulating 0-10V smoke exhaust / stair pressurization control damper.
  - `FAST_ACTING_SPRING_RETURN_ACTUATOR`: 15-second fast-acting actuator with auxiliary feedback switches.
  - `THERMAL_DISC_SENSOR_SLEEVE`: Duct thermal response sensor (TSD) sleeve assembly with manual test switch.
- **Attributes**: Width and height (150–1800 mm), actuator voltage (24V AC/DC, 230V AC, 120V AC, pneumatic), leakage rating (Class I, II, III), fire rating (60–240 minutes), and closure time.

## Safety & Governance
- Strictly candidate shadow authority (`status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`).
- Snapping tolerance: 2.5 pt deterministic snapping.
- Primitive cap: 20,000 primitives.
