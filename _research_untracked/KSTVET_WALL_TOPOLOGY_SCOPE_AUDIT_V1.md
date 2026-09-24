# KSTVET wall-topology scope audit v1

Base: `00d5f1cef79729389e3638fafbcd30fbbf786f1c`

Branch intent: diagnostic/shadow only. No production quantities, benchmark gold, wall-role outputs, or completeness invariants are changed.

## Executive finding

The current source-backed physical-wall authority is **page-scoped**, not authenticated floor-plan-viewport-scoped.

That matters because `scope_complete` is computed over every W4 wall candidate produced from the page-wide visible segment universe. A single dangling wall candidate at a page/viewport/unresolved boundary anywhere on the sheet sets the entire page scope incomplete. The downstream source topology producer then publishes no topology records at all when `scope_complete=False`.

For KSTVET page 54, this creates a strong candidate explanation for the observed chain:

`scope_complete=False`
-> `_derive_scope_records()` returns `{}`
-> no `WallTopologyEvidence`
-> `WallRoleProducer.publish()` abstains / `WALL_ROLE_UNRESOLVED`.

**Do not weaken `scope_complete`.** The architecture gap to test is scope ownership.

## Proven from main

### 1. Physical-wall scope ID is page-only

`pb_physical_wall_candidate_authority._decision_scope_id(page_id)` returns:

`wall-source:page-{page_id}`

There is no viewport identity in the physical-wall decision scope.

### 2. Source membership is page-wide

`_source_page_segments(...)` resolves every producer-owned visible observation on the requested page, reconstructs every native/raster visible segment on that page, and appends it to the W2 input.

For native segments the function sets:

- `document_id`
- `page_id`
- `viewport_id = decision_scope_id`
- `source_observation_id`

but it does **not** spatially filter the segment against a floor-plan viewport before W2.

Therefore stamping `viewport_id` here does not prove viewport ownership; it labels a page-wide segment universe with a page decision-scope identifier.

### 3. W2/W3/W4 are run over that full page-wide segment set

`_build_scope_result(...)` calls:

- `build_wall_graph_for_viewport(segments)`
- `classify_junctions(... viewport_id=scope_id)`
- `assemble_wall_topology(... viewport_id=scope_id)`

where `segments` is the page-wide set above.

### 4. Completeness is poisoned by any wall in that page-wide universe

After wall assembly, `_build_scope_result(...)` iterates every ordered wall and calls `_scope_boundary_reason(...)`.

Any non-None boundary reason makes:

`cropped = True`

and therefore:

`scope_complete = False`.

This is conservative for a truly page-wide drawing, but it can falsely make a target floor plan incomplete if unrelated details/elevations/sections/borders elsewhere on the same sheet enter the same candidate universe.

### 5. Source topology correctly refuses incomplete scopes

`pb_source_wall_topology_authority._derive_scope_records(scope)` begins with:

```python
if (
    scope.status is not EvidenceResolutionStatus.CORROBORATED
    or not scope.scope_complete
    or not records
):
    return {}
```

This invariant is correct and should remain.

### 6. The existing diagnostic W1-W10 path already contains the missing ownership pattern

`pb_wall_topology_diagnostics.collect_topology_from_page(...)`:

1. runs F.07 `segment_page_viewports`,
2. accepts only safe floor-plan viewports (RESOLVED by default),
3. chooses an authenticated floor-plan viewport,
4. spatially scopes native segments using `_segment_in_viewport`,
5. where `_segment_in_viewport` requires **both endpoints** inside the viewport bbox,
6. only then runs W2-W10.

This is the architectural pattern that the newer source-backed physical-wall authority has not yet carried across.

## KSTVET-specific hypothesis

The reported KSTVET physical-wall universe was approximately 2,635 wall candidates.

That count must be audited against the authenticated target floor-plan viewport on page 54.

The key question is:

> Is KSTVET's actual target floor-plan topology incomplete, or are page-wide/unrelated primitives outside the authoritative floor-plan viewport causing `scope_complete=False`?

No production fix should be merged until that question is answered with counts.

## Required local shadow run

Source fixture:

`benchmarks/sources/1727358888238-bq-nd-drawing.pdf`

Page:

`54`

First list F.07 viewports:

```powershell
$env:PYTHONPATH="."
python tools/audit_wall_topology.py benchmarks/sources/1727358888238-bq-nd-drawing.pdf --page 54 --list-viewports
```

Then run the safe floor-plan viewport diagnostic:

```powershell
$env:PYTHONPATH="."
python tools/audit_wall_topology.py benchmarks/sources/1727358888238-bq-nd-drawing.pdf --page 54 --json scratch/kstvet-p54-topology.json --markdown scratch/kstvet-p54-topology.md --svg scratch/kstvet-p54-topology.svg
```

