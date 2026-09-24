# KSTVET Page 54 Native Graphic Scale-Bar Authority Audit

Base main: `a7980ed1e47f8320b1d37f1faa4ce0049b3140fc`

Targets only:

- `view_p54_7` — SECTION S-03
- `view_p54_9` — ROOF PLAN

This is an audit-only lane. No production scale rules, tolerance, segmentation
geometry, figured-span reconciliation, live binding, benchmark definition or
commercial publication are changed.

## PHASE 1 — EXISTING AUTHORITY TRACE

### Native observation root

`SourceVisibilityProducer` owns the current source revision and source bytes.
`PhysicalScaleProducer` can only be created from that producer-owned root.

For a `PhysicalScaleSelector`, `_revision_inputs` verifies:

- document ID,
- current revision,
- exact source SHA-256,
- exact snapshot ID,
- decoded page coverage,
- source bytes hashing back to the selector SHA.

Trusted text is then recovered through the existing PDF text-integrity authority.
Visible native line segments are recovered through the existing source-visibility
authority. Caller-provided coordinates, status, ratios, calibration or source
type are not accepted as truth inputs.

### Scale-bar candidate contract

Within the producer-selected source bbox, `_bar_candidates` requires:

1. one source-native baseline segment;
2. exactly one valid perpendicular tick crossing each baseline endpoint;
3. the two ticks must be distinct;
4. trusted endpoint text must resolve as:
   - zero at exactly one endpoint with no physical label there; and
   - exactly one positive explicit `mm`, `cm` or `m` label at the other endpoint, with no zero there;
5. native segment observation IDs and trusted text observation IDs are retained.

Ordinary ratio text such as `1:100` is not physical scale authority. It may
only corroborate or contradict a source-native graphic bar.

If no bar candidate exists, the producer abstains with
`physical_scale_bar_unavailable`. Multiple incompatible bar mappings, multiple
ratio readings or bar/ratio disagreement fail closed as
`physical_scale_conflict`.

### Canonical call path

`native PDF source bytes`
→ producer-owned visible segment observations + trusted text observations
→ `_bar_candidates`
→ `PhysicalScaleProducer.publish_scope`
→ producer-owned `PhysicalScaleAuthority`
→ CORROBORATED `PhysicalScaleEvidence(source_kind="native_graphic_scale_bar")`
→ `build_physical_scale_calibration`
→ `ScaleSourceReading(source_type=SCALE_BAR)`
→ `resolve_page_scale_calibration`
→ `ScaleCalibration(status=VALID, source_type=scale_bar)`
→ `measurement_authority_for_page_scale`
→ FIRM.

Manual `USER_APPROVED` remains the separate existing FIRM path.

Figured-span `INFERRED` and title-block `TITLE_BLOCK` remain capped at
PROVISIONAL. The existing canonical 5% reconciliation rule is unchanged.

## OBSERVED OWNERSHIP BOUNDARY

Current `PhysicalScaleProducer._scope_bbox` reruns
`segment_page_viewports` on the source page. It considers both RESOLVED and
DERIVED records "usable" for deciding whether a page-level selector is allowed,
but a viewport-scoped selector is accepted only when the matching viewport has:

`viewport.status == ViewportSegmentationStatus.RESOLVED.value`

An authoritative F.07 `columnar_title_grid` DERIVED viewport is therefore not
currently selectable by `PhysicalScaleAuthority`, even though the separately
approved migration adapter can authenticate that exact producer-owned DERIVED
ownership for figured-span scale shadow.

Consequently, the two current targets will return
`physical_scale_viewport_unavailable` from the existing producer before bar
candidate evaluation, because both are authoritative DERIVED.

This is an existing scale-bar ownership-interface limitation; it is not a reason
to broaden DERIVED authority. Whether it is a material generic gap depends on
the native-source audit below: if neither target contains an authentic graphic
scale bar, no production change is justified.

## SOURCE AUDIT PLAN

For each exact target viewport, audit native page-54 geometry and text directly:

