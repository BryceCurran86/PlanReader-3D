import subprocess

REPO = "BryceCurran86/PlanReader-3D"
STALE = {
    1339: (761, 2), 1481: (676, 1), 1593: (647, 5), 1744: (603, 1),
    1844: (603, 5), 1864: (603, 5), 1868: (603, 6), 1953: (590, 13),
}
TEMPLATE = ("**Closing as stale (repository clean-up, 2026-10-16; the branch is kept and this PR can be reopened).** "
            "This draft was last updated before 2026-10-13, its merge base is {behind} commits behind `main`, and "
            "`git merge-tree` against current `main` reports conflicts ({conflicts} conflicting paths). The work it carried has since been "
            "re-done on top of the source-owned physical opening / wall authorities that are now in `main` (see the open GPT MAX, "
            "GPT2 and GPT3 PRs on #2396 / #2608), and nothing here is on the critical path. If anyone still needs it: rebase onto "
            "`main`, re-run the original-source jobs, and reopen. No code was merged or deleted.")

def comment_and_close(n, body):
    subprocess.run(["gh", "pr", "comment", str(n), "--repo", REPO, "--body", body], check=True, capture_output=True, text=True)
    r = subprocess.run(["gh", "pr", "close", str(n), "--repo", REPO], capture_output=True, text=True)
    print(n, (r.stdout + r.stderr).strip().splitlines()[-1])

for n, (behind, conflicts) in STALE.items():
    comment_and_close(n, TEMPLATE.format(behind=behind, conflicts=conflicts))

comment_and_close(2799, "**Closing as superseded (repository clean-up, 2026-10-16).** `tools/diag_gptmax_same_root_f07_g17_original.py` and "
                  "`tests/test_gptmax_same_root_f07_g17_original.py` are byte-identical to what merged in #2801; this PR only differs in the "
                  "workflow's `branches:` filter and conflicts with `main` on the workflow and the doc. #2804 carries the follow-on on top of "
                  "merged #2801. Branch kept; reopen if needed.")
comment_and_close(2692, "**Closing as superseded (repository clean-up, 2026-10-16).** The bounded complete-handoff measurement this workflow "
                  "was added for is done and recorded (profile record in #2775 and the hand-off folder; the variant comparison tool and "
                  "workflow shipped with #2784). Nothing else depends on this workflow. Branch kept; reopen if the measurement needs repeating.")
