# Architecture Report: Source Acoustic Floating Wall Resilient Base Angle Isolator Shadow Authority (Item 213 / Blocker 153)

## 1. Executive Summary
Acoustic isolation of floating walls, studio partitions, cinema barriers, and mechanical room perimeter walls requires decoupling the bottom wall framing (sole plate, bottom track, or masonry base) from the structural floor slab to mitigate structure-borne flanking noise transmission.
Architectural and acoustic details define resilient base angle isolators, continuous elastomeric strips (e.g. Sylomer, Regupol, neoprene), discrete elastomeric pads/brackets, dynamic natural frequency ratings (Hz), static deflection (mm), acoustic anchor bushings/decoupling washers, and continuous non-hardening acoustic caulking sealant beads.

This shadow authority extracts and validates acoustic floating wall resilient base angle callouts and geometries strictly in shadow candidate mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`), enforcing the 20,000 primitive safety cap and 2.5 pt coordinate snapping.

## 2. Producer & First Failing Authority
- **Producer:** Architectural acoustic detail drawings, studio construction plans, partition schedules, and MEP plant room acoustic partition specifications.
- **First Failing Authority:** Downstream room extraction and framing parsers treat partition base lines as rigid structural connections to the floor slab, failing to capture elastomeric decoupling layers, resilient angle brackets, acoustic anchor bushings, and dual sealant beads required for STC/Rw acoustic ratings and vibration control.

## 3. Data Model & Extraction Capabilities
- `AcousticWallResilientBaseCallout`:
  - `raw_text`: Original unedited callout string.
  - `isolator_type`: `CONTINUOUS_ELASTOMERIC_STRIP`, `RESILIENT_BASE_ANGLE_BRACKET`, `DISCRETE_MOUNT_BLOCK`, `SWAY_BRACE_BASE_CHANNEL`, `GENERIC_RESILIENT_BASE`.
  - `elastomer_material`: `SYLOMER`, `REGUPOL`, `NEOPRENE`, `POLYURETHANE`, `NATURAL_RUBBER`, `EPDM`, `UNSPECIFIED`.
  - `thickness_mm`: Thickness of elastomeric isolation layer (e.g., 12.5mm, 15mm, 25mm, 50mm).
  - `natural_frequency_hz`: Natural frequency rating if specified (e.g., 6.0 Hz, 8.0 Hz, 10.0 Hz).
  - `deflection_mm`: Static or dynamic deflection (e.g., 2.5mm, 5.0mm).
  - `spacing_mm`: Spacing of discrete brackets or mounts (e.g., 300mm, 400mm, 600mm c/c) or `CONTINUOUS`.
  - `fastener_decoupling`: `NEOPRENE_BUSHING_WASHER`, `ACOUSTIC_SLEEVE`, `ISOLATED_ANCHOR_BOLT`, `UNSPECIFIED`.
  - `acoustic_sealant`: `DUAL_BEAD_ACOUSTIC_CAULKING`, `SINGLE_BEAD_ACOUSTIC_SEALANT`, `NON_HARDENING_MASTIC`, `UNSPECIFIED`.
  - `wall_subtype`: `DRYWALL_STUD_TRACK`, `MASONRY_BLOCK_BASE`, `DOUBLE_STUD_ACOUSTIC`, `CINEMA_BARRIER`, `GENERIC_PARTITION`.
  - `acoustic_rating`: Extracted STC, Rw, or Rw+Ctr rating (e.g. `STC 55`, `RW 58`).
  - `position`: Snapped `(x, y)` coordinate.
  - `status`: Constant `"CANDIDATE"`.
  - `commercial_projection_allowed`: Constant `False`.
  - `takeoff_eligible`: Constant `False`.
  - `metadata`: Supplemental dictionary.

## 4. Invariants & Safety
- Strict shadow candidate isolation: no commercial projection or takeoff eligibility.
- Global 2.5 pt coordinate snapping (`SNAP_TOLERANCE_PT = 2.5`).
- Maximum 20,000 primitive safety cap (`MAX_SAFETY_CAP_PRIMITIVES = 20_000`).
- Customer retention baseline verification: byte-for-byte invariance maintained on `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
