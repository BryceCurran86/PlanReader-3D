# Architecture Report: Source Industrial Concrete Slab Sawn Contraction Joint Polyurethane Sealant Shadow Authority (v1)

## 1. Executive Summary
Concrete ground slabs in industrial warehouses, retail centers, and parking garages require crack control sawcut joints to relieve drying shrinkage stresses. Complying with ACI 302.1R, ACI 360R, and AS 3600, contraction joints are formed via diamond blade or early-entry saws to a depth of one-quarter slab thickness (D/4) or nominal 40-50mm. To protect joint shoulders against heavy forklift wheel spalling or environmental water ingress, joints are sealed with either semi-rigid polyurea (full depth without backer rod for industrial hard wheels) or elastomeric polyurethane backed by closed-cell polyethylene foam rods. Capturing these joint specifications provides essential floor finish and crack control geometry without affecting baseline takeoff calculations.

## 2. Geometry & Extraction Model
- **Sawcut Dimensions**:
  - Kerf width: 3 mm to 6 mm.
  - Depth ratio: D/4, D/3, or explicit dimension (e.g. 50 mm).
- **Sealant Chemistry**:
  - `SEMI_RIGID_POLYUREA`: Shore A 80+ hardness, supporting joint spall resistance under hard polyurethane forklift tires.
  - `ELASTOMERIC_POLYURETHANE`: High-movement polyurethane sealant (e.g. Sikaflex PRO) accommodating cyclic joint opening.
  - `SILICONE_SEALANT`: UV-resistant silicone for exterior apron slabs.
- **Backing Material**: Closed-cell polyethylene foam backer rod preventing three-sided adhesion in elastomeric configurations.
- **Arris Edge Geometry**: Square cut vs 2-3mm 45° beveled joint edges.

## 3. Safe Shadow Architecture & Non-Negotiables
- Strict candidate shadow isolation: `status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`.
- Hard safety cap enforced at 20,000 primitives.
- Geometric coordinate snapping at `SNAP_TOLERANCE_PT = 2.5`.
- Preserves customer retention baseline `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb` byte-for-byte.
