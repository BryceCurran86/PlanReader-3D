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

## Source partition consumer — 2 November 2026

Observed: `recover_source_opening_areas` compares a new area only with baseline competitors, while `_append_reproved_areas` rejects every shared observation even when it is wall support between separate gaps. Claude #4147 now supplies extent-first `partition_receipt` and recomputing `verify_partition_receipt`; its old source-ID-only shortcut is removed. The real original explicit recovery separately fails immutable historical representative/source geometry retention. Default eight signed/customer bodies pass byte retention on both Python versions.

Inference: a source-owned partition can distinguish shared wall support from competing aperture readings, but cannot authenticate a changed historical representative, missing rival, host, figure or metric void. A caller's receipt list or record IDs are insufficient.

Proposed integration: have the original replayer pass its concrete physical-opening authority to the existing composer. Reprove both canonical objects' exact source scope, representative geometry, members and lineage, then obtain and independently verify the authority's pairwise receipt for every fresh rival. Permit shared members only with that verified physical partition. Preserve unconditional same-physical-ID, exact-geometry and complete metric-overlap negatives, the historical immutable-source guard, and the final source-snapshot check. No new authority or receipt allowlist is introduced. Tests use real generated PDF producers and the existing issuer/sealer/customer path, with wrong-pair, altered-source, stale-snapshot, overlap and inventory-order controls.

Benchmark observations are excluded from prediction and tests. Original-source reports remain private. This is a throwaway integration of the fixed Claude dependency with the existing MAX branch; no source or customer promotion is inferred from synthetic success.

### Source-authenticated representative reissue

Actual immutable original execution of the combined tree proves all 21 new-opening/rival partitions (20 disjoint, one partitioned shared-support pair), with exact canonical/source binding. Default eight signed/customer retention passes both Python versions. The remaining failure changes only an unsupported historical candidate's representative and its representative-line geometry; physical identity, complete member roster and lineage are unchanged.

The canonical `source_geometries` field contains the representative observation geometry, not an aperture boundary. A changed representative must not be forced back to an ambiguous selector. Proposed narrow exception: only for an unmeasured historical object with unchanged nonrepresentative physical core, members and lineage, reprove the fresh canonical object through the concrete source authority and independently authenticate the old representative's exact unchanged raw source observation in that same source scope. Both representatives must remain members of the same producer-issued physical record. All pairwise partition checks still apply, and the returned historical canonical object stays byte-identical. Missing raw source, altered geometry/membership/lineage, foreign physical identity and measured-row rewrites remain conflicts. No guessed retirement or equivalence receipt is created.
