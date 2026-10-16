import subprocess

REPO = "BryceCurran86/PlanReader-3D"
ROWS = [
    (2738, "537cef5d", "6c6def6b", "exact-head checks 20 SUCCESS (original-lot16, original-maryborough-retention, maryborough-core, both GPT3 signed replays); my review of this head is above"),
    (2809, "4d811f11", "61fcb385", "exact-head checks 31 SUCCESS incl. the SHA-pinned split-frame replay and both GPT3 signed replays on a `main` base; flag-off path unchanged by construction"),
    (2802, "1a305c52", "d87c4a36", "exact-head checks 11 SUCCESS; shadow-only module with no production importer"),
    (2806, "c41a40a1", "4d4bca64", "exact-head checks 17 SUCCESS; shadow-only classmethod seam, default expressions untouched"),
    (2693, "a370da9a", "5ee56c40", "performance stack, outputs byte-identical (see the measurements on #2784 / #2775)"),
    (2694, "1be9979c", "45631368", "performance stack, outputs byte-identical"),
    (2695, "9be00ebf", "b5a43303", "performance stack, outputs byte-identical (staged cyclic-GC regime is the default)"),
    (2705, "ba44dbe6", "318a7e1d", "performance stack, outputs byte-identical"),
    (2706, "7b3c05e0", "cd045547", "performance stack; the merge commit `cd045547` only merges `main` into the verified head `f4a679c6` (GitHub reported a criss-cross conflict that `git` resolves cleanly) and its tree equals the locally verified merge result"),
]
TEMPLATE = (
    "**Merged by Claude (integration / CI / performance lane) as `{merge}` on the repository owner's explicit instruction of 2026-10-16 "
    "(\"clean the repo review, fix and merge anything we need\"). This is not a formal independent approval and not a claim of "
    "reviewer independence: the repository still has one shared login (B1).**\n\n"
    "Basis: independent technical review (COMMENT) of head `{head}`; {evidence}. The batch was verified as one tree in the "
    "verification PR #2816 (87 checks SUCCESS, 2 skipped by path filter, 0 failing; Lot16 and Maryborough `source_sealed_run.json` / "
    "`verified_customer_rows.json` byte-identical to the archived signed originals), the nine non-W2 PRs were then merged in order "
    "and the resulting `main` tree equals the locally verified merge. A post-merge replay of both signed outputs on the final "
    "integrated `main` is recorded in the release ledger on #2608 / #2004."
)
for n, merge, head, evidence in ROWS:
    body = TEMPLATE.format(merge=merge, head=head, evidence=evidence)
    r = subprocess.run(["gh", "pr", "comment", str(n), "--repo", REPO, "--body", body], capture_output=True, text=True, encoding="utf-8")
    print(n, (r.stdout or r.stderr).strip().splitlines()[-1][:90])
