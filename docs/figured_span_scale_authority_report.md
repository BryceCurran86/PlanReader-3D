# Figured-dimension span identity -> scale authority architecture report

Base inspected: `70ad47abc1f74c9fb134ffc4c505580b8caca61d`.

This report is the required first deliverable under `AGENTS.md`. It changes no production path and proposes no benchmark-tuned threshold.

## Compliance

Files actually read:
- `AGENTS.md`
- `docs/AI_ENGINEERING_PLAYBOOK.md`
- `pb_figured_dimension_evidence.py`
- `pb_viewport_dimension_binding.py`
- `pb_dimension_chain_evidence_extractor.py`
- `pb_page_scale_calibration_authority.py`
- `pb_viewport_scale_binding.py`
- `pb_physical_scale_calibration_bridge.py`
- `pb_figured_dimension_authority.py`
- `pb_measurement_input_authority.py`
- `pb_source_roof_covering_authority.py`
- diagnostic PR #874 and shadow roof-edge PR #875.

Exact functions traced:
- `extract_dimension_evidence_by_viewport`
- `bind_observation_to_vector_geometry`
- `apply_anchor_binding`
- `resolve_page_scale_calibration`
- `measurement_authority_for_page_scale`
- `bind_viewport_scale`
- `build_physical_scale_calibration`
- `resolve_measurement_authority`
- `resolve_linear_measurement_input`
- `resolve_gable_apex_in_viewport`
- `measure_source_roof_covering`
- shadow-only `collect_longitudinal_roof_edge`, `collect_gable_outer_roof_edge`, and `reconcile_roof_eave_geometry` in PR #875.

Authority boundaries crossed by the proposed seam:
1. native text/vector capture
2. F.07 viewport ownership
3. F.13 figured-dimension witness binding
4. physical-scale evidence production
5. existing page-scale calibration
6. viewport scale binding
7. existing measurement-input authority

Expected abstentions before implementation:
- figured text without a unique dimension line and two unique witnesses
- partial-witness / line-only / ambiguous F.13 bindings
- endpoints outside or crossing the owning viewport
- missing document/revision/source-SHA/page/viewport identity
- multiple incompatible figured spans for the same viewport
- duplicate or competing witness bundles that imply different point/mm ratios
- non-finite or non-positive figured values or native spans
- stale revision
- sibling-viewport evidence leakage
- roof-edge geometry whose viewport/entity identity does not match the calibration owner
- title-block scale text alone
- any candidate where independent scale witnesses disagree beyond the existing authority tolerance

Files that remain untouched by this report and by the proposed first implementation:
- `pb_planreader_pdf_extractor.py`
- `pb_planreader_jobhub_publish_contract.py`
- live opening/deduction files
- `benchmarks/**`
- `pb_benchmark_accuracy_engine.py`
- W10 takeoff/deduction defaults
- benchmark mappings/tolerances/manifests

## Observed repository behavior

### Figured-dimension geometry already has a conservative ownership path

`pb_viewport_dimension_binding.extract_dimension_evidence_by_viewport` spatially scopes words and vector segments to one eligible viewport before any anchor association. It requires full text-bbox containment and both vector endpoints inside the viewport.

`pb_figured_dimension_evidence.bind_observation_to_vector_geometry` can return `WITNESS_BOUND` with:
- one explicit dimension-line id,
- two witness-line ids,
- two native PDF-point endpoints.

When multiple line candidates are spatially indistinguishable, it returns `AMBIGUOUS` rather than selecting by ID. Partial or line-only associations do not receive resolved endpoints.

This is already the correct primitive for a documented physical span witness.

### Existing page-scale authority has one firm graphic path

`pb_page_scale_calibration_authority.resolve_page_scale_calibration` is the canonical scale resolver. `measurement_authority_for_page_scale` makes:
- validated `SCALE_BAR` or manual evidence FIRM,
- title-block text PROVISIONAL,
- unknown/conflicting/stale evidence blocked.

`pb_physical_scale_calibration_bridge.build_physical_scale_calibration` shows the approved adapter pattern: producer-owned physical evidence is retained, converted to an existing `ScaleSourceReading`, and delegated into `resolve_page_scale_calibration`. The bridge does not create a second scale resolver.

### Figured dimensions are already allowed to be firm measurements, but not yet a general scale producer

