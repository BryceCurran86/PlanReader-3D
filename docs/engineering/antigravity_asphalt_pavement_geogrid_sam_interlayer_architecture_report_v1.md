# Architecture Report: Civil Asphalt Pavement Geogrid Reinforcement & Stress Absorbing Membrane Shadow Authority (v1)

## Executive Summary
This document establishes the shadow candidate geometry authority for civil asphalt pavement geogrids, Stress Absorbing Membrane Interlayers (SAMI), glass/carbon fiber reinforcement meshes, and crack bandages (`pb_source_asphalt_pavement_geogrid_sam_interlayer_shadow.py`).

## Scope & Classification
- **Element Types**:
  - `FIBERGLASS_ASPHALT_GEOGRID`: Knitted glass fiber geogrid with elastomeric bitumen coating.
  - `CARBON_FIBER_PAVEMENT_GRID`: High-modulus carbon grid for heavy bus lanes / airport taxiways.
  - `SAMI_STRESS_ABSORBING_MEMBRANE`: Stress Absorbing Membrane Interlayer (non-woven paving fabric saturated with hot tack coat).
  - `POLYPROPYLENE_BIAXIAL_GEOGRID`: Extruded biaxial polypropylene geogrid for subbase/subgrade stabilization.
  - `JOINT_SEAL_REINFORCEMENT_STRIP`: Narrow 300–500 mm wide self-adhesive pavement crack bandage/strip across expansion/cold joints.
- **Attributes**: Ultimate tensile strength (50–200 kN/m), grid aperture (12.5–40 mm), roll width (1.0–4.0 m), self-adhesive backing, bitumen retention (L/m²), and high-temperature resistance.

## Safety & Governance
- Strictly candidate shadow authority (`status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`).
- Snapping tolerance: 2.5 pt deterministic snapping.
- Primitive cap: 20,000 primitives.
