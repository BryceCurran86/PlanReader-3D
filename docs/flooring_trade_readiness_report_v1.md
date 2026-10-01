# Flooring & Tiling Trade Readiness Report (v1.0)
**Task Reference:** AG-26 — Flooring Readiness  
**Author:** Anti Gravity (Autonomous Integration Authority)  
**Date:** October 2026  
**Status:** COMPLETED & VERIFIED  

---

## 1. Executive Summary

This report establishes the verified production authority for the **Flooring and Tiling Trade** within PlanReader-3D.

By binding directly to canonical room boundaries and floor area polygons, `pb_flooring_trade_authority.py` generates accurate trade takeoffs without manual polygon tracing or duplicate room measurement:
- Engineered timber, hybrid, and laminate flooring ($\text{m}²$) with acoustic underlay ($\text{m}²$) and perimeter quad beading ($\text{lm}$)
- Broadloom carpet and carpet tiles ($\text{m}²$) with underlay ($\text{m}²$) and architectural smooth-edge grippers ($\text{lm}$)
- Floor tiling ($\text{m}²$) with tile skirtings ($\text{lm}$)
- Wet-area substrate preparation: Sand & cement screed beds graded to floor waste ($\text{m}²$)
- Liquid-applied waterproofing membrane with vertical perimeter upturns ($\text{m}²$)

All rows strictly conform to PlanReader's canonical **21-field core contract** and unit system (`TAKEOFF_UNITS`).

---

## 2. Mathematical Derivation Specifications

| Flooring Element | Primary Unit | Derivation Methodology | Mathematical Formula | Contract Unit |
|:---|:---:|:---|:---|:---:|
| **Timber / Laminate** | $\text{m}²$ | Net room floor polygon area | $A_{\text{floor}} = \text{Area}(\text{Polygon})$ | $\text{m}²$ |
| **Acoustic Underlay** | $\text{m}²$ | Matches floating timber area | $A_{\text{underlay}} = A_{\text{floor}}$ | $\text{m}²$ |
| **Perimeter Quad** | $\text{lm}$ | Room perimeter minus door openings | $L_{\text{quad}} = P_{\text{room}} - w_{\text{door}}$ | $\text{lm}$ |
| **Carpet Covering** | $\text{m}²$ | Net room floor area | $A_{\text{carpet}} = \text{Area}(\text{Polygon})$ | $\text{m}²$ |
| **Carpet Grippers** | $\text{lm}$ | Room perimeter minus door openings | $L_{\text{grip}} = P_{\text{room}} - w_{\text{door}}$ | $\text{lm}$ |
| **Floor Tiling** | $\text{m}²$ | Wet-area room floor area | $A_{\text{tile}} = \text{Area}(\text{Polygon})$ | $\text{m}²$ |
| **Screed to Falls** | $\text{m}²$ | Sand & cement bed over wet area slab | $A_{\text{screed}} = A_{\text{tile}}$ | $\text{m}²$ |
| **Waterproofing** | $\text{m}²$ | Floor area plus 150mm vertical perimeter upturns | $A_{\text{wp}} = A_{\text{tile}} + (P_{\text{room}} \times 0.15\text{m})$ | $\text{m}²$ |
| **Tile Skirtings** | $\text{lm}$ | Perimeter minus door opening | $L_{\text{skirt}} = P_{\text{room}} - w_{\text{door}}$ | $\text{lm}$ |

---

## 3. Strict Contract Compliance

1. **Takeoff Units:** Conforms to `TAKEOFF_UNITS = ('m²', 'lm', 'No.', 'item', 'L', 'allowance')`.
2. **21-Field Core Contract:** All generated rows contain `workspace_id`, 17 editable columns, `row_role`, `created_at`, `updated_at`.
3. **Traceability:** All rows carry `source_reference` prefixed with `PB Flooring Authority v1.0` and finishes schedule sheet provenance (e.g. `Finishes Schedule A501`).

---

## 4. Automated Test Verification

- **Engine:** `pb_flooring_trade_authority.py`
- **Test File:** `tests/test_flooring_trade_authority.py`
- **Test Coverage:**
  - `test_timber_flooring_calculations`: Engineered timber, underlay, perimeter quads.
  - `test_carpet_flooring_calculations`: Carpet area, underlay, smooth-edge grippers.
  - `test_wet_area_tiling_screed_and_waterproofing`: Porcelain floor tiles, sand & cement screed to falls, waterproofing with upturns, tile skirtings.
  - `test_sqlite_publication_and_contract_compliance`: SQLite schema round-trip and validation.

### Test Execution:
```powershell
python -m unittest tests/test_flooring_trade_authority.py
```
*Result:* `Ran 4 tests in 0.023s. OK.`
