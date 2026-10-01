# Formwork Trade Readiness Report (v1.0)
**Task Reference:** AG-22 — Formwork Readiness  
**Author:** Anti Gravity (Autonomous Integration Authority)  
**Date:** October 2026  
**Status:** COMPLETED & VERIFIED  

---

## 1. Executive Summary

This report establishes the verified production authority for the **Formwork Trade** within PlanReader-3D.

Formwork is a major cost center in multi-storey, commercial, and residential concrete construction. By implementing `pb_formwork_trade_authority.py`, PlanReader derives exact contact-area measurements directly from authenticated structural model objects (suspended slabs, slab edges, drop panels, in-situ concrete walls, RC columns, downstand/band beams, balcony stepdowns, and service penetrations).

All formwork quantities are strictly mapped into PlanReader's canonical **21-field core contract** and unit system (`TAKEOFF_UNITS`).

---

## 2. Mathematical Derivation Specifications

| Formwork Element | Primary Unit | Derivation Methodology | Mathematical Formula | Contract Unit |
|:---|:---:|:---|:---|:---:|
| **Soffit Formwork** | $\text{m}²$ | Suspended slab bottom face | $A_{\text{soffit}} = L \times W$ | $\text{m}²$ |
| **Drop Panels** | $\text{m}²$ | Column capital base + 4-sided drops | $A = N \times (L \times W + 2(L + W) \times d)$ | $\text{m}²$ |
| **Cantilever Balconies** | $\text{m}²$ | Exposed cantilever slab underside | $A = L \times W\text{ (special screen protection)}$ | $\text{m}²$ |
| **Slab Edge Boards** | $\text{lm}$ | Exposed slab perimeter by height band | $P_{\text{edge}} = \sum \text{edges}$; $\text{Contact Area} = P \times d$ | $\text{lm}$ |
| **Double-Faced Walls** | $\text{m}²$ | Both wall faces less opening deductions | $A_{\text{form}} = 2 \times (L \times H - \sum A_{\text{openings}})$ | $\text{m}²$ |
| **Wall Blockouts** | $\text{lm}$ | Window and door opening perimeter forms | $P_{\text{boxout}} = 2 \times (w_{\text{op}} + h_{\text{op}})$ | $\text{lm}$ |
| **Rectangular Columns** | $\text{m}²$ | 4 contact faces per column | $A_{\text{form}} = N \times 2(w + d) \times H$ | $\text{m}²$ |
| **Circular Columns** | $\text{m}²$ | Cylindrical surface contact area | $A_{\text{form}} = N \times (\pi D \times H)$ | $\text{m}²$ |
| **High Column Propping** | $\text{No.}$ | Additional propping/scaffold allowance | $\text{Count} = N\text{ where } H > 3.6\text{m}$ | $\text{No.}$ |
| **Beam Sides & Soffit** | $\text{m}²$ | Underside soffit plus both vertical sides | $A_{\text{form}} = L \times (w + 2d)$ | $\text{m}²$ |
| **Stepdown Rebates** | $\text{lm}$ | Balcony and shower drop formers | $L_{\text{rebate}} = \sum \text{rebate lengths}$ | $\text{lm}$ |
| **Slab Penetrations** | $\text{No.}$ | Pipe sleeves and duct blockout boxouts | $\text{Count} = \sum \text{penetrations}$ | $\text{No.}$ |

---

## 3. Strict Contract Compliance

1. **Takeoff Units:** All units strictly belong to `TAKEOFF_UNITS = ('m²', 'lm', 'No.', 'item', 'L', 'allowance')`.
2. **21-Field Core Contract:** All generated rows contain `workspace_id`, 17 editable columns, `row_role`, `created_at`, `updated_at`.
3. **Traceability:** All rows carry `source_reference` prefixed with `PB Formwork Authority v1.0` and structural sheet provenance (e.g. `Structural S102`).

---

## 4. Automated Test Verification

- **Engine:** `pb_formwork_trade_authority.py`
- **Test File:** `tests/test_formwork_trade_authority.py`
- **Test Coverage:**
  - `test_soffit_formwork_calculations`: Flat soffits, cantilevers, drop panels.
  - `test_edge_and_wall_formwork_calculations`: Slab edge boards, double-faced walls with opening deductions and blockouts.
  - `test_columns_beams_stepdowns_penetrations`: Rectangular/circular columns, high-propping allowances, beam sides/soffits, stepdowns, pipe penetrations.
  - `test_sqlite_publication_and_contract_compliance`: SQLite schema round-trip and validation.

### Test Execution:
```powershell
python -m unittest tests/test_formwork_trade_authority.py
```
*Result:* `Ran 4 tests in 0.023s. OK.`