If more than one RESOLVED FLOOR_PLAN viewport exists, run each explicitly with `--viewport-id`.

Record:

- raw page primitive count
- scoped primitive count
- W4 wall-candidate count
- connected-component count
- target viewport id / bbox / status / title
- number of physical-wall authority records in current page scope
- exact walls returning each `_scope_boundary_reason`
- whether those walls are inside or outside the chosen target floor-plan viewport

## Diagnostic table required

For every wall that contributes a boundary reason, collect:

| field | required |
|---|---|
| wall_candidate_id | yes |
| centerline endpoints | yes |
| junction types at both ends | yes |
| boundary reason | yes |
| page-edge contact | yes |
| containing RESOLVED viewport ids | yes |
| target floor-plan viewport membership | yes |
| target viewport boundary contact | yes |
| topology component id / size | yes |
| target-plan member vs unrelated sheet geometry | yes |

## Preferred production architecture if hypothesis is confirmed

Do not reinterpret page-wide `scope_complete`.

Instead introduce a producer-owned viewport-scoped physical-wall universe:

source visibility snapshot
-> source page
-> F.07 producer-owned RESOLVED FLOOR_PLAN viewport
-> exact segment membership owned by that viewport
-> W2/W3/W4 physical-wall candidates
-> scope completeness over only that authenticated universe
-> source wall topology
-> wall role

Important constraints:

1. No caller bbox may mint production authority.
2. DERIVED / AMBIGUOUS / UNSUPPORTED viewports must not silently become positive physical-wall authority.
3. Viewport identity/bbox must come from source-derived F.07 evidence.
4. Preserve exact source-observation lineage for every included segment.
5. Preserve page-wide scope behavior for genuinely undivided whole-page drawings where F.07 finds no sub-viewport structure.
6. Keep `scope_complete` fail-closed.
7. Do not use nearest-title, nearest-wall, benchmark quantity, perimeter rank, thickness, or caller labels to select the target wall universe.

## Regression tests required before production change

### A. Unrelated page-edge geometry cannot poison an authenticated plan viewport

Synthetic sheet:

- one RESOLVED titled floor-plan viewport containing a complete two-room wall network,
- one unrelated dangling visible segment outside that viewport ending at the PDF page edge.

Expected:

- page-wide diagnostic can observe the unrelated segment,
- floor-plan physical-wall scope excludes it,
- viewport-scoped plan remains complete,
- wall topology can resolve external/internal roles for the plan.

### B. Real viewport crop remains incomplete

A wall owned by the authenticated floor-plan viewport has a dangling ENDPOINT exactly on that viewport boundary.

Expected:

- `scope_complete=False`,
- no source wall-topology positive publication,
- wall role remains unresolved.

### C. Two floor-plan viewports do not contaminate each other

Two RESOLVED FLOOR_PLAN viewports on one sheet, each with independent geometry.

Expected:

- separate source-owned scopes,
- stable distinct decision-scope IDs,
- no cross-viewport wall candidates or topology edges.

### D. Derived/ambiguous viewport fails closed

Title anchors exist but no authenticated RESOLVED floor-plan boundary.

Expected:

- no positive viewport-scoped physical-wall authority is minted from the inferred bbox.

### E. Whole-page plan compatibility

No sub-viewport structure exists; plan occupies the page and all relevant dangling ends are interior.

Expected:

- existing page-scope behavior remains available and complete.

### F. Source lineage integrity

Every viewport-scoped segment must map bijectively to a CORROBORATED visible observation from the same document/revision/source/snapshot/page.

No caller-authored segment list may enter production authority.

## Production change location if confirmed

Likely touchpoints:

- `pb_physical_wall_candidate_authority.py`
  - source scope identity
  - source-segment ownership/subsetting
  - scope materialization
- focused new tests under `tests/`

Do **not** modify `pb_source_wall_topology_authority._derive_scope_records` to accept incomplete scopes.

## Status

### Proven
- page-wide physical-wall source universe
- page-only decision scope id
- completeness evaluated over all page-derived wall candidates
- incomplete scope causes source topology to publish no records
- existing diagnostic path already has RESOLVED FLOOR_PLAN + both-endpoints-inside viewport scoping

### Not yet proven
- exact KSTVET page-54 boundary-wall counts
- exact KSTVET RESOLVED floor-plan viewport id/bbox
- whether viewport-only KSTVET topology is complete
- whether all 2,635 reported candidates came from the current page-scope path

Those must be measured locally against the immutable KSTVET source before any production merge.
