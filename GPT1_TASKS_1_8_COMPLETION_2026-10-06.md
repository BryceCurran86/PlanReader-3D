# GPT-1 Tasks 1–8 completion — 2026-10-06

## Frozen completion point

- Starting main: `1c4b1d1dc3e04b5421b6bf07b852d5670d95ad6f`
- Final production base: `ef0aaa7c48b5811a6e629d3f1021f726b27ca400`
- Benchmark: `full_plan_takeoff_reconciliation_v2`
- Active denominator audited: **51** (Lot16 27 + Maryborough 24)
- Full Plan V2 integrity check: **PASS**
- No benchmark truth, expected quantities, object universes, source manifests, tolerances, denominator eligibility, evaluator or scoring logic changed.

## Tasks 1–8

| Task | Status | Evidence |
|---|---|---|
| 1. Clean V2 baseline | **COMPLETE — blocked baseline recorded** | Lot16 executes/seals; exact reconciliation is blocked by physical-opening identity drift. Maryborough final replay exceeds the execution cap before a sealable final run; no score is invented. |
| 2. Per-object failure ledger | **COMPLETE** | All 51 denominator objects are explicitly classified below by first proven failing stage. |
| 3. Source Visibility | **COMPLETE** | #1343 merged: raster recall, ownership, stable raster identity and producer-scoped cache hardening. |
| 4. Raster-plan understanding | **COMPLETE (GPT-1 scope)** | Lot16 p3: 1,727 native + 2,356 raster visible observations, complete 2,094-wall scope, and 20 PhysicalWallIdentity records carrying both native and raster primitive lineage. |
| 5. Physical Wall Candidate Authority | **COMPLETE (GPT-1 scope)** | #1349/#1362/#1366/#1367/#1381/#1388. #1388 measured A110 complete page wall producer at ~30.9 s excluding worker-shutdown noise. |
| 6. Source Room Face Authority | **COMPLETE** | #1352 exact Maryborough validation publishes 687 source room faces while unsafe/incomplete faces remain fail-closed. |
| 7. Room-label binding | **COMPLETE** | #1355 authenticates FOOD PREP, COLD ROOM, FREEZER, PWD, AIRLOCK, LAUNDRY and OFFICE; DRY STORE remains unbound/ABSTAIN. |
| 8. CanonicalSpace creation | **COMPLETE** | #1358 bridges the stable physical room into existing CanonicalSpace while source PDF-point geometry remains non-metric provenance. |

## Final baseline facts

### Lot16
Source SHA: `10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`

Current production at `ef0aaa7`:
- 2,094 wall candidates, complete/corroborated page-3 scope
- 67 canonical openings
- 3 host-bound opening traces
- one sealed opening-area row = **5.67 m2**
- runtime to seal = **12.51 s**
- current physical opening id = `physical_opening_existence_5a364bc74fd3f995d9992392af93b839`

The frozen exact-identity binding for the same 2127 STACKER quantity was established for
`physical_opening_existence_944762236add056fd689d46326ce6f39`.
Current reconciliation therefore emits a `production-unmapped` row. Do **not** update benchmark truth or the frozen map to chase this drift.

Lot16 also produces 61 canonical rooms, 61 floors and 61 CanonicalSpaces, but **0 metric floors** and **0 firm room-area quantities**.

### Maryborough
Source SHA: `b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007`

The immediately preceding byte-identical live-claim path produced:
- 3,694 canonical walls
- 259 canonical openings
- 687 canonical rooms
- 687 canonical floors
- 687 CanonicalSpaces
- 0 firm room-area QuantityEvidence in that exact full live claim.

#1379 independently source-validates Food Prep 4025 mm x 3297 mm = **13.270425 m2**.
The final `ef0aaa7` replay with the merged #1391 sealer exceeded the 320 s execution cap before a source-closed run was emitted.

## Accuracy statement

**No new combined V2 percentage is publishable from this completion baseline.**

That is deliberate fail-closed behavior:
1. Lot16 has a sealed quantity but its production physical identity drifted from the frozen exact binding.
2. Maryborough did not emit a final source-closed run within the execution cap.
3. The current checked-in evaluator publication facade exposes denominator 0 for these incomplete source manifests; reporting that as “0%” would be false.

The historical 1/51 result remains historical only; it is not relabelled as current.

## 51-object first-failure ledger

Summary:
- **PHYSICAL IDENTITY: 30**
- **MEASUREMENT AUTHORITY: 19**
- **QUANTITY GENERATION: 2**

