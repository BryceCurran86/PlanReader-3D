# Architecture Report: Source Hydronic Heating Chilled Water Air Dirt Separator Magnetic Filter Shadow Authority (v1)

## 1. Executive Summary
Commercial HVAC hydronic systems (Chilled Water CHW, Heating Hot Water HHW, and Condenser Water CW) require continuous air removal and particulate filtration to prevent pump cavitation, heat transfer degradation, and magnetite sludge accumulation in control valves and heat exchangers. Mechanical engineers specify inline microbubble deaerators and dirt separators equipped with high-intensity neodymium dry-well magnetic inserts (complying with CIBSE Commissioning Code W and BSRIA BG29). Capturing these vessels, connection sizes, system designations, and thermal insulation jackets establishes mechanical plantroom authority without altering customer baseline takeoffs.

## 2. Geometry & Extraction Model
- **Hydronic Service Categorization**:
  - `CHILLED_WATER_CHW`: Low-temperature closed loops (typically 6°C / 12°C).
  - `HEATING_HOT_WATER_HHW`: High-temperature closed loops (typically 80°C / 60°C).
  - `CONDENSER_WATER_CW`: Cooling tower open/closed heat rejection loops.
- **Vessel & Connection Sizing**: Flanged or grooved pipe connections (DN50 to DN250).
- **Separation Mechanism**:
  - Coalescing wire matrix (spirotube/pall ring) inducing microbubble release to an automatic top vent.
  - Quiescent lower chamber for gravitational sediment accumulation.
  - Dry-well neodymium magnetic rod attracting ferrous magnetite particles.
- **Maintenance Provisions**: Full-bore bottom blow-down ball valve with hose coupling.
- **Thermal Envelope**: Custom-moulded removable EPP insulation jackets preventing condensation in CHW or thermal loss in HHW.

## 3. Safe Shadow Architecture & Non-Negotiables
- Strict candidate shadow isolation: `status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`.
- Hard safety cap enforced at 20,000 primitives.
- Geometric coordinate snapping at `SNAP_TOLERANCE_PT = 2.5`.
- Preserves customer retention baseline `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb` byte-for-byte.
