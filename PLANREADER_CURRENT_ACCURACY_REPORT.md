# PlanReader Current Accuracy Gap Report — 2026-09-28

## Verified current baseline

Fresh canonical-five validation on production main `819b6aca4f671b34c37d97f63d9d31a678af247b`:

- **36 / 60 accepted = 60.00%**
- **29 / 60 strict exact = 48.33%**
- **7 additional rows within 5%**
- **0 gross mismatches**
- **0 hallucinations**
- **23 missed rows**
- **1 additional row within 20% but outside acceptance**

Per project:

| Project | Accepted | Accuracy | Strict exact |
| :--- | ---: | ---: | ---: |
| KSTVET | 6/13 | 46.15% | 30.77% |
| Murera | 4/10 | 40.00% | 40.00% |
| Ghazi | 7/13 | 53.85% | 30.77% |
| Umma | 15/15 | 100.00% | 100.00% |
| Lamu | 4/9 | 44.44% | 22.22% |

The score is unchanged from the previous trustworthy 36/60 baseline. The fresh run proves that newer merged production work has not yet produced an additional accepted canonical row.

## Every remaining non-accepted row

| Project | Item | Description | Current status | Current | Expected |
| :--- | :--- | :--- | :--- | ---: | ---: |
| KSTVET | `BOQ-C36-A` | 150 mm Thick concrete block walling | missed_in_extraction | — | 58 SM |
| KSTVET | `BOQ-C41-B` | Window overall size 3000 x 1200mm High steel casement | missed_in_extraction | — | 2 NO |
| KSTVET | `BOQ-C41-C` | Window overall size 2900 x 1200mm High steel casement | missed_in_extraction | — | 3 NO |
| KSTVET | `BOQ-C46-A` | 12 mm (minimum) two-coat plaster to internal walls | missed_in_extraction | — | 69 SM |
| KSTVET | `BOQ-C46-C` | Three coats of premium quality silk vinyl paint to plastered internal walls | missed_in_extraction | — | 69 SM |
| KSTVET | `BOQ-C47-A` | Extra over walling for key pointing externally | missed_in_extraction | — | 60 SM |
| KSTVET | `BOQ-C47-B` | 12mm plaster to external walls, beams, columns | missed_in_extraction | — | 20 SM |
| Murera | `substructure_surface_bed` | 125mm thick reinforced concrete class 25 surface bed | missed_in_extraction | — | 196 SM |
| Murera | `substructure_bed_dpm` | 1000 gauge polythene damp-proof membrane under bed | missed_in_extraction | — | 208 SM |
| Murera | `substructure_a142_mesh` | Steel mesh fabric reinforcement Ref A142 in floor bed | missed_in_extraction | — | 208 SM |
| Murera | `masonry_external_walling` | 150mm thick natural stone external walling | missed_in_extraction | — | 132 SM |
| Murera | `masonry_piers` | 300 x 300mm masonry piers 4,500mm high | missed_in_extraction | — | 13 NO |
| Murera | `damp_proof_course` | 150mm wide bituminous felt damp proof course | missed_in_extraction | — | 67 M |
| Ghazi | `GZ-E3-B` | Approved coral block walling in 200mm thick walling externally | missed_in_extraction | — | 109 SM |
| Ghazi | `GZ-E3-C` | Ditto internally (200mm thick coral block walling) | missed_in_extraction | — | 41 SM |
| Ghazi | `GZ-E3-D` | Ditto gable wall (200mm thick coral block walling) | missed_in_extraction | — | 12 SM |
| Ghazi | `GZ-E8-A` | 20mm thick cement and sand (1:5) plaster steel trowelled to internal walls | missed_in_extraction | — | 203 SM |
| Ghazi | `GZ-E8-C` | Prepare and apply three coats first grade plastic paint to plastered internal walls | missed_in_extraction | — | 203 SM |
| Ghazi | `GZ-E8-H` | 10mm chip board ceiling lining on brandering | missed_in_extraction | — | 160 SM |
| Lamu | `LMU-E3-A` | 200mm thick approved local; machine cut; natural stone walling; bedding, jointing and pointing in cement sand (1:3) mortar | missed_in_extraction | — | 136 SM |
| Lamu | `LMU-E3-B` | Damp proofing: 200mm wide; B.S. 743 Type A bitumen hessian base, 150mm laps (no allowance made for laps); horizontal, 1No. layer, bedded in cement sand (1:3) mortar | within_20_percent | 64 | 75 LM |
| Lamu | `LMU-E4-A` | Galvanized corrugated sheet roofing, 28 gauge, prepainted; G.C.I roof covering not exceeding 30 degrees from horizontal | missed_in_extraction | — | 172 SM |
| Lamu | `LMU-E7-A` | Wall finishes: 20mm thick cement and sand (1:4) plaster steel trawled to walls | missed_in_extraction | — | 268 SM |
| Lamu | `LMU-E7-C` | Painting and decorations to walls: prepare and apply three coats of first quality plastic emulsion paint to plastered walls and beams | missed_in_extraction | — | 268 SM |

## Root-capability grouping

There are **24 non-accepted rows**. They cluster much more tightly than 24 unrelated bugs:

