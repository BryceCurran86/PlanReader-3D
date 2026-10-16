# GPT MAX — next 33 Lot16 gates (21 schedule + 12 height)

Issue #2396. Original Lot16 SHA256
`10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`, page 3,
snapshot `source_snapshot_3fcb6bc5c44b51d930e9600080501d27`.

Traced `compose_live_wall_opening_authority` →
`compose_live_physical_opening_voids` →
`ScheduleOpeningInstanceBindingProducer.publish_scope` →
`OpeningHeightProducer.publish_scope` →
`OpeningVerticalPlacementProducer.publish_scope`. No measurement seam.
`#273` ranking was not consulted. Default frames stay 9. This census
publishes 0 void records. It does not replace the eight signed
opening-area quantities, which remain on `OpeningLabelDimensionProducer`.

## Observed repository behavior

Page-3 ingest coverage is not `complete`.
`ScheduleOpeningInstanceBindingProducer.publish_scope` returns
`schedule_opening_instance_binding_partial_source_coverage` before
aperture, tag, or schedule-row lookup
(`published.coverage.state != "complete"` or `failed_pages`).
`OpeningHeightProducer` and `OpeningVerticalPlacementProducer` copy that
binding reason. They do not call `OpeningDimensionAuthority.resolve_height`.

The 2026-10-12 queue sentence that all 21 height traces abstain at
`schedule_opening_instance_binding_no_contained_tag` is stale for this
page-3 path. That code is later in the same function and is not reached
while coverage is partial. Do not describe the current first fail as a
missing plan tag.

All 21 widths remain `opening_dimension_witness_topology_required`.
All 21 scales remain `physical_scale_bar_unavailable`.
All 21 voids remain `opening_universe_completeness_record_unavailable`
plus `physical_opening_void_universe_incomplete`.

## Tasks 1–21 — schedule binding

Every page-3 physical opening. Status ABSTAIN. First reason
`schedule_opening_instance_binding_partial_source_coverage`.

| # | Opening |
|---|---|
| 1 | `physical_opening_existence_00d50eb9ef77840451522efdc25f2df5` |
| 2 | `physical_opening_existence_2b2a91e8afaf8b7e9a3e07605a80a4a9` |
| 3 | `physical_opening_existence_2c31ccb074d8eae86cac281c0fde1176` |
| 4 | `physical_opening_existence_33d277d4c6b6ce758b0594f9d47ce4d8` |
| 5 | `physical_opening_existence_38c03575cd66ed19cae7f9e4489f1609` |
| 6 | `physical_opening_existence_4b8c096b603c87f06f2692aa00494ab8` |
| 7 | `physical_opening_existence_661fc5e6f0c5975d5e9bdd5d759bd180` |
| 8 | `physical_opening_existence_81a45c3a33c2a4c0bfdf243aa45a780d` |
| 9 | `physical_opening_existence_86236fe338e5f5efb4cddf273a5013ff` |
| 10 | `physical_opening_existence_8ecb81b6524804c80710ec323050be6b` |
| 11 | `physical_opening_existence_91ae06327d4fcc8004a557b116a77820` |
| 12 | `physical_opening_existence_a68d0b7d738b5de9a1588b4e680e1a8f` |
| 13 | `physical_opening_existence_ab431bf4eca30b24da97e2fe3b0f424b` |
| 14 | `physical_opening_existence_b248972669988c108ebc90c6ca3908fd` |
| 15 | `physical_opening_existence_ba7f75a2e5f68bcce87cd00ac1acf90b` |
| 16 | `physical_opening_existence_bd108c2c1bfd88752311aab5901737bb` |
| 17 | `physical_opening_existence_c3c1e04acd78419e4f707dfcd89c7096` |
| 18 | `physical_opening_existence_c4d87543028146e1cff0b5e2ca480c55` |
| 19 | `physical_opening_existence_dbcec9c3cfa8e22b332479d09a601985` |
| 20 | `physical_opening_existence_f5adf8438fb6f48cc03b03d8ca2125f5` |
| 21 | `physical_opening_existence_f819752382d44a00d9f28feca4b00787` |

## Tasks 22–33 — height on openings without a default frame

Same binding reason. Height is not a millimetre. Vertical placement
copies the same reason. These twelve still have no default complete frame.

| # | Opening |
|---|---|
| 22 | `physical_opening_existence_2b2a91e8afaf8b7e9a3e07605a80a4a9` |
| 23 | `physical_opening_existence_2c31ccb074d8eae86cac281c0fde1176` |
| 24 | `physical_opening_existence_33d277d4c6b6ce758b0594f9d47ce4d8` |
| 25 | `physical_opening_existence_4b8c096b603c87f06f2692aa00494ab8` |
| 26 | `physical_opening_existence_81a45c3a33c2a4c0bfdf243aa45a780d` |
| 27 | `physical_opening_existence_a68d0b7d738b5de9a1588b4e680e1a8f` |
| 28 | `physical_opening_existence_ab431bf4eca30b24da97e2fe3b0f424b` |
| 29 | `physical_opening_existence_b248972669988c108ebc90c6ca3908fd` |
| 30 | `physical_opening_existence_ba7f75a2e5f68bcce87cd00ac1acf90b` |
| 31 | `physical_opening_existence_c3c1e04acd78419e4f707dfcd89c7096` |
| 32 | `physical_opening_existence_dbcec9c3cfa8e22b332479d09a601985` |
| 33 | `physical_opening_existence_f819752382d44a00d9f28feca4b00787` |

Tasks 25, 28 and 31 are the three 870 shadow frames. Shadow frame
identity does not grant schedule, height, vertical, scale, or void.

## Inference

Partial coverage is the page-3 ingest contract, not a missing tag.
Completing coverage inside the wall composition would pull every other
sheet into the same snapshot. That is a different source scope. It must
not be used to mint a schedule row, a height, or a void.

## Proposed change

None. Keep ABSTAIN. Do not weaken the complete-coverage predicate. Do
not copy a schedule height from an uncontained tag, a label area, or a
typical door height. A later shadow may ingest complete original coverage
and then stop at the real tag or row predicate, only after this page-3
snapshot and the nine default frames stay unchanged.

## Benchmark observations that must not influence implementation

Lot16 Full Plan V2 8/27, expected BOQ, and schedule millimetres were not
used as prediction inputs.
