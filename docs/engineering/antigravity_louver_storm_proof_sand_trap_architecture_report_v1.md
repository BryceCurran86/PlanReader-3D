# Architecture Report: Source Architectural Louver Storm Proof Blade & Sand Trap Shadow Authority (v1)

## 1. Executive Summary
Building facade plantrooms, electrical substations, and mechanical intake/exhaust plenums require architectural louvers designed to prevent wind-driven rain infiltration and sand penetration while ensuring mandatory aerodynamic free ventilation area. Stormproof two-stage chevron blades and sand-trap louvers featuring internal guttering and self-draining sill slots represent specialized envelope penetrations. Parsing these elements in source drawings ensures accurate 3D envelope geometry without interfering with customer baseline takeoffs.

## 2. Geometry & Extraction Model
- **Blade Profiles**:
  - `TWO_STAGE_CHEVRON`: High-efficiency rain defense (AS/NZS 4740 Class A aerodynamic rain rejection).
  - `SAND_TRAP_SELF_DRAINING`: Vertically or horizontally baffled blades with bottom drainage channels to eject sand particulates.
  - `SINGLE_STAGE_DRAINABLE`: Standard exterior weather louvers with integral rain gutters.
- **Blade Pitch & Depth**: Standard extrusion depths (e.g. 100 mm, 150 mm) and vertical blade spacings (e.g. 75 mm pitch).
- **Free Area Percentage**: Aerodynamic free air percentage (typically 45% - 60% free area).
- **Rear Screen Backing**: Removable stainless steel bird mesh (e.g. 12x12 mm SS mesh) or fine aluminum insect screen.
- **Material Finish**: Architectural grade extruded aluminum (alloy 6063-T6) with polyester powdercoat or 25µm natural anodizing.

## 3. Safe Shadow Architecture & Non-Negotiables
- Strict candidate shadow isolation: `status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`.
- Hard safety cap enforced at 20,000 primitives.
- Geometric coordinate snapping at `SNAP_TOLERANCE_PT = 2.5`.
- Preserves customer retention baseline `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb` byte-for-byte.
