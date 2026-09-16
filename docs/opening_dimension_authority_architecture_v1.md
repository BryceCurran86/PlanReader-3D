# Opening Dimension Authority — Architecture (v1)

**Status:** architecture + test-first only. No production implementation authorized.
**Base:** merged G17 `main` `62a161519e617cdf9ce23069820dbf7c68aaf521`
**Lane:** Opening dimensions (width / height). Opening identity owned by PR #331 — out of scope.

## 1. Decision

`existence ≠ identity ≠ width ≠ height ≠ type ≠ host`.

Width and height must be independently proveable. G17 existence alone must not invent dimensions. Schedule dimensions alone must not invent physical openings or assign instance geometry without separately proven type/instance binding (identity lane).

Until a reviewed Opening Dimension Authority exists, `PhysicalOpeningAuthority.capabilities()["opening_dimensions"]` remains **False**.

## 2. OBSERVED (repository behavior)

### 2.1 Capability lock

`pb_physical_opening_authority.PhysicalOpeningAuthority.capabilities()`:

- `physical_opening_existence=True` (G17 merged)
- `physical_opening_identity=False` (PR #331)
- `opening_dimensions=False`
- host / void / net-wall / universe completeness = False

### 2.2 Reusable linear-measurement seams (do not fork)

| Seam | Module / function |
|---|---|
| Page scale | `pb_page_scale_calibration_authority.resolve_page_scale_calibration` |
| Viewport scale | `pb_viewport_scale_binding.bind_viewport_scale` |
| Linear measurement input | `pb_measurement_input_authority.resolve_linear_measurement_input` |
| Figured measurement authority | `pb_figured_dimension_authority.resolve_measurement_authority` |
| Figured extract + witness bind | `pb_figured_dimension_evidence.extract_dimension_evidence_bundle`, `bind_observation_to_vector_geometry` |
| Contracts | `EvidenceResolutionStatus`, `EvidenceAtom`, `QuantityEvidence`, `stable_contract_id` |

### 2.3 Opening-adjacent dimension paths (not firm opening-dimension authority)

| Path | Role |
|---|---|
| `pb_hosted_opening_geometry` `span_pt` / `width_m` | Geometric gap; height always absent; firm unwired |
| `pb_opening_callout_dimension_binder` | Unique door WxH pair → tag; atomic W+H |
| `pb_opening_schedule_v171.parse_dimension` | Schedule cell WxH parsing |
| `pb_opening_provenance_graph` | Shadow; height from schedule/callout after identity edges |
| `pb_opening_deduction_pipeline` / F.9 | Commercial; requires **both** W and H |
| `pb_elevation_evidence_v172` | Elevation rects / labels; basis often unknown |
| `pb_drawing_ocr_evidence_layer` | OCR vs native reconciliation |
| `pb_dimension_chain_evidence_extractor` | Dimension chains |
| `pb_opening_deduction_readiness` | Dev-only; separate width/height atoms; cannot FIRM |

### 2.4 Unsafe defaults / fallbacks (must not become Opening Dimension Authority)

| Location | Behavior |
|---|---|
| `pb_opening_deduction_v175.parse_opening_dimensions` | Empty/unparsed → `(2040.0, 820.0)` mm |
| `pb_planreader_3d_app.py` | UI defaults ~0.9 m × 2.1 m |
| Plan detector confidence bands | e.g. 0.6–1.2 m door leaf boosts confidence (plausibility ≠ authority) |
| Nearest tag/label helpers | `_find_tag_near`, elevation `_extract_label_near_rect` — identity proximity, not dimension authority |
| Atomic W+H bundles | Callout binder / OpeningEvidence replace rules couple axes |

### 2.5 Issue #330 (CMap / ToUnicode)

No in-repo reference to GitHub issue #330 / CMap / ToUnicode found on this base. Attack 14 remains a required fail-closed case for corrupt native text → must not silently FIRM.

## 3. INFERENCE

1. Opening width/height should mirror wall length/height: owned figured (or authenticated elevation) evidence + firm scale + independent axis atoms — not gap geometry alone.
2. PR #331 physical-instance identity is a **prerequisite consumer input** for assigning plan/elevation/schedule dimensions to an instance; this lane must not invent identity.
3. Source-space jamb span ≠ physical millimetre width without separately authoritative scale.
4. Schedule `D-01 = 900×2100` is type/table evidence, not instance dimension authority without proven binding.

## 4. PROPOSED (future production — not in this PR)

Shadow-first module (name illustrative): `pb_opening_dimension_authority.py`

- Inputs: producer-owned G17 existence + (#331) identity selectors + figured/elevation/schedule evidence atoms under document/revision/page/viewport ownership.
- Outputs: independent `OpeningWidthResult` / `OpeningHeightResult` (or equivalent) using existing vocabulary; abstain/conflict rather than nearest/first/smallest.
- Reuses scale + figured + measurement-input seams; never promotes `parse_opening_dimensions` defaults or hosted gap width to FIRM.
- Does not unlock host binding, void, deductions, commercial, or JobHub.

**Stop for review.** No production implementation in this PR.

## 5. Benchmark observations that must not drive design

Development score **31/61 = 50.82%**, gold, mappings, tolerances, project names, “typical door” sizes, detector confidence bands.

## 6. Explicit non-goals (this PR)

- Opening identity production (#331)
- Enabling `opening_dimensions` capability
- Host binding / voids / deductions / FIRM commercial / JobHub
- Fixing legacy `2040×820` defaults in production (document only)
- Same-PR gold/scorer changes
