# Architecture Report: Source Concrete Slab Dowelled Contraction Joint Flanged Plate Dowel Shadow Authority (v1)

## 1. Executive Summary
Industrial, warehouse, and logistics concrete slabs-on-ground experience volumetric shrinkage during curing and thermal cycles during operation. Traditional round slip dowels risk joint locking and spalling if misaligned. Modern industrial slab engineering utilizes diamond plate dowels and rectangular plate dowels installed within plastic expansion sleeves (complying with ACI 360R and AS 3600). These provide vertical load transfer across sawcut contraction or formed expansion joints while allowing free longitudinal opening and +/- 10mm lateral slab displacement. Extracting plate dowel systems establishes joint load transfer geometry without modifying takeoff baselines.

## 2. Geometry & Extraction Model
- **Plate Dowel Geometries**:
  - `DIAMOND_PLATE`: Diamond geometry widest at joint face, tapering inward to minimize concrete restraint during slab shrinkage.
  - `RECTANGULAR_PLATE`: Rectangular steel plate with side compressible foam pockets for lateral travel.
  - `ROUND_DOWEL_SLEEVE`: Round bar dowels housed in de-bonding plastic sleeves.
- **Plate Thickness**: Typical heavy-duty sizes (6 mm, 8 mm, 10 mm, 12 mm).
- **Plate Plan Dimensions**: Standard diamond or rectangular dimensions (e.g. 150x150 mm, 110x110 mm).
- **Joint Spacing Centers**: Spaced along joint lines at 450 mm, 500 mm, or 600 mm centers.
- **Sleeve Mechanism**: Rigid polymeric pockets with compressible lateral foam inserts allowing differential joint movement.

## 3. Safe Shadow Architecture & Non-Negotiables
- Strict candidate shadow isolation: `status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`.
- Hard safety cap enforced at 20,000 primitives.
- Geometric coordinate snapping at `SNAP_TOLERANCE_PT = 2.5`.
- Preserves customer retention baseline `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb` byte-for-byte.
