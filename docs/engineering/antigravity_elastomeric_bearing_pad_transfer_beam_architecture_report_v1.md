# Precast Concrete Bridge / Transfer Beam Neoprene Elastomeric Bearing Pad Shadow Authority Architecture Report (v1)

## Executive Summary
This authority module implements deterministic, candidate-only shadow extraction for structural steel-laminated elastomeric bearing pads, plain neoprene strips, PTFE sliding bearings, pot bearings, and shear dowels under precast bridge girders and transfer beams.

## Scope & Classification
- **Bearing System Configurations**:
  - `STEEL_LAMINATED_ELASTOMERIC`: Vulcanized polychloroprene (neoprene) interleaved with high-strength carbon steel shims.
  - `PLAIN_ELASTOMERIC_STRIP`: Unreinforced high-durometer neoprene bearing strips.
  - `PTFE_SLIDING_BEARING`: Dimpled virgin PTFE bonded to elastomer sliding against mirror-finish stainless steel.
  - `POT_BEARING`: Confined elastomer disc within a machined steel cylinder (fixed or guided).
  - `SHEAR_DOWEL_PIN`: Restraining shear dowel locating pin.
- **Physical & Loading Metrics**:
  - Plan dimensions and overall thickness (e.g., 400x300x52mm).
  - Hardness durometer (standard 60 IRHD / Shore 60A).
  - Design ultimate vertical load capacity ($kN$).

## Safety & Governance
- Strictly candidate shadow mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`).
- Deterministic 2D coordinate grid snapping (default `2.5 pt`).
- Safety primitive ceiling (`MAX_SAFETY_CAP_PRIMITIVES = 20_000`).
