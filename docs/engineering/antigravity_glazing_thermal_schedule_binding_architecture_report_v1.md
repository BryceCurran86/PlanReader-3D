# Antigravity Glazing U-Value and Thermal Performance Schedule Binding Report (v1)

## Compliance & Context

### Files Actually Read
- `AGENTS.md`
- `docs/AI_ENGINEERING_PLAYBOOK.md`
- `pb_source_window_door_void_classification_shadow.py`
- `pb_source_rcp_ceiling_region_shadow.py`
- PR #3462 (shared coordination hub)

### Exact Functions Traced
- `pb_source_window_door_void_classification_shadow.WindowDoorVoidClassificationShadowAuthority.evaluate_opening_void`: Void physical kind classification
- `pb_page_scale_calibration_authority.resolve_page_scale_calibration`: Measurement basis

### Authority Boundaries Crossed
- Window schedule entity parsing, thermal rating attribution (U-value, SHGC), frame substrate classification, and binding to physical window openings.
- Strictly non-publishing shadow authority (`status = CANDIDATE`, `commercial_projection_allowed = False`, `takeoff_eligible = False`).

### Expected Abstentions Before Any Tests
- Any window opening with no matching schedule entry or ambiguous mark (e.g. multiple distinct W01 rows with conflicting U-values) must abstain (`EvidenceResolutionStatus.ABSTAINED`).
- Non-physical U-values ($U \notin [0.5, 7.5]$ W/m²K) or SHGC ($\notin [0.1, 0.9]$) fail closed.
- Downstream commercial projection and takeoff eligibility remain strictly `False`.
- Customer retention baseline preserved byte-for-byte.

### Files That Will Remain Untouched
- All benchmark gold and holdout definitions (`benchmarks/**`).
- Production extractors and commercial writers (`pb_planreader_pdf_extractor.py`, `pb_opening_production_v175.py`).
- 20,000 primitive safety cap and 2.5 pt snap tolerance.

---

## 1. Observed Repository Behavior

Existing opening modules in PlanReader-3D detect geometric void spans and physical door vs window classifications. However, thermal performance data required for building energy compliance (such as Section J of the NCC or BASIX in Australia)—specifically Solar Heat Gain Coefficient (SHGC), thermal transmittance ($U$-value in W/m²K), glazing assembly (single, double, low-E), and frame material (thermally broken aluminium, uPVC, timber)—are specified in window schedule tables on separate drawing sheets (e.g. Page 29 in Maryborough, or elevation sheets in Lot16).

Without a dedicated thermal schedule binding authority, physical window openings remain un-attributed with respect to thermal ratings, preventing energy facade takeoff.

---

## 2. Inference

A robust, fail-closed thermal schedule binding authority requires:
1. `GlazingType` and `FrameSubstrate` standard classifications.
2. Schedule record extraction validating physical bounds:
   - $U$-value $\in [0.5, 7.5]$ W/m²K.
   - SHGC $\in [0.10, 0.85]$.
   - Dimensions matching opening schedule callouts within tolerance ($\pm 50$ mm).
3. Exact tag / mark matching (e.g. "W01" -> physical opening W01).
4. Ambiguity veto: conflicting entries for the same window mark fail closed with `CONFLICTING_THERMAL_RATINGS`.

---

## 3. Proposed Change

Implement `pb_source_glazing_thermal_schedule_binding_shadow.py` with:
- Data structures: `ThermalScheduleEntry`, `GlazingThermalBindingEvidence`.
- `GlazingThermalScheduleBindingShadowAuthority`:
  - `register_schedule_entry(entry: ThermalScheduleEntry)`
  - `bind_opening_thermal_performance(opening_id, mark, width_m, height_m) -> GlazingThermalBindingEvidence`
- Invariants:
  - Candidate status only.
  - Fail closed on missing, out-of-range, or conflicting thermal ratings.
  - Zero commercial projection.

---

## 4. Benchmark Observations That Must Not Influence Implementation

- No specific project codes or benchmark numbers are used.
- Purely physical and engineering validation based on thermodynamics and Australian/international fenestration standards (AS 2047, NFRC).
