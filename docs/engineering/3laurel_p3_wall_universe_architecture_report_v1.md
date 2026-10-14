# 3Laurel page 3: why the canonical wall universe is empty — architecture report v1

Status: **report only, for review. No code, test, workflow or benchmark file is changed.**
Author lane: Claude (integration / CI / source-safety). Related owners: GPT1 (#2017), GPT3 (#2004). Tracking: #2427.
Main inspected: `6ed1877f`. Source: original 3Laurel plan set, SHA-256 `014e9f68b377bef4fb556de61b83a94388792dfa4bfb8ea981644f9c323e9e2e` (matches the frozen manifest), page 3 (index 2).

## 0. Contract compliance (AGENTS.md "before proposing")

- **Files read:** `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md` (§3, §8, §12, §13), `pb_physical_wall_candidate_authority.py`, `pb_live_canonical_wall_composition.py`, `pb_live_physical_net_wall_integration.py`, `pb_viewport_segmentation.py`, `tools/run_source_closed_project_handoff.py`, GPT1's 3Laurel workflows and CI artifacts (runs 38337309939 / 38337309984).
- **Functions traced:** `segment_page_viewports` → `_scope_boundary_reason_from_viewports` → `_assemble_scope_result` → `compose_live_canonical_walls` → `collect_live_physical_net_wall_claim` → handoff `canonical_counts`.
- **Authority boundaries crossed:** none changed. Source visibility → wall candidate scope → canonical wall composition → host binding → gross/net wall → publication. This report proposes nothing that raises authority.
- **Untouched:** every production module, the 20,000 primitive cap, source-authentication rules, W10 (`takeoff_eligible=False`, `deduction_authority=False`), all benchmark-defining files.

## 1. Observed repository behavior

Observations come from (a) `tools/diag_gptmax_source_authority_stages.py --pdf <3Laurel> --page-id 3` on main (67 s, Windows); (b) a read-only code tracer re-deriving the chain from source with line citations; (c) GPT1's CI artifacts. Provenance is stated per item.

1. **The page is a native vector floor plan, not a raster scan.** Wall candidates carry CAD layer metadata (`Enclosure_WallExternal`, `Enclosure_WallInternal`, `Interior_Joinery`, `Finish_Floor`, …). Raster augmentation is secondary. (a)
2. **The wall scope is incomplete.** `source_owned_wall_scopes[0]`: `scope_kind=page`, `status=corroborated`, `scope_complete=False`, 1,559 wall candidates, 114 boundary-tainted with `physical_wall_candidate_scope_bounds_unresolved`; equivalence: 204 representatives, 1,354 ambiguous. Lot16 p3 on the same tool: `scope_complete=True`, 2,094 records, 0 tainted. (a)
3. **Why incomplete.** `segment_page_viewports` returns exactly one viewport: `derived`, `floor_plan`, `title_partition`, no title text, bbox (21.48, 22.73, 1166.68, 769.16). `_scope_boundary_reason_from_viewports` (`pb_physical_wall_candidate_authority.py` ~L1523–1576) taints any wall with a free end (`JunctionType.ENDPOINT`, `_dangling_ends` L1281) when spatial viewports exist but no **RESOLVED** viewport contains the end. Exactly 114 of 1,559 walls have such an end (median length 7 pt); 110 lie fully inside the DERIVED box; none is on the page edge. (a)(b)
4. **Internal inconsistency.** The same viewport passes `is_authoritative_derived_viewport` (single floor-plan sheet frame, validated) at ~L440–465, but the boundary rule at ~L1552–1557 counts only `RESOLVED` viewports as containing. (b)
5. **Lot16 passes the same rule only because it has no spatial viewport structure** (its p3 viewport is a `legend`, `unsupported`, no bbox, filtered out at ~L1544–1550), not because of stronger boundary proof. (b)
6. **Incomplete scope does not by itself zero the page on main.** Since #1312, `compose_live_canonical_walls` (`pb_live_canonical_wall_composition.py` ~L277–334) keeps the 1,445 boundary-clean candidates as candidate walls (`candidate_boundary_clean_scope_incomplete`). (b)
7. **The actual `walls=0` trigger is a single canonical-ID collision.** `wall_21e89af0…` and `wall_6f7d1277…` are both boundary-clean, share `candidate_identity_id wall2_ec726c2a…`, are built from the same source primitives (`d1902i1`, `d1932i2`; path ≈ (947.27, 338.70)→(949.83, 336.15), ~3.6 pt) and differ only in edge ids (`split_4048` / `split_4078`); they are in one `SAME_PHYSICAL_WALL` class. The clean-candidate branch uses `candidate_identity_id` as canonical id; the collision guard (~L467–477) then returns `CONFLICT`, `walls=()`, empty mapping — all 1,559 become unresolved. (a)(b)
8. **The cause is invisible in the handoff summary.** `canonical_wall_reason_codes` (carrying `live_canonical_wall_frame_conflict`) is a separate claim field that `run_source_closed_project_handoff.py` does not write; `claim_reason_codes` shows only the downstream codes. No test covers a duplicate id on this path. (b)
9. **Same DERIVED viewport also removes physical scale.** `PhysicalScaleAuthority` returns `physical_scale_viewport_unavailable` for a viewport-id request on a non-RESOLVED viewport, so wall scope gets no `points_per_mm`. (b)
10. **Downstream codes are propagation.** `complete_authenticated_host_wall_universe_required`, `no_authenticated_host_wall_band`, `host_*`, `live_gross_wall_geometry_*`, `live_whole_wall_role_*`, `live_physical_net_wall_integration_unavailable` follow from an incomplete or empty wall universe. 65 of 139 openings fail the local boundary-clean host fallback; the fallback exists only for incomplete scopes. (b)
11. **A second, independent root family** blocks publication regardless of walls: `semantic_opening_*` and `opening_universe_completeness_record_unavailable`, from the semantic enumeration and universe-completeness authorities. Fixing walls alone cannot make openings publishable. (b)
12. **Runtime is not the blocker** for one page in CI (~100 s job time; `no_sealable_quantities`, `claim_status=abstained`). (c)

## 2. Open discrepancies (not resolved; do not build on them)

- A `collect_live_physical_net_wall_claim(pages=[3], topology_pages=[3])` probe in a scratch checkout took ~6–15 min and returned a **complete-scope** wall composition (104 equivalence-resolved + 1,063 unresolved walls) with **11** canonical-id collisions (2 members each) and again `CONFLICT`, `walls=0`. Its wall candidate ids do not match the stage report's, so it used a different source snapshot. Both paths end in the same collision-guard zeroing, but via different scope states. Which one CI ran is **unverified**.
- A local Windows run of the full handoff call hung for >55 min after the OCR step while CI finished in ~100 s. Environment divergence is **undiagnosed**.
- Whether the 114 free-ended walls are real terminations or stubs from jambs, swings, symbols or hatch ticks is **unknown** (needs layer/graphic-state of their primitives and a render).

## 3. Inference

- Earliest root for the wall chain: one DERIVED (not RESOLVED) floor-plan viewport + free wall ends ⇒ `scope_complete=False` ⇒ no complete wall universe ⇒ host/gross/net chains abstain.
- Earliest root for `walls=0` specifically: the all-or-nothing collision guard, triggered by a duplicate-geometry pair that the equivalence authority already classifies as the same physical wall.
- If the scope were complete, the SAME pair would be absorbed by the equivalence-representative loop; the result would be candidate walls (never CORROBORATED, ~1,354 still ambiguous), not publishable walls. Walls would still be necessary but not sufficient.
- `scripts/wall_scope_funnel_report.py` is stale: it asserts an incomplete scope yields no canonical walls, ignoring #1312, and cannot see the collision zeroing.

## 4. Proposed change (options; nothing is started)

**Option A — make id collision local, not global (smallest).** When two candidates share a canonical id, do not return `CONFLICT` for the whole page. Retain both as candidates under lineage-disambiguated ids (for example, canonical id + sorted edge/primitive lineage), keep the colliding group `unresolved`, and keep a distinct typed reason. Never delete, merge by first/nearest, or promote. Related: playbook §13 priority 2, #2233. *Expected effect alone:* candidate walls reappear and downstream diagnostics become informative; **no quantity changes** (candidates stay unresolved).

**Option B — align the boundary rule with viewport authority.** Treat an authoritative-derived single-floor-plan-frame viewport as containing in `_scope_boundary_reason_from_viewports`, and likewise for the scale lookup. This is an **authority-promotion decision** (completeness and scale), needs its own review, and may conflict with `test_unresolved_viewport_bounds_do_not_claim_completeness`. Risk: free ends that are not real terminations would no longer taint the scope. **Superseded by Addendum A (§9): measured to add one false host; do not ship alone.**

**Option C — second root family (semantic opening enumeration / universe completeness).** Out of scope here; needed before openings can publish.

**Recommendation:** Option A first, shadow-only, with a diagnostic that exposes `canonical_wall_reason_codes` in the handoff summary (read-only). Option B only after the owners decide the viewport-authority question. State plainly: neither A nor B alone yields a sealed 3Laurel quantity.

## 5. Benchmark observations that must not influence implementation

Frozen 3Laurel universe sizes (41 openings, floor/ceiling surface counts), the project's 63-point share of the 120-point denominator, and any expected quantity or score. They were used only to triage, and nothing here derives a threshold from them. Layer names are source metadata, not wall authority; none may be used as a positive existence atom without a separate authority review.

## 6. Required tests before any implementation (AGENTS.md)

Synthetic: duplicate-geometry pair inside an incomplete scope (positive), look-alike negatives (parallel walls, different primitives), ambiguous/conflicting identities, translation/rotation/scale metamorphic, input-order and segment-splitting invariance, unrelated-content and viewport-expansion invariance, deterministic replay and stable ids, no-mutation, and proof that live predictions and commercial quantities are unchanged in shadow mode. A real-PDF replay on the original 3Laurel p3 and a no-regression replay on Lot16 p3 (2,094 W4 records, 8/27 candidate, 20,000 cap).

## 7. Collision map (open PRs touching the same files)

#2638 and #1953, #1864, #1844, #1481 (`pb_physical_wall_candidate_authority.py`); #1953, #1868, #1339 (`pb_opening_host_binding_authority.py`); #2639 (`pb_wall_room_topology_typed_negative_evidence.py`). #1339 (opening-local host scope) overlaps the host-fallback logic in finding 10. None touches `pb_live_canonical_wall_composition.py`. Coordinate with the owners before editing the shared file.

## 8. Not covered

Three planned tracers (raster source path, opening dependency, prior art) had not returned when this report was written; items 9–11 and §7 rest on the first tracer plus direct inspection. Only page 3 of 3Laurel and only main `6ed1877f` were examined. Q5446 and Maryborough are not covered.

Next step after review: owners choose between Options A and B; then a shadow-mode PR with the §6 tests. No change before that.


## 9. Addendum A (v2, 2026-10-14): measured gate trace, and why a boundary alignment alone must not ship

Status: still **report only, no production change**. Option A (#2680) is independent of everything below. Source: original 3Laurel p3 (SHA `014e9f68…`, verified against the frozen manifest), through the stage-tool path that reproduces the CI numbers (1,559 W4 / 114 tainted / 1,445 clean, run 38499859114). All counterfactuals swap module attributes inside a running process; nothing is written to a checkout. Reproduction scripts and expected output: `3laurel_p3_wall_authority_gate_trace/`.

### 9.1 What the 114 tainted candidates are (observed)

- 130 free ends on 114 candidates. 110 candidates lie fully inside the DERIVED plan frame; 4 sit in the title-block strip below it (y 798–819), are 10–33 pt long and are built from non-native, raster-derived primitives with no layer (logo or text strokes).
- The free ends are mostly **near-misses, not dangling walls**: the nearest other-wall centerline is a median 2.06 pt away (37 ends within 1 pt, 78 within 3 pt, all 114 within 6 pt). They are wall-face contacts typed `ENDPOINT`, or symbol and dimension graphics.
- A render of the page with the free ends marked shows them on dimension strings and ticks, the compass symbol, the scale bar, title-block text, door and fixture details, and a minority of real wall ends at openings. (`3laurel_p3_wall_authority_gate_trace/evidence/page_free_ends_overview.png`: red = free ends of tainted candidates, blue = the DERIVED frame.)
- Source layer class of **all 1,559** candidates (layers read from the PDF's optional-content names; descriptive only):

| class | candidates | tainted | ambiguous in equivalence | equivalence representatives |
|---|---|---|---|---|
| non-wall layers (floor finish 402, joinery 240, plumbing fixtures 149, elevation markers 72, roof, electrical, slab, ceiling, stormwater …) | 1,004 | 84 | 867 | 137 |
| wall-named layers only | 369 | 22 | 303 | 65 |
| mixed wall + other layers | 115 | 1 | 115 | 0 |
| no layer / raster-derived | 71 | 7 | 69 | 2 |

### 9.2 Two places honor RESOLVED only (observed)

- Boundary rule `_scope_boundary_reason_from_viewports` (`pb_physical_wall_candidate_authority.py` ~L1552) counts only `RESOLVED` viewports as containing a free end, while `_authenticated_viewports_from_rows` (~L440–465) already defines F.07-**eligible** viewports as RESOLVED or authoritative-derived with a non-overlapping sibling set, and viewport scopes use it. The p3 viewport (`derived`, `title_partition`, `single_floor_plan_sheet_frame`, validated) is eligible.
- `PhysicalScaleProducer._scope_bbox` (`pb_physical_scale_authority.py` L851–883): a page-wide request returns `physical_scale_viewport_required` whenever any usable viewport exists, and a viewport-id request accepts only `RESOLVED`. The docstring of `_producer_owned_points_per_mm` says DERIVED-only viewports intentionally get no scale and that overlapping candidates then stay fail-closed.

### 9.3 Counterfactuals through host binding (measured)

| mode | tainted walls | authenticated hosts | scope complete | pair classes ambiguous / distinct / same |
|---|---|---|---|---|
| baseline (production) | 114 | 1 | no | 36,529 / 554 / 53 |
| eligible viewports honored for free ends | 4 | **2** | no | unchanged |
| same, only for wall-named-layer candidates | 89 | 1 | no | unchanged |
| scale accepts the single eligible viewport | 114 | 1 | no | unchanged |
| boundary and scale | 4 | 2 | no | unchanged |
| upper bound: nothing tainted (not a candidate rule) | 0 | n/a | yes | 204 representatives, 1,354 still ambiguous |

### 9.4 The extra host is a false positive (observed, rendered)

- The one additional authenticated host is opening `…733d836d…` (`jamb_bounded_two_face_interruption`, x 899–909, y ≈ 509). Its four host-wall candidates are 11 pt lines, all on layer `Service_Gas.Bottled`: the tops of **two gas-cylinder symbols** hanging below the garage wall. (`evidence/false_host_gas_cylinders.png`; the red lines are the four host-wall candidates.) The 114-candidate taint was accidentally preventing this false host.
- The host production already binds (`…63281952…`, four members on `Enclosure_WallExternal`, a sliding door between the Alfresco and Living areas) is a genuine wall opening. That judgement is from the render, not an authority. (`evidence/genuine_host_sliding_door.png`.)
- Restricting the relaxation to wall-named layers retains 25 more candidates and adds **no** host.

### 9.5 Scale is a second, independent blocker (observed)

- The sheet carries a real scale bar: native numerals `0 … 10m` spaced about 28.4 pt per metre (1 m at 1:100) over 10 filled blocks. The scale producer's bar detector does not recognize this block style: `scale_probe.py` returns `physical_scale_bar_unavailable` **even when the viewport bbox is forced**.
- Without scale, parallel longitudinally-overlapping pairs stay in contest regardless of separation by design (`pb_physical_wall_identity.py` L328–333). That is why 36,529 of 37,136 pair classifications are ambiguous.

### 9.6 The exact first impossible authority gate

**No authority separates structural wall geometry from finish, joinery, fixture and annotation geometry.** Candidates are retained from every layer by design. Every relaxation behind it (boundary completeness, scale, equivalence) raises *ownership of non-wall candidates*: the false host above, and two thirds of the upper-bound identities (137 of 204 are non-wall-layer candidates). Today layer tokens are descriptive only by explicit design (`pb_physical_wall_source_metadata_shadow.py`: "not support or opposition"), so no safe local correction exists below that gate. Ordered dependencies:

1. **Structural source evidence** (typed support and opposition atoms from source graphic state: layer token, stroke/width rank, dash, fill, plus geometry roles). Needs an authority review before any consumer exists.
2. **Producer-owned scale for the plan frame:** (a) the eligibility gate in `_scope_bbox`, and (b) block-style scale-bar detection with label-spacing corroboration.
3. **Scope completeness for the plan frame:** boundary rule aligned to F.07 eligibility, plus a rule for geometry wholly outside every physical viewport (the 4 title-block artifacts) that withholds it without poisoning the plan.
4. Equivalence, host bands and opening-universe completeness (already separate blockers).

### 9.7 Recommendation (nothing started)

- Do **not** ship the boundary alignment alone (§4 Option B). The measured result is one more host, and it is wrong.
- Next work, shadow-first, one PR each, each needing authority review: (1) typed structural-evidence atoms computed from the existing shadow descriptors and consumed by diagnostics only; (2) block-style scale-bar detector in shadow; (3) only then aligned eligibility, with admission gated on (1). Required negative control for (1): the gas-cylinder symbol must never yield an authenticated host.
- No quantity, score or sealed output is affected by this report or by Option A.

### 9.8 Limits

One page, Windows, the stage-tool path (CI-matching). My Windows `collect_live_physical_net_wall_claim` path produced a different candidate set (§2); it is unresolved and not used here. Host genuineness is by visual inspection. The structural-class table uses the literal substring convention already in the repo and is descriptive, not a classifier.
