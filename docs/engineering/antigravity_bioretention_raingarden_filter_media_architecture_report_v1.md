# Antigravity Architecture Report: Stormwater Bioretention Raingarden & Saturated Zone Shadow Authority (v1)

## Executive Summary
This report defines the deterministic shadow extraction authority for civil stormwater bioretention basins, raingardens, biofiltration media layers, submerged saturated anoxic zones (IWS), and perforated underdrain collection systems from civil engineering and landscape drainage plans.

## Scope & Target Geometry
- Identifies bioretention basins, raingarden cells, and tree biofilter pits.
- Classifies filter media depth (typically 400mm-800mm loamy sand), transition sand layer depth (100mm-150mm), drainage gravel depth (150mm-200mm), submerged saturated zone depth (for denitrification), extended detention ponding depth, and slotted underdrain pipe diameter.

## Guardrails & Non-Negotiables
- Shadow Candidate Mode: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Snapping Tolerance: `SNAP_TOLERANCE_PT = 2.5 pt`.
- Primitive Cap: `MAX_SAFETY_CAP_PRIMITIVES = 20_000`.
- Zero alterations to baseline gold benchmarks or commercial schemas.
