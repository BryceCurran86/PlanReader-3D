# Architecture Report: Civil Retaining Wall Perforated Corrugated Strip Drain & Geocomposite Sheet Shadow Authority (v1)

## Executive Summary
This document establishes the shadow candidate geometry authority for civil retaining wall perforated corrugated strip drains, dimpled geocomposite sheet drains, agricultural collector pipes, and weep hole assemblies (`pb_source_retaining_wall_geocomposite_strip_drain_shadow.py`).

## Scope & Classification
- **Element Types**:
  - `GEOCOMPOSITE_DIMPLE_SHEET`: High-density polyethylene dimpled core with bonded non-woven geotextile.
  - `PERFORATED_STRIP_DRAIN`: Corrugated prefabricated composite subsoil strip drain (e.g. Megaflo, Stripdrain).
  - `AGRICULTURAL_AG_PIPE`: Perforated slotted subsoil collector pipe with filter sock.
  - `DISCHARGE_WEEPHOLE_ASSEMBLY`: Retaining wall through-wall weep hole.
  - `COLLECTOR_DISCHARGE_OUTLET`: Connector fittings between strip/sheet drains and stormwater outlets.
- **Attributes**: Core width (50 to 2400 mm), core thickness (4 to 30 mm), filter fabric type, compressive strength (kPa), and flow capacity (L/(min·m)).

## Safety & Governance
- Strictly candidate shadow authority (`status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`).
- Snapping tolerance: 2.5 pt deterministic snapping.
- Primitive cap: 20,000 primitives.
