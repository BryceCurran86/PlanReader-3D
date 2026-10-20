# Architecture Report: Source Operable Acoustic Folding Partition Wall & Overhead Tracking Shadow Authority (v1)

## Executive Summary
Hospitality venues, convention centers, corporate boardrooms, and institutional educational facilities utilize acoustic operable walls (movable walls / acoustic folding partitions) to subdivide large multipurpose floor plates into independent sound-isolated suites. Achieving high laboratory acoustic ratings (Rw 45 dB to Rw 55 dB) requires precision-manufactured composite acoustic panels with mechanical expanding top/bottom acoustic pressure seals, heavy-duty extruded aluminium overhead track profiles, dedicated stacking bay parking pockets, and continuous mineral wool / mass-loaded vinyl plenum sound barriers directly above the ceiling line to stop flanking sound transmission.

This module introduces `SourceOperableAcousticWallShadowAuthority`, providing an authoritative shadow-mode extraction and quantification framework for operable wall runs, panel counts, overhead structural track lengths, parking stack bay layouts, plenum acoustic baffles, and integrated pass door hardware directly from interior architectural floor plans and partition schedules.

## Domain Model & Operable Wall Anatomy
1. **System Typology (`OperableWallSystemType`)**:
   - `INDIVIDUAL_OMNI_DIRECTIONAL_PANELS`: Multi-directional overhead track trolleys allowing panels to maneuver through 90° T and X track junctions to remote parking pockets.
   - `CENTER_HUNG_PAIRED_PANELS`: Center-hung panels hinged in pairs for rapid setup folding to opening jambs.
   - `CONTINUOUSLY_HINGED_TRAIN`: Mechanically linked bi-folding panels traversing a single continuous track.
   - `VERTICAL_LIFT_RETRACTABLE_WALL`: Motorized ceiling-storing vertical acoustic wall.
2. **Acoustic Rating (`acoustic_rating_rw_db`)**:
   - Tested laboratory sound transmission: typically Rw 45 dB, Rw 48 dB, Rw 50 dB, Rw 53 dB, or Rw 55 dB.
3. **Overhead Tracking & Stacking (`track_points`, `parking_stack_track_length_m`)**:
   - Heavy structural aluminium overhead track suspended from structural slab via steel drop rods/hangers, plus remote parking pocket branches.
4. **Plenum Acoustic Flanking Barrier (`has_plenum_baffle`, `plenum_height_m`)**:
   - Continuous vertical sound baffle in ceiling cavity between top of track and slab soffit.
5. **Integrated Pass Doors (`pass_doors_count`)**:
   - Inset single or double acoustic pass doors providing egress between subdivided rooms.

## Mathematical Formulations
- **Operable Wall Clear Linear Run (\(L_{wall}\))**:
  \[
  L_{wall} = \sum_{i} \text{Length}(\text{centerline}_i)
  \]
- **Wall Elevation Surface Area (\(A_{wall}\))**:
  \[
  A_{wall} = \sum_{i} \text{Length}(\text{centerline}_i) \cdot H_{wall, i}
  \]
- **Total Overhead Track Linear Length (\(L_{track}\))**:
  \[
  L_{track} = \sum_{i} (\text{Length}(\text{centerline}_i) + L_{parking\_stack, i})
  \]
- **Panels Count (\(N_{panels}\))**:
  \[
  N_{panels} = \sum_{i} \left\lceil \frac{\text{Length}(\text{centerline}_i)}{W_{panel, i}} \right\rceil
  \]
- **Ceiling Plenum Acoustic Barrier Area (\(A_{baffle}\))**:
  \[
  A_{baffle} = \sum_{i \in \text{PlenumBaffle}} \text{Length}(\text{centerline}_i) \cdot H_{plenum, i}
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for wall centerlines, track intersections, and parking pocket endpoints.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
