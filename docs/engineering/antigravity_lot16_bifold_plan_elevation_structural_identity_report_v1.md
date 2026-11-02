# Architectural Report: Lot 16 2142 BIFOLD Plan-to-Elevation Whole-Aperture Identity & Dimension Ownership Shadow Authority

**Document ID**: `docs/engineering/antigravity_lot16_bifold_plan_elevation_structural_identity_report_v1.md`  
**Author**: AntiGravity (Autonomous Structural Opening Accuracy Recovery)  
**Date**: 2026-10-28 AEST  
**Status**: DRAFT ARCHITECTURE & STRUCTURAL EVIDENCE (SHADOW MODE)

---

## 1. Observed Repository Behavior

### 1.1 Source Documents and Plan-to-Elevation Evidence
- Source PDF: `1. Construction Plans - Lot 16 Power (REV E).pdf`  
  - SHA-256: `10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844` (13 pages, 7,141,615 bytes).
- **Sheet 3 (Floor Plan)**:
  - A physical opening interruption in the external wall band exists at `[969.36, 295.20, 972.72, 413.28]` pt along $x \approx 969.36$, with span $\Delta y = 118.08$ pt ($\approx 4165.6$ mm at 1:100 scale).
  - The live opening discovery authority classifies this feature as `raster_framed_wall_band_interruption` (`physical_opening_existence_00d50eb9ef77840451522efdc25f2df5`).
  - Native text tokens `2142` (bbox `[958.97, 357.82, 964.65, 366.84]`) and `BIFOLD` (bbox `[958.97, 341.78, 964.65, 356.74]`) are present, proven visible, and validated ToUnicode.
  - Adjacent dimension chains on Sheet 3 at $x \in [1045, 1062]$ specify competing frame and divider intervals:
    - Outer string: $1080$ mm, $90$ mm stud, $1030$ mm, $70$ mm divider, $2210$ mm frame ($1030 + 70 + 2210 = 3310$ mm).
    - Inner sub-division string: $1050$ mm, $70$ mm divider, $1090$ mm ($1050 + 70 + 1090 = 2210$ mm).
    - Macro wall span: $4945$ mm bounded by $90$ mm wall studs.
- **Sheets 4 and 5 (Elevations 1 through 4)**:
  - Total native text words across Sheets 4 and 5:
    - Sheet 4: `ELEVATION 1` and `ELEVATION 2`. Opening tags present: `1218 SGW`, `0630 FG`, `1218 SGW`, `0906 SGW obs`, `0621 SGW`. Notes: `CUSTOM WINDOWS TO FRONT. MEASURE ON SITE.`
    - Sheet 5: `ELEVATION 3` and `ELEVATION 4`. Opening tags present: `0615 SGW`, `1215 SGW obs`, `2127 STACKER`.
    - **Zero** native occurrences of token `2142` or `BIFOLD` exist anywhere on Sheets 4 or 5.
    - Lintel datum `JL 70660` and slab datum `FSL 68560` are drawn ($70660 - 68560 = 2100$ mm nominal head height), but neither datum carries a direct reference, witness line, or callout pointing to the bifold opening.
- **Sheet 7 (Notes)**:
  - Bradnams Windows and Doors manufacturer reference exists, but no schedules or window/door tables are provided in this drawing set.
  - NatHERS reference points to an external certificate not included in this document set.

### 1.2 Downstream Pipeline & Existing Blockers
- In `docs/engineering/gptmax_owned_bifold_quantity_shadow_20261015.md` and `pb_bifold_filling_kind_shadow.py`:
  - An exploratory shadow option `bifold_descriptor_shadow=True` allowed `2142 BIFOLD` to nominate candidate door area $8.82\text{ m}^2$ ($2.100 \times 4.200$).
  - However, commercial publication was strictly withheld:
    - `first_remaining_gate = "opening_filling_kind_unproven"`
    - `axis_order_resolved = False`
    - `dimension_ownership_unproven`
    - `structural_host_unavailable` / `whole_wall_frame_unavailable`
  - Commercial publication requires authenticated structural proof of aperture boundary, elevation cross-view identity, divider structural role, and dimension ownership.

---

## 2. Inferred Engineering Causes

### 2.1 Missing Elevation Cross-View Identifier
In multi-view architectural drawings, tying a plan opening to an elevation opening requires an authentic cross-view receipt (e.g. identical opening mark, elevation callout, or coordinated coordinate projection). Because Sheets 4 and 5 contain no `2142` or `BIFOLD` callout:
- Relying on visual appearance (e.g. noticing multi-panel folded leaves in elevation drawings) violates the core observation authority contract.
- The cross-view elevation role must fail closed with `EvidenceResolutionStatus.ABSTAINED` and `first_remaining_gate = "cross_view_elevation_role_unproven"`.

