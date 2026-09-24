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
