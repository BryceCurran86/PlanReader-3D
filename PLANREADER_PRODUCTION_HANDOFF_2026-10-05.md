# PlanReader production accuracy handoff — 2026-10-05

This note records the production work completed and source-validated by ChatGPT on the active Full Plan V2 accuracy lane so parallel agents do not repeat it.

## GPT-3 / GPT-4 lane completion status

The assigned production accuracy lanes are complete on current `main`.

- GPT-3 Tasks 17-23 merged in PR #1350 as `f064dd7ae4c6fab265839bca1fbc9147a77c4765`.
  - source-owned schedule/material semantics
  - finish/legend semantic authority
  - cross-view physical identity and internal-elevation wall-face mapping
  - structural definition-family expansion
  - fail-closed source roof measurement hardening
  - trade-authority guardrails
- GPT-4 Tasks 24-30 completed through:
  - PR #1364 `9b14639b8a2b41eafe9bc8454920e5e12bd2fd76` — stable finish-surface physical identity
  - PR #1361 `1abd63d1e215b6347f7c67dbb529564eb8899e87` — Room identity hardening, separate Door/Window filling identities, live customer-publication reconciliation and shadow isolation
  - PR #1374 `78be1061379519cac4dec9fa60e8441d19b6e3fd` — Slab and Floor physical identities, Roof physical identity + source-owned quantity linkage, generic distinct-source duplicate suppression, and final Tasks 24-30 integration
- PR #1372 `1a77ae6512b56a8d9dc16dd88d9a6b97ea1fdb88` is merged and removed the prior figured-dimension blocker while preserving F23 orthogonal-depth symmetry.
- Final #1374 integrated validation passed:
  - full CI
  - Performance Fastpath CI
  - Docker Runtime Smoke
  - Item19B Wall Equivalence Grid Shadow

Do not reopen Tasks 17-30 unless a new production regression proves a specific defect. Remaining accuracy work is new downstream work: explicit room-area evidence, customer quantity publication, raster-plan recovery and exact Full Plan V2 reconciliation.

## Active benchmark scope

- `benchmarks/frozen_holdout/full_plan_v2`
- `au_qld_maryborough_service_station` — denominator 24
- `au_qld_lot16_power` — denominator 27
- Do not modify benchmark truth, expected quantities, tolerances, denominator eligibility, manifests or scoring.
- Retired canonical-five results are not the current accuracy metric.

## Last independently verified V2 score

Verified on production SHA `8e4bd2dccbaf0061163cfa2998f89cb2f6561621`:

- Maryborough: 0 / 24
- Lot16: 1 / 27
- Combined: 1 / 51 = 1.960784%
- Unsupported extras: 0
- Lineage conflicts: 0
- Lot16 recovered item: source-closed 2127 STACKER opening area = 5.67 m2

This score predates the room/dimension fixes listed below. Do not report 1.96% as the latest current-main score without rerunning V2.

## Production fixes completed / merged

### Room topology and identity

- #1352 `a7c8a1d4e3d5ee181bf5230c86dc27be2a69cce7`
  - recover boundary-clean room faces from incomplete authenticated viewport wall scopes
  - incomplete viewport stays globally incomplete
  - local face publication requires producer-owned boundary audit, clean bounding walls and no excluded structural primitive crossing the face
- #1353 `6aaf7d7a78515c2fd678841e6956fc526ca8ac8a`
  - separate physical room identity from revision/evidence lineage
- #1355 `f4e17704db89cba668fe83542a4e52ea23c2d1dd`
  - source-authenticated room-label authority
  - labels annotate proven geometry only; they cannot create/close/resize rooms
  - exact Maryborough A110 validation published: FOOD PREP, COLD ROOM, FREEZER, PWD, AIRLOCK, LAUNDRY, OFFICE
  - DRY STORE correctly remained unbound / fail-closed
- #1358 `70d2cbb036bfca6571e9a663d350d68bb619cd61`
  - attach authenticated labels to stable live rooms
  - bridge live rooms into existing CanonicalSpace
  - PDF-point geometry remains provenance only; no fake metric polygon, no takeoff authority

### Figured-dimension authority

- #1359 `b49b9e70608689d597da13861801dadce07225db`
  - allow OCR numeric text to bind to producer-authenticated native-vector visible witness geometry as well as raster geometry
  - normalize OCR boxes from display-rotated page coordinates into native PDF coordinates using the existing NativePageFrame contract
  - critical for Maryborough rotated sheets
- #1360 `d3fbbeb7152bf89c9fc7200521470b0e9aceb058`
  - authenticate native numeric dimension text via PdfTextIntegrity / independent raster corroboration
  - share existing figured-dimension witness calibration
  - exact Maryborough A110 validation authenticated 13 bound figured dimensions while correctly abstaining from inventing one page-wide orthogonal scale

## Exact Maryborough source findings

Frozen Maryborough PDF SHA-256:

`b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007`

### A110 / PDF page 7

Current room pipeline now reaches approximately:

- 1 authenticated floor-plan viewport
- 3,467 wall candidates
- 3,457 boundary-clean walls
- 687 source room faces
- 687 live room/floor candidates
- 7 authenticated labels listed above

A110 itself does **not** contain the Food Prep 4025 x 3297 figured dimensions.

### A140 / PDF page 11

The Food Prep figured dimensions are on A140 / PDF page 11.

After #1359 + #1360:

- page 11 production dimension run binds 28 source dimensions
- the stronger native figured-dimension authority already binds 3297 with witness geometry
- 4025 was initially rejected because two nearby vector line candidates were equally plausible

## Current work / next blocker

PR #1372 is merged and the previous dimension tie-break blocker is closed.

The next production accuracy blocker is downstream of the now-authenticated cross-view dimensions: generically bind a proven physical room / CanonicalSpace to two authenticated orthogonal figured dimensions, derive one source-owned explicit room-area EvidenceAtom, and feed the existing room-area quantity/customer publication path. Do not multiply arbitrary same-sheet dimensions merely because their values look plausible.

## Intended next authority chain

Now that #1372 is merged:

1. proven A110 physical room / stable CanonicalSpace identity
2. authenticated cross-view room label binding to A140
3. A140 figured dimensions 4025 mm x 3297 mm
4. derive producer-owned explicit room area evidence
5. existing `pb_source_room_area_bridge.py`
6. existing `pb_room_area_quantity.py`
7. Food Prep authoritative area = 13.270425 m2
8. canonical floor / customer quantity publication
9. rerun exact Full Plan V2 Maryborough + Lot16 and publish new score

The room-area bridge already supports authoritative explicit area EvidenceAtom without requiring a physical page scale. Do not invent a scale for A110.

## Safety / non-negotiable constraints

- No Maryborough/Lot16-specific production names, coordinates, page numbers or dimensions.
- No benchmark truth/scoring/tolerance changes.
- Do not force Dry Store closed; its correct current result is ABSTAIN.
- Do not globally map raw IP -> insulated_panel.
- Do not globally map sealed -> FLOOR_EPOXY.
- Do not set a global room minimum area of 5 m2.
- Preserve provenance, ABSTAIN, CONFLICT, duplicate suppression and fail-closed source authority.

## Coordination note

Before starting another fix, inspect current `main` and open PRs. Several other agents are actively modifying wall/opening/identity/surface lanes. Prefer clean replay on current main and do not duplicate an existing PR.
