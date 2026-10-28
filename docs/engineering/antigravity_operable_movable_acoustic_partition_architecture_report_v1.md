# Architecture Report: Architectural Operable Movable Acoustic Partition Wall Shadow Authority (v1)

## Executive Summary
This document establishes the shadow candidate geometry authority for architectural operable movable acoustic partitions, sliding folding panels, stacking pocket enclosures, pass doors, and overhead structural tracks (`pb_source_operable_movable_acoustic_partition_shadow.py`).

## Scope & Classification
- **Element Types**:
  - `OPERABLE_ACOUSTIC_WALL_RUN`: Standard multi-panel operable acoustic partition wall run.
  - `STACKING_POCKET_ENCLOSURE`: Recessed panel stacking enclosure / pocket closet with acoustic pocket door.
  - `PASS_DOOR_INSERT_PANEL`: Full-height single or double pass door inserted within an operable panel.
  - `OVERHEAD_STRUCTURAL_TRACK`: Heavy-duty extruded aluminum / steel overhead track with multi-directional trolleys.
  - `MOTORIZED_ELECTRIC_OPERABLE_WALL`: Continuously hinged electrically driven motorized operable wall system.
- **Attributes**: Acoustic rating (Rw 45–58 / STC), panel thickness (75–125 mm), panel height (2400–6000 mm), surface finishes (HPL, timber veneer, fabric wrapped, magnetic whiteboard), mechanical retractable seals, and suspension type (top-hung omni-directional, center stack, floor supported).

## Safety & Governance
- Strictly candidate shadow authority (`status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`).
- Snapping tolerance: 2.5 pt deterministic snapping.
- Primitive cap: 20,000 primitives.
