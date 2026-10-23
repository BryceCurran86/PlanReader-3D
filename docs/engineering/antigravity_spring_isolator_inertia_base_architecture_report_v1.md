# Architecture Report v1: Source Mechanical Vibration Spring Isolator & Inertia Base Shadow Authority

## 1. Problem Statement & Scope
Heavy rotating HVAC mechanical plant (chillers, primary CHW/CW pumps, cooling towers, air compressors, and emergency diesel generator sets) requires open or housed helical steel spring vibration isolators and reinforced concrete inertia base frames to attenuate structure-borne acoustic vibration, prevent resonance amplification through suspended building floors, and stabilize pipework nozzle connections. In structural and mechanical basement plantroom drawings, concrete inertia bases and spring isolators are frequently conflated with simple equipment housekeeping plinths.

This module introduces `SourceVibrationSpringIsolatorInertiaBaseShadowAuthority` to extract and validate vibration spring isolators, inertia bases, static deflection ratings (25mm - 75mm), rated load capacities (kg / kN), concrete inertia base depth (mm) and weight ratio (typically 1.5x - 2.0x equipment weight), neoprene acoustical friction pads, and seismic snubber restraint brackets strictly in shadow candidate mode.

## 2. Design Principles & Non-Negotiables
1. **Strict Shadow Candidate Mode**:
   - `status = "CANDIDATE"`
   - `commercial_projection_allowed = False`
   - `takeoff_eligible = False`
2. **Deterministic Geometric Snapping**:
   - Snapped with `SNAP_TOLERANCE_PT = 2.5 pt`.
3. **Safety Primitive Cap**:
   - Inputs capped at `MAX_SAFETY_CAP_PRIMITIVES = 20_000`.
4. **Zero Gold Dependencies**:
   - Pure regex and keyword parsing without benchmark gold dependencies.
5. **Customer Baseline Invariance**:
   - Maintains exact isolation from customer gold baselines.

## 3. Authority Interface
- `VibrationSpringIsolatorCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `isolator_type`: `OPEN_SPRING_ISOLATOR`, `HOUSED_SPRING_ISOLATOR_WITH_SNUBBER`, `SEISMIC_RESTRAINED_SPRING_MOUNT`
  - `static_deflection_mm`: Rated spring static deflection (mm)
  - `load_capacity_kg`: Rated load capacity per isolator (kg)
  - `inertia_base_included`: Boolean indicating concrete inertia base frame
  - `inertia_base_depth_mm`: Structural steel channel frame depth for concrete fill (mm)
  - `neoprene_pad_thickness_mm`: Acoustic base friction pad thickness (mm)
  - `position`: Snapped `(x, y)` coordinate
- `parse_vibration_spring_isolator_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceVibrationSpringIsolatorInertiaBaseShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
