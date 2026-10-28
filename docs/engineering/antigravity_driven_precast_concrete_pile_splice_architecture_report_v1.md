# Architecture Report: Structural Deep Foundation Driven Precast Concrete Piling & Splice Shadow Authority (v1)

## Executive Summary
This document establishes the shadow candidate geometry authority for structural deep foundation driven precast prestressed concrete piles, mechanical locking splices, hardened rock chisel shoes, and pile cut-off head assemblies (`pb_source_driven_precast_concrete_pile_splice_shadow.py`).

## Scope & Classification
- **Element Types**:
  - `DRIVEN_PRECAST_SQUARE_PILE`: Precast prestressed concrete pile section (Grade 50–80 MPa).
  - `MECHANICAL_PILE_SPLICE_JOINT`: Precision locking-pin mechanical pile splice connecting upper and lower segments.
  - `DRIVING_ROCK_SHOE_POINT`: Cast steel hardened rock chisel shoe point welded to internal rebar cage.
  - `PILE_HEAD_CUTOFF_ASSEMBLY`: Debonded tendon / exposed rebar starter cage embedded in pile cap.
  - `CYLINDRICAL_SPUN_CONCRETE_PILE`: Spun prestressed concrete cylinder pile (PHC pile).
- **Attributes**: Pile cross-section (200–600 mm), segment length (6–16 m), concrete compressive strength (50–80 MPa), safe working load (SWL in kN), driving shoe type (chisel, flat steel, Oslo point), and splice type (mechanical locking pins, welded collar, epoxy dowels).

## Safety & Governance
- Strictly candidate shadow authority (`status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`).
- Snapping tolerance: 2.5 pt deterministic snapping.
- Primitive cap: 20,000 primitives.
