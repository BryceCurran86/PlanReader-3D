# Roof Access Ladder with Safety Cage & Fall-Arrest Static Line Shadow Authority Architecture Report (v1)

## Executive Summary
This authority module implements deterministic, candidate-only shadow extraction for roof height safety equipment: fixed vertical caged access ladders, un-caged cat ladders, horizontal fall-arrest static line cables, intermediate rest platforms, lockable security gates, and weatherproof roof access hatches.

## Scope & Classification
- **Element Configurations**:
  - `CAGED_ACCESS_LADDER`: Permanently mounted ladders with safety hoops/cages for heights $\ge 3.0$ m.
  - `UNCAGED_LADDER`: Low-height vertical cat ladders or ladders equipped with vertical fall-arrest arrestors.
  - `STATIC_LINE_SYSTEM`: Continuous 8mm Grade 316 stainless steel wire rope horizontal lifelines.
  - `ACCESS_HATCH`: Insulated counter-balanced aluminum roof access hatch.
  - `STEP_OVER_PLATFORM`: Crossover bridge / step-over platform.
- **Physical & Safety Standards Compliance**:
  - Vertical ladder climb height (mm).
  - Safety cage provision and intermediate landing/rest platforms.
  - Anti-climb lockable security gate at base.
  - Materials: Structural aluminium, hot-dip galvanized steel, stainless steel 316.

## Safety & Governance
- Strictly candidate shadow mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`).
- Deterministic 2D coordinate grid snapping (default `2.5 pt`).
- Safety primitive ceiling (`MAX_SAFETY_CAP_PRIMITIVES = 20_000`).
