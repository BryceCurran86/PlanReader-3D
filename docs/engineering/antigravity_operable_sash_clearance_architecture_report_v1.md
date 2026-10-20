# Architecture Report: Source Glazing Operable Sash & Awning / Casement Opening Clearance Shadow Authority (v1)

## Executive Summary
Architectural window schedules and facade elevations distinguish between fixed vision glazing and operable sashes. Identifying operable sash sub-frames, opening mechanisms, and spatial projection envelopes is essential for natural ventilation statutory compliance (NCC/BCA Part F4), window winder hardware procurement, insect/flyscreen quantification, and clearance collision detection.

This module introduces `SourceOperableSashClearanceShadowAuthority`, providing an authoritative shadow-mode framework for parsing, validating, and quantifying operable window sashes directly from elevation swing conventions and schedule annotations.

## Domain Model & Operation Mechanics
1. **Awning Sash (`AWNING`)**:
   - Top-hinged sash projecting outward at the bottom operated via chain winder.
   - Ventilation area is determined by throat perimeter clearance opening.
2. **Casement Sash (`CASEMENT_LH`, `CASEMENT_RH`)**:
   - Side-hinged sash swinging outward (left-hand or right-hand). Encroaches directly on exterior circulation if at ground level.
3. **Sliding Sash (`SLIDING`)**:
   - Horizontally traversing sash within parent frame. Max ventilation area = 50% of nominal window opening.
4. **Louvre Gallery (`LOUVRE`)**:
   - Multiple horizontal glass blades pivoting synchronously (~70% net free ventilation area).
5. **Fixed Panel (`FIXED`)**:
   - Non-operable direct glazed vision lite (0% openable ventilation).

## Mathematical Formulations
- **Nominal Sash Area (\(A_{sash}\))**:
  \[
  A_{sash} = \left(\frac{W_{mm}}{1000}\right) \times \left(\frac{H_{mm}}{1000}\right)
  \]
- **Effective Ventilation Openable Area (\(A_{vent}\))**:
  - For `SLIDING`:
    \[
    A_{vent} = 0.5 \times A_{sash}
    \]
  - For `AWNING` (with bottom projection \(d_{proj}\)):
    \[
    A_{vent} = \min\left(A_{sash}, \left(\frac{d_{proj}}{1000}\right) \times \left(\frac{W_{mm} + 2 \times H_{mm}}{1000}\right)\right)
    \]
  - For `CASEMENT` (opening angle \(\theta\)):
    \[
    A_{vent} = A_{sash} \times \sin(\theta)
    \]
  - For `LOUVRE`:
    \[
    A_{vent} = 0.70 \times A_{sash}
    \]
- **Insect Screen Surface Area (\(A_{screen}\))**:
  Sum of nominal sash areas for all operable sashes fitted with screens:
  \[
  A_{screen} = \sum_{k \in \text{Screened}} A_{sash, k}
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt snap tolerance on sash boundary frames.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
