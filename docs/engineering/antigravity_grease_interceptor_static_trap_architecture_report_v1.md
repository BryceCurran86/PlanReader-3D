# Architecture Report: Source Hydraulic Trade Waste Grease Interceptor Static Trap Shadow Authority (v1)

## 1. Executive Summary
Commercial kitchen, hospitality, and retail food preparation drainage requires trade waste grease interceptor traps (grease arrestors/interceptors complying with AS/NZS 3500.2 and water utility regulations). These static gravity separation vessels (1000L to 5000L) utilize internal baffles and deep-water seals to separate fats, oils, and grease (FOG) prior to municipal sewer discharge. Capturing grease trap locations, capacities, baffle geometries, vent connections, and sampling pits provides key hydraulic source authority without disrupting customer baseline takeoffs.

## 2. Geometry & Extraction Model
- **Vessel Capacity**: Nominal liquid volume in litres (typically 1000L, 1500L, 2000L, 3000L, or 5000L).
- **Construction Material**:
  - `ROTOMOULDED_POLYETHYLENE`: Lightweight corrosion-proof thermoplastic for below-ground or above-ground placement.
  - `PRECAST_CONCRETE`: Heavy-duty in-ground precast concrete tanks with protective epoxy or acid-resistant linings.
  - `FABRICATED_STAINLESS_STEEL`: Grade 304 or 316 stainless steel for compact indoor plantroom applications.
- **Baffle & Hydraulics**: Dual-compartment internal baffle walls or deep submerged T-pipe inlet/outlet dip pipes.
- **Gastight Access Covers**: AS 3996 Class B or Class D gastight double-sealed bolted access covers to prevent sewer odor egress.
- **Venting & Sampling**: Dedicated high-level vent stack (DN100 or DN50) and downstream inspection sampling pit.

## 3. Safe Shadow Architecture & Non-Negotiables
- Strict candidate shadow isolation: `status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`.
- Hard safety cap enforced at 20,000 primitives.
- Geometric coordinate snapping at `SNAP_TOLERANCE_PT = 2.5`.
- Preserves customer retention baseline `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb` byte-for-byte.
