# Architecture Report: Source Post-Tensioned Concrete Monostrand Dead End Onion Anchor Shadow Authority (v1)

## 1. Executive Summary
Post-tensioned concrete floor slabs and band beams frequently incorporate tendons terminating internally within the concrete cross-section (e.g. adjacent to lift cores, stair voids, or slab drops) where edge access for jacking equipment is unavailable. These non-stressing terminations utilize "dead end" anchorages, primarily hydraulically splayed "onion" bulbs (flower anchors) or factory swaged compression sleeves embedded directly in the pour. Precise detection of dead-end bulb geometries, development bond lengths, anti-burst ties, and concrete covers establishes internal structural tendon geometry without disrupting baseline customer takeoff calculations.

## 2. Geometry & Extraction Model
- **Anchor Configurations**:
  - `HYDRAULIC_ONION_BULB`: Strand wires mechanically splayed into a bulbous cage to develop bond strength directly in the surrounding concrete.
  - `SWAGED_BARREL_SLEEVE`: Steel extrusion swaged onto strand with integral bearing plate.
  - `PLATE_DEAD_END`: Internal dead-end casting with locked wedge assembly.
- **Strand Diameters**: 12.7 mm (0.5") or 15.2 mm (0.6") 7-wire low-relaxation strand.
- **Embedment Bond Length**: Specified development length (typically 600 mm to 1000 mm).
- **Anti-Bursting Containment**: N12/N16 U-hairpins or helical spirals confining high localized tensile burst stresses.
- **Cover Requirements**: Structural concrete bottom and top cover (typically 30 mm to 50 mm).

## 3. Safe Shadow Architecture & Non-Negotiables
- Strict candidate shadow isolation: `status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`.
- Hard safety cap enforced at 20,000 primitives.
- Geometric coordinate snapping at `SNAP_TOLERANCE_PT = 2.5`.
- Preserves customer retention baseline `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb` byte-for-byte.
