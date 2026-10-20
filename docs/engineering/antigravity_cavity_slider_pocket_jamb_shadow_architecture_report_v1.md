# Antigravity Cavity Slider and Pocket Door Jamb Continuity Shadow Authority Report (v1)

## Executive Summary
Cavity sliders and pocket doors retract inside hollow wall framing. Naive opening detectors treat the cavity pocket as an open void and sever wall continuity, cutting a single continuous wall into two disconnected stubs and generating duplicate or missing wall IDs.

This milestone (Item 65 / Workstream A Item 7 & 4) implements the producer-owned cavity slider and pocket door jamb continuity shadow authority (`pb_source_cavity_slider_pocket_jamb_shadow.py`).

## Core Architecture & Invariants

1. **Wall Framing Continuity Rule**:
   - The structural wall does NOT terminate at the split jamb post of a cavity pocket.
   - Continuous structural wall centerline and physical wall ID span continuously across the pocket recess segment (`retains_wall_continuity = True`).
   - The pocket is marked as `WALL_EMBEDDED_POCKET`, carrying split-stud framing (e.g. 70mm or 90mm cavity framing).

2. **Delineation of Walkthrough vs Pocket**:
   - `clear_opening_width_m`: Clear walkthrough passage between closing jamb and split jamb post ($W_{clear} \in [0.50, 2.40]$ m).
   - `pocket_length_m`: Hollow frame recess into which the door leaf retracts ($W_{pocket} \ge 0.85 \times W_{clear}$).
   - Floor finish continuity is ONLY interrupted / transitioned at the clear opening passage ($W_{clear}$), NOT across the wall-enclosed pocket recess.

3. **Validation & Fail-Closed Checks**:
   - Fails closed on insufficient pocket depth for the door leaf width.
   - Fails closed on incompatible wall thicknesses ($T_{wall} \notin [0.06, 0.35]$ m).
   - Fails closed on non-physical door widths ($W_{clear} \notin [0.50, 2.40]$ m).

4. **Shadow Mode Invariants**:
   - Candidate status only (`status = CANDIDATE` / `CORROBORATED` internally).
   - Non-publishing: `commercial_projection_allowed = False`, `takeoff_eligible = False`.
   - Customer retention baseline preserved byte-for-byte.
