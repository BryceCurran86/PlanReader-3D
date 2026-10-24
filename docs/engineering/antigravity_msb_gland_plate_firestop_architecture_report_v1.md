# Architecture Report: Source Electrical Main Switchboard Cable Entry Gland Plate & Firestop Shadow Authority (v1)

## 1. Executive Summary
Main electrical switchboards (MSB) and distribution boards (MDB) receive high-current single-core incoming conductors and outgoing feeder cables. Under AS/NZS 3000 and AS/NZS 61439, single-core AC currents passing through individual ferrous cable entries generate localized eddy currents resulting in severe electromagnetic inductive heating. Switchboards mandate non-magnetic aluminum, brass, or composite gland plates (minimum 3mm to 6mm thickness) with elastomeric gaskets to preserve ingress protection (IP54 / IP65). Furthermore, penetration through switchroom floors or fire separation barriers requires multi-cable transit frames (e.g. Roxtec MCT) or intumescent firestop systems preserving up to 120-minute fire resistance levels (-/120/120). Extracting these assemblies establishes electrical room boundary and containment authority without disrupting takeoff baselines.

## 2. Geometry & Extraction Model
- **Gland Plate Metallurgy**:
  - `ALUMINIUM_NON_MAGNETIC`: 5005 or 5083 structural aluminum alloy plate eliminating magnetic hysteresis losses.
  - `BRASS_NON_MAGNETIC`: Naval or commercial brass plate for corrosive environments.
  - `COMPOSITE_BAKELITE`: High-dielectric non-conductive laminated synthetic resin.
  - `MILD_STEEL_MAGNETIC`: Ferrous sheet requiring continuous slotted openings between conductors.
- **Entry Orientation**: Bottom entry (sub-floor trench/basement void) or top entry (overhead cable ladder).
- **Firestopping & Cable Sealing**:
  - `MODULAR_TRANSIT_FRAME`: Cast-in or bolted modular frames with elastomeric sealing blocks and wedge compression.
  - `INTUMESCENT_FIRESTOP_PILLOWS`: Replaceable intumescent fire pillows or mortar bed.
- **Ingress Protection**: Certified dust and water resistance ratings (IP54 to IP65).

## 3. Safe Shadow Architecture & Non-Negotiables
- Strict candidate shadow isolation: `status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`.
- Hard safety cap enforced at 20,000 primitives.
- Geometric coordinate snapping at `SNAP_TOLERANCE_PT = 2.5`.
- Preserves customer retention baseline `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb` byte-for-byte.