| Denominator item | First failing stage | First proven blocker |
|---|---|---|
| `lot16-0615-sgw-01-area` | **PHYSICAL IDENTITY** | opening/host identity not uniquely source-closed; only 3/67 current openings host-bound |
| `lot16-0621-sgw-01-area` | **PHYSICAL IDENTITY** | opening/host identity not uniquely source-closed; only 3/67 current openings host-bound |
| `lot16-0630-fg-01-area` | **PHYSICAL IDENTITY** | opening/host identity not uniquely source-closed; only 3/67 current openings host-bound |
| `lot16-0906-sgw-obs-01-area` | **PHYSICAL IDENTITY** | opening/host identity not uniquely source-closed; only 3/67 current openings host-bound |
| `lot16-1215-sgw-obs-01-area` | **PHYSICAL IDENTITY** | opening/host identity not uniquely source-closed; only 3/67 current openings host-bound |
| `lot16-1218-sgw-01-area` | **PHYSICAL IDENTITY** | opening/host identity not uniquely source-closed; only 3/67 current openings host-bound |
| `lot16-1218-sgw-02-area` | **PHYSICAL IDENTITY** | opening/host identity not uniquely source-closed; only 3/67 current openings host-bound |
| `lot16-2124-corner-stack-01-area` | **PHYSICAL IDENTITY** | opening/host identity not uniquely source-closed; only 3/67 current openings host-bound |
| `lot16-2127-stacker-01-area` | **PHYSICAL IDENTITY** | firm 5.67 m2 row exists but production physical-opening id drifted from frozen exact binding |
| `lot16-2148-panel-lift-01-area` | **PHYSICAL IDENTITY** | opening/host identity not uniquely source-closed; only 3/67 current openings host-bound |
| `lot16-1200-entry-hinged-01-area` | **PHYSICAL IDENTITY** | opening/host identity not uniquely source-closed; only 3/67 current openings host-bound |
| `lot16-0870-laundry-external-01-area` | **PHYSICAL IDENTITY** | opening/host identity not uniquely source-closed; only 3/67 current openings host-bound |
| `lot16-0870-garage-personnel-01-area` | **PHYSICAL IDENTITY** | opening/host identity not uniquely source-closed; only 3/67 current openings host-bound |
| `lot16-internal-access-0870-bed3-area` | **PHYSICAL IDENTITY** | opening/host identity not uniquely source-closed; only 3/67 current openings host-bound |
| `lot16-internal-access-0870-bed2-area` | **PHYSICAL IDENTITY** | opening/host identity not uniquely source-closed; only 3/67 current openings host-bound |
| `lot16-internal-access-0870-bath-area` | **PHYSICAL IDENTITY** | opening/host identity not uniquely source-closed; only 3/67 current openings host-bound |
| `lot16-internal-access-0870-laundry-area` | **PHYSICAL IDENTITY** | opening/host identity not uniquely source-closed; only 3/67 current openings host-bound |
| `lot16-internal-access-0870-bed1-area` | **PHYSICAL IDENTITY** | opening/host identity not uniquely source-closed; only 3/67 current openings host-bound |
| `lot16-internal-access-0870-wir-area` | **PHYSICAL IDENTITY** | opening/host identity not uniquely source-closed; only 3/67 current openings host-bound |
| `lot16-internal-access-0870-ensuite-area` | **PHYSICAL IDENTITY** | opening/host identity not uniquely source-closed; only 3/67 current openings host-bound |
| `lot16-internal-access-0870-wc-area` | **PHYSICAL IDENTITY** | opening/host identity not uniquely source-closed; only 3/67 current openings host-bound |
| `lot16-internal-access-0870-garage-to-entry-area` | **PHYSICAL IDENTITY** | opening/host identity not uniquely source-closed; only 3/67 current openings host-bound |
| `lot16-ceiling-garage-flat-area` | **MEASUREMENT AUTHORITY** | 61 canonical rooms/floors/spaces exist, but current Lot16 claim has 0 metric floors and 0 firm room-area quantities |
| `lot16-ceiling-ensuite-raked-12deg-area` | **MEASUREMENT AUTHORITY** | 61 canonical rooms/floors/spaces exist, but current Lot16 claim has 0 metric floors and 0 firm room-area quantities |
| `lot16-ceiling-wir-raked-12deg-area` | **MEASUREMENT AUTHORITY** | 61 canonical rooms/floors/spaces exist, but current Lot16 claim has 0 metric floors and 0 firm room-area quantities |
| `lot16-floor-ensuite-area` | **MEASUREMENT AUTHORITY** | 61 canonical rooms/floors/spaces exist, but current Lot16 claim has 0 metric floors and 0 firm room-area quantities |
| `lot16-floor-wir-area` | **MEASUREMENT AUTHORITY** | 61 canonical rooms/floors/spaces exist, but current Lot16 claim has 0 metric floors and 0 firm room-area quantities |
| `maryborough-door-ipf3-count` | **PHYSICAL IDENTITY** | 259 canonical openings exist, but complete authenticated host-wall universe / host binding remains unproven |
| `maryborough-door-laminex-partition-count` | **PHYSICAL IDENTITY** | 259 canonical openings exist, but complete authenticated host-wall universe / host binding remains unproven |
| `maryborough-door-aluminium-glazed-count` | **PHYSICAL IDENTITY** | 259 canonical openings exist, but complete authenticated host-wall universe / host binding remains unproven |
| `maryborough-window-tagged-count` | **PHYSICAL IDENTITY** | 259 canonical openings exist, but complete authenticated host-wall universe / host binding remains unproven |
| `maryborough-window-w01-gross-frame-opening-area` | **PHYSICAL IDENTITY** | 259 canonical openings exist, but complete authenticated host-wall universe / host binding remains unproven |
| `maryborough-window-w02-gross-frame-opening-area` | **PHYSICAL IDENTITY** | 259 canonical openings exist, but complete authenticated host-wall universe / host binding remains unproven |
| `maryborough-window-w05-gross-frame-opening-area` | **PHYSICAL IDENTITY** | 259 canonical openings exist, but complete authenticated host-wall universe / host binding remains unproven |
| `maryborough-window-w06-gross-frame-opening-area` | **PHYSICAL IDENTITY** | 259 canonical openings exist, but complete authenticated host-wall universe / host binding remains unproven |
| `maryborough-food-prep-ft3-floor-area` | **QUANTITY GENERATION** | Food Prep 4025 x 3297 figured-dimension area is independently authenticated, but final sealed denominator quantity is not available in the frozen baseline run |
| `maryborough-food-prep-fpb-ceiling-area` | **QUANTITY GENERATION** | Food Prep 4025 x 3297 figured-dimension area is independently authenticated, but final sealed denominator quantity is not available in the frozen baseline run |
| `maryborough-wc-shower-north-ft2-floor-area` | **MEASUREMENT AUTHORITY** | source-owned room exists, but no firm metric measurement is linked into the sealed denominator quantity path |
| `maryborough-wc-shower-middle-ft2-floor-area` | **MEASUREMENT AUTHORITY** | source-owned room exists, but no firm metric measurement is linked into the sealed denominator quantity path |
| `maryborough-wc-shower-south-ft2-floor-area` | **MEASUREMENT AUTHORITY** | source-owned room exists, but no firm metric measurement is linked into the sealed denominator quantity path |
| `maryborough-wc-shower-north-wfpb-ceiling-area` | **MEASUREMENT AUTHORITY** | source-owned room exists, but no firm metric measurement is linked into the sealed denominator quantity path |
| `maryborough-wc-shower-middle-wfpb-ceiling-area` | **MEASUREMENT AUTHORITY** | source-owned room exists, but no firm metric measurement is linked into the sealed denominator quantity path |
| `maryborough-wc-shower-south-wfpb-ceiling-area` | **MEASUREMENT AUTHORITY** | source-owned room exists, but no firm metric measurement is linked into the sealed denominator quantity path |
| `maryborough-pwd-ft2-floor-area` | **MEASUREMENT AUTHORITY** | source-owned room exists, but no firm metric measurement is linked into the sealed denominator quantity path |
| `maryborough-pwd-wfpb-ceiling-area` | **MEASUREMENT AUTHORITY** | source-owned room exists, but no firm metric measurement is linked into the sealed denominator quantity path |
| `maryborough-airlock-ft2-floor-area` | **MEASUREMENT AUTHORITY** | source-owned room exists, but no firm metric measurement is linked into the sealed denominator quantity path |
| `maryborough-airlock-wfpb-ceiling-area` | **MEASUREMENT AUTHORITY** | source-owned room exists, but no firm metric measurement is linked into the sealed denominator quantity path |
| `maryborough-laundry-ft2-floor-area` | **MEASUREMENT AUTHORITY** | source-owned room exists, but no firm metric measurement is linked into the sealed denominator quantity path |
| `maryborough-laundry-wfpb-ceiling-area` | **MEASUREMENT AUTHORITY** | source-owned room exists, but no firm metric measurement is linked into the sealed denominator quantity path |
| `maryborough-office-ft3-floor-area` | **MEASUREMENT AUTHORITY** | source-owned room exists, but no firm metric measurement is linked into the sealed denominator quantity path |
| `maryborough-office-grid-ceiling-area` | **MEASUREMENT AUTHORITY** | source-owned room exists, but no firm metric measurement is linked into the sealed denominator quantity path |

## Merged GPT-1 changes

- #1343 Source Visibility hardening
- #1349 split-fragment lineage performance
- #1352 local boundary-clean room-face recovery
- #1353 physical-room identity separation
- #1355 authenticated room-label authority
- #1358 CanonicalSpace bridge
- #1362 opening-proven same-face wall relations with non-wall jambs
- #1366 duplicate structural opening geometry collapse
- #1367 native page-decode reuse
- #1381 batch visible authority + motif reuse
- #1388 dense-page viewport/opening authority-state reuse

## Dependencies handed to other lanes

- Lot16 physical-opening identity stability (same physical object currently changes production identity).
- Opening host/kind closure for the remaining Lot16 and Maryborough openings.
- Metric measurement for remaining floor/ceiling surfaces.
- Maryborough source-closed runtime / final sealed reconciliation.
- Downstream customer surface/finish quantity publication.

GPT-1 Tasks **1–8 are complete at this frozen base**. The remaining items are broader >99% program dependencies, not justification to weaken fail-closed rules or alter benchmark truth.
