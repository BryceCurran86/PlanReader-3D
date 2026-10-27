# Civil Subsurface Infiltration Basin & Trench Geocellular Drainage Shadow Authority Architecture Report (v1)

## Executive Summary
This authority module implements deterministic, candidate-only shadow extraction for civil stormwater subsurface infiltration basins, soakaway trenches, geocellular infiltration matrix crates, non-woven geotextile envelopes, and inspection risers.

## Scope & Classification
- **System Configurations**:
  - `GEOCELLULAR_BASIN`: Subsurface modular polypropylene infiltration cells with high void ratios (≥90%).
  - `INFILTRATION_TRENCH`: Clean aggregate-filled soakaway trenches with perforated distribution pipes.
  - `SURFACE_BASIN`: Open unlined dry infiltration swale or detention basin promoting natural exfiltration.
  - `INSPECTION_RISER`: Vertical inspection, sediment sampling, and ventilation shafts.
  - `SILT_TRAP`: Upstream pre-treatment catchpit/sump.
- **Physical & Material Attributes**:
  - Usable storage volume in cubic meters ($m^3$).
  - Trench excavation depth (mm).
  - Geotextile permeable membrane specification (non-woven needle-punched vs geomembrane).
  - Aggregate grading (e.g., 20-40mm washed aggregate).

## Safety & Governance
- Strictly candidate shadow mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`).
- Deterministic 2D coordinate grid snapping (default `2.5 pt`).
- Safety primitive ceiling (`MAX_SAFETY_CAP_PRIMITIVES = 20_000`).
