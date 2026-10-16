**Claude independent technical review — GPT1 integrity fixes #2735 (head `11f84350`) and #2732 (head `01092b8b`), both base `b48c3ad6`.** Review COMMENT only; shared login, not a formal APPROVE; not merged by me.

- **#2735** (`pb_live_floor_area_quantity_publication.py`): adds `_valid_original_source_sha` (exactly 64 hex chars, `type(value) is str`) as an extra restrictive gate before a FIRM floor reissue and before a canonical-room reissue; a malformed room SHA now abstains that room only instead of raising `AttributeError`. No new resolver, no id derivation change (no quantity id can move), no schema change. All checks pass at the head (8 ok / 0 fail); the exact original Maryborough 3 FIRM floors / 3 seals / 3 customer rows workflow (`test-gpt2-source-room-handoff-integrity.yml`) repeats. My independent re-verification of the archived Maryborough signed run (3 FIRM, ids unchanged) agrees.
- **#2732** (`pb_live_ceiling_area_quantity_publication.py`): same predicate for canonical ceiling SHA; the new original 3Laurel partial-source job asserts `ceiling_area == 0`, `benchmark_score_granted False`, `complete_project_handoff False`. Restrictive only.
- Neither touches benchmark-defining files, scale, the 20,000 cap, W10 flags or customer projection. Main's commits since the base (#2745) touch only `pb_g17_*` files - no overlap.
- Caveat both PRs state correctly: a well-formed 64-hex string is only a *well-formed identifier*; it never proves the original PDF. Keep the producer's independent SHA verification mandatory.
- Minor test gap: add a positive control with upper-case hex to pin the deliberately preserved case folding.

**Eligibility:** technically complete, restrictive, exact-head green; eligible for authorised integration.
