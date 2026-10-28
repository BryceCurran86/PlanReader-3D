# Architecture Report: Civil Sewer Vacuum Air Release & Combined Vacuum Breaker Valve Pit Shadow Authority (v1)

## Executive Summary
This document establishes the shadow candidate geometry authority for civil sewer force main combination air valves, vacuum breaker valves, isolation/flush assemblies, and precast valve chamber pits (`pb_source_sewer_air_release_vacuum_breaker_valve_shadow.py`).

## Scope & Classification
- **Element Types**:
  - `SEWAGE_COMBINATION_AIR_VALVE`: Non-slam wastewater combination air release and vacuum breaker valve.
  - `SEWAGE_AIR_RELEASE_VALVE`: Continuous pressurised air exhaust valve with elongated anti-fouling lower neck.
  - `VACUUM_BREAKER_VALVE`: Large-orifice vacuum relief / air inflow valve preventing negative pressure collapse.
  - `ISOLATION_AND_FLUSH_ASSEMBLY`: Resilient seat gate / knife gate isolation and maintenance flushing connection.
  - `AIR_VALVE_CHAMBER_PIT`: Precast concrete valve pit with vented access cover and odor filter canister.
- **Attributes**: Nominal size (DN50–DN300), pressure rating (PN10–PN40), body material (epoxy ductile iron, 316 stainless steel, polymeric nylon), activated carbon odor filter, and backflush assembly.

## Safety & Governance
- Strictly candidate shadow authority (`status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`).
- Snapping tolerance: 2.5 pt deterministic snapping.
- Primitive cap: 20,000 primitives.
