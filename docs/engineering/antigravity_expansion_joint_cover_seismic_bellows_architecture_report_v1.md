# Architecture Report: Architectural Expansion Joint Cover Floor / Wall Seismic Bellows Shadow Authority (v1)

## Executive Summary
This document establishes the shadow candidate geometry authority for architectural expansion joint covers, seismic floor/wall bellows, fire-rated barriers, and roof weather-seal joints (`pb_source_expansion_joint_cover_seismic_bellows_shadow.py`).

## Scope & Classification
- **Element Types**:
  - `SEISMIC_FLOOR_JOINT_COVER`: Heavy-duty centering bar seismic floor joint cover with flush pans or solid plates.
  - `FLUSH_WALL_JOINT_COVER`: Surface-mount or flush elastomeric/aluminum wall joint cover.
  - `CEILING_EXPANSION_COVER`: Concealed or flush ceiling expansion cover with centering clips.
  - `ROOF_EXPANSION_BELLOWS`: Weatherproof EPDM/Santoprene roof expansion bellows with flashing.
  - `FIRE_RATED_BLANKET_BARRIER`: 2-hour or 4-hour intumescent / ceramic fire blanket barrier assembly.
- **Attributes**: Nominal gap width (20–500 mm), movement capacity percent (±25% to ±100%), cover materials (anodized aluminum, stainless steel, extruded bronze, Santoprene, EPDM), moisture/vapor barrier, and load ratings (pedestrian, pneumatic tire, heavy forklift).

## Safety & Governance
- Strictly candidate shadow authority (`status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`).
- Snapping tolerance: 2.5 pt deterministic snapping.
- Primitive cap: 20,000 primitives.
