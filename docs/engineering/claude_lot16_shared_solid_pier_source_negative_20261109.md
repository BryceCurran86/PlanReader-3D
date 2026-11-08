# Claude — Lot16 shared solid pier: no false opening on current main (test-only regression), plus 3Laurel external-door audit

Date: 2026-11-09. Base: `origin/main` `22ebd4e3c`. Branch `claude/lot16-shared-pier-source-negative-20261109`. Shadow and test only: **no production module, benchmark-defining file, identity map, signed fixture, snap (2.5 pt) or primitive cap (20 000) is changed.** Counts, ids and point coordinates only; no private drawing text, names or addresses are repeated.

## 0. Compliance block (AGENTS.md)

- **Read this session:** `AGENTS.md`; the 6 Nov handover (pier lines); `gptmax_81a45_f819_shared_pier_20261016.md`; `gptmax_lot16_33_accuracy_gates_20261016.md`; `gptmax_lot16_host_source_queue_20261016.md`; `lot16_original_signed_eight_row_20261015/README.md`; #4135 comments 6717887739 (assignment), 6719067608, 6720598612, 6723106839. `docs/AI_ENGINEERING_PLAYBOOK.md` was **not** re-read in this session.
- **Traced (real call path, Lot16 page 3):** `compose_live_wall_opening_authority` → `SourceVisibilityProducer.augment_with_raster_opening_primitives` / `augment_with_unmeasured_g17_flanks_source_shadow` → `PhysicalOpeningAuthority.prove_existence` (aperture bbox, `CandidateSemanticOpening`, `PhysicalOpeningExistenceRecord`) → `OpeningHostBindingProducer` → `OpeningHostFrameProducer._shared_host_frame` / `publish` → `collect_live_physical_net_wall_claim(recover_supported_opening_areas=True)` → `recover_source_opening_areas` (`pb_live_append_only_opening_area_composition`) → `pb_opening_label_dimension_authority.figured_opening_label_area` → `seal_live_opening_area_claim_run` → `project_live_opening_customer_rows` → `verify_sealed_customer_output`.
- **Authority boundaries crossed:** none changed. Every seam above was only *called*.
- **Untouched:** all `pb_*.py` modules, `tools/`, `benchmarks/frozen_holdout/full_plan_v2/`, `documents/sources/`, `docs/engineering/lot16_original_signed_eight_row_20261015/`, both identity maps, the 2.5 pt snap, the 20 000 cap, `takeoff_eligible=False` on W10.

## 1. Observed repository behaviour (original Lot16, SHA `10109b4b…`, page 3, current main)

| Measure | Result |
|---|---|
| Physical opening existence records | 22 (all `CORROBORATED`; 16 get a corroborated whole-wall frame, 6 abstain at host or frame) |
| Semantic enumeration | 4 093 visible observations; 22 representatives; 690 residual (none has an existence record) and 385 conflict observations (4 of them resolve to two of the 22 existing door-swing records; the rest are unresolved) |
| Adjacent aperture pairs on one wall line (i.e. a pier between two openings) | 9 (8 horizontal, 1 vertical) |
| Existence / residual / conflict observations inside a pier interior | **0** opening candidates. The only unresolved observations that touch a pier interior are 4 perpendicular wall lines and 1 page-long wall line, in four piers of the y 194 pt wall line, all `visible_wall_continuation_required` (abstained) |
| The door/stacker pier (south wall: x 716.16 to 760.56 pt, y 426.24 to 429.6 pt, 44.4 pt) | **no observation of any kind**; the door aperture ends at 716.16 and the stacker aperture starts at 760.56 |
| Signed-eight physical identities | all 8 are among the 22 records |

Pier spans (pt): 83.76, 29.76, 61.68, 87.12 (wall line y 194); 155.52, 23.04 (wall line y 298); 31.20 and 44.40 (wall line y 428: window/door and door/stacker); 5.04 (wall line x 426: the 4.8 pt pier shared by the two openings that the 16 Oct note already records as host-unmapped).

## 2. Synthetic proof (new test file, 18 tests including 1 control, no source PDF needed)

Two framed raster gaps separated by a solid pier, drawn at 2 px per point:

