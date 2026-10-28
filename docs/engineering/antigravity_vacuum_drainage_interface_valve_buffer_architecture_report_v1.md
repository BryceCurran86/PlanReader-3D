# Sanitary Plumbing Vacuum Drainage Interface Valve & Buffer Tank Shadow Authority Architecture Report (v1)

## Executive Summary
This authority module implements deterministic, candidate-only shadow extraction for commercial sanitary vacuum drainage infrastructure: pneumatically operated vacuum interface valves (VIV), graywater collection buffer units, vacuum toilets, central vacuum pump generator skids, and negative-pressure collection mains.

## Scope & Classification
- **Component Configurations**:
  - `VACUUM_INTERFACE_VALVE`: Non-electric pneumatic diaphragm valves (50mm/65mm) cycling on liquid level triggers.
  - `BUFFER_SUMP_UNIT`: Floor-recessed or ceiling-suspended graywater accumulation boxes.
  - `VACUUM_TOILET`: Ultra-low flush (typically 1.0–1.2 L) vacuum pans.
  - `VACUUM_STATION_SKID`: Central skid containing dual vacuum tanks, liquid ring/rotary vane pumps, and discharge pumps.
- **Hydraulic & Pneumatic Parameters**:
  - Nominal valve orifice size (DN50, DN65, DN80).
  - Operating sub-atmospheric pressure level (-40 kPa to -70 kPa).
  - Pipework material: Vacuum-rated Class 12 PVC-U or PE-100 electrofusion welded pipe.

## Safety & Governance
- Strictly candidate shadow mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`).
- Deterministic 2D coordinate grid snapping (default `2.5 pt`).
- Safety primitive ceiling (`MAX_SAFETY_CAP_PRIMITIVES = 20_000`).
