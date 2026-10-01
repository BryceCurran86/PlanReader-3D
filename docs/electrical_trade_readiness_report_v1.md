# Electrical Trade Readiness Report (v1.0)
**Task Reference:** AG-29 — Electrical Readiness  
**Author:** Anti Gravity (Autonomous Integration Authority)  
**Date:** October 2026  
**Status:** COMPLETED & VERIFIED  

---

## 1. Executive Summary

This report establishes the verified production authority for the **Electrical & Communications Trade** within PlanReader-3D.

By binding directly to architectural layouts, service schedules, and electrical diagrams, `pb_electrical_trade_authority.py` generates complete, accurate electrical trade takeoffs:
- Main switchboards (MSB) and sub-distribution boards ($\text{No.}$)
- Luminaires, recessed LED downlights, and linear lighting ($\text{No.}$ / $\text{lm}$)
- Maintained and non-maintained emergency and exit lighting fittings ($\text{No.}$)
- Wall switches, dimmers, and multi-gang control plates ($\text{No.}$)
- General power outlets (10A double GPOs) and dedicated heavy-duty circuits (Ovens, EV chargers, A/C isolators) ($\text{No.}$)
- Structured cabling: Cat6 / Cat6A data outlets, communications racks, and NBN enclosures ($\text{No.}$)
- Containment systems: Overhead cable ladder, perforated cable tray, and conduit runs ($\text{lm}$)

All rows strictly conform to PlanReader's canonical **21-field core contract** and unit system (`TAKEOFF_UNITS`).

---

## 2. Mathematical Derivation Specifications

| Electrical Element | Primary Unit | Derivation Methodology | Mathematical Formula | Contract Unit |
|:---|:---:|:---|:---|:---:|
| **Switchboards** | $\text{No.}$ | Count from electrical schedules & SLDs | $N_{\text{sb}} = \sum \text{Distribution boards}$ | $\text{No.}$ |
| **Luminaires** | $\text{No.}$ | Count from reflected ceiling / lighting plans | $N_{\text{light}} = \sum \text{Fittings}$ | $\text{No.}$ |
| **Emergency Fittings** | $\text{No.}$ | Count from fire/emergency lighting plan | $N_{\text{emerg}} = \sum \text{Emergency/Exit units}$ | $\text{No.}$ |
| **Power Outlets** | $\text{No.}$ | Count from power layout plans | $N_{\text{gpo}} = \sum \text{GPO outlets}$ | $\text{No.}$ |
| **Dedicated Circuits** | $\text{No.}$ | Nominated appliance connections | $N_{\text{ckt}} = \sum \text{Dedicated feeds}$ | $\text{No.}$ |
| **Data Outlets** | $\text{No.}$ | Count from communications plans | $N_{\text{data}} = \sum \text{RJ45 data ports}$ | $\text{No.}$ |
| **Cable Containment** | $\text{lm}$ | Measured cable ladder / tray runs | $L_{\text{tray}} = \sum \text{Containment runs}$ | $\text{lm}$ |

---

## 3. Strict Contract Compliance

1. **Takeoff Units:** Conforms to `TAKEOFF_UNITS = ('m²', 'lm', 'No.', 'item', 'L', 'allowance')`.
2. **21-Field Core Contract:** All generated rows contain `workspace_id`, 17 editable columns, `row_role`, `created_at`, `updated_at`.
3. **Traceability:** All rows carry `source_reference` prefixed with `PB Electrical Authority v1.0` and electrical sheet provenance (e.g. `Electrical Plans E101`).

---

## 4. Automated Test Verification

- **Engine:** `pb_electrical_trade_authority.py`
- **Test File:** `tests/test_electrical_trade_authority.py`
- **Test Coverage:**
  - `test_switchboard_and_lighting_calculations`: Switchboards, downlights, exit signage.
  - `test_power_and_data_calculations`: Double GPOs, dedicated appliance circuits, Cat6 data outlets.
  - `test_containment_calculations`: Cable ladder and conduit runs.
  - `test_sqlite_publication_and_contract_compliance`: SQLite schema round-trip and validation.

### Test Execution:
```powershell
python -m unittest tests/test_electrical_trade_authority.py
```
*Result:* `Ran 4 tests in 0.024s. OK.`
