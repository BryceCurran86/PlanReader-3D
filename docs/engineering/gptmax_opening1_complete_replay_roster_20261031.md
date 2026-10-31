# GPT MAX — OPENING-1 complete replay roster handoff (2026-10-31)

**Status:** source-neutral candidate for #4145, stacked; no original-positive acceptance, no score, no merge until required tests/replay.

## Observed production behavior

`collect_live_physical_net_wall_claim(recover_supported_opening_areas=True)` enters the existing original-source opening replayer from the PDF extractor, workspace, and project handoff. `recover_source_opening_areas` builds `voids.canonical_openings` from one original-source replay and the actual publisher checks that entire producer roster. `_append_reproved_areas` then retains historical canonical objects plus the new measured objects, dropping fresh-only unmeasured/abstained source siblings. The resulting `LivePhysicalNetWallClaim` has no way for GPT1's subsequent preflight to distinguish a full fresh replay from a conveniently truncated subset. Existing signed eight are preserved; PR #4145 reports a ninth through the actual customer adapter but is not yet an official evaluator increase.

## Inference

Dropping an unsupported source sibling is a loss of negative evidence, even if the sibling cannot itself issue an area. A new area cannot borrow the baseline's signed identity or resolve a conflict merely because an unsupported rival was omitted. Retaining the typed roster separately does not grant measured authority; it permits an independent downstream source-closed review without merging independent snapshots.

## Narrow implementation

- Add an optional immutable `opening_area_replay_source_inventory` tuple to `LivePhysicalNetWallClaim`. An ordinary collector result stays unchanged.
- For an actual append, verify a single original document/revision/SHA/snapshot scope and unique physical IDs in the full fresh roster. Store **all** fresh canonical objects, including unmeasured siblings, in deterministic order. Preserve historical `canonical_openings` and `opening_quantity_evidence` exactly as before, appending only validated measured additions. The witness is not exported as an opening count, net-wall void or customer row.
- Reject a fresh-only unmeasured sibling with the same physical ID, the same nonempty source observation roster or the exact same nonempty source geometry as a newly measured opening. This is a definite alias veto, **not** a complete identity equivalence authority. More complex rivals remain present for the source-owned GPT1 consumer to adjudicate.

## Synthetic gates and actual release gates

Focused production composition tests cover an unmeasured source-only sibling surviving in the witness but not the customer rows, an equal-source-observation collision, a same-geometry collision, and a foreign snapshot. Existing signed retention, optional/native/default and source floor-plan scope tests must continue passing.

The stacked #4145 source replay and customer output still require a trusted SHA-pinned original Lot16 execution on the final head, immutable eight signed/customer bodies and exact ninth source identity, complete GPT1 sibling/lineage review and GPT3 unchanged frozen four-project scoring. **This patch alone must not be merged as commercial opening authority.** Because original binaries are private, public CI is not original-source proof.

## Benchmark firewall

No expected BOQ, scoring threshold, benchmark denominator, labels, private PDF contents or source identities are used as prediction inputs. The frozen 120-item benchmark, 20,000 primitive cap and 2.5 pt snap are untouched.
