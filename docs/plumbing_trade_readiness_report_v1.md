# Plumbing & Drainage Trade Readiness Report (v1.0)
**Task Reference:** AG-28 — Plumbing Readiness  
**Author:** Anti Gravity (Autonomous Integration Authority)  
**Date:** October 2026  
**Status:** COMPLETED & VERIFIED  

---

## 1. Executive Summary

This report establishes the verified production authority for the **Plumbing & Drainage Trade** within PlanReader-3D.

By binding directly to architectural room fixtures, sanitary schedules, and hydraulic pipe layouts, `pb_plumbing_trade_authority.py` generates complete, construction-ready plumbing and drainage takeoffs:
- Sanitary fixtures (WCs, basins, kitchen sinks, showers, baths, laundry troughs) ($\text{No.}$)
- Associated rough-in water & waste service connection points ($\text{No.}$)
- Underground sanitary sewer drainage pipework (100mm DWV PVC) in linear metres ($\text{lm}$)
- Sewer inspection openings, boundary traps, and inspection shafts ($\text{No.}$)
- Hot and cold water reticulation pipework (PEX/Copper) in linear metres ($\text{lm}$)
- Vertical multi-storey soil and waste stacks with acoustic lagging ($\text{lm}$)
- Cast-in slab intumescent fire collars for penetrations ($\text{No.}$)

All rows strictly conform to PlanReader's canonical **21-field core contract** and unit system (`TAKEOFF_UNITS`).

---

## 2. Mathematical Derivation Specifications

| Plumbing Element | Primary Unit | Derivation Methodology | Mathematical Formula | Contract Unit |
|:---|:---:|:---|:---|:---:|
| **Sanitary Fixtures** | $\text{No.}$ | Count from fixtures schedule & plans | $N_{\text{fix}} = \sum \text{Fixtures}$ | $\text{No.}$ |
| **Rough-In Points** | $\text{No.}$ | 1 water/waste service point per fixture | $N_{\text{rough}} = N_{\text{fix}}$ | $\text{No.}$ |
| **Sewer Drainage** | $\text{lm}$ | Measured drainage run to boundary/main | $L_{\text{drain}} = \sum \text{Pipe runs}$ | $\text{lm}$ |
| **Inspection Openings** | $\text{No.}$ | 1 IO per 15m run or change of direction | $N_{\text{io}} = \lceil L_{\text{drain}} / 15.0 \rceil$ | $\text{No.}$ |
| **Water Supply** | $\text{lm}$ | Measured hot/cold reticulation routes | $L_{\text{water}} = \sum \text{Supply runs}$ | $\text{lm}$ |
| **Soil/Waste Stacks** | $\text{lm}$ | Vertical riser run through storeys | $L_{\text{stack}} = N_{\text{storeys}} \times H_{\text{storey}}$ | $\text{lm}$ |
| **Cast-In Fire Collars** | $\text{No.}$ | 1 collar per slab penetration per stack | $N_{\text{collar}} = \lceil L_{\text{stack}} / 3.0\text{m} \rceil$ | $\text{No.}$ |

---

## 3. Strict Contract Compliance

1. **Takeoff Units:** Conforms to `TAKEOFF_UNITS = ('m²', 'lm', 'No.', 'item', 'L', 'allowance')`.
2. **21-Field Core Contract:** All generated rows contain `workspace_id`, 17 editable columns, `row_role`, `created_at`, `updated_at`.
3. **Traceability:** All rows carry `source_reference` prefixed with `PB Plumbing Authority v1.0` and hydraulic sheet provenance (e.g. `Hydraulic Plans H101`).

---

## 4. Automated Test Verification

- **Engine:** `pb_plumbing_trade_authority.py`
- **Test File:** `tests/test_plumbing_trade_authority.py`
- **Test Coverage:**
  - `test_fixture_calculations`: Fixture counts and rough-in service points.
  - `test_drainage_and_water_pipe_calculations`: Underground sewer drainage and hot/cold water reticulation.
  - `test_stacks_and_fire_collars`: Vertical soil stacks and slab fire collars.
  - `test_sqlite_publication_and_contract_compliance`: SQLite schema round-trip and validation.

### Test Execution:
```powershell
python -m unittest tests/test_plumbing_trade_authority.py
```
*Result:* `Ran 4 tests in 0.033s. OK.`
