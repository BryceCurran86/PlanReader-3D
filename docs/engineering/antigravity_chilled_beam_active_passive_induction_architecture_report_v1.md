# Architecture Report: HVAC Chilled Beam Induction Terminal (Active & Passive) Shadow Authority (v1)

## Executive Summary
This document establishes the shadow candidate geometry authority for HVAC active and passive chilled beam induction terminals, multi-service beams, and exposed architectural hydronic beams (`pb_source_chilled_beam_active_passive_induction_shadow.py`).

## Scope & Classification
- **Element Types**:
  - `ACTIVE_CHILLED_BEAM`: Active induction chilled beam with primary air plenum and aerodynamic induction nozzles.
  - `PASSIVE_CHILLED_BEAM`: Natural convection passive chilled beam (cooling coil only, zero duct airflow).
  - `MULTI_SERVICE_CHILLED_BEAM`: Integrated active/passive beam housing LED luminaires, PIR occupancy sensors, and emergency audio.
  - `EXPOSED_ARCHITECTURAL_BEAM`: Free-hanging architectural beam with perforated fascia and seismic suspension kit.
- **Attributes**: Length (1200–3600 mm), width (300, 600 mm), pipe configuration (2-pipe cooling, 4-pipe heating/cooling), primary airflow (L/s), cooling capacity (W), and integrated lighting.

## Safety & Governance
- Strictly candidate shadow authority (`status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`).
- Snapping tolerance: 2.5 pt deterministic snapping.
- Primitive cap: 20,000 primitives.
