# Antigravity Architecture Report: Solar PV Roof Array DC Isolator Switch & Inverter Shadow Authority (v1)

## Executive Summary
This report defines the deterministic shadow extraction authority for solar photovoltaic (PV) string/central inverters, rooftop lockable DC isolator switches, combiner boxes, and PV balance of system (BOS) components from electrical and renewable energy layouts.

## Scope & Target Geometry
- Identifies solar PV rooftop DC isolator switches, array disconnects, string inverters, and DC combiner boxes.
- Classifies electrical power ratings (kW/kVA), DC voltage and current ratings (e.g. 1000V 32A, 1500V), IP weather protection ratings (e.g. IP66 outdoor enclosures), mounting configuration (roof-mounted with sunshade, wall-mounted), and MPPT input channels.

## Guardrails & Non-Negotiables
- Shadow Candidate Mode: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Snapping Tolerance: `SNAP_TOLERANCE_PT = 2.5 pt`.
- Primitive Cap: `MAX_SAFETY_CAP_PRIMITIVES = 20_000`.
- Zero alterations to baseline gold benchmarks or commercial schemas.
