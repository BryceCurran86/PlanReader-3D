# Antigravity Architecture Report: Galvanized Steel Shelf Angle & Brickwork Lintel Shadow Authority (v1)

## Executive Summary
This report defines the deterministic shadow extraction authority for galvanized structural steel shelf angles, brickwork opening lintels, T-bars, and cavity wall support angles from structural steel and masonry drawings.

## Scope & Target Geometry
- Identifies hot-dip galvanized steel angle lintels (equal angles, unequal angles, T-bars, shelf angles, and proprietary Galintel/Rendabar profiles) over masonry and cavity wall openings.
- Classifies section profile (EA, UA, T-bar, shelf angle), dimensions (leg 1 x leg 2 x thickness), span length, minimum end bearing (e.g. 150mm), and corrosion protection coating (HDG R3/R4, stainless steel 316).

## Guardrails & Non-Negotiables
- Shadow Candidate Mode: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Snapping Tolerance: `SNAP_TOLERANCE_PT = 2.5 pt`.
- Primitive Cap: `MAX_SAFETY_CAP_PRIMITIVES = 20_000`.
- Zero alterations to baseline gold benchmarks or commercial schemas.
