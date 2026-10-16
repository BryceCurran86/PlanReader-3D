# MAX Lot16 source/host checkpoint, 16 October 2026

This checkpoint executes the shared MAX queue, not a proposal to promote a
wall, frame or quantity. Code inspected and locally executed:
`6bfd22fa8e09b2cbed5ed59a38128157c3bf83af`. The accompanying
`gptmax_lot16_host_source_queue_20261016.json` preserves exact source records,
first-failure traces, original report hashes and existing signed quantity IDs.
Local execution used Python 3.12.14, PyMuPDF 1.28.0, OpenCV 4.14.0 and Shapely
2.1.2. It is separate from the linked Actions executions.

## Observed source and signed output

Original architectural PDF SHA256:
`10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`.
Selected geometry page: 3. Selected producer snapshot:
`source_snapshot_3fcb6bc5c44b51d930e9600080501d27`.
Wall decision scope: `wall-source:page-3`.

The actual selected producer yields **21 physical openings, 15 authenticated
hosts, 9 frames and 8 area-bearing canonical openings**. The actual original
single-page collector, source sealer, customer projection and independent
verifier also yield eight valid signed quantities. Current main's complete
sealed run and customer rows are byte-equal to the archived #2748 original
customer receipt bodies when serialized by their existing canonical writer:

| Artifact | SHA256 |
| --- | --- |
| `source_sealed_run.json` | `61c4e5d27c2505bf811a300c39a48298f19d0363d5942c684fe44dd16406482c` |
| `verified_customer_rows.json` | `c840b9c18989a2376d132ee6c26b3134e9428671cb1d22921468b0c80a87a0c6` |

