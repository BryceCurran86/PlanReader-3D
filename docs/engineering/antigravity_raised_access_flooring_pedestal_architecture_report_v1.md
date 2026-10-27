# Raised Access Computer Flooring Pedestal & Stringer Shadow Authority Architecture Report (v1)

## Executive Summary
This authority module implements deterministic, candidate-only shadow extraction for commercial office and data center raised access flooring (RAF), adjustable pedestals, interlocking stringers, perforated airflow panels, and cable grommets.

## Scope & Classification
- **Element Types**:
  - `PANEL`: Modular 600x600mm access floor tile.
  - `PEDESTAL`: Adjustable galvanized steel subfloor pedestals.
  - `STRINGER`: Bolted or snap-on grid perimeter/field stringers.
  - `RAMP_STEP`: Transition ramp or perimeter fascia step.
  - `CABLE_GROMMET`: Airtight brush grommet or cable pass-through.
  - `AIR_GRILLE`: Perforated ventilation tile with volume control damper.
- **Core Materials & Grades**:
  - Steel cementitious core, high-density particleboard (woodcore), calcium sulphate.
  - Load classes: Light, Medium, Heavy, Extra-Heavy point load ratings.
  - Finished Floor Height (FFH) extraction (e.g., 150mm to 900mm).

## Safety & Governance
- Strictly candidate shadow mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`).
- Deterministic 2D coordinate grid snapping (default `2.5 pt`).
- Safety primitive ceiling (`MAX_SAFETY_CAP_PRIMITIVES = 20_000`).
