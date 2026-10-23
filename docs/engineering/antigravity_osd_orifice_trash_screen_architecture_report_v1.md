# Architecture Report: Source Stormwater Retention OSD Orifice Plate & Trash Screen Shadow Authority (v1)

## 1. Executive Summary
Civil stormwater infrastructure for commercial and residential developments requires On-Site Stormwater Detention (OSD) systems to control runoff rates. The critical governing node is the Discharge Control Pit (DCP), which houses a precision-machined stainless steel or brass orifice plate (calibrated for permissible site discharge), an emergency overflow weir crest for storm events exceeding design capacity, and a protective trash screen (aperture <= 20mm or wedge-wire profile) preventing blockage. Capturing DCP locations, orifice dimensions, weir crests, and trash screen geometries establishes hydraulic site authority without affecting takeoff baselines.

## 2. Geometry & Extraction Model
- **Calibrated Orifice Plate**: Machined aperture (typically 50 mm to 200 mm diameter) bolted over the low-level outlet pipe.
- **Plate Metallurgy**: 316 Grade stainless steel or naval brass plate (minimum 3mm to 6mm thickness) with neoprene gasket seals.
- **Protective Trash Screen**: Removable screen with maximum 20mm opening size (or stainless wedge wire) presenting at least 1.5x the orifice cross-sectional area.
- **Overflow Crest / Weir**: High-level weir discharging excess flow during intense rainfall events.
- **Access Covers**: Heavy-duty trafficable Class D or footpath Class B gas-tight/hinged covers with integrated step irons.

## 3. Safe Shadow Architecture & Non-Negotiables
- Strict candidate shadow isolation: `status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`.
- Hard safety cap enforced at 20,000 primitives.
- Geometric coordinate snapping at `SNAP_TOLERANCE_PT = 2.5`.
- Preserves customer retention baseline `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb` byte-for-byte.
