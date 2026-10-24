# Architecture Report: Source Post-Tensioned Concrete Monostrand Live End Anchorage Pocket Shadow Authority (v1)

## 1. Executive Summary
Post-tensioned concrete floor slabs and band beams utilize high-strength steel strands anchored at slab perimeters or construction joints. During casting, pocket formers create recesses (blockouts) for stressing jacks to tension live end anchors. After tensioning and wedge seating, strand tails are cropped and pockets are packed with non-shrink grout. Accurate detection of live-end anchorage pockets, tendon types, recess blockouts, and bursting reinforcement is vital for slab edge geometry without contaminating takeoff baselines.

## 2. Geometry & Extraction Model
- **Tendons & Diameter**: Monostrand tendons typically use 12.7 mm (0.5") or 15.2 mm (0.6") 7-wire low-relaxation prestressing strand.
- **Tendon Bond Type**: Categorized as `UNBONDED_MONOSTRAND` (greased with plastic sheathing) or `BONDED_MULTISTRAND` (flat corrugated duct).
- **Recess Blockout Dimensions**: Standard pocket blockouts (e.g. 120 mm width x 70 mm depth) embedded at slab edges.
- **Anti-Bursting Reinforcement**: Bursting zone helical spirals (e.g. R10 helix) or U-hairpin ties to resist high local bearing stresses.
- **Pocket Grout Infill**: High-performance non-shrink grout or polymer mortar seals the anchor against moisture penetration and corrosion.

## 3. Safe Shadow Architecture & Non-Negotiables
- Strict candidate shadow isolation: `status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`.
- Hard safety cap enforced at 20,000 primitives.
- Geometric coordinate snapping at `SNAP_TOLERANCE_PT = 2.5`.
- Preserves customer retention baseline `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb` byte-for-byte.
