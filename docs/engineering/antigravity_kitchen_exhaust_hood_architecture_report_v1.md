# Architecture Report v1: Source Commercial Kitchen Exhaust Canopy Hood & Baffle Filter Shadow Authority

## 1. Problem Statement & Scope
Commercial culinary kitchens and hospitality dining facilities require AS 1668.1 / NFPA 96 compliant stainless steel exhaust canopy hoods equipped with flame-retardant stainless steel baffle grease filters, perimeter grease gutters with collection drain cups, makeup air (compensating plenum) supply slots, and integrated fire suppression nozzles. In mechanical ventilation layout drawings, kitchen exhaust hoods are often misclassified as simple architectural soffits, bulkheads, or generic supply grilles.

This module introduces `SourceKitchenExhaustHoodShadowAuthority` to extract and validate commercial kitchen exhaust hoods, canopy dimensions (length x width x overhang mm), stainless steel grade (Grade 304 / 316), baffle grease filter counts, exhaust airflow rates (L/s), and compensating makeup air induction slots strictly in shadow candidate mode.

## 2. Design Principles & Non-Negotiables
1. **Strict Shadow Candidate Mode**:
   - `status = "CANDIDATE"`
   - `commercial_projection_allowed = False`
   - `takeoff_eligible = False`
2. **Deterministic Geometric Snapping**:
   - Snapped with `SNAP_TOLERANCE_PT = 2.5 pt`.
3. **Safety Primitive Cap**:
   - Inputs capped at `MAX_SAFETY_CAP_PRIMITIVES = 20_000`.
4. **Zero Gold Dependencies**:
   - Pure regex and keyword parsing without benchmark gold dependencies.
5. **Customer Baseline Invariance**:
   - Maintains exact isolation from customer gold baselines.

## 3. Authority Interface
- `KitchenExhaustHoodCallout`: Frozen dataclass capturing:
  - `raw_text`: Exact callout text
  - `hood_type`: `WALL_MOUNTED_CANOPY`, `ISLAND_V_BANK_CANOPY`, `LOW_PROXIMITY_BACKSHELF_HOOD`
  - `length_mm`: Overall canopy length (mm)
  - `width_mm`: Overall canopy width/depth (mm)
  - `exhaust_airflow_lps`: Total rated exhaust volume in L/s
  - `filter_count`: Number of stainless steel baffle grease filters
  - `makeup_air_included`: Boolean flag indicating integrated compensating makeup air plenum
  - `material_grade`: `STAINLESS_STEEL_304_NO4_FINISH`, `STAINLESS_STEEL_316`
  - `position`: Snapped `(x, y)` coordinate
- `parse_kitchen_exhaust_hood_callout(text: str)`: Parsing function extracting attributes from raw text.
- `SourceKitchenExhaustHoodShadowAuthority`: Batch processor enforcing safety caps and deterministic deduplication.
