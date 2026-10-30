# Architecture Report: Cast-in Electrical Floor Trench Duct & Junction Box Trunking Shadow Authority (v1)

## Executive Summary
This document establishes the shadow candidate geometry authority for cast-in and in-screed electrical floor trench ducts, multi-compartment flush trunking, accessible service outlet boxes, and crossover junction boxes (`pb_source_cast_in_floor_trench_duct_trunking_shadow.py`).

## Scope & Classification
- **Element Types**:
  - `FLUSH_FLOOR_TRUNK_3_COMPARTMENT`: 3-compartment flush floor trunking (Power, Telecom, Data).
  - `FLUSH_FLOOR_TRUNK_2_COMPARTMENT`: 2-compartment flush floor trunking (Power, Data).
  - `IN_SCREED_FLOOR_DUCT`: Fully enclosed in-screed duct run.
  - `SERVICE_OUTLET_BOX`: Recessed/flush service box with power/data accessory mounting.
  - `INTERSECTION_JUNCTION_BOX`: Crossover junction box with flyover segregation bridge.
- **Attributes**: Width (150–450 mm), depth (25–100 mm), number of compartments (1, 2, or 3), cover infill type (carpet tray, tile infill, brass trim, stainless trim), and load class (light pedestrian, medium commercial, heavy wheeled).

## Safety & Governance
- Strictly candidate shadow authority (`status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`).
- Snapping tolerance: 2.5 pt deterministic snapping.
- Primitive cap: 20,000 primitives.
