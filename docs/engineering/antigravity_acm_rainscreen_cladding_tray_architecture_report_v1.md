# Architectural Metal Composite Material (MCM) / ACM Rainscreen Cladding Shadow Authority Architecture Report (v1)

## Executive Summary
This authority module implements deterministic, candidate-only shadow extraction for architectural metal composite materials (MCM), aluminium composite materials (ACM), routed cassette trays, non-combustible mineral cores, open-joint ventilated rainscreens, and top-hat subframing.

## Scope & Classification
- **Element Types**:
  - `CASSETTE_TRAY`: Prefabricated folded cassette tray hung on concealed clips.
  - `FLAT_SHEET`: Flat panel sheets face-fixed with structural rivets.
  - `SUBFRAME_TOP_HAT`: Aluminium or galvanized steel top-hat subframing rails.
  - `HELPING_HAND_BRACKET`: Adjustable thermal-break wall brackets.
  - `FLASHING`: Perimeter, sill, and head aluminum flashings.
- **Core & Fire Performance**:
  - `NON_COMBUSTIBLE_MINERAL`: A2 / FR non-combustible mineral filled core.
  - `SOLID_ALUMINIUM`: 3mm/4mm solid non-composite aluminum plate.
  - `ALUMINIUM_HONEYCOMB`: Honeycomb composite core.
- **Joint & Cavity Detail**:
  - Open-joint ventilated and drained rainscreen cavity vs sealed silicone joints.
  - Ventilated cavity insulation depth (e.g., 50mm to 150mm).

## Safety & Governance
- Strictly candidate shadow mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`).
- Deterministic 2D coordinate grid snapping (default `2.5 pt`).
- Safety primitive ceiling (`MAX_SAFETY_CAP_PRIMITIVES = 20_000`).
