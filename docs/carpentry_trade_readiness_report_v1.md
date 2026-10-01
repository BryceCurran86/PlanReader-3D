# Carpentry Trade Readiness Report (v1.0)
**Task Reference:** AG-27 — Carpentry Readiness  
**Author:** Anti Gravity (Autonomous Integration Authority)  
**Date:** October 2026  
**Status:** COMPLETED & VERIFIED  

---

## 1. Executive Summary

This report establishes the verified production authority for the **Carpentry & Timber Framing Trade** within PlanReader-3D.

By binding directly to canonical wall runs, floor footprints, roof planes, and exterior eaves geometries, `pb_carpentry_trade_authority.py` generates complete, fabrication-ready timber framing and exterior cladding takeoffs:
- Timber stud wall framing elevation area ($\text{m}²$)
- Wall plates: Bottom plate and double top plate ($3 \times \text{length}$ in $\text{lm}$)
- Common and opening jamb/corner studs ($\text{No.}$) spaced at 450mm or 600mm centres
- Horizontal wall noggings / dwangs ($\text{lm}$)
- Subfloor structural particleboard sheet flooring ($\text{m}²$) and timber floor joists ($\text{lm}$)
- Prefabricated roof trusses ($\text{No.}$) and roof battens ($\text{lm}$)
- External weatherboard / fibre-cement cladding ($\text{m}²$)
- Eaves soffit lining ($\text{m}²$) and timber fascia boards ($\text{lm}$)

All rows strictly conform to PlanReader's canonical **21-field core contract** and unit system (`TAKEOFF_UNITS`).

---

## 2. Mathematical Derivation Specifications

| Carpentry Element | Primary Unit | Derivation Methodology | Mathematical Formula | Contract Unit |
|:---|:---:|:---|:---|:---:|
| **Wall Framing Area** | $\text{m}²$ | Wall run length × framing height | $A_{\text{frame}} = L \times H$ | $\text{m}²$ |
| **Wall Plates** | $\text{lm}$ | 1 bottom plate + 2 top plates | $L_{\text{plates}} = 3 \times L_{\text{wall}}$ | $\text{lm}$ |
| **Wall Studs** | $\text{No.}$ | (Length / spacing + 1) + opening/corner extras | $N_{\text{studs}} = \lceil L / s \rceil + 1 + 2 N_{\text{openings}} + 2$ | $\text{No.}$ |
| **Noggings** | $\text{lm}$ | 1 or 2 horizontal rows per wall run | $L_{\text{nog}} = N_{\text{rows}} \times L_{\text{wall}}$ | $\text{lm}$ |
| **Subfloor Flooring** | $\text{m}²$ | First floor / subfloor area | $A_{\text{floor}} = \text{Area}(\text{Polygon})$ | $\text{m}²$ |
| **Floor Joists** | $\text{lm}$ | 2.4 lm of joist per m² of subfloor | $L_{\text{joist}} = A_{\text{floor}} \times 2.4\text{ lm/m}²$ | $\text{lm}$ |
| **Roof Trusses** | $\text{No.}$ | Roof run length / 900mm spacing + 1 | $N_{\text{truss}} = \lceil L_{\text{roof}} / 0.900 \rceil + 1$ | $\text{No.}$ |
| **Roof Battens** | $\text{lm}$ | 1.25 lm of batten per m² of roof plane | $L_{\text{batten}} = A_{\text{roof}} \times 1.25\text{ lm/m}²$ | $\text{lm}$ |
| **External Cladding** | $\text{m}²$ | Gross wall area minus opening deductions | $A_{\text{clad}} = (L \times H) - \sum A_{\text{openings}}$ | $\text{m}²$ |
| **Eaves Soffits** | $\text{m}²$ | Eave perimeter × overhang width | $A_{\text{eave}} = P_{\text{eave}} \times w_{\text{overhang}}$ | $\text{m}²$ |
| **Timber Fascia** | $\text{lm}$ | Eave perimeter | $L_{\text{fascia}} = P_{\text{eave}}$ | $\text{lm}$ |

---

## 3. Strict Contract Compliance

1. **Takeoff Units:** Conforms to `TAKEOFF_UNITS = ('m²', 'lm', 'No.', 'item', 'L', 'allowance')`.
2. **21-Field Core Contract:** All generated rows contain `workspace_id`, 17 editable columns, `row_role`, `created_at`, `updated_at`.
3. **Traceability:** All rows carry `source_reference` prefixed with `PB Carpentry Authority v1.0` and architectural/structural sheet provenance (e.g. `Framing Plan A102`).

---

## 4. Automated Test Verification

- **Engine:** `pb_carpentry_trade_authority.py`
- **Test File:** `tests/test_carpentry_trade_authority.py`
- **Test Coverage:**
  - `test_wall_framing_calculations`: Wall frame area, plates, studs count, noggings.
  - `test_subfloor_and_roof_framing`: Structural particleboard subfloor, joists, trusses, roof battens.
  - `test_cladding_and_eaves`: Weatherboard cladding, eaves soffit linings, timber fascia.
  - `test_sqlite_publication_and_contract_compliance`: SQLite schema round-trip and validation.

### Test Execution:
```powershell
python -m unittest tests/test_carpentry_trade_authority.py
```
*Result:* `Ran 4 tests in 0.030s. OK.`
