import json, os, subprocess, sys

DRY = "--apply" not in sys.argv
MAIN = "C:/Users/bryce/Documents/PB-PlanReader-3D"
rows = json.load(open("C:/claude-work/audit-out/clean/worktrees.json"))

KEEP_MINE = {  # worktrees tied to open PRs of mine or to work still in progress this session
    "C:/claude-work/ci-trigger", "C:/claude-work/handoff-record", "C:/claude-work/ft3-edit", "C:/claude-work/prof",
    "C:/claude-work/stack", "C:/claude-work/t3-auth", "C:/claude-work/t3-clone", "C:/claude-work/t3-gc",
    "C:/claude-work/t3-share", "C:/claude-work/t3-text", "C:/claude-work/t3-diag",
    "C:/claude-work/rev-2811",
}
MY_SCRATCH_LOCAL_ONLY = {  # throwaway merge trials I created this session; clean, nothing of value
    "C:/claude-work/int-trial", "C:/claude-work/mt-2694-2511", "C:/claude-work/mt-2705-2773",
    "C:/claude-work/mt-2726-2638", "C:/claude-work/t3-abc",
}
NEVER = ("/.chatgpt-worktrees/",)

remove, skip = [], []
for r in rows:
    path = r["path"].replace("\\", "/")
    if r.get("state") == "MISSING_DIR":
        continue
    if any(n in path for n in NEVER) or path in KEEP_MINE:
        skip.append((path, "kept (active/other agent)"))
        continue
    if r.get("dirty"):
        skip.append((path, "dirty"))
        continue
    mine = path.startswith("C:/claude-work/")
    if mine and (r.get("on_remote") or path in MY_SCRATCH_LOCAL_ONLY):
        remove.append(path)
    elif (not mine) and r.get("on_remote") and r.get("in_main"):
        remove.append(path)
    else:
        skip.append((path, "not pushed or not merged"))
print(("DRY RUN " if DRY else "APPLY ") + f"remove={len(remove)} skip={len(skip)}")
done = failed = 0
for p in remove:
    if DRY:
        print("  would remove", p)
        continue
    res = subprocess.run(["git", "-C", MAIN, "worktree", "remove", p], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode == 0:
        done += 1
    else:
        failed += 1
        print("  FAILED", p, res.stderr.strip()[:140])
if not DRY:
    subprocess.run(["git", "-C", MAIN, "worktree", "prune"])
    print(f"removed={done} failed={failed}")
