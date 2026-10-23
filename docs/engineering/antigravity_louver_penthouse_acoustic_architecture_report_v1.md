# Architecture Report: Source Architectural Louver Penthouse & Acoustic Attenuation Splitter Shadow Authority (v1)

## Executive Summary
Commercial rooftop mechanical plant enclosures require architectural louver penthouses providing air intake/exhaust ventilation while preventing rain ingress and mitigating plant noise emissions to surrounding properties. These assemblies integrate chevron or two-stage drainable louver blades, bird mesh / insect screens, structural mullion framing, and acoustic silencer / attenuation baffles.
This report establishes the candidate shadow authority for parsing and extracting architectural louver penthouse enclosures and acoustic splitter geometry from architectural and mechanical rooftop plans.

## Domain Model & Extraction Rules
1. **Callout Recognition**:
   - Matches callouts including `LOUVER PENTHOUSE`, `LOUVRE ENCLOSURE`, `ACOUSTIC LOUVER`, `ATTENUATION SPLITTER`, `ROOFTOP SCREEN`, `WEATHERPROOF LOUVER ENCLOSURE`, `PLANT SCREEN`.
2. **Key Physical Parameters**:
   - `enclosure_type`: `LOUVER_PENTHOUSE`, `ACOUSTIC_SCREEN`, `PLANT_ENCLOSURE`, `ATTENUATION_SPLITTER`.
   - `blade_type`: `WEATHERPROOF_CHEVRON`, `DRAINABLE`, `ACOUSTIC_LOUVER_BOX`, `SOUND_ATTENUATION_SPLITTER`.
   - `height_mm`: Overall screen/penthouse height (e.g. `2400MM`, `3000MM`).
   - `free_area_pct`: Aerodynamic free area percentage (e.g. `50%`, `55%`, `60%`).
   - `acoustic_rating`: Sound insulation rating (e.g. `Rw 15`, `Rw 20`, `STC 25`).
   - `has_bird_mesh`: True if bird wire or insect screen specified.
3. **Geometric Snapping & Polyline Representation**:
   - Boundary polylines snapped within global `SNAP_TOLERANCE_PT = 2.5` pt.
   - Computes total boundary or splitter length.
4. **Governance Invariants**:
   - `status="CANDIDATE"`
   - `commercial_projection_allowed=False`
   - `takeoff_eligible=False`
   - Safety cap: 20,000 primitives
   - Byte-for-byte baseline integrity for `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
