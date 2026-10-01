# Masonry Trade Readiness Report (v1.0)
**Task Reference:** AG-25 — Masonry Readiness  
**Author:** Anti Gravity (Autonomous Integration Authority)  
**Date:** October 2026  
**Status:** COMPLETED & VERIFIED  

---

## 1. Executive Summary

This report establishes the verified production authority for the **Masonry Trade (Brickwork & Blockwork)** within PlanReader-3D.

By binding directly to canonical physical wall geometries and verified opening deductions, `pb_masonry_trade_authority.py` generates complete, accurate masonry bills directly from architectural and structural plans:
- External face brick veneer and double-brick skins in net wall area ($\text{m}²$) with brick counts and mortar requirements
- Galvanized cavity wall ties at standard structural grid spacing ($\text{No.}$)
- Continuous base damp-proof course (DPC) and perimeter flashings ($\text{lm}$)
- Concrete blockwork walls (100mm, 150mm, 200mm series) in net area ($\text{m}²$)
- Full, half, or quarter core-fill concrete / grout volume ($\text{item}$)
- Horizontal knock-out bond beams with reinforcing steel ($\text{lm}$)
- Galvanized structural steel angle and T-bar lintels over openings including 150mm end bearings ($\text{lm}$)

All rows strictly conform to PlanReader's canonical **21-field core contract** and unit system (`TAKEOFF_UNITS`).

---

## 2. Mathematical Derivation Specifications

| Masonry Element | Primary Unit | Derivation Methodology | Mathematical Formula | Contract Unit |
|:---|:---:|:---|:---|:---:|
| **Face Brickwork** | $\text{m}²$ | Gross wall area minus opening deductions | $A_{\text{net}} = (L \times H) - \sum A_{\text{openings}}$ | $\text{m}²$ |
| **Brick Count** | $\text{notes}$ | Standard 76mm brick factor | $N_{\text{bricks}} = A_{\text{net}} \times 48.5\text{ bricks/m}²$ | $\text{notes}$ |
| **Mortar Volume** | $\text{notes}$ | Standard single-skin bedding factor | $V_{\text{mortar}} = A_{\text{net}} \times 0.040\text{ m}³\text{/m}²$ | $\text{notes}$ |
| **Cavity Wall Ties** | $\text{No.}$ | Standard 600×400mm grid density | $N_{\text{ties}} = A_{\text{net}} \times 4.5\text{ ties/m}²$ | $\text{No.}$ |
| **Base DPC Flashing** | $\text{lm}$ | Wall base run length | $L_{\text{dpc}} = L_{\text{wall}}$ | $\text{lm}$ |
| **Concrete Blockwork** | $\text{m}²$ | Net block wall area | $A_{\text{net}} = (L \times H) - \sum A_{\text{openings}}$ | $\text{m}²$ |
| **Core-Fill Grout** | $\text{item}$ | Core-fill factor based on block series | $V_{\text{grout}} = A_{\text{net}} \times \text{rate}_{\text{series}} \times F_{\text{fill}}\text{ (m}³\text{)}$ | $\text{item}$ |
| **Bond Beams** | $\text{lm}$ | Wall run length | $L_{\text{bond}} = L_{\text{wall}}$ | $\text{lm}$ |
| **Opening Lintels** | $\text{lm}$ | Opening width plus 2× 150mm bearings | $L_{\text{lintel}} = w_{\text{op}} + 0.30\text{m}$ | $\text{lm}$ |

---

## 3. Strict Contract Compliance

1. **Takeoff Units:** Conforms to `TAKEOFF_UNITS = ('m²', 'lm', 'No.', 'item', 'L', 'allowance')`. Core fill grout volume is safely represented via unit `"item"` with explicit mathematical formula notes.
2. **21-Field Core Contract:** All generated rows contain `workspace_id`, 17 editable columns, `row_role`, `created_at`, `updated_at`.
3. **Traceability:** All rows carry `source_reference` prefixed with `PB Masonry Authority v1.0` and architectural/structural sheet provenance (e.g. `Architectural A101`).

---

## 4. Automated Test Verification

- **Engine:** `pb_masonry_trade_authority.py`
- **Test File:** `tests/test_masonry_trade_authority.py`
- **Test Coverage:**
  - `test_brickwork_veneer_calculations`: Face brickwork skin, cavity wall ties, base DPC.
  - `test_blockwork_and_core_fill_calculations`: Concrete blockwork, core-fill grout volumes, bond beams.
  - `test_lintel_calculations`: Galvanized steel opening lintels with end bearings.
  - `test_sqlite_publication_and_contract_compliance`: SQLite schema round-trip and validation.

### Test Execution:
```powershell
python -m unittest tests/test_masonry_trade_authority.py
```
*Result:* `Ran 4 tests in 0.029s. OK.`
