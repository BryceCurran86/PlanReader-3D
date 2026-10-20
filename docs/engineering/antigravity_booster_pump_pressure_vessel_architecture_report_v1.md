# Architecture Report: Source Cold Water Booster Pump Variable Speed Hydro-Pneumatic Pressure Vessel Shadow Authority (v1)

## 1. Executive Summary
Multi-level domestic cold water distribution networks rely on skid-mounted variable-speed drive (VSD) booster pumping stations coupled with hydro-pneumatic diaphragm expansion pressure vessels. Complying with AS/NZS 3500.1, these assemblies maintain constant downstream head under fluctuating demand cycles while mitigating pump cycling frequency and hydraulic transient shock (water hammer). Capturing pump configurations (simplex/duplex/triplex), expansion vessel capacities, manifold diameters, and acoustic inertia isolation pads establishes mechanical-hydraulic source authority without altering takeoff baselines.

## 2. Geometry & Extraction Model
- **Pump Skid Configurations**:
  - `SIMPLEX_PUMP_SET`: Single variable-speed booster unit.
  - `DUPLEX_PUMP_SET`: Paired duty/standby or duty/assist configuration.
  - `TRIPLEX_PUMP_SET`: Three-pump duty/assist/standby setup for large facilities.
  - `QUADPLEX_PUMP_SET`: Four-pump high-demand commercial array.
- **Pressure Vessel Volume & Rating**: Diaphragm bladder vessels (50L to 500L) with PN10, PN16, or PN25 pressure classes.
- **Header Manifold Sizing**: Stainless steel 316 or copper suction/discharge headers (DN50 to DN100).
- **Vibration & Acoustic Isolation**: Inertia concrete slabs or rubber-in-shear/spring mounts decoupling pumps from building slabs.

## 3. Safe Shadow Architecture & Non-Negotiables
- Strict candidate shadow isolation: `status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`.
- Hard safety cap enforced at 20,000 primitives.
- Geometric coordinate snapping at `SNAP_TOLERANCE_PT = 2.5`.
- Preserves customer retention baseline `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb` byte-for-byte.
