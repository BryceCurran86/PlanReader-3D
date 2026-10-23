# Architecture Report: Source Fire Compartment Separation Wall & Damper Penetration Shadow Authority (v1)

## Executive Summary
Life safety and building code compliance (AS 1530.4 / NCC / IBC) necessitate fire compartment barriers separating sole-occupancy units, public egress corridors, fire escape stairs, and plant enclosures.
Standard wall extraction treats fire-rated partitions as generic walls, causing two critical omissions:
1. Missing fire resistance level (FRL) classification (e.g. 60/60/60, 90/90/90, 120/120/120), failing to verify structural adequacy, integrity, and insulation ratings.
2. Completely dropping fire damper units and intumescent collar seals when mechanical ducts and plumbing pipes penetrate fire-rated barriers.

This authority inventories fire compartment boundaries, binds FRL ratings to wall runs, and registers service penetrations requiring certified fire dampers and collar seals in shadow candidate mode.

## Workstream Reference
- **Workstream A Item 3:** Fire-rated separating walls, compartmentation boundaries, and service penetration protection.

## Fire Resistance & Damper Model
Given:
- Fire compartment boundary wall length $L$ and height $H$.
- Fire Resistance Level (FRL) string: `Structural / Integrity / Insulation` (in minutes).
- Service penetrations: mechanical ducts requiring tested fire dampers, plumbing pipes requiring intumescent collar assemblies.

Calculations:
1. Fire wall barrier surface area: $A = L \cdot H$.
2. Penetration protection units:
   - Mechanical Fire Dampers: counted per duct crossing.
   - Intumescent Pipe Collars: counted per hydraulic crossing.

## Invariants & Safety
- Candidate shadow mode only (`status = EvidenceResolutionStatus.CANDIDATE`).
- `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Global 2.5 pt snap tolerance.
- Customer retention baseline preserved byte-for-byte.
