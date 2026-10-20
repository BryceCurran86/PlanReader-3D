# Antigravity Wet-Area Floor Waste Fall and Hob Boundary Shadow Authority Report (v1)

## Executive Summary
Tiled wet-area floors (FT2/FT3 in bathrooms, ensuites, laundries, airlocks, PWD, M-AMB, F-AMB) feature shower hobs, step-downs, and waste falls. Existing naive extraction algorithms either lump the shower hob into general floor area (ignoring vertical hob tile face and waterproofing upturns) or mistake the hob line for a structural wall, splitting the bathroom into two disjoint rooms.

This milestone (Item 64 / Workstream B Item 14 & Workstream A Item 10) implements the producer-owned wet-area floor waste fall and hob boundary shadow authority (`pb_source_wet_area_hob_waste_fall_shadow.py`).

## Core Architecture & Invariants

1. **Hob vs. Structural Wall Disambiguation**:
   - Validates that hobs have sub-room height ($H_{hob} \in [0.015, 0.400]$ m) and typical width ($W_{hob} \in [0.05, 0.15]$ m).
   - Any candidate divider exceeding $0.40$ m height is classified as a structural wall, preventing false hob creation.
   - Genuine hobs do NOT sever the parent room boundary, preserving single physical room ownership.

2. **Hob Kinds (`HobKind`)**:
   - `RAISED_HOB`: Traditional raised concrete/brick curb (2 vertical tile faces + top face).
   - `RECESSED_STEPDOWN`: Recessed shower tray floor step-down (1 vertical tile face + top face).
   - `FLUSH_WATERSTOP_ANGLE`: Flush concealed angle waterstop.
   - `INSET_SHOWER_TRAY`: Prefabricated composite shower base.

3. **Complete Tiling & Waterproofing Takeoff**:
   - Differentiates main bathroom floor from shower floor area.
   - Integrates hob top face ($L \times W$) and hob vertical curb faces ($2 \times L \times H$ or $L \times H$).
   - Calculates mandatory waterproofing perimeter upturns ($H \ge 0.15$ m) per AS 3740.

4. **Shadow Mode Invariants**:
   - Candidate status only (`status = CANDIDATE` / `CORROBORATED` internally).
   - Non-publishing: `commercial_projection_allowed = False`, `takeoff_eligible = False`.
   - Customer retention baseline preserved byte-for-byte.
