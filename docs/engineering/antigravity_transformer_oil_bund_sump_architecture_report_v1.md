# Architecture Report: Source Electrical Substation Transformer Bund Oil Containment Sump Shadow Authority (Item 220 / Blocker 160)

## 1. Executive Summary
Substation civil, structural, and electrical drawings detail environmental oil containment bunds (spill containment enclosures) beneath oil-immersed electrical transformers. Mandated by IEEE 980 and electrical safety codes, transformer bunds must hold 100% to 110% of transformer dielectric fluid volume plus design stormwater allowance. Drawings incorporate reinforced concrete perimeter bund walls (300mm–900mm height), flame trap rock/gravel beds or aluminum fire quenching baffles, oil-water separator drainage sumps, optical oil sensor probes, and fail-safe pneumatic shutoff valves to prevent oil contamination of municipal drains.

This shadow authority extracts and validates electrical substation transformer bund, oil containment sump, and flame trap callouts and geometries strictly in shadow candidate mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`), enforcing the 20,000 primitive safety cap and 2.5 pt coordinate snapping.

## 2. Producer & First Failing Authority
- **Producer:** Electrical substation layout drawings, civil trade waste plans, transformer compound details, and environmental spill containment schedules.
- **First Failing Authority:** Downstream civil and spatial room parsers interpret transformer bund walls as generic masonry partition walls or slab curbs, dropping oil retention capacity (litres), fire-quenching gravel beds, oil sensor fail-safe valves, and transformer kVA rating associations.

## 3. Data Model & Extraction Capabilities
- `TransformerOilBundSumpCallout`:
  - `raw_text`: Original unedited callout string.
  - `containment_type`: `TRANSFORMER_OIL_BUND_WALL`, `OIL_WATER_SEPARATOR_SUMP`, `FIRE_QUENCHING_FLAME_TRAP`, `INTEGRAL_POLY_CONTAINMENT_BASIN`, `GENERIC_OIL_SPILL_BUND`.
  - `bund_capacity_litres`: Extracted retention volume in litres.
  - `flame_trap_medium`: `WASHED_CRUSHED_GRAVEL_BED`, `ALUMINUM_FLAME_QUENCHING_BAFFLES`, `FIRE_RETARDANT_GRATING`, `UNSPECIFIED`.
  - `oil_sensor_shutoff`: `OIL_DETECTION_OPTICAL_SENSOR`, `PNEUMATIC_FAIL_SAFE_SHUTOFF_VALVE`, `OIL_SPILL_FLOAT_SWITCH`, `UNSPECIFIED`.
  - `bund_wall_height_mm`: Perimeter bund wall height in mm (e.g. 300mm, 450mm, 600mm).
  - `transformer_kva_rating`: Rating of protected transformer (e.g., `1000 KVA`, `1500 KVA`, `2500 KVA`, `10 MVA`).
  - `dielectric_fluid_type`: `MINERAL_INSULATING_OIL`, `SYNTHETIC_ESTER_FLUID`, `NATURAL_ESTER_FR3`, `SILICONE_OIL`, `UNSPECIFIED`.
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
