# Post-Installed Mechanical Undercut & Chemical Epoxy Anchor Stud Shadow Authority Architecture Report (v1)

## Executive Summary
This authority module implements deterministic, candidate-only shadow extraction for structural concrete post-installed fastening systems: heavy-duty undercut anchors, injectable vinyl-ester/pure epoxy adhesive anchor studs, torque-controlled expansion wedge anchors, and heavy-duty concrete screw anchors with seismic ratings.

## Scope & Classification
- **Anchor System Types**:
  - `CHEMICAL_EPOXY_STUD`: Pure epoxy or hybrid adhesive resin with high-tensile threaded rod.
  - `MECHANICAL_UNDERCUT`: Pre- or self-undercut mechanical anchors for dynamic/cracked concrete.
  - `CONCRETE_SCREW_BOLT`: Direct concrete screw bolts (e.g., HUS-4, Titen HD).
  - `EXPANSION_ANCHOR`: Torque-controlled mechanical expansion anchors (HST3).
  - `DROP_IN_ANCHOR`: Internally threaded flush drop-in anchors (HKD).
- **Technical & Geometric Parameters**:
  - Thread metric sizes (M8 through M36).
  - Effective embedment depth ($h_{ef}$ in mm).
  - Metallurgy: Grade 8.8 galvanized, Grade A4/316 stainless, High Corrosion Resistance (HCR).
  - Seismic qualification (Seismic C1, Seismic C2, cracked concrete approval).

## Safety & Governance
- Strictly candidate shadow mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`).
- Deterministic 2D coordinate grid snapping (default `2.5 pt`).
- Safety primitive ceiling (`MAX_SAFETY_CAP_PRIMITIVES = 20_000`).
