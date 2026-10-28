# Architecture Report: Industrial Compressed Air Rotary Screw Compressor & Refrigerated Dryer Skid Shadow Authority (v1)

## Executive Summary
This document establishes the shadow candidate geometry authority for industrial plant compressed air systems, rotary screw air compressors, refrigerated and desiccant dryers, vertical pressure receivers, and compact total air skids (`pb_source_compressed_air_rotary_screw_dryer_skid_shadow.py`).

## Scope & Classification
- **Element Types**:
  - `ROTARY_SCREW_AIR_COMPRESSOR`: Stationary rotary screw air compressor (fixed speed or VSD inverter drive).
  - `REFRIGERATED_AIR_DRYER`: Refrigerated air dryer (+3°C pressure dew point).
  - `DESICCANT_AIR_DRYER`: Desiccant adsorption air dryer (-40°C to -70°C dew point).
  - `VERTICAL_AIR_RECEIVER_VESSEL`: Vertical ASME/AS pressure vessel with safety valve and drain.
  - `COMPACT_TOTAL_AIR_SYSTEM_SKID`: Integrated skid mounting compressor, tank, dryer, and dual coalescing filters.
- **Attributes**: Motor power (7.5–110 kW), free air delivery (20–350 L/s), working pressure (7.5–13 bar), VSD inverter drive, pressure dew point (°C), and receiver vessel capacity (L).

## Safety & Governance
- Strictly candidate shadow authority (`status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`).
- Snapping tolerance: 2.5 pt deterministic snapping.
- Primitive cap: 20,000 primitives.
