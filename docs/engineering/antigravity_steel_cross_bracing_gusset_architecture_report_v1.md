# Architecture Report: Source Structural Steel Cross-Bracing Gusset Plate & Slotted Pin Hole Shadow Authority (v1)

## Executive Summary
In structural steel lateral load resisting systems (such as concentrically braced frames CBF, roof diaphragm bracing trusses, and vertical wall cross-bracing bays), diagonal tension and compression braces transfer wind and seismic racking loads into columns, beams, and foundations via heavy fabricated steel gusset plates. High-load or long-span connections incorporate edge stiffeners to prevent out-of-plane buckling, slotted holes to accommodate thermal movement, or machined pin holes for architectural rod systems (e.g. Macalloy rods).
This report establishes the candidate shadow authority for parsing and extracting steel gusset plate geometries, thicknesses, bolt counts, and slotted/pin details from structural steel detail drawings.

## Domain Model & Extraction Rules
1. **Callout Recognition**:
   - Matches callouts including `GUSSET PLATE`, `CROSS-BRACING GUSSET`, `BRACING GUSSET`, `TENSION ROD GUSSET`, `PINNED GUSSET`, `BRACED BAY GUSSET`.
2. **Key Physical Parameters**:
   - `gusset_type`: `CORNER_BEAM_COLUMN_GUSSET`, `CHEVRON_V_BRACE_GUSSET`, `X_BRACE_CENTER_GUSSET`, `TENSION_ROD_PIN_GUSSET`.
   - `plate_thickness_mm`: Gusset plate thickness (e.g. `12MM`, `16MM`, `20MM`, `25MM`, `32MM`).
   - `bolt_spec`: Bolt diameter and grade (e.g. `M20`, `M24`, `M30`).
   - `bolt_count`: Number of bolts in brace connection.
   - `has_slotted_holes`: True if slotted or oversized holes are specified.
   - `has_edge_stiffener`: True if gusset edge stiffener plate/flange is specified.
3. **Geometric Snapping & Polyline Representation**:
   - Gusset plate outlines and connection node coordinates snapped within global `SNAP_TOLERANCE_PT = 2.5` pt.
   - Computes total boundary or diagonal length.
4. **Governance Invariants**:
   - `status="CANDIDATE"`
   - `commercial_projection_allowed=False`
   - `takeoff_eligible=False`
   - Safety cap: 20,000 primitives
   - Byte-for-byte baseline integrity for `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
