# Antigravity Architecture Report: Architectural Acoustic Louver & Plantroom Screen Shadow Authority (v1)

## Executive Summary
This report defines the deterministic shadow extraction authority for architectural acoustic louvers, rooftop plantroom acoustic screen walls, continuous weather louvers, and perforated acoustic blade enclosures from architectural facade details and mechanical roof plan drawings.

## Scope & Target Geometry
- Identifies exterior acoustic louvers and mechanical rooftop plantroom screen barriers.
- Classifies louver frame depth (e.g. 150mm single bank, 300mm double bank, 600mm), blade acoustic infill insulation, sound reduction index (Rw in dB), aerodynamic free area percentage (e.g. 40-55%), and bird/insect wire mesh screens.

## Guardrails & Non-Negotiables
- Shadow Candidate Mode: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Snapping Tolerance: `SNAP_TOLERANCE_PT = 2.5 pt`.
- Primitive Cap: `MAX_SAFETY_CAP_PRIMITIVES = 20_000`.
- Zero alterations to baseline gold benchmarks or commercial schemas.
