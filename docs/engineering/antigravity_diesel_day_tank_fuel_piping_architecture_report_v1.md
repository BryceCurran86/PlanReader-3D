# Antigravity Architecture Report: Emergency Diesel Generator Fuel Day Tank & Double-Wall Fuel Piping Shadow Authority (v1)

## Executive Summary
This report defines the deterministic shadow extraction authority for emergency standby diesel generator fuel day tanks, base/belly tanks, and double-wall fuel supply/return containment piping from building services and hydraulic mechanical drawings.

## Scope & Target Geometry
- Identifies day tank equipment callouts, belly tanks, and fuel storage containment specifications.
- Identifies double-wall coaxial fuel oil/diesel transfer pipe lines with secondary containment and interstitial leak detection sensors.
- Classifies tank storage volume (liters or gallons), mounting type (self-bunded, belly, floor/skid mounted, wall mounted), fuel pipe diameter (DN/nominal mm), and line service (supply, return, vent, overflow, fill).

## Guardrails & Non-Negotiables
- Shadow Candidate Mode: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Snapping Tolerance: `SNAP_TOLERANCE_PT = 2.5 pt`.
- Primitive Cap: `MAX_SAFETY_CAP_PRIMITIVES = 20_000`.
- Zero alterations to baseline gold benchmarks or commercial schemas.
