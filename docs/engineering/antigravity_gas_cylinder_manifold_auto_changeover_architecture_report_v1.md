# Architecture Report: High-Purity Gas Laboratory Gas Cylinder Manifold & Changeover Skid Shadow Authority (v1)

## Executive Summary
This document establishes the shadow candidate geometry authority for high-purity laboratory gas cylinder manifolds, automatic changeover panels, point-of-use pressure regulator stations, and ventilated gas safety cabinets (`pb_source_gas_cylinder_manifold_auto_changeover_shadow.py`).

## Scope & Classification
- **Element Types**:
  - `AUTO_CHANGEOVER_GAS_MANIFOLD`: Differential pressure / pneumatic automatic continuous supply changeover manifold.
  - `MANUAL_GAS_MANIFOLD`: Manual dual-bank header rack with isolation valves and purge ports.
  - `POINT_OF_USE_REGULATOR_PANEL`: Secondary laboratory bench / fume hood pressure regulation station.
  - `TOXIC_GAS_SAFETY_CABINET`: Exhausted gas cylinder enclosure with automatic shutoff and gas leak monitoring.
  - `EXTERNAL_GAS_CYLINDER_CAGE`: Outdoor perimeter bottle storage cage with cylinder racks.
- **Attributes**: Gas service (Nitrogen, Argon, Helium, Hydrogen, Oxygen, Carbon Dioxide, Specialty Mix), cylinder bank configuration (1 to 12 cylinders), inlet pressure (200–300 bar), outlet pressure (1–10 bar), purity grade (Grade 5.0, 6.0, industrial), purge assembly, and alarm telemetry.

## Safety & Governance
- Strictly candidate shadow authority (`status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`).
- Snapping tolerance: 2.5 pt deterministic snapping.
- Primitive cap: 20,000 primitives.