| Capability cluster | Rows | Canonical rows |
| :--- | ---: | :--- |
| Physical wall identity → gross/net wall → finish-face publication | **14** | KSTVET C36-A, C46-A, C46-C, C47-A, C47-B; Murera masonry_external_walling; Ghazi E3-B/C/D, E8-A/C; Lamu E3-A, E7-A/C |
| Substructure floor-area / layer-stack authority | **3** | Murera substructure_surface_bed, substructure_bed_dpm, substructure_a142_mesh |
| Explicit stacked opening schedule-row binding | **2** | KSTVET C41-B, C41-C |
| DPC complete-wall-run authority | **2** | Murera damp_proof_course; Lamu LMU-E3-B |
| Structural pier identity/count | **1** | Murera masonry_piers |
| Roof-plane geometry + scale | **1** | Lamu LMU-E4-A |
| Ceiling-area + finish authority | **1** | Ghazi GZ-E8-H |

## Mathematics for >90%

With a fixed denominator of 60:

- 54/60 = 90.00% — **not over 90**
- **55/60 = 91.67%** — first score over 90
- Current = 36/60
- Therefore PlanReader needs **19 additional accepted rows with no regressions**.

## Quickest evidence-preserving route to >90%

The shortest row-leverage route is three capability groups:

### 1. Complete the wall → opening → net wall → finish-face chain
**Potential leverage: 14 rows.**

This is the dominant blocker and should remain the primary coding lane. Current work that may contribute must be reviewed/ported rather than blindly merged:

- #935 — source-owned component completeness (active current work)
- #858 — live source-owned physical net-wall publication (stale base; capability may be reusable)
- #623 — authenticated raster visibility for wall topology (very stale base; Ghazi prerequisite concepts may be reusable)

Required end state:

`SOURCE WALL PRIMITIVES → PHYSICAL WALL IDENTITY → WALL ROLE → GROSS GEOMETRY → HOST-BOUND OPENING VOID → NET WALL → WALL FACE/SIDE → FINISH INSTANCE → PUBLISHABLE QUANTITY`

This cluster is where the majority of KSTVET, Ghazi and Lamu misses converge.

### 2. Port/fix stacked opening schedule-row binding
**Potential leverage: 2 rows.**

KSTVET `BOQ-C41-B` and `BOQ-C41-C` already have a focused generic candidate in stale PR #602. Do **not** merge the stale branch. Re-diagnose on current main and port only the still-needed generic logical-row continuation capability.

Expected score if both recover and no regressions: **38/60 = 63.33%** before other gains.

### 3. Complete source-owned substructure area/layer-stack authority
**Potential leverage: 3 rows.**

Murera's surface bed, DPM and A142 mesh share one physical floor-area basis but must retain independent material/layer authority. Existing shadow work in #893 is relevant but stale and shadow-only.

Required chain:

`FIGURED DIMENSIONS / WITNESS EVIDENCE → AUTHENTICATED FLOOR FOOTPRINT → SUBSTRUCTURE BED AREA → DPM SCOPE → A142 SCOPE`

If all three capability groups recover their theoretical rows:

- current 36
- wall/finish +14
- schedule +2
- substructure +3
- **55/60 = 91.67%**

That is the minimum theoretical route over 90%.

## Buffer route recommended for regression safety

Do not plan to stop at exactly 55. Target **56–57 accepted rows** before declaring the >90 milestone robust.

Best contingency rows after the three primary clusters:

1. **Ghazi GZ-E8-H ceiling lining** — existing stale PR #694 contains a source-owned ceiling publication concept that can be reassessed/ported.
2. **Lamu LMU-E3-B DPC** — current main produces 64m vs 75m; it is now within 20%, so this is a bounded geometry-completeness problem rather than a total extraction miss.
3. **Murera masonry_piers** — isolated structural identity/count capability.
4. **Lamu LMU-E4-A roof** — requires source-owned roof plane plus trustworthy scale; likely higher risk than the first three contingencies.

## Immediate priority order

1. **#935 / physical wall identity + component completeness**, because it is current and feeds the 14-row cluster.
2. **Port #602 concept to current main**, because two rows may be comparatively cheap.
3. **Current-main diagnosis/port of #893 floor-dimension authority**, then wire the 3-row Murera substructure stack.
4. **Net wall + finish publication on top of proven wall identity**, using current architecture rather than stale branch history.
5. Use GZ-E8-H and LMU-E3-B as buffer targets to get beyond 55 safely.

## Guardrails

For every gain:

- no benchmark/project-specific production constants;
- no gold/expected/scorer/tolerance/denominator edits;
- no definition → physical-instance promotion without evidence;
- no proximity-only wall equivalence;
- no opening deduction without explicit host ownership;
- no finish propagation without physical wall-face/side ownership;
- ambiguity must remain fail-closed;
- rerun the canonical five after each meaningful capability merge and compare accepted rows plus regressions.

## Source of truth

This report is derived from the fresh SHA-pinned canonical-five run on `819b6aca4f671b34c37d97f63d9d31a678af247b` captured in test-only PR #945. PR #945 is diagnostic only and must not be merged.