- exact F.07 bbox and producer provenance;
- all baseline-like native segments wholly inside the bbox;
- endpoint perpendicular tick multiplicity;
- nearby trusted/native text words;
- zero labels;
- explicit physical-distance labels;
- native primitive / observation IDs;
- ordinary dimension-line / grid / frame / title / detail look-alikes;
- any candidate crossing or belonging to a sibling viewport.

Then run the existing `PhysicalScaleAuthority` unmodified to record its actual
selector result.

No parser or ownership patch will be written in this audit.

## PHASE 2 — EXACT-VIEWPORT NATIVE SOURCE AUDIT

Registered source:

- URL: `https://tenders.go.ke/storage/Documents/1727358888238-bq-nd-drawing.pdf`
- SHA-256: `6856bfa739aa136dd8e0bf17cb25fd43d0d31c9c3dfe3252525454f09d8fa4dc`
- page 54 only was ingested through `SourceVisibilityProducer`
- producer document ID: `kstvet-source-6856bfa739aa136dd8e0bf17`
- revision: `source_revision_5fca6a5c98bdb07f1cc1ff18fb1f4419`
- snapshot: `source_snapshot_7b987ddf6937ba35862271b8f2421fb2`

### view_p54_7 — SECTION S-03

F.07 ownership:

- status: DERIVED
- boundary source: TITLE_PARTITION
- authoritative-derived: true
- bbox: `[597.895760, 1249.514221, 1277.487900, 1683.780029]`
- `partition_mode=columnar_title_grid`
- `grid_validated=True`
- column 1 / 3, row 2 / 3
- source-visible native segments wholly scoped to bbox: 1916
- trusted text words in exact bbox under existing PDF-text integrity authority: 0
- trusted zero labels: 0
- trusted explicit physical-unit labels: 0
- trusted ratio-text words: 0
- existing `_bar_candidates`: 0

Two native line chains meet the *geometry-only* requirement of exactly one
perpendicular tick at each end, but fail the mandatory semantics completely:

1. baseline:
   - observation: `source_observation_8fa6a3671e83d8bcd2fada676dae4124`
   - primitive: `visible:segment:d9546i0`
   - start/end: `(941.123596,1423.198364) → (1065.862427,1423.198364)`
   - span: `124.738830566 pt`
   - left tick: `source_observation_4537df5be87bd433cd36ce7acbf4f383` / `visible:segment:d9548i0`
   - right tick: `source_observation_6b170a6305cd8b2f69984603faa46e1d` / `visible:segment:d9549i0`
   - endpoint words: none
   - zero: none
   - physical label: none

2. baseline:
   - observation: `source_observation_e0f436f3b21183cc0906939692ac48d7`
   - primitive: `visible:segment:d9550i0`
   - start/end: `(1065.862427,1423.198364) → (1194.340088,1423.198364)`
   - span: `128.477661133 pt`
   - left tick: `source_observation_6b170a6305cd8b2f69984603faa46e1d` / `visible:segment:d9549i0`
   - right tick: `source_observation_ddcf4f28611aeb998994864c39d6bb05` / `visible:segment:d9552i0`
   - endpoint words: none
   - zero: none
   - physical label: none

These spans are the same native dimension-chain spans already observed by the
figured-dimension lane (approximately 3300 and 3399 mm mappings). They are
ordinary figured-dimension / witness geometry look-alikes, not a semantic
graphic scale bar.

### view_p54_9 — ROOF PLAN

F.07 ownership:

- status: DERIVED
- boundary source: TITLE_PARTITION
- authoritative-derived: true
- bbox: `[0.000000, 1229.849762, 597.895760, 1683.780029]`
- `partition_mode=columnar_title_grid`
- `grid_validated=True`
- column 0 / 3, row 1 / 2
- source-visible native segments wholly scoped to bbox: 121
- trusted text words in exact bbox under existing PDF-text integrity authority: 0
- trusted zero labels: 0
- trusted explicit physical-unit labels: 0
- trusted ratio-text words: 0
- existing `_bar_candidates`: 0

Two geometry-only dimension chains have exactly one endpoint tick each:

