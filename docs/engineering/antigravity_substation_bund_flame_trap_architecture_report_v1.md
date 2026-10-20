# Architecture Report: Source High-Voltage Substation Oil Containment Bund & Flame Trap Shadow Authority (v1)

## Executive Summary
Major power distribution substations, data centres, and industrial power plants utilize large liquid-filled power transformers containing dielectric insulating oil. Environmental protection codes and fire safety standards mandate reinforced concrete secondary containment bunds sized to contain 110% of oil volume plus rainwater/fire deluge. In addition, an integrated flame trap bed filled with crushed basalt rock quenches burning oil, and oil-water separation sumps drain uncontaminated storm runoff while trapping oil.
This report defines the candidate shadow authority for parsing and extracting transformer oil containment bund perimeters, wall heights, and flame trap aggregate details from civil and electrical substation plans.

## Domain Model & Extraction Rules
1. **Callout Recognition**:
   - Matches callouts including `TRANSFORMER BUND`, `OIL CONTAINMENT BUND`, `SUBSTATION BUND`, `FLAME TRAP`, `CRUSHED ROCK FLAME TRAP`, `OIL-WATER SEPARATOR`, `TRANSFORMER PIT`.
2. **Key Physical Parameters**:
   - `bund_type`: `TRANSFORMER_OIL_BUND`, `FLAME_TRAP_BASIN`, `OIL_WATER_SEPARATOR_SUMP`, `SECONDARY_CONTAINMENT_WALL`.
   - `wall_height_mm`: Bund wall height above slab (e.g. `600`, `900`, `1200`, `1500`).
   - `wall_thickness_mm`: Concrete wall thickness (e.g. `200`, `250`, `300`).
   - `containment_volume_m3`: Required capacity in cubic metres.
   - `flame_trap_aggregate`: `CRUSHED_BASALT`, `CRUSHED_GRANITE`, `ROUNDED_RIVER_GRAVEL`.
   - `has_flame_trap`: True if flame trap rock bed or baffle is included.
3. **Geometric Snapping & Polyline Representation**:
   - Bund perimeter polylines and sump points snapped within global `SNAP_TOLERANCE_PT = 2.5` pt.
   - Computes total perimeter or boundary length.
4. **Governance Invariants**:
   - `status="CANDIDATE"`
   - `commercial_projection_allowed=False`
   - `takeoff_eligible=False`
   - Safety cap: 20,000 primitives
   - Byte-for-byte baseline integrity for `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
