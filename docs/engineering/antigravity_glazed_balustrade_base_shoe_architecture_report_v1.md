# Structural Glazed Balustrade & Base U-Channel Shoe Shadow Authority Architecture Report (v1)

## Executive Summary
This authority module implements deterministic, candidate-only shadow extraction for structural glass balustrades, frameless balustrade base shoe channels, standoff fixings, and spigot clamps from architectural drawings and schedules.

## Scope & Classification
- **System Types**:
  - `BASE_SHOE`: Continuous structural aluminium or stainless U-channel base profiles (dry glaze wedge system).
  - `SPIGOT`: Core-drilled or surface bolted stainless steel mini-posts / spigot clamps.
  - `POINT_FIXED`: Side-mounted disc standoffs / point fixings.
  - `POST_AND_RAIL`: Traditional vertical post system with glass infill panels.
- **Glass Configurations**:
  - Toughened Laminated (PVB / SentryGlas interlayers) or Monolithic Toughened.
  - Thickness identification (e.g., 12mm, 15mm, 17.52mm, 21.52mm).
- **Handrail & Barrier Rules**:
  - Channel caps, offset continuous handrails, or frameless top edges.
  - Minimum barrier height identification (e.g., 1000mm, 1100mm, 1200mm).

## Safety & Governance
- Strictly candidate shadow mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`).
- Deterministic 2D coordinate grid snapping (default `2.5 pt`).
- Safety primitive ceiling (`MAX_SAFETY_CAP_PRIMITIVES = 20_000`).
