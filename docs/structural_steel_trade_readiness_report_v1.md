# Structural Steel Trade Readiness Report (v1.0)
**Task Reference:** AG-24 — Structural Steel Readiness  
**Author:** Anti Gravity (Autonomous Integration Authority)  
**Date:** October 2026  
**Status:** COMPLETED & VERIFIED  

---

## 1. Executive Summary

This report establishes the verified production authority for the **Structural Steel Trade** within PlanReader-3D.

By binding directly to canonical structural building framing elements, `pb_structural_steel_trade_authority.py` generates comprehensive, fabrication-ready steel takeoffs directly from engineering plans without manual scaling or hallucinated members:
- Primary steel beams and trimmers (UB/WB) measured in linear metres ($\text{lm}$) and fabrication tonnage ($\text{tonnes}$)
- Structural steel columns and posts (UC/SHS) with member count ($\text{No.}$), height, and mass
- Secondary cold-formed framing (purlins & girts: C/Z sections) in linear metres ($\text{lm}$)
- Structural cross-bracing and fly-bracing bays ($\text{No.}$ / $\text{lm}$)
- Industry-standard connection and fitting allowances (e.g. 10% on primary steel tonnage) for base plates, cleats, splices, and high-strength bolts ($\text{item}$)
- Protective surface treatment & coating areas (Shop primer, Hot-Dip Galvanizing, Intumescent fire protection) ($\text{m}²$)

All rows strictly conform to PlanReader's canonical **21-field core contract** and unit system (`TAKEOFF_UNITS`).

---

## 2. Mathematical Derivation Specifications

| Steel Element | Primary Unit | Derivation Methodology | Mathematical Formula | Contract Unit |
|:---|:---:|:---|:---|:---:|
| **Primary Beams** | $\text{lm}$ | Beam runs by section mark | $L_{\text{tot}} = \sum (N \times L)$ | $\text{lm}$ |
| **Fabrication Tonnage** | $\text{item}$ | Linear length × section linear mass | $M = (L_{\text{tot}} \times \rho_{\text{lin}}) / 1000\text{ (t)}$ | $\text{item}$ |
| **Columns & Posts** | $\text{lm}$ | Column height × count | $L_{\text{col}} = N \times H;\quad M = (L_{\text{col}} \times \rho_{\text{lin}}) / 1000$ | $\text{lm}$ |
| **Protective Coating** | $\text{m}²$ | Member length × perimeter surface area | $A_{\text{coat}} = L_{\text{tot}} \times a_{\text{surf}}$ | $\text{m}²$ |
| **Purlins & Girts** | $\text{lm}$ | Roof & wall cold-formed runs | $L_{\text{purlin}} = N_{\text{runs}} \times L$ | $\text{lm}$ |
| **Cross-Bracing** | $\text{No.}$ / $\text{lm}$ | Tension rod / angle bracing bays | $N_{\text{bays}} = \text{Count of braced bays}$ | $\text{No.}$ |
| **Connection Allowance** | $\text{item}$ | Standard industry % on primary tonnage | $M_{\text{conn}} = M_{\text{primary}} \times 0.10\text{ (10\%)}$ | $\text{item}$ |

---

## 3. Strict Contract Compliance

1. **Takeoff Units:** Conforms to `TAKEOFF_UNITS = ('m²', 'lm', 'No.', 'item', 'L', 'allowance')`. Member runs use $\text{lm}$, counts use $\text{No.}$, coatings use $\text{m}²$, and calculated tonnage is represented via unit `"item"` with explicit mathematical notes.
2. **21-Field Core Contract:** All generated rows contain `workspace_id`, 17 editable columns, `row_role`, `created_at`, `updated_at`.
3. **Traceability:** All rows carry `source_reference` prefixed with `PB Structural Steel Authority v1.0` and structural sheet provenance (e.g. `Structural S201`).

---

## 4. Automated Test Verification

- **Engine:** `pb_structural_steel_trade_authority.py`
- **Test File:** `tests/test_structural_steel_trade_authority.py`
- **Test Coverage:**
  - `test_primary_steel_member_calculations`: Primary beams and columns (length, tonnage, coating area).
  - `test_purlins_girts_and_bracing`: Secondary cold-formed purlins and cross-bracing bays.
  - `test_connection_fittings_allowance`: Standard 10% connection and base plate tonnage allowance.
  - `test_sqlite_publication_and_contract_compliance`: SQLite schema round-trip and validation.

### Test Execution:
```powershell
python -m unittest tests/test_structural_steel_trade_authority.py
```
*Result:* `Ran 4 tests in 0.023s. OK.`
