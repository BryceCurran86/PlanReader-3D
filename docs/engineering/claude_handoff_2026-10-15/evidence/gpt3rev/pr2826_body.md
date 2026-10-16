Hardening found by the strict-xfail matrix of #2821 (GPT1); reproduced independently (comment on #2821).

**Problem.** `QuantityEvidence.__post_init__` forbids an *abstained* quantity without blocking reasons but allows a value-bearing, FIRM-looking one to carry them. `build_gross_wall_area_quantity` checked `abstained`, `value`, `status`, authority and provenance but never `blocking_reasons`, so `replace(firm_length, blocking_reasons=("original_source_conflict",))` still published a FIRM 12 m2 (AGENTS.md: unknown, conflicting, stale or ambiguous evidence must abstain).

**Change.** Two conditions in `pb_wall_gross_area_quantity.py`: a non-abstained length or height that still lists blocking reasons adds `wall_length_source_blocked` / `wall_height_source_blocked` and the gross area abstains. An abstained parent keeps exactly its previous reasons.

**Safety.** No builder emits FIRM with blockers (`pb_wall_length_quantity`, `pb_wall_height_authority` pass `blocking_reasons` only on abstaining paths) and `build_gross_wall_area_quantity` has no production caller outside tests, so no published quantity can change; the signed Lot16 / Maryborough outputs do not involve wall gross area. The new tests (`tests/test_wall_gross_area_contradictory_parent.py`, 9 cases) fail 7 of 9 without the guard and pass with it; together with the 82 existing gross-area tests: 91 pass.

When this lands, the two strict xfails in #2821 become XPASS and must lose their markers. Owner for the Q07 follow-up: GPT1.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
