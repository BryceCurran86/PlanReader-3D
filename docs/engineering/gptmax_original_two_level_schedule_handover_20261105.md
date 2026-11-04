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