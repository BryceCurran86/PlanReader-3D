# Antigravity Architecture Report: Precast Insulated Sandwich Concrete Panel & Composite Tie Shadow Authority (v1)

## Executive Summary
This report defines the deterministic shadow extraction authority for precast insulated sandwich concrete wall panels, non-conductive fiber-composite connector ties (GFRP / BFRP / CFRP), and continuous rigid insulation cores from structural precast and architectural facade drawings.

## Scope & Target Geometry
- Identifies 3-layer insulated precast concrete sandwich panels (outer facade wythe, rigid insulation core, and inner structural wythe).
- Classifies wythe thicknesses (outer, insulation core, inner loadbearing wythe), insulation material (XPS, PIR, EPS, phenolic foam), connector pin technology (glass fiber composite, basalt fiber, stainless steel trusses), and continuous thermal barrier ratings.

## Guardrails & Non-Negotiables
- Shadow Candidate Mode: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Snapping Tolerance: `SNAP_TOLERANCE_PT = 2.5 pt`.
- Primitive Cap: `MAX_SAFETY_CAP_PRIMITIVES = 20_000`.
- Zero alterations to baseline gold benchmarks or commercial schemas.