- pier 20 / 45 / 80 pt → exactly 2 records, each equal to its gap columns (±3 px), none reaching into the pier;
- translation (0, 30, 100 pt) and horizontal mirror: same two openings, moved with the sheet, pier still clear;
- look-alike pier renderings (outline only, two faces without caps, diagonal hatch poche, chase through a solid pier): **no record on the pier** (the pipeline abstains for all four rather than minting a third opening);
- 3 pt and 8 pt piers: neighbours abstain; **no record spans both gaps** (they are never merged);
- deterministic replay (one source byte string, because PyMuPDF stamps a random trailer `/ID`) and no mutation of the input array or bytes;
- a control (no pier at all) merges the two gaps into one aperture and trips both assertions, so they have teeth;
- two helper checks pin the pier finder and overlap measure used by the original-source test so that it cannot pass vacuously.

## 3. Original-source regression (private PDF, read in place, skipped when absent)

`test_lot16_original_every_shared_pier_stays_wall_and_the_signed_eight_identities_remain` composes page 3, finds every pier between consecutive apertures on a wall line, requires the south door/stacker pier to be one of them, requires **no existence record to overlap any pier interior**, and requires all 8 signed physical identities to be present. It ran green on this machine in 6 min 11 s (`PLANREADER_LOT16_ORIGINAL_PDF` or `documents/sources/…`).

## 4. Measured production output (local, original PDF, no code change)

| Run | Result |
|---|---|
| `tools.run_gptmax_original_retention_check --project lot16` at head `91acb7ecd` (clean tree) | `retention_verified: true`; `source_sealed_run.json` and `verified_customer_rows.json` **byte-identical** to the signed archive |
| `tools/run_source_closed_project_handoff.py --family-group core` (uniform door-height shadow hard-coded off) | status `sealed`; `opening_area` = **9** quantities: the signed eight with identical values, plus the 2127 stacker (5.67 m², `figured_opening_label_area`); `claim_status: abstained` and `verified_customer_row_count: 0` in this path; owner door-height template lists 7 Lot16 doors |
| `tools.run_gpt3_lot16_original_sealed_score_input --recover-additional-opening-areas` | 9 sealed quantities, **9 verified customer rows** (`PROVISIONAL` / `To review`), signed eight identical in identity and value, plus the stacker |

So the default signed output is 8; the explicit-recovery output is 9; the ninth is the stacker, the opening that sits next to the shared pier, and its aperture does not reach into it.

## 5. Inference and decision

The shared solid pier is never counted as an opening on current main, in the original or in any synthetic or look-alike rendering. The earlier 16 Oct notes (`81a45`/`f819`, `a68d`, `33d2`) describe the **opposite** failure: piers that are not nominated as wall, so a neighbouring opening has no host. That is a missing-wall problem, not a false-opening problem, and it stays ABSTAIN. **Proposed production change: none.** The regression above locks the behaviour in.

## 6. 3Laurel external doors (audit, page 3, current main, same core runner)

| Measure | Result |
|---|---|
| Sealed `opening_area` quantities | 35 |
| Identity-map bindings reproduced | **19 of 23** |
| Not reproduced | the 3 external single-figure doors (main entry, ground-floor entry, garage personnel) and one two-figure sliding door |
| Doors in the owner height template (could be approved) | 6, none of them one of the 3 mapped external doors |
| Customer rows in this path | 0 (claim abstained) |

The three mapped door ids were added on 7 Nov under the page-uniform door-height shadow, which main now refuses (`compose_live_physical_opening_voids` raises; the handoff forces it off). On current main they are neither sealed nor approvable, so the 23/23 count is 19/23 here. Cause is inferred from the code and dates; the old configuration was not re-run. No height was invented and no approval record was written.

## 7. Not proven

- Python 3.14, protected private-runner replay and Maryborough three-quantity retention (Tesseract is not installed on this machine): not run here. This change touches no production module, so they are expected to be unaffected, but that is not a measurement.
- 3Laurel numbers use RapidOCR on this machine; the protected environment may differ.
- The stacker is not part of the signed default; promoting it to the default customer path is a commercial-output change that needs the separate authority-promotion review.
- No benchmark item is newly scoreable from this change.

## 8. Benchmark observations that must not influence implementation

Item ids, trades and units were read for planning only; no expected quantity, tolerance or object reference was read. The two identity maps were used only to compare which already-produced physical ids they bind; nothing in the tests or the producer depends on them.
