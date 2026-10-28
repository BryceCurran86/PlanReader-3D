# Building Automation System (BAS/BMS) Direct Digital Controller (DDC) Panel Shadow Authority Architecture Report (v1)

## Executive Summary
This authority module implements deterministic, candidate-only shadow extraction for Building Automation System (BAS/BMS) Direct Digital Control (DDC) panels, field controller enclosures, remote I/O satellite cabinets, BACnet/Modbus communication modules, and power supply transformers.

## Scope & Classification
- **Panel Configurations**:
  - `MAIN_PLANT_DDC`: Central chilled water, heating water, and central plant DDC panel.
  - `FLOOR_DDC`: Floor/zone level air handling unit and fan coil controller enclosure.
  - `ROOFTOP_DDC`: Weatherproof rooftop plantroom and packaged unit DDC enclosure.
  - `REMOTE_IO_PANEL`: Distributed field bus I/O expansion enclosure.
- **Enclosure & Hardware Metrics**:
  - Ingress protection rating (IP54, IP55, IP56, IP65, IP66).
  - Enclosure dimensions (e.g., 1000x800x300mm).
  - Physical I/O point capacity (16 to 256 points).
  - Communications protocol (BACnet/IP, BACnet MS/TP, Modbus RTU).
  - Auxiliary power (UPS-backed 24VAC / 24VDC power supply).

## Safety & Governance
- Strictly candidate shadow mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`).
- Deterministic 2D coordinate grid snapping (default `2.5 pt`).
- Safety primitive ceiling (`MAX_SAFETY_CAP_PRIMITIVES = 20_000`).
