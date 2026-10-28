# Chilled Water / Condenser Water Thermal Storage Stratified Buffer Tank Shadow Authority Architecture Report (v1)

## Executive Summary
This authority module implements deterministic, candidate-only shadow extraction for commercial HVAC hydronic chilled water (CHW) and heating water (HHW) thermal buffer vessels, stratified thermal energy storage (TES) tanks, low-loss hydraulic separators, and radial internal flow diffusers.

## Scope & Classification
- **Tank System Configurations**:
  - `CHILLED_WATER_BUFFER`: Loop volume stabilizer preventing chiller compressor short-cycling.
  - `HEATING_WATER_BUFFER`: Heat pump / condensing boiler thermal flywheel storage.
  - `THERMAL_STRATIFIED_STORAGE`: High-performance gravity-stratified cool energy storage (TES).
  - `HYDRAULIC_SEPARATOR`: 4-pipe decoupled primary/secondary flow distribution tank.
- **Physical & Thermodynamic Attributes**:
  - Volume capacity in litres (1,000L to 50,000L).
  - Geometric orientation: Vertical cylindrical (stratified) vs Horizontal low-headroom.
  - Internal radial velocity-reduction flow diffusers.
  - Factory applied closed-cell polyurethane/PIR insulation with protective embossed stucco cladding.

## Safety & Governance
- Strictly candidate shadow mode (`status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`).
- Deterministic 2D coordinate grid snapping (default `2.5 pt`).
- Safety primitive ceiling (`MAX_SAFETY_CAP_PRIMITIVES = 20_000`).