### 2.2 Competing Frame Assemblies and 70 mm Divider Ambiguity
The plan geometry contains conflicting evidence regarding frame unity:
1. The physical wall interruption spans $118.08$ pt ($\approx 4165.6$ mm), which aligns with the nominal $4200$ mm tag in `2142`.
2. However, the dimension strings directly adjacent to this opening document multiple competing assemblies:
   - A $70$ mm divider separates an assembly into $1050$ mm and $1090$ mm spans ($1050 + 70 + 1090 = 2210$ mm).
   - An adjacent dimension string places another $70$ mm divider between a $1030$ mm span and a $2210$ mm span ($1030 + 70 + 2210 = 3310$ mm).
3. The structural role of the $70$ mm divider cannot be determined from plan raster alone:
   - Is it an internal glazing mullion (subdividing a single master bifold frame)?
   - Is it a structural timber stud post separating two independent adjacent frame assemblies?
4. This competing geometric evidence constitutes a structural ambiguity that must be explicitly resolved as `EvidenceResolutionStatus.CONFLICT` with `first_remaining_gate = "competing_frame_assemblies_unresolved"` rather than arbitrarily selecting the $4200$ mm whole span.

### 2.3 Unproven Dimension Ownership and Axis Order
The compact text `2142` specifies figures `21` and `42`:
- In standard Australian practice, these imply nominal $2100$ mm height and $4200$ mm width.
- However, without an elevation tag linking the opening to the $2100$ mm JL datum ($70660 - 68560$), or a published window/door schedule:
  - Axis order is not authenticated (`axis_order_resolved = False`).
  - Metric void placement cannot be published (`metric_void_placement = False`).
  - Dimension ownership fails closed with `first_remaining_gate = "dimension_ownership_unproven"`.

### 2.4 Filling Kind Ambiguity (`door` vs `window`)
BIFOLD describes an operation mechanism (folding panels), not an architectural object type. Without a schedule, legend definition, or cross-view door sill detail:
- Bifold could be a bifold patio door or a high-sill servery bifold window.
- Granting `door` semantics prematurely violates source fidelity.

---

## 3. Proposed Repair & Structural Authority Contract

### 3.1 Architectural Scope & Invariant Guarantees
We implement `pb_bifold_plan_elevation_structural_authority.py`:
- **Sealed Production & Authority**: `BifoldPlanElevationStructuralProducer` and `BifoldPlanElevationStructuralAuthority`.
- **Divider Structural Role Classification**:
  - `DividerStructuralRole.UNKNOWN`: Unexamined divider.
  - `DividerStructuralRole.INTERNAL_MULLION_DIVIDER`: Proven non-structural frame divider.
  - `DividerStructuralRole.STRUCTURAL_PIER_DIVIDER`: Proven structural stud/pier between separate openings.
  - `DividerStructuralRole.AMBIGUOUS_COMPETING_FRAME_SEPARATOR`: Proven competing frame evidence ($70$ mm divider present between conflicting dimension spans).
- **Plan-to-Elevation Cross-View Resolution**:
  - Verifies presence of explicit matching callouts on elevation sheets.
  - In Lot 16, marks `elevation_identity_proven = False`, setting `first_remaining_gate = "cross_view_elevation_role_unproven"`.
- **Competing Frame Assembly Detection**:
  - Captures candidate spans: nominal callout ($4200$ mm), sub-assembly ($3310$ mm), minor assembly ($2210$ mm).
  - Marks `competing_frame_assemblies_detected = True`, setting `status = EvidenceResolutionStatus.CONFLICT` when multiple incompatible frame spans co-exist.
- **Fail-Closed Dimension Ownership**:
  - Asserts `axis_order_resolved = False` and `opening_kind_granted = False`.
  - Sets `first_remaining_gate = "dimension_ownership_unproven"` or `"opening_filling_kind_unproven"`.
- **Shadow Mode Strictness**:
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`

### 3.2 Verification and Test Strategy
- Synthetic positive: Fully matched plan callout + elevation tag + unambiguous single frame + verified schedule.
- Synthetic negative: Missing elevation tag (Lot 16 case).
- Competing frame negative: $70$ mm divider with competing $2210$ mm / $3310$ mm / $4200$ mm spans.
- Ambiguous filling kind negative: `BIFOLD` without schedule definition.
- Metamorphic invariance: Rotation, translation, and scale transformations.
- Input ordering invariance: Reordering elevation and plan evidence records.
- Deterministic regression: Lot 16 Power Page 3 & Pages 4/5 actual PDF evidence.

---

## 4. Benchmark Observations That Must Not Influence Implementation

- In `benchmarks/frozen_holdout/full_plan_v2/projects/au_qld_lot16_power/reference_takeoff.json`, nine internal 870 mm openings are scored; external openings remain unpromoted or held out.
- The candidate area $8.82\text{ m}^2$ ($2.1\text{ m} \times 4.2\text{ m}$) from previous shadow exploratory runs is NOT benchmark ground truth and MUST NOT be hardcoded, assumed, or targeted.
- The 20,000 primitive safety cap, 2.5 pt coordinate snapping rule, and zero mutation of frozen benchmark files remain strictly preserved.
