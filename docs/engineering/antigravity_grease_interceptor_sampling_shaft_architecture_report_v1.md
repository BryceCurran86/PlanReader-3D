# Commercial Kitchen Grease Arrestor / Interceptor Pit & Sampling Shaft Shadow Authority Architecture Report (v1)

## Executive Summary
This authority module implements deterministic, candidate-only shadow extraction for commercial kitchen trade waste grease interceptor traps (arrestors), coalescing plate separators, gastight trafficable covers, remote tanker suction pump-out lines, and downstream authority sampling shafts.

## Scope & Classification
- **Element Configurations**:
  - `BELOW_GROUND_ARRESTOR`: In-ground precast concrete or heavy-duty polyethylene trade waste interceptor.
  - `ABOVE_GROUND_ARRESTOR`: Freestanding indoor/basement suspended grease trap unit.
  - `SAMPLING_SHAFT`: Mandated water authority monitoring, dip-testing, and compliance sampling chamber.
  - `PUMP_OUT_LINE`: Fixed remote suction line with camlock coupling for vacuum tanker waste disposal.
  - `DOSING_UNIT`: Biological enzyme or bio-additive dosing injection system.
- **Capacity & Mechanical Attributes**:
  - Effective grease retention volume in litres (1,000L to 10,000L).
  - Tank shell fabrication: Precast reinforced concrete, roto-moulded polyethylene, or GRP.
  - Heavy vehicle trafficable access covers (AS 3996 Class B/D gastight seal).

## Safety & Governance
- Strictly candidate shadow mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`).
- Deterministic 2D coordinate grid snapping (default `2.5 pt`).
- Safety primitive ceiling (`MAX_SAFETY_CAP_PRIMITIVES = 20_000`).
