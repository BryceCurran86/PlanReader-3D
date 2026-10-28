# Architecture Report: Architectural Louvered Sunshade / Aerofoil Louver Cantilever Shadow Authority (v1)

## Executive Summary
This document establishes the shadow candidate geometry authority for architectural louvered sunshades, horizontal aerofoil cantilevers, vertical solar fins, motorized tracking louvers, and outrigger brackets (`pb_source_louvered_sunshade_aerofoil_cantilever_shadow.py`).

## Scope & Classification
- **Element Types**:
  - `HORIZONTAL_CANTILEVER_SUNSHADE`: Horizontal cantilevered sunshade canopy with outrigger blades and fascia bullnose tube.
  - `VERTICAL_AEROFOIL_SOLAR_FIN`: Vertical facade aerofoil fin mounted between slab edges.
  - `MOTORIZED_ELECTRIC_OPERABLE_SOLAR_LOUVER`: Automated pivoting solar tracking aerofoil louvers driven by 24V linear actuators.
  - `CONTINUOUS_LINEAR_FACADE_LOUVER`: Continuous architectural screening louver bank over plant rooms or parking decks.
  - `STRUCTURAL_OUTRIGGER_BRACKET`: Heavy extruded aluminum / galvanized steel knife outrigger bracket.
- **Attributes**: Blade chord width (150–400 mm), projection outreach (600–1800 mm), blade tilt angle (0° to 90°), blade profile (aerofoil elliptical, rectangular box, Z-blade, C-channel), finish type (powder coated, anodized, timber grain), and motorized automation.

## Safety & Governance
- Strictly candidate shadow authority (`status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`).
- Snapping tolerance: 2.5 pt deterministic snapping.
- Primitive cap: 20,000 primitives.
