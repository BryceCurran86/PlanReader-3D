# Architecture Report: Producer-Owned Source Figured Dimension and Wall Witness Shadow Authority (Item 18)

## Executive Summary
This document establishes the architecture for the **Producer-Owned Source Figured Dimension and Wall Witness Shadow Authority** (`pb_source_figured_dimension_wall_witness_shadow.py`), resolving Workstream B, Item 18 of the Autonomous Core Accuracy Engineering Mission: "Recover figured room dimensions and corresponding wall witnesses."

The primary blockers addressed are:
1. **Unproven Figured Dimension Association:** Previously, figured dimension text (e.g. "3570", "2536", "4025") was associated with rooms or walls using loose bounding-box proximity heuristics or axis projections. In complex architectural drawings with stacked dimension chains, this caused misattribution of dimensions to wrong rooms or exterior grids.
2. **Missing Physical Witness Line Verification:** In drafting standards, figured dimension strings do not contact walls directly; they run on offset dimension lines connected to internal wall faces via perpendicular witness lines (extension lines) terminated with witness ticks. Without verifying the continuous physical stroke chain ($E_{\text{dim}} \to \text{witness} \to \text{wall}$), room dimension claims remain ungrounded spatial hypotheses.
3. **Producer-Owned Witness Binding:** This module provides an authentic, source-derived witness authority that proves the geometric chain from figured text, through the dimension line, across perpendicular witness strokes within standard snap tolerance ($\le 2.5$ pt), to authenticated internal wall faces.

---

## Technical Architecture & Invariants

### 1. Sealed Producer / Authority Pattern
- Standard `_PRODUCER_SEAL`, `_AUTHORITY_SEAL`, and `_RECORD_SEAL` internal singletons ensure immutable writer boundaries.
- Factory method `SourceFiguredDimensionWitnessProducer.create()` produces the mutable producer.
- Calling `.authority()` returns a frozen `SourceFiguredDimensionWitnessAuthority` mapping selectors to results.

### 2. Figured Witness Chain Geometric Gates
- **Figure vs Scaled Length Consistency:**
  - If physical scale is corroborated ($\text{scale\_px\_per\_m} > 0$), the dimension line length $L_{\text{dim}}$ is converted to meters: $\text{scaled\_m} = L_{\text{dim}} / \text{scale\_px\_per\_m}$.
  - The figured numeral distance $D_{\text{figured}}$ must match $\text{scaled\_m}$ within $\le 0.05$ m or $\le 2\%$.
  - Mismatches fail with `DIMENSION_FIGURE_MISMATCH`.
- **Perpendicular Witness Geometry Gate:**
  - At each endpoint of the dimension line ($E_1, E_2$), a perpendicular witness line stroke must exist ($|u_{\text{dim}} \cdot u_{\text{wit}}| \le 0.035$, corresponding to $90^\circ \pm 2^\circ$).
  - One end of the witness stroke must touch or intersect the dimension line endpoint within snap tolerance ($\le 2.5$ pt). Fails with `WITNESS_LINE_DISCONTINUOUS_OR_MISSING`.
- **Wall Face Contact Gate:**
  - The opposite end of each witness stroke must terminate at a verified internal wall face within snap tolerance ($\le 2.5$ pt).
  - Both endpoints must contact distinct, parallel wall faces.
  - If a witness stroke fails to reach a wall or reaches an ambiguous non-wall primitive, fails with `WITNESS_WALL_CONTACT_UNRESOLVED`.
- **Serialised WKB Geometry:**
  - Encodes the complete 3-stroke witness system (dimension line + two witness extension lines) as an OGC MultiLineString.

### 3. Shadow Mode Guards
- Record `status = CANDIDATE`.
- Explicit flags: `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Preserves all 8 holdout customer quantities and SHA-256 fingerprint (`ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`).
