# Architecture Report: Source Architectural Expansion Joint Fire Barrier Blanket Shadow Authority (Item 222 / Blocker 162)

## 1. Executive Summary
Building codes mandate that fire-resistance compartmentation must continue uninterrupted across structural movement, expansion, and seismic joints. Architectural expansion joint details (e.g. Inpro Fireline, Construction Specialties Reflex, Balco, Emseal) specify flexible fire barrier blankets (ceramic fiber quilted foil blankets, intumescent multi-layer blankets, or pre-compressed mineral wool with silicone/elastomeric coating) suspended across joint gaps (50mm–300mm) beneath surface cover plates. The fire barrier must withstand multi-directional cyclic movement (+/-25% to +/-100%) while preserving 1 to 4 hour fire-resistance ratings (FRL / FRR).

This shadow authority extracts and validates expansion joint fire barrier blanket callouts, joint widths, movement allowances, and fire ratings strictly in shadow candidate mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`), enforcing the 20,000 primitive safety cap and 2.5 pt coordinate snapping.

## 2. Producer & First Failing Authority
- **Producer:** Architectural joint details, fire compartmentation drawings, seismic joint details, and expansion joint schedule documents.
- **First Failing Authority:** Downstream room boundary, floor finish, and wall parsers interpret expansion joint lines merely as floor surface plate breaks or generic wall gaps, omitting subterranean fire blankets, fire-resistance hours, smoke barrier membranes, and seismic movement ratings.

## 3. Data Model & Extraction Capabilities
- `ExpansionJointFireBarrierBlanketCallout`:
  - `raw_text`: Original unedited callout string.
  - `barrier_type`: `CERAMIC_FIBER_FOIL_BLANKET`, `MULTI_LAYER_INTUMESCENT_BLANKET`, `MINERAL_WOOL_ELASTOMERIC_SEAL`, `MODULAR_FIRE_BARRIER_SYSTEM`, `GENERIC_FIRE_BLANKET`.
  - `nominal_joint_width_mm`: Extracted nominal joint gap in mm (e.g., 50mm, 75mm, 100mm, 150mm, 200mm).
  - `movement_capacity_percent`: Extracted +/- movement allowance percentage (e.g., `+/-25%`, `+/-50%`, `+/-100%`).
  - `fire_rating_hours`: Fire-resistance rating (e.g., `1 HR`, `2 HR`, `3 HR`, `4 HR`, `FRL -/120/120`).
  - `retaining_flange_brackets`: `GALVANIZED_RETAINING_ANGLES`, `STAINLESS_STEEL_SPRING_CLIPS`, `FASTENER_PINNED_COLLAR`, `UNSPECIFIED`.
  - `smoke_barrier_layer`: `INTEGRAL_VAPOR_SMOKE_MEMBRANE`, `ELASTOMERIC_SMOKE_COATING`, `DUAL_SMOKE_SEAL`, `UNSPECIFIED`.
  - `joint_orientation`: `FLOOR_EXPANSION_JOINT`, `WALL_EXPANSION_JOINT`, `SOFFIT_EXPANSION_JOINT`, `ROOF_EXPANSION_JOINT`, `GENERIC_JOINT`.
  - `position`: Snapped `(x, y)` coordinate.
  - `status`: Constant `"CANDIDATE"`.
  - `commercial_projection_allowed`: Constant `False`.
  - `takeoff_eligible`: Constant `False`.
  - `metadata`: Supplemental dictionary.

## 4. Invariants & Safety
- Strict shadow candidate isolation: no commercial projection or takeoff eligibility.
- Global 2.5 pt coordinate snapping (`SNAP_TOLERANCE_PT = 2.5`).
- Maximum 20,000 primitive safety cap (`MAX_SAFETY_CAP_PRIMITIVES = 20_000`).
- Customer retention baseline verification: byte-for-byte invariance maintained on `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
