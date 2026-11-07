# GPT MAX — two-level door schedule parser first gate (2026-11-05)

## Observed repository behaviour

- The existing production caller `pb_opening_production_v175.extract_schedule_entries` calls `pb_opening_schedule_v171.parse_schedule_page`, which obtains `_word_rows` and calls `parse_schedule_rows`. Its B2 `ScheduleEntry` type is not a physical opening.
- In the existing parser, `_is_header_row` returns true if *any* mark-like **or** dimensions-like heading appears. `parse_schedule_rows` stops at its **first** match and uses that column map for all following text. A door-notes row containing `DOOR` can therefore intercept the real schedule header. This structural failure is directly visible in code.
- The paused agent's **handover report** says that the Maryborough page-28 printed 28-row door schedule yielded only two parsed rows, after a text rotation experiment, and that the original page-7 tag scan had 4 tag+schedule matches but no dimensions. These are observations *reported by the handover*, not independently rerun on this branch.
- An independently source-owned A600 door-schedule authority (`pb_source_door_schedule_authority.py`) already exists. The B2 compatibility parser is not allowed to override its source-integrity or physical/metric authority.

## Inference (not yet original-source proven)

- First-match header selection may explain missing schedule dimensions, but loss of spatial row grouping in `_word_rows` or missing trust/column binding could be an independent upstream gate. Rotation alone is not sufficient evidence for either fix.
- A strict opt-in candidate may recognize a two-level header if a following heading explicitly combines a mark column and a size column (or both separate width/height columns). Without such a unique schema it should return no results. No "first available" semantic tie-break is authorized.

## Proposed bounded change

- Add an opt-in, **default-False** two-level-header mode to the existing B2 parser and page wrapper. Leave the production caller unchanged until an original page run proves that its source-native rows contain the required complete headings and correct table membership.
- Do not harvest notes rows preceding the schedule header. Accept repeated *identical* explicit schemas, but abstain on competing incompatible schemas. Do not infer dimension basis from generic Width/Height, schedule counts from row count, wall/instance ownership or an opening from a schedule row.
- Start with source-neutral positive, misleading-header and conflicting-header regression tests. Next gate is the existing owner-trusted SHA-verified original Maryborough producer→tag/schedule→consumer run, checking all source identities and current signed/customer retention. If page-28 native rows are already malformed before this parser, fix the existing source row builder rather than invent values.
- The original #4194 owner-labelled study and 3Laurel p3 text-trust failure remain separate; no quantity, FIRM, evaluator or frozen120 score effect is claimed.

## Benchmark observations excluded from implementation

The frozen four-project 120-item score and expected quantities do not inform the header recognition or parser negatives. No benchmark-truth files, private PDFs, source receipts or score tolerances are modified.

## Files/ownership

Claimed for this bounded work: `pb_opening_schedule_v171.py::{parse_schedule_rows,parse_schedule_page}`, new `tests/test_gptmax_two_level_schedule_header_shadow.py` and this report. Protected GPT3 release pins, source-owned A600 producer/consumer, physical host/frame, GPT1 takeoff, original PDFs and #4194 remain untouched.

## Subsequent live consumer correction (same bounded case)

Read `pb_schedule_opening_instance_binding_authority._header_table_specs` and its existing `_schedule_entries_for_page` consumer, which extracts rows from producer-owned `SourceVisibilityProducer` trusted text with printed geometry. The live source-owned binder previously accepted mark+notes/description alone as a schedule table. Such a header could admit an unrelated labeled note as `ScheduleOpeningInstanceBindingRecord` with neither printed width nor height; `BINDING_RESOLVED` still reported source row ownership, not metric authority.

The narrowly claimed additional change requires mark plus combined dimensions, or mark plus both separate width and height. Other type-only/notes-like text cannot masquerade as a dimensioned schedule table, while explicitly drawn side-by-side complete tables remain individually discoverable and competing rows still fail closed. The new tests call the *real binder's* `_header_table_specs` and `_schedule_entries_for_page`, exercising notes-before-real-table, complete/compound and side-by-side cases.

**This is a live correctness/safety change, not yet a confirmed Maryborough recovery.** The handover's original A600 printed header has multiple native groups and a rotated coordinate frame; selecting a complete header from one flattened source row alone may still abstain. A source-backed next step must bind native column ownership already represented by `pb_source_door_schedule_authority._original_door_schedule_column_proof`, with source metric unit proof before mapping numeric fields into `*_mm`. A lexical integer is not an authenticated millimetre dimension. Preserve the original SourceDoorScheduleResult rivals and source word IDs. Enabling the optional compatibility parser in the live path would require the same original-positive source/physical/customer validation.

For 3Laurel, the original text-trust diagnostic already attributes the zero-native-trust gate primarily to subset Type0 Identity-H fonts without an independently verifiable Unicode glyph cmap. Existing raster corroboration and amortized glyph shadows are the appropriate producers; do not grant trust from ToUnicode alone. No 3Laurel font, tag or quantity promotion is made in this PR.

Full source-neutral Python3.13/3.14 CI and trusted owner-original replay are still required for the current exact head, and all candidate impacts remain unscored.

## Current-main integration repair — 8 November 2026 Brisbane

MAX reconstructed the schedule stack on main `e5dfdd517`, then included the exact room/wall integration from #4237 without changing its nine blobs. The old stack conflicts with main's `compose_live_physical_opening_voids` signature and validation: main now supports explicit target-owned/owner-approved second-axis records and refuses page-wide door-height inference. The repaired composition retains those inputs and refusals, adds the independent strictly Boolean default-off rotated schedule option, and preserves the existing physical/metric issuer prerequisites. It does not infer a missing height or turn a source schedule row into an installed opening.

The complete #4201/#4203/#4204 history is retained under #4212. No blanket merge of unrelated stale release stacks is involved. Source-neutral checks on the combined tree: 149 passed. Two existing A600 original-only tests were deliberately deselected locally after confirming the originals are available only in the private companion repository; both must execute and pass in the protected run, not be counted as local passes. Final-head full Python 3.13/3.14 CI, actual source cases and historical customer retention remain required. Current main's baseline is eight Lot16 signed/customer quantities, three Maryborough room areas and the separate Q5446 customer positive. A candidate or source-row count establishes no additional customer measurement or score.
