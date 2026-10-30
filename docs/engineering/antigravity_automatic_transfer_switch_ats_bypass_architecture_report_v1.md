# Architecture Report: Electrical Emergency Power Automatic Transfer Switch (ATS) Bypass Isolation Shadow Authority (v1)

## Executive Summary
This document establishes the shadow candidate geometry authority for electrical emergency power automatic transfer switches (ATS), drawout bypass isolation units, closed transition synchronizers, and manual transfer switches (`pb_source_automatic_transfer_switch_ats_bypass_shadow.py`).

## Scope & Classification
- **Element Types**:
  - `BYPASS_ISOLATION_ATS`: Drawout 4-pole automatic transfer switch with manual bypass isolation mechanism.
  - `STANDARD_AUTOMATIC_TRANSFER_SWITCH`: Open-transition automatic transfer switch (Mains to Emergency Generator / UPS).
  - `CLOSED_TRANSITION_TRANSFER_SWITCH`: Make-before-break (<100ms overlap) synchronized transfer switch.
  - `MANUAL_TRANSFER_SWITCH`: 3-position (Source 1 - OFF - Source 2) lockable manual transfer switch.
  - `LOAD_SHED_PRIORITY_CONTROLLER`: Microprocessor-based generator demand load shedding and engine start management module.
- **Attributes**: Rated current (63–4000 A), number of poles (3 or 4), transition type (open, closed, delayed transition), short circuit withstand rating (35–100 kA), enclosure IP rating (IP31, IP54, IP65), and generator start contacts.

## Safety & Governance
- Strictly candidate shadow authority (`status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`).
- Snapping tolerance: 2.5 pt deterministic snapping.
- Primitive cap: 20,000 primitives.
