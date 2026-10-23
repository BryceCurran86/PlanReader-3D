# Architecture Report: Source Architectural Expansion Joint Waterstop Floor Floor Shadow Authority (v1)

## 1. Executive Summary
Multi-building complexes, podium slabs, suspended car parks, and healthcare campuses utilize structural expansion and seismic joints that sever finished concrete floor slabs completely. These joints accommodate thermal expansion, building creep, and differential seismic movements while maintaining watertight integrity and pedestrian/vehicular trafficability. Proprietary floor expansion joint systems (such as Latham, Uniflex, or Miska) combine extruded architectural aluminum or stainless steel frames, Santoprene/EPDM elastomeric seal inserts, and sub-slab continuous waterstop drainage membranes. Parsing these elements provides critical floor plane discontinuity and waterstop authority without modifying customer takeoff baselines.

## 2. Geometry & Extraction Model
- **Joint Structural Gap**: Nominal design aperture (typically 25 mm, 50 mm, 75 mm, or 100 mm).
- **Surface Plate Profiles**:
  - `FLUSH_CENTRAL_SANTOPRENE_SEAL`: Smooth or ribbed Santoprene/EPDM center insert level with adjacent flooring.
  - `ALUMINIUM_SERRATED_COVER_PLATE`: Non-slip serrated aluminum floor plate spanning the joint gap.
  - `STAINLESS_STEEL_PAN_PLATE`: Recessed pan cover accepting tile or terrazzo infill.
- **Sub-Joint Waterproofing Barrier**:
  - `CONTINUOUS_EPDM_DRAINAGE_TROUGH`: Flexible membrane drainage gutter channeling incidental moisture to drain connections.
  - `CENTRAL_BULB_PVC_WATERSTOP`: Heavy-duty cast-in PVC waterstop with hollow center bulb.
- **Seismic Movement Capacity**: Tri-axial dynamic movement range (+/- 15mm to +/- 50mm).
- **Traffic Rating**: Commercial pedestrian (shopping malls, hospital gurneys) vs heavy vehicular (multi-deck car parks).

## 3. Safe Shadow Architecture & Non-Negotiables
- Strict candidate shadow isolation: `status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`.
- Hard safety cap enforced at 20,000 primitives.
- Geometric coordinate snapping at `SNAP_TOLERANCE_PT = 2.5`.
- Preserves customer retention baseline `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb` byte-for-byte.
