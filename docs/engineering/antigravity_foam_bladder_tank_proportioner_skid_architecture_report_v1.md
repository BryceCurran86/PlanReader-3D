# Architecture Report: Fire Protection Foam Water Deluge / Bladder Tank Proportioner Skid Shadow Authority (v1)

## Executive Summary
This document establishes the shadow candidate geometry authority for high-hazard fire protection foam-water deluge systems, vertical/horizontal bladder tanks, ratio controllers, proportioner skids, and high-expansion foam generators (`pb_source_foam_bladder_tank_proportioner_skid_shadow.py`).

## Scope & Classification
- **Element Types**:
  - `VERTICAL_BLADDER_TANK_PROPORTIONER`: Vertical foam concentrate bladder tank with pre-piped ratio controller.
  - `HORIZONTAL_BLADDER_TANK_PROPORTIONER`: Horizontal bladder tank for low-headroom plant rooms or hangars.
  - `FOAM_WATER_DELUGE_VALVE_SKID`: Water deluge valve skid with hydraulic concentrate shutoff valve.
  - `INLINE_BALANCED_PRESSURE_PROPORTIONER`: In-line balanced pressure proportioner (ILBP) skid.
  - `HIGH_EXPANSION_FOAM_GENERATOR`: High-expansion foam generator for warehouse/hangar total flooding.
- **Attributes**: Tank volume (500–10,000 L), proportioning ratio (1%, 3%, 6%), ratio controller size (DN50–DN250), concentrate type (fluorine-free SFFF, AR-AFFF, standard AFFF, high-expansion detergent), and working pressure rating.

## Safety & Governance
- Strictly candidate shadow authority (`status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`).
- Snapping tolerance: 2.5 pt deterministic snapping.
- Primitive cap: 20,000 primitives.