1. baseline:
   - observation: `source_observation_790f51ab2c7837a6b9dcd18a11d7c9b6`
   - primitive: `visible:segment:d9572i0`
   - start/end: `(270.132782,1525.988403) → (394.869568,1525.988403)`
   - span: `124.736785889 pt`
   - left tick: `source_observation_db435a28661f6a13537a2a9b382c34bb` / `visible:segment:d9574i0`
   - right tick: `source_observation_da0e7f39fada54dcc05f5b76d8aea589` / `visible:segment:d9575i0`
   - endpoint words: none
   - zero: none
   - physical label: none

2. baseline:
   - observation: `source_observation_2280ae9471db628bf953d3da466920c8`
   - primitive: `visible:segment:d9576i0`
   - start/end: `(394.869568,1525.988403) → (523.350098,1525.988403)`
   - span: `128.480529785 pt`
   - left tick: `source_observation_da0e7f39fada54dcc05f5b76d8aea589` / `visible:segment:d9575i0`
   - right tick: `source_observation_fbe71b5a8948441ef78d8e39cb80987c` / `visible:segment:d9578i0`
   - endpoint words: none
   - zero: none
   - physical label: none

Again these native spans match the figured-dimension chains already producing
the two compatible INFERRED readings. They are not graphic scale bars.

## PHASE 3 — EXISTING AUTHORITY UNMODIFIED

For both target selectors the unmodified
`PhysicalScaleProducer.publish_scope(selector)` returns:

- status: ABSTAINED
- reason: `physical_scale_viewport_unavailable`
- evidence: none
- source kind: none
- physical span: none
- source span: none
- segment/text evidence IDs: none

This occurs before bar detection because current `_scope_bbox` allows
viewport-scoped physical-scale publication only for F.07 RESOLVED viewports.

The independent exact-bbox source audit using the existing producer's own
trusted observations and existing `_bar_candidates` logic finds **zero bar
candidates in both target viewports anyway**. Therefore the RESOLVED-only scope
limitation is not a material blocker for these two KSTVET targets and does not
justify a production change in this lane.

Because no CORROBORATED `native_graphic_scale_bar` evidence exists,
`build_physical_scale_calibration` is not eligible to run. No
`ScaleSourceReading(SCALE_BAR)` is minted and no additional canonical
reconciliation is performed.

Existing figured-span results remain unchanged:

- `view_p54_7`: CORROBORATED INFERRED → canonical PROVISIONAL → measurement PROVISIONAL
- `view_p54_9`: CORROBORATED INFERRED → canonical PROVISIONAL → measurement PROVISIONAL

No new conflict is introduced because no SCALE_BAR reading exists.

## PHASE 4 — DECISION

| Viewport | Figured status | Native scale-bar candidate | PhysicalScaleAuthority | Canonical source type | Calibration | Measurement authority |
| --- | --- | --- | --- | --- | --- | --- |
| SECTION S-03 (`view_p54_7`) | CORROBORATED | None; two figured-dimension line/tick look-alikes fail zero + physical-label semantics | ABSTAINED — `physical_scale_viewport_unavailable`; exact-bbox existing bar detector also yields zero candidates | INFERRED only | PROVISIONAL | PROVISIONAL |
| ROOF PLAN (`view_p54_9`) | CORROBORATED | None; two figured-dimension line/tick look-alikes fail zero + physical-label semantics | ABSTAINED — `physical_scale_viewport_unavailable`; exact-bbox existing bar detector also yields zero candidates | INFERRED only | PROVISIONAL | PROVISIONAL |

Both targets classify as decision **D: only figured dimensions exist**.

No authentic source graphic scale bar was found. No title-block scale or ratio
text inside these exact source scopes can substitute for one.

## FREEZE

`AUTOMATIC_FIRM_BLOCKED_NO_VIEWPORT_OWNED_PHYSICAL_SCALE_SOURCE`

No production code change is justified for these targets. Freeze this lane and
return for reassignment. Do not add more figured spans, change the 5% policy,
promote title-block scale, or fabricate manual approval.

