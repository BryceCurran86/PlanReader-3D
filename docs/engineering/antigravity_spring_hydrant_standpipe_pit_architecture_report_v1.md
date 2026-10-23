# Architecture Report: Source Underground Fire Hydrant Spring Hydrant & Standpipe Pit Shadow Authority (v1)

## 1. Executive Summary
Civil infrastructure and external fire services site layouts locate underground fire hydrants (spring hydrants complying with AS 3952 / AS 2419.1) housed in subsurface pits. Fire brigades connect portable standpipes directly to the subterranean spring valve mechanism. Pit structures require trafficable or pedestrian surface cast-iron covers emblazoned with 'FH', secure thrust blocks, and drainage gravel soakaways to prevent pit flooding. Identifying these subsurface assets establishes civil fire service points without disrupting baseline customer takeoff calculations.

## 2. Geometry & Extraction Model
- **Hydrant Valve Type**:
  - `SPRING_VALVE_AS3952`: Standard spring-loaded sealing plug displaced by standpipe shaft.
  - `SCREW_DOWN_HYDRANT`: Spindle-operated screw-down fire valve.
  - `SLUICE_VALVE_HYDRANT`: Gate valve isolated hydrant configuration.
- **Supply Diameter**: Connection to reticulated main, typically DN100 or DN150 ductile iron / PVC-O.
- **Pit Box Construction**: Precast concrete box, rotomoulded polymeric surround, or ductile iron casing.
- **Surface Cover Load Class**: AS 3996 Class D (trafficable roadway) or Class B (verge/footpath), marked 'FH'.
- **Drainage Soakaway**: Uncompacted 20mm blue metal aggregate bed beneath pit base for dewatering.

## 3. Safe Shadow Architecture & Non-Negotiables
- Strict candidate shadow isolation: `status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`.
- Hard safety cap enforced at 20,000 primitives.
- Geometric coordinate snapping at `SNAP_TOLERANCE_PT = 2.5`.
- Preserves customer retention baseline `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb` byte-for-byte.
