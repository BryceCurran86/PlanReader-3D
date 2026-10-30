# Architecture Report: Structural Timber Glulam / CLT Concealed Knife Plate Connection Shadow Authority (v1)

## Executive Summary
This document establishes the shadow candidate geometry authority for mass timber glulam and cross-laminated timber (CLT) concealed knife plate connections, internal steel blades, drift dowel pin arrays, and standoff base boots (`pb_source_glulam_clt_concealed_knife_plate_shadow.py`).

## Scope & Classification
- **Element Types**:
  - `CONCEALED_BEAM_COLUMN_KNIFE_PLATE`: Glulam beam-to-column concealed knife plate with internal steel blade and transverse dowel pins.
  - `CONCEALED_COLUMN_BASE_KNIFE_PLATE`: Heavy mass timber column base boot / standoff knife plate preventing timber water-wicking.
  - `CLT_SHEAR_PANEL_SPLICE_PLATE`: Internal concealed edge or floor diaphragm splice knife connector for CLT panels.
  - `TRUSS_NODE_MULTIAXIAL_KNIFE_PLATE`: Multiaxial multi-slot steel connector node for glulam timber trusses.
  - `TENSION_TIE_HOLD_DOWN_BLADE`: Seismic/wind uplift concealed knife tie-down bracket.
- **Attributes**: Plate thickness (6–30 mm), knife slot count (single, double, triple blade), dowel diameter (10–24 mm) and quantity, fire rating (30–90 minutes char protection), and base standoff height (mm).

## Safety & Governance
- Strictly candidate shadow authority (`status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`).
- Snapping tolerance: 2.5 pt deterministic snapping.
- Primitive cap: 20,000 primitives.
