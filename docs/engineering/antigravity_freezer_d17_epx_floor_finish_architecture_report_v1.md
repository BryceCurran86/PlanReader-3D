# Antigravity Freezer D17 Insulated Wall Ends and EPX Floor Finish Report (v1)

## Compliance & Context

### Files Actually Read
- `AGENTS.md`
- `docs/AI_ENGINEERING_PLAYBOOK.md`
- `pb_source_cold_room_insulated_panel_shadow.py`
- `pb_source_floor_finish_occurrence_ownership_shadow.py`
- `pb_source_page11_page7_plan_correspondence_shadow.py`
- PR #3462 (shared coordination hub)
- PR #3477 (GPT2 architecture review)

### Exact Functions Traced
- `pb_source_cold_room_insulated_panel_shadow.ColdRoomInsulatedPanelShadowAuthority.evaluate_panel_boundary`
- `pb_source_floor_finish_occurrence_ownership_shadow.evaluate_source_floor_finish_ownership_shadow`
- `pb_source_page11_page7_plan_correspondence_shadow.box_correspondence`

### Authority Boundaries Crossed
- D17 door filling vs insulated wall jamb stroke weight classification.
- Cross-sheet local translation election (+77.76 pt confirmed; +43.92 pt rival rejected).
- Floor finish material role assignment (`EPX` polyurethane/epoxy vs `FT2`/`FT3`).
- Strictly non-publishing shadow authority (`status = CANDIDATE`, `commercial_projection_allowed = False`, `takeoff_eligible = False`).

### Expected Abstentions Before Any Tests
- Thin door filling ink ($W_{stroke} \le 0.50$ pt) spanning D17 must not be classified as a physical wall, failing closed on spurious continuous wall claims across the doorway.
- Competing registrations that fail to align the D17 jamb stops must be rejected (`RIVAL_TRANSLATION_REJECTED_BY_D17_STOPS`).
- Any attempt to assign FT2 or FT3 tile/vinyl finishes to the FREEZER room must fail closed with `INCOMPATIBLE_FLOOR_FINISH_FOR_FREEZER`.
- Customer retention baseline preserved byte-for-byte.

### Files That Will Remain Untouched
- All benchmark gold and holdout definitions (`benchmarks/**`).
- Production extractors and commercial writers.
- 20,000 primitive safety cap and 2.5 pt snap tolerance.

---

## 1. Observed Repository Behavior

As detailed in GPT2 PR #3477:
1. On Maryborough page 7, FREEZER door D17 has thick insulated wall panel ink ($\approx 0.96$ pt) terminating at jamb endpoints $x = 476.16$ and $x = 521.52$. On page 11, the corresponding wall panel stops occur at $x = 553.92$ and $x = 599.28$.
   $553.92 - 476.16 = +77.76$ pt, and $599.28 - 521.52 = +77.76$ pt.
   The competing candidate translation $\Delta x = +43.92$ pt completely fails to align these physical jamb stops.
2. Across the D17 clear opening, a thin stroke ($\approx 0.48$ pt) represents the door leaf in closed/open position. Naive vector extractors mistake this stroke for a continuous wall, erroneously partitioning or sealing the doorway.
3. In the schedule, FREEZER is specified with `EPX` (Allnex Nuthane SB polyurethane resin, min R12 slip resistance, with 100mm coving), distinct from `FT2` (ceramic tile) and `FT3` (vinyl).

---

## 2. Inference

1. Line weight differentiation is critical: thick lines ($W \ge 0.80$ pt) represent structural insulated sandwich panels; thin lines ($W \le 0.50$ pt) inside opening voids represent door leaves and hardware, and must never be promoted to physical wall candidates.
2. The exact +77.76 pt translation between p7 and p11 is uniquely corroborated by the D17 jamb endpoints.
3. The FREEZER room finish boundary terminates at the internal faces of insulated sandwich panels (WA06/WA07), owns material `EPX`, and includes a 100mm vertical coving perimeter takeoff.

---

## 3. Proposed Change

Implement `pb_source_freezer_d17_epx_floor_finish_shadow.py` with:
- `FreezerD17OpeningEvidence`:
  - `jamb_stop_left_pt`, `jamb_stop_right_pt`
  - `door_filling_stroke_present`: bool
  - `retains_clear_walkthrough`: bool = True
  - `translation_dx_pt`: float = +77.76
- `FreezerFloorTakeoffEvidence`:
  - `room_id`: str = "FREEZER"
  - `material_code`: str = "EPX"
  - `internal_floor_area_sqm`: float
  - `perimeter_coving_length_m`: float
  - `coving_upturn_area_sqm`: float ($L \times 0.100$ m)
  - `status`: EvidenceResolutionStatus
- Invariants:
  - Strict shadow mode.
  - Vetoes FT2/FT3 in FREEZER zone.
  - Zero commercial projection.

---

## 4. Benchmark Observations That Must Not Influence Implementation

- No benchmark answers or gold area values determine the algorithm.
- Line weight and translation calculations are derived strictly from geometric source strokes and coordinates.
