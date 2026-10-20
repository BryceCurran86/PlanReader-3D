# Architecture Report: Source Structural Timber Glulam Beam Moment Connection & Concealed Knife Plate Shadow Authority (v1)

## Executive Summary
Mass timber and engineered wood structures utilize glue-laminated timber (glulam) beams and columns for structural post-and-beam and portal frame assemblies. Beam-to-column and moment splice connections are routinely executed using concealed internal steel knife plates (flitch plates) inserted into longitudinal kerfs within the glulam section, connected by arrays of tight-tolerance steel dowels or drift pins. This concealed topology achieves high structural moment and shear resistance while shielding steel components behind sacrificial charring timber to achieve required fire-resistance ratings.
This report establishes the candidate shadow authority for parsing and extracting glulam beam dimensions, concealed knife plate thicknesses, dowel arrays, and connection details from mass timber structural plans.

## Domain Model & Extraction Rules
1. **Callout Recognition**:
   - Matches callouts including `GLULAM BEAM`, `GLULAM MOMENT CONNECTION`, `CONCEALED KNIFE PLATE`, `FLITCH PLATE`, `SLOTTED TIMBER CONNECTION`, `DOWEL PIN CONNECTION`, `MASS TIMBER CONNECTION`.
2. **Key Physical Parameters**:
   - `connection_type`: `CONCEALED_KNIFE_PLATE`, `DOUBLE_INTERNAL_FLITCH`, `MOMENT_SPLICE`, `BEAM_TO_COLUMN_PINNED`.
   - `timber_grade`: Glulam strength class (e.g. `GL18`, `GL17`, `GL13`, `GL28h`).
   - `timber_width_mm`: Glulam section width.
   - `timber_depth_mm`: Glulam section depth.
   - `knife_plate_thickness_mm`: Internal steel plate thickness (e.g. `10MM`, `12MM`, `16MM`, `20MM`).
   - `dowel_diameter_mm`: Steel dowel pin diameter (e.g. `10MM`, `12MM`, `16MM`).
   - `dowel_count`: Total number of dowels in connection.
3. **Geometric Snapping & Polyline Representation**:
   - Glulam centerlines, knife plate lines, and dowel array coordinates snapped within global `SNAP_TOLERANCE_PT = 2.5` pt.
   - Computes total line or coordinate span.
4. **Governance Invariants**:
   - `status="CANDIDATE"`
   - `commercial_projection_allowed=False`
   - `takeoff_eligible=False`
   - Safety cap: 20,000 primitives
   - Byte-for-byte baseline integrity for `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