`pb_figured_dimension_authority.resolve_measurement_authority` gives a valid documented dimension FIRM linear authority and blocks malformed values.

`pb_measurement_input_authority.resolve_linear_measurement_input` consumes a CORROBORATED figured evidence atom as a firm measurement for an exact entity, or a FIRM viewport-owned scale binding for scaled geometry. It does not treat a figured dimension as a page/viewport calibration producer.

Therefore the repository currently contains the two required ingredients—an owned witness-bound figured span and the existing page-scale resolver—but no contract-correct bridge between them.

### Current roof lane

PR #875 retains outer roof geometry only in native points. It deliberately emits no area because no firm physical scale is attached to those elevation viewports.

The diagnostic source trace in PR #874 observed two independent structural figured spans on the same drawing sheet. Those observations nominate this seam only; they are not authority by themselves and are not implementation constants.

## Inference

A witness-bound figured dimension can establish a local physical mapping only when the documented value and the native witness-to-witness span belong to the same resolved viewport and source revision.

That mapping is qualitatively different from title-block scale text:
- title-block text asserts a nominal drawing ratio without proving the local vector geometry follows it;
- a witness-bound figured dimension explicitly maps a physical value to two source-native geometric endpoints.

However, promoting such a mapping to reusable viewport scale is only safe if the repository treats it as producer-owned physical-scale evidence and routes it through the existing scale authority. Directly dividing points by metres at a roof consumer would create a prohibited second scale resolver.

One witness bundle may be enough to nominate a candidate mapping, but promotion should require corroboration or an explicit existing authority policy. Multiple compatible witness bundles in the same viewport can provide that corroboration. Competing mappings must remain conflict/abstention.

## Proposed change

Do not modify live extraction or commercial output.

First implementation, after review:

1. Add a shadow-only producer that consumes F.13 `DimensionEvidenceBundle` output for one resolved viewport.
2. Accept only `WITNESS_BOUND` observations with:
   - valid figured physical value,
   - explicit dimension-line id,
   - exactly two witness ids,
   - finite positive native endpoint distance,
   - exact document/source/revision/page/viewport ownership supplied by the caller.
3. Retain every candidate physical mapping as source evidence; never choose first/nearest/smallest.
4. Reconcile compatible mappings in that viewport:
   - zero -> abstain,
   - one -> candidate/provisional physical-scale evidence pending authority review,
   - two or more mutually compatible -> corroborated physical-scale evidence,
   - incompatible mappings -> conflict retaining alternatives.
5. Reuse the existing physical-scale/page-scale bridge pattern rather than adding any scale math to roof code.
6. Keep PR #875 roof edges shadow-only. A later authority-promotion review may decide whether a corroborated viewport calibration can bind to those exact roof-edge viewports and permit a derived area.
7. Preserve source observation ids, witness ids, dimension-line ids, endpoints, figured text/value, source SHA, revision, page, viewport, and entity scope in stable IDs.

No benchmark quantity, project name, file name, expected area, known ratio, or development score may be an input.

## Required synthetic proof before any promotion

- positive unique witness-bound horizontal and vertical dimensions
- two agreeing independent bundles in one viewport
- look-alike numeric text, room/grid/sheet/revision tokens
- dimension line with one witness only
- two equally plausible dimension lines
- two complete but conflicting physical mappings
- cross-viewport line/text contamination
- translation, 90/180-degree rotation, uniform scale transforms
- input order and segment splitting invariance
- unrelated content and viewport expansion invariance
- deterministic replay/stable-ID equality
- input nonmutation
- proof that live predictions, commercial quantities, and benchmark denominator remain unchanged

## Benchmark observations that must not influence implementation

The canonical five-project benchmark on main is currently recorded as 36/60 accepted, strict exact 29/60, zero hallucinations.

The Lamu development benchmark contains a roof-covering target, but that expected value must not select witness bundles, tolerances, ratios, roof lines, or promotion rules. Diagnostic calculations in PR #874 are evaluation/debug information only.

## Review question

Is a uniquely witness-bound figured dimension an acceptable producer of provisional physical-scale evidence, with FIRM viewport calibration allowed only after independent compatible witness bundles corroborate the same local mapping through the existing page-scale authority?

Until that authority question is approved, no implementation should publish scale or roof area.
