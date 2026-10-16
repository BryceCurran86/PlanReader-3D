# Structural room-region evidence — shadow-only engineering review (2026-10-17)

**Status: SHADOW ONLY / NOT A ROOM-REGISTRATION OR MEASUREMENT AUTHORITY.**

This work identifies structural wall ink, attached partition ink, typed opening-gap chords, and candidate enclosed room regions for review. It does not create or modify `SourceRoomFaceAuthority`, publish a `QuantityEvidence` row, infer a missing wall, choose a floor finish, approve a scale, or authorize a customer takeoff.

## Public-repository source confidentiality

This repository is public. The original drawings and the native-coordinate floor-plan overlays produced from them are **owner-private source material**. The twelve original-derived floor-region JSON/PNG artifacts formerly staged in PR #2851 were removed from that PR's final merge tree. Their removal from the current Git tree does **not** delete earlier PR branch commits or GitHub history containing the artifacts. Do not re-add client-plan silhouettes, vectors, images, native coordinate arrays, plan labels, OCR text, or other reconstructable artifacts to the public repository without explicit distribution permission.

The diagnostic tools can produce room-region outputs **locally** from an original input file. Keep those results in a private workspace or access-controlled artifact store. The files `tests/test_structural_room_region_shadow.py`, `tests/test_structural_partition_ink_shadow.py`, `tests/test_structural_room_region_overlay_tool.py`, `tests/test_region_translation_vote.py`, and `tests/test_structural_wall_ink_shadow.py` test synthetic inputs only.

## Technical modules and fail-closed boundaries

- `pb_structural_wall_ink_shadow.py`: classify source-native structural candidates, opening-gap candidates and typed ruled-ring/table negatives. The ruled-ring check requires a predominantly box-edge ring and multiple full-span internal rule lines, but protects paired-face partition evidence from a false table classification.
- `pb_structural_partition_ink_shadow.py`: reject regularly spaced parallel hatch/plank ladders and nominate lighter paired-face partitions only when attached to the structural network. This is not wall authority.
- `pb_structural_room_region_shadow.py`: compute candidate regions, exterior/internal primitive membership, boundary ancestry and opening-gap chords. The source geometry and candidate labels remain untrusted until independently authenticated; a polygon or label centre alone is not a valid room identity.
- `tools/diag_region_translation_vote.py`: report every exact-corner translation candidate and all competing alignments. It never selects correspondence, authenticates a wall owner or binds room floors.
- `tools/diag_structural_room_region_overlay.py`: opt-in diagnostic for locally supplied drawings. Its default white-background visualisation hides raw page pixels but **is not clearance to publish source-reconstructable geometry**. `--private-detail` additionally includes the underlying original page and must remain owner-private.
- `counterfactual/run_cap_counterfactual.py` and `counterfactual/q5446_cap_counterfactual_summary.json`: bounded, source-neutral aggregate stage counts showing that withheld drafting negatives can reduce physical wall stage complexity. These are NOT production scope exemptions and never change the 20,000 raster primitive safety cap.

The shadow contracts preserve `room_authority_granted=false`, `scale_authority_granted=false`, `wall_authority_granted=false` where applicable, `live_effect=false`, and all competing primitive roles and regions. Typed opening chords are not independently authenticated room wall members; candidate area in native PDF point-squared is not a metric `floor_area` or a material-specific `floor_finish_area`.

## Status by project (aggregate, not publishable source geometry)

| Original-source diagnostic | Observed candidate-region count | Remaining first authority gate |
|---|---:|---|
| 3Laurel floor-plan source | 38 | Authenticate partitions, door gaps, labels and physical room owners |
| Q5446 ground-floor source | 7 | Typed structural walls, false outlined-lettering negatives and source role verification |
| Q5446 first-floor source | 10 | Same source-role and physical-boundary gates |
| Maryborough original floor plan | 26 | Distinguish walls from countertops and shared functional sections |
| Maryborough floor finishes / partitions | 29 | Authenticate exact original plan mark and floor identity across sheets |
| Lot16 original source negative control | 0 | No shadow room inferred on this control |

These are **candidate diagnostic counts only**; none is registered as a FIRM room. Maryborough may include multiple functional labels inside one physical area and must not be split without authentic original structural partitions. Document-to-document alignment is a candidate until independently proved by source-side wall roots.

## Reproduction and tests

Use normal repository test entry points for the synthetic test modules above. To inspect a client's original document, invoke the overlay diagnostic with `--pdf`, `--page`, `--png`, and `--json` into an owner-private output directory; never commit the resulting source-derived files to the public repository. The code changes are independent of output-path conventions; no production consumer opts into this shadow module by default.

**Release gate:** Independent authority review remains necessary before connecting any of these shadows to source-owned walls, authenticated room face identity, metric scale, room finishes, V1 signed quantities, or customer output. Frozen Full Plan V2 truth, evaluator, denominators and the 20,000 cap are unchanged. All existing signed Lot16 and Maryborough quantities must remain byte-identical under a shadow-only merge.