Sealed run fingerprint:
`ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
Archive: [original #2748 run 38651231157](https://github.com/BryceCurran86/PlanReader-3D/actions/runs/38651231157),
artifact 11934748920. The new main replay is a **local execution**, not a claim
that this historical Actions run executed current main.

The all-pages diagnostic separately yields
`source_snapshot_7ad8bf09e3ebbec9797df89842574683`. It must not replace or alias
the selected collector root. In the selected root the first schedule/height
reason is partial source coverage; in the independently executed all-pages
root it is `schedule_opening_instance_binding_no_contained_tag`. Both roots
retain `opening_dimension_witness_topology_required` for all 21 oriented widths.
Neither result proves a second dimension is absent from the original PDF.

The eight signed areas are 0.54, 0.90, 1.26, 1.80, 1.80, 2.16, 2.16 and
10.08 m2. The proposed 5.67 m2 STACKER is not one of these receipts. Raster
closure remains 30 raw / 21 resolved / 9 unresolved, with universe completeness
false. Opening count remains ABSTAIN. No evaluator was modified or run here;
no benchmark increase is claimed.

## Observed authority seams

The real trace is source augmentation and nomination in
[`SourceVisibilityProducer._proven_raster_opening_flank_boxes`](https://github.com/BryceCurran86/PlanReader-3D/blob/6bfd22fa8e09b2cbed5ed59a38128157c3bf83af/pb_source_visibility_authority.py#L2161)
then source-owned W2/W4, physical equivalence,
[`OpeningHostBindingProducer.publish`](https://github.com/BryceCurran86/PlanReader-3D/blob/6bfd22fa8e09b2cbed5ed59a38128157c3bf83af/pb_opening_host_binding_authority.py#L482)
and its
[`_resolve_raster_source_band_host_from_records`](https://github.com/BryceCurran86/PlanReader-3D/blob/6bfd22fa8e09b2cbed5ed59a38128157c3bf83af/pb_opening_host_binding_authority.py#L2902).
Selector lookup is `OpeningHostBindingAuthority.resolve`, not a `resolve`
method on that producer. Whole-wall frames pass through
[`OpeningHostFrameProducer._scope_bindings`](https://github.com/BryceCurran86/PlanReader-3D/blob/6bfd22fa8e09b2cbed5ed59a38128157c3bf83af/pb_opening_host_frame_authority.py#L395)
and `_shared_host_frame`, then distinct metric/quantity/sealing producers.

`_proven_raster_opening_flank_boxes` requires a CORROBORATED label receipt with
`area_m2 is not None` to nominate additional source capture. It does not prove
a host. Removing the default gate changes source nomination and historical
host identities; this checkpoint does not remove it. Authenticated G17 faces
are already retained as source evidence even when nomination or W4 membership
fails. Re-emitting those same faces is not a structural repair.

## Case ledger: observations and precise blockers

All opening digests in this table carry `physical_opening_existence_`.
Full IDs and every competing source support are in the JSON.

| Case | Actual first failure on main | Existing authentic source | Remaining proof / owner |
| --- | --- | --- | --- |
| `2c31ccb074d8eae86cac281c0fde1176` | Frame: `opening_host_frame_connected_edge_unproven` | Host `opening_host_binding_v3_a697e7a7a6b492438ada99cf52aaa17a`; members `wall_7d3dcc7ce4afc5c15704`, `wall_b25b5ffd3a29be53747f` | Cursor owns the split-frame correction. Its later aligned-fragment gate still requires independent positive identity proof; MAX has no such proof for the real retained competitor. |
| `dbcec9c3cfa8e22b332479d09a601985` | Frame: `opening_host_frame_aligned_band_geometry_inconsistent` | Host `opening_host_binding_v3_bd08d853e34f452a55e76b3d4439fac7`, member `wall_b689beedb69c1be4eae7`; original stepped band preserved | MAX/source-role reviewer: source-owned segment/transition proof compatible with a reviewed frame contract. Averaging or widening tolerance is not a repair. |
| `a68d0b7d738b5de9a1588b4e680e1a8f` | Host: `raster_source_band_left_source_primitive_unmapped` | Faces 1498/1499 at x=661.44..692.4 and 1515/1516 at x=716.16..760.32, y=426.24/429.36; two original ends; one owned literal 870 | MAX/source-role reviewer: opening-own W4 flank membership and competing raw-source reconciliation. The fresh ordinary W2/W4 audit finds no local parallel source candidate; no transfer of the 1215 neighbour's host or infill run 482. |
| `81a45c3a33c2a4c0bfdf243aa45a780d` | Host: `raster_source_band_right_source_primitive_unmapped` | Shared faces 1449/1453, x=425.28/427.44, y=247.68..252.48; 4.8 pt pier and own end; one owned 870 | Shared pier has no nominated ordinary W4 owner. Cursor has an independent shared-pier follow-up; MAX leaves its edits alone. Positive structural membership and historical-host retention remain required. |
| `f819752382d44a00d9f28feca4b00787` | Host: `raster_source_band_left_source_primitive_unmapped` | Same 1449/1453 pier with the other opening's own end, plus its opposite faces; all conflicting text retained | Same shared-pier owner blocker, plus figured-label CONFLICT (`opening_label_dimension_ambiguous`). Neither neighbour supplies its dimensions or identity. |
| `33d277d4c6b6ce758b0594f9d47ce4d8` | Host: `raster_source_band_left_source_primitive_unmapped` | Faces 1467/1468, (581.04,361.68/363.84)..(584.88,361.68/363.84), and end 1325; length 3.84 pt; one owned 870 | MAX/source-role reviewer: an admissible structural owner under the unchanged 4 pt rule, possibly independently proved composite membership. The source is already preserved; no accepted composite ownership is established here. |
| `b248972669988c108ebc90c6ca3908fd` | Host: `raster_source_band_left_source_primitive_unmapped` | Faces 1480/1484 at x=604.8/607.44, y=191.76..197.52 (5.76 pt), faces 1481/1485 opposite, ends 1328/1329 | MAX/source-role reviewer: genuine solid-flank W4 ownership. No local parallel ordinary raster source candidate is found. Figured label is separately unavailable. |
| `ba7f75a2e5f68bcce87cd00ac1acf90b` | Host: `raster_source_band_left_source_primitive_unmapped` | Short faces 1472/1477 at x=581.04/584.16, y=527.04..533.52 (6.48 pt), opposite faces 1469/1476 and ends 1320/1321; one owned 870 | MAX/source-role reviewer: actual local W4 chain reaching the missing solid flank. Ordinary parent 1749 has three remote W4 members; exact parent ancestry does not elect any as the short flank's owner. |

### 2c31: candidate exclusion is not DISTINCT

The actual ordinary 144-DPI source parent suffix `:1583` is
`raster_segment:64e58ab817b1b89d3c83e0e04a972f5e4e48fa3816d346af9cc809b9b56357ab:1.0.0:1583`,
observation `source_observation_aa9499d9571b6ad115745535d68c4831`, source line
(408.75,586)..(408.75,624.5). Retained W4 addresses include
`wall_3c9933f91a1a3079fcf3` and `wall_6cbf01ceb337722e0c4c`, including its
snap-collapsed source fragment. Their relations to both original host members
are UNRECORDED in the actual published scope.

Re-evaluating the existing pair-candidacy predicate on serialized identities
returns `pair_excluded_no_longitudinal_overlap` for all four pairs. This is
explicitly a diagnostic replay, not new authority. A second actual
`RasterPlanDimensionProducer.publish` probe on the same selected root returns
`raster_dimension_orthogonal_scope_unavailable`, retaining two candidate bound
dimensions elsewhere and none owning this fragment. Visual inspection of the
original dimension/PCD region does not supply missing source-role or positive
wall-equivalence authority. **Positive DISTINCT remains UNPROVEN.**

This opening already has signed quantity
`opening_area_4227fdeb71838722a4a7f0251c3dda60`, 10.08 m2. The frame is not a
new area opportunity. `dbce` likewise already has
`opening_area_6809b61112132ffd701e6eae02076876`, 1.26 m2. Preserve both
figured-label area contracts while geometry remains incomplete.

### dbce: the first comparison and the local step are separate facts

A transparent, delegating trace of the actual `_scope_bindings` call captures
the first failing comparison against
`physical_opening_existence_91ae06327d4fcc8004a557b116a77820`: its origin is
(645.12,193.68), thickness 3.36 pt, versus dbce at (346.8,194.16), thickness
2.40 pt. Both existing comparison tolerances are 0.75 pt. The actual published
wall scope positively classifies the other host `wall_44435f10931bfe1d18b4`
DISTINCT from dbce's `wall_b689beedb69c1be4eae7`. This is an observed positive
classification, not a no-overlap inference.

Separately, dbce's own source faces 1405/1406 have y=192.96/195.36, while its
other flank faces 1438/1439 have y=192.0/195.36. The local 2.40/3.36 pt step
is real source geometry. Both authenticated source end records and all parent
addresses are retained in the JSON. The transparent call returned exactly the
same 21 bindings and 21 frame decisions as the uninstrumented selected run.

**PROPOSED, not implemented in Cursor's module:** a component-aware shadow
could authenticate and retain all aligned contexts, establish the complete
connected host component, then apply thickness consistency within that
component. Outside contexts may be excluded only with positive DISTINCT
against every component member, including members reached through other
openings. A pairwise skip against only the selected binding is insufficient.
Even if this advances the first remote comparison, the original local step
still needs a compatible source-supported frame representation. No valid
constant-thickness frame is established by this checkpoint. No averaging,
new tolerance or quantity follows from the proposed ordering change. The
exact source finding was handed to Cursor for review without changing its
frame/motif module or stack.

## Corrections and review queue

No additional structural correction passed the source-proof threshold in
this run. The six unhosted cases remain source-owner blockers; the two hosted
cases remain whole-wall/geometry blockers. No existing authenticated evidence
is silently promoted or discarded. Changing one threshold or skipping a
competing primitive would not recover a justified output.

Concrete owned changes made separately:

| PR | New head | Reviewable change / gate |
| --- | --- | --- |
| #2791 | `6e14def07e455133e7ab932d562cffdba9eaf6e7` | Add main trigger; original run [38835555139](https://github.com/BryceCurran86/PlanReader-3D/actions/runs/38835555139). |
| #2792 | `4a08c9dc85fc7710cbd569a2582922687149e8e2` | Repair main trigger on its own and inherited workflow; original run [38835609620](https://github.com/BryceCurran86/PlanReader-3D/actions/runs/38835609620). |
| #2795 | `14a5d1b19349176d70ecf8b6ff6890f4e61dffb2` | Repair three inherited workflow copies; run [38835620346](https://github.com/BryceCurran86/PlanReader-3D/actions/runs/38835620346). |
| #2797 | `8359938cdbe5fc1119308a98780f5305f34858a1` | Repair four inherited workflow copies; run [38835629383](https://github.com/BryceCurran86/PlanReader-3D/actions/runs/38835629383). |
| #2803 | `510ab49713e64d83bb70b507e27be6bc9048e2fa` | Retain parent and add main trigger; run [38835638795](https://github.com/BryceCurran86/PlanReader-3D/actions/runs/38835638795). |
| #2804 | `42da25092fb6fcd9ad4b406333619bd1ab6c6d6f` | Restore main alongside parent trigger; run [38835645636](https://github.com/BryceCurran86/PlanReader-3D/actions/runs/38835645636). |
| #2754 | `7421e26d8a5f18ae75dd36f987dcb2a3f8641974` | Address Claude's missing synthetic matrix: 12 source-generated cases; 25 tests pass locally; workflow includes the file; original run [38836360956](https://github.com/BryceCurran86/PlanReader-3D/actions/runs/38836360956). |

Six distinct workflow files had 12 stale branch copies in total. Only the
branch trigger lists changed; jobs, permissions, source assertions and parent
triggers were retained. Full current-main trigger/source-membership suite:
205 tests passed. #2748's eight focused files: 164 passed locally. #2754's
dedicated + existing binder/label cases: 25 passed locally; ruff F821/F823 and
diff checks passed. Actions status is live at the links; a queued or skipped
required job is not a pass.

#2748 remains at `815aaa72810cd48e2cb48ce1142cbe1841911ebb`. Claude's requested
`_graph` signature union depends on their single #2770/#2771/#2805 integration
branch. MAX coordinated on #2771 and did not edit shared stage A or Cursor's
frame modules. After integration, rebase #2748 and rerun its original source
and actual customer parity job; the old-head success cannot certify the new
union. Owner/independent-review identity B1 remains a release gate, not a
reason to stop independent preparation.

#2799 was already closed. Independently compared all four paths with merged
#2801 and current main: tool/tests are byte-identical, main retains #2801's
workflow/doc exactly, and the old differences are only parent trigger and
stack description. No unique executable work is lost; no second close action.

## Consumer handoff and next action

GPT1 receives no new complete host/frame/type/metric bundle from MAX here.
The JSON preserves each genuine opening's own source/label evidence and the
exact metric failures, including f819's conflict and b248's missing label.
An owned literal 870 remains one unordered number, not a height or measured
area. Cursor's three unsigned frames stay in Cursor/GPT1's separate review
lane. GPT3 can verify the unchanged existing quantity receipts; there is no
ninth receipt to seal. No new benchmark match is counted.

The next structural implementation requires one of the missing positive
proofs in the case ledger, with architecture/source-role review and a
default-off retention-preserving change. Do not retry the disproven area-gate
removal, inclusive-cell nomination, no-overlap DISTINCT, wider snap, lower
minimum, host transfer or averaged thickness proposals without new evidence.

## Reproduction

Run from the pinned repository with its pinned dependencies. Set `PYTHONPATH=.`.
`PDF` below addresses the immutable source; its filename is not a prediction
input.

```bash
PDF='documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf'
python tools/diag_gptmax_source_authority_stages.py --pdf "$PDF" --page-id 3 --include-unhosted-raster-flank-source --output /tmp/max-selected-source.json
python tools/diag_gptmax_source_authority_stages.py --pdf "$PDF" --page-id 3 --source-all-pages --include-unhosted-raster-flank-source --output /tmp/max-all-pages-source.json
python tools/diag_gptmax_raster_host_source_membership.py --pdf "$PDF" --page-id 3 --expected-source-sha 10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844 --output /tmp/max-original-w2-ancestry.json
python tools/run_gpt3_lot16_original_sealed_score_input.py --pdf "$PDF" --output-dir /tmp/max-fresh-original-seal
```

The final output directory must be fresh. The last command performs the
existing collector/sealer/customer verifier; it is not the frozen evaluator.
The JSON's dimension-probe result is from the existing producer's public
`create(source_visibility=source)` and `publish(revision_id=...,page_id='3')`
on the already-composed selected source, with no test OCR backend or supplied
dimension coordinates. Its serialized results carry no authority.

To inspect the dbce first failure without replacing a producer, use the
standard debugger on the pinned source-stage command, break at
`pb_opening_host_frame_authority.py:481` conditioned on
`selected_opening.record_id == 'physical_opening_existence_dbcec9c3cfa8e22b332479d09a601985'`,
and inspect `opening.record_id`, `selected_geometry`, `geometry`, `center_tol`
and `thickness_tol`. Resolve both host member IDs in the same published wall
scope's `equivalence.pair_classifications`. The preserved trace is a local
delegating observer of this exact failure, not a modified authority result.
