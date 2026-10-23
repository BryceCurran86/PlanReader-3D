# Architecture Report: Source Acoustic Gypsum Plasterboard Resilient Mount Wall Furring Channel Shadow Authority (v1)

## 1. Executive Summary
High-performance architectural acoustic partitions separating apartments, cinema auditoriums, plantrooms, and recording spaces require structural decoupling to eliminate flanking vibration and impact noise transmission. Resilient acoustic clips (e.g. Resilmount, Embelton, or Regupol rubber mounts) decouple steel furring channels (16mm or 28mm hat profiles) from base masonry, concrete, or light-gauge steel stud walls. Combined with acoustic mineral or glasswool insulation and multi-layer high-density plasterboard, these assemblies achieve NCC/BCA acoustic compliance (Rw + Ctr >= 50 dB). Parsing these wall build-ups provides accurate boundary envelope depth and acoustic layering without impacting takeoff baselines.

## 2. Geometry & Extraction Model
- **Acoustic Isolation Clips**:
  - `THERMOPLASTIC_RUBBER_CLIP`: Synthetic rubber grommet/elastomeric acoustic bracket.
  - `STEEL_SPRING_MOUNT`: Helical spring-loaded acoustic isolator for low-frequency rumble.
  - `DIRECT_RESILIENT_CHANNEL`: Slotted single-leg roll-formed resilient channel (RC-1).
- **Furring Channel Profile**: Standard 16mm or 28mm hat-shaped cold-formed galvanised steel furring channels.
- **Framing Spacing**: Standard 450mm or 600mm centers.
- **Insulation Cavity**: Cavity depths (typically 20mm to 50mm) packed with density-rated acoustic insulation.
- **Gypsum Linings**: Single or double layer 13mm/16mm fire- and sound-rated gypsum boards.

## 3. Safe Shadow Architecture & Non-Negotiables
- Strict candidate shadow isolation: `status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`.
- Hard safety cap enforced at 20,000 primitives.
- Geometric coordinate snapping at `SNAP_TOLERANCE_PT = 2.5`.
- Preserves customer retention baseline `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb` byte-for-byte.
