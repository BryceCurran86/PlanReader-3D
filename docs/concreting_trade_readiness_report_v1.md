# Concreting Trade Readiness Report (v1.0)
**Task Reference:** AG-21 — Concreting Readiness  
**Author:** Anti Gravity (Autonomous Integration Authority)  
**Date:** October 2026  
**Status:** COMPLETED & VERIFIED  

---

## 1. Executive Summary

This report establishes the verified production authority for the **Concreting Trade** within PlanReader-3D.

By binding directly to canonical building model geometries (slabs, footings, columns, beams, stairs, and perimeters), the concreting trade authority (`pb_concreting_trade_authority.py`) derives accurate, construction-grade quantities without manual re-measurement, duplicate rasterization, or hallucinated values.

All concrete trade rows strictly adhere to PlanReader's canonical **21-field core contract** and unit system (`TAKEOFF_UNITS`).

---

## 2. Mathematical Derivation Specifications

| Concrete Element | Primary Unit | Derived Secondary Trade Items | Mathematical Derivation Formula | Contract Unit |
|:---|:---:|:---|:---|:---:|
| **Slab on Ground** | $\text{m}²$ | Concrete supply & pump<br>Edge formwork<br>Damp-proof membrane (DPM) | $V = A \times t$<br>$\text{Contact Area} = P \times t$<br>$\text{DPM} = A \times 1.10\text{ (10\% lap)}$ | $\text{m}²$<br>$\text{item}$<br>$\text{lm}$<br>$\text{m}²$ |
| **Suspended Slab** | $\text{m}²$ | Concrete supply & pump<br>Soffit formwork<br>Edge formwork | $V = A \times t$<br>$\text{Soffit} = A$<br>$\text{Edge} = P \times t$ | $\text{m}²$<br>$\text{item}$<br>$\text{m}²$<br>$\text{lm}$ |
| **Strip Footing** | $\text{lm}$ | Trench concrete supply | $V = L \times W \times D$ | $\text{lm}$<br>$\text{item}$ |
| **Pad Footings** | $\text{No.}$ | Pad concrete volume | $V = N \times (L \times W \times D)$ | $\text{No.}$<br>$\text{item}$ |
| **Bored Piers** | $\text{No.}$ | Bored pier concrete volume | $V = N \times (\pi r^2 \times D)$ | $\text{No.}$<br>$\text{item}$ |
| **RC Columns** | $\text{No.}$ | Column formwork (4-faced) | $V = N \times (w \times d \times h)$<br>$\text{Formwork} = N \times 2(w + d) \times h$ | $\text{No.}$<br>$\text{m}²$ |
| **RC Beams** | $\text{lm}$ | Beam formwork (soffit + 2 sides) | $V = L \times w \times d$<br>$\text{Formwork} = L \times (w + 2d)$ | $\text{lm}$<br>$\text{m}²$ |
| **RC Stairs** | $\text{No.}$ | Stair formwork (soffit + risers) | $V = F \times \text{steps} \times w \times 0.08$<br>$\text{Formwork} = F \times \text{steps} \times (w \times 0.18 + w \times 0.28)$ | $\text{No.}$<br>$\text{m}²$ |

---

## 3. Strict Contract Compliance

1. **Takeoff Units:** Concrete volumes ($m³$) are safely represented within `TAKEOFF_UNITS = ('m²', 'lm', 'No.', 'item', 'L', 'allowance')` using primary element measurement units ($\text{m}²$, $\text{lm}$, $\text{No.}$) with volume formulas explicitly published in `notes`, and supply/pump items utilizing unit `"item"`.
2. **21-Field Core Contract:** Every concrete row includes all ordered fields:
   `workspace_id`, `section`, `element`, `location`, `substrate`, `finish_system`, `quantity`, `unit`, `quantity_status`, `source_page`, `source_reference`, `inclusion_status`, `coats`, `coverage_m2_per_litre`, `productivity_m2_per_hour`, `rate_per_unit`, `confidence`, `notes`, `row_role`, `created_at`, `updated_at`.
3. **Idempotence & Traceability:** All rows carry `source_reference` prefixed with `PB Concrete Authority v1.0` and exact structural source page provenance (e.g. `Structural S101`).

---

## 4. Automated Test Verification

- **Engine:** `pb_concreting_trade_authority.py`
- **Test File:** `tests/test_concreting_trade_authority.py`
- **Test Coverage:**
  - `test_slab_concrete_trade_derivation`: Ground & suspended slab takeoffs.
  - `test_footings_and_piers_derivation`: Strip, pad, and bored pier foundations.
  - `test_columns_beams_and_stairs_derivation`: Column count, beam runs, stairs, and formwork areas.
  - `test_sqlite_publication_and_contract_compliance`: Round-trip SQLite database persistence and schema contract compliance.

### Test Execution:
```powershell
python -m unittest tests/test_concreting_trade_authority.py
```
*Result:* `Ran 4 tests in 0.025s. OK.`
