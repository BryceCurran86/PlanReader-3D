# Civil Stormwater Detention Orifice Plate & Trash Screen Pit Shadow Authority Architecture Report (v1)

## Executive Summary
This authority module implements deterministic, candidate-only shadow extraction for civil stormwater on-site detention (OSD) discharge control pits (DCP), laser-cut stainless steel orifice restrictor plates, debris trash screens, and emergency overflow weirs.

## Scope & Classification
- **Element Types**:
  - `DISCHARGE_CONTROL_PIT`: Complete OSD outlet control chamber (DCP).
  - `ORIFICE_PLATE`: Machined or laser-cut stainless steel flow restricting orifice plate.
  - `TRASH_SCREEN`: Inclined or vertical debris barrier cage protecting low-flow orifices.
  - `OVERFLOW_WEIR`: Internal weir baffle crest accommodating peak bypass storm flows.
- **Dimensional & Flow Attributes**:
  - Calibrated orifice plate internal diameter ($D_o$ from 40mm to 300mm).
  - Metallurgy: Grade 316 or 304 stainless steel with neoprene seating gasket.
  - Trash screen geometry: Inclined (45°/60°) mesh screen vs vertical box cage.
  - Overflow weir notch width (mm).

## Safety & Governance
- Strictly candidate shadow mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`).
- Deterministic 2D coordinate grid snapping (default `2.5 pt`).
- Safety primitive ceiling (`MAX_SAFETY_CAP_PRIMITIVES = 20_000`).
