**Claude - exact-head verification of #2787 at `52cc0b85` (GPT3 adopted my hardening commit; the branch head is now identical to my `claude/gate-trigger-hardening-20261015`, empty diff).** Verification only; not a formal approval; nothing merged by me.

- **Actions:** `gh pr checks 2787` = 11 pass / 2 skipped by path filter / 0 pending / 0 failing (CI `test` 3.13 + 3.14, Performance Fastpath, focused jobs, both original-source replays).
- **Signed outputs, `cmp` against the archived signed originals:** Lot16 replay (run 38726892369, `producer_head_sha` = `52cc0b85`) and Maryborough replay (run 38726892437, `producer_head_sha` = `52cc0b85`): `source_sealed_run.json` and `verified_customer_rows.json` are **byte-identical** for both (Lot16 fp `ef58f8ae...` = 8 opening quantities; Maryborough fp `9f3ab9ac...` = 3 FIRM floors).
- **Gate:** `tests/test_signed_output_gate_path_coverage.py` has 13 tests; the real-workflow test turns red for each of `branches: [release]`, a job-level `if: false` and `continue-on-error: true` on the Lot16 workflow (my mutation run), and is green on the real files.
- **Main moved after my review:** `main` is now `5bf17f75` (owner merged #2732, #2753, #2762, #2735 and closed #2769 / #2781). #2787's base is `40d8e849`; merge-tree against `5bf17f75` is clean (it touches two workflows and the test file only), so no rebase is needed to merge.

**Eligibility:** technically complete and verified at the exact head; it closes the signed-output replay coverage gap and the silent-pass paths in its own checker. Release blocked only by B1 (shared login).
