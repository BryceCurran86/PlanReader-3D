# Architecture Report: Automatic Sprinkler System Pre-Action & Deluge Valve Skid Shadow Authority (v1)

## Executive Summary
This document establishes the shadow candidate geometry authority for Automatic Fire Sprinkler Pre-Action and Deluge Valve Skids (`pb_source_sprinkler_preaction_deluge_valve_skid_shadow.py`).

## Scope & Classification
- **Pre-action Types**: Single Interlock (`SINGLE_INTERLOCK_PREACTION`), Double Interlock (`DOUBLE_INTERLOCK_PREACTION`), Non-Interlock (`NON_INTERLOCK_PREACTION`), Deluge Valve Skid (`DELUGE_VALVE_SKID`), and Preaction Trim Station (`PREACTION_TRIM_STATION`).
- **Nominal Size**: DN40 to DN250 (1.5" to 10"), standard default DN100 (4").
- **Pressure Ratings**: Standard working pressure (default 1725 kPa / 250 psi).
- **Actuation & Supervision**: Electric-Pneumatic, Electric-Only, Pneumatic-Only, Hydraulic, Manual Emergency; Nitrogen or Compressed Air supervisory gas charging.
- **Ancillaries**: Solenoid release, Air Maintenance Device (AMD), Water Motor Alarm Gong.

## Safety & Governance
- Strictly candidate shadow authority (`status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`).
- Snapping tolerance: 2.5 pt deterministic snapping.
- Primitive cap: 20,000 primitives.
