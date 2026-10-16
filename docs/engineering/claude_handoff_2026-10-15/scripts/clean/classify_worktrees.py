import subprocess, sys, json, os

MAIN = "C:/Users/bryce/Documents/PB-PlanReader-3D"

def git(cwd, *a):
    r = subprocess.run(["git", "-C", cwd, *a], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout.strip()

rc, out = git(MAIN, "worktree", "list", "--porcelain")
wts = []
cur = {}
for line in out.splitlines() + [""]:
    if not line:
        if cur:
            wts.append(cur)
        cur = {}
        continue
    k, _, v = line.partition(" ")
    cur[k] = v
rows = []
for w in wts:
    path = w["worktree"]
    if os.path.normcase(os.path.normpath(path)) == os.path.normcase(os.path.normpath(MAIN)):
        continue
    head = w.get("HEAD", "")
    branch = w.get("branch", "").replace("refs/heads/", "") or "(detached)"
    if not os.path.isdir(path):
        rows.append({"path": path, "branch": branch, "state": "MISSING_DIR"})
        continue
    rc, st = git(path, "status", "--porcelain", "--untracked-files=normal")
    dirty = bool(st)
    rc, rem = git(MAIN, "branch", "-r", "--contains", head)
    on_remote = bool(rem.strip())
    rc, mrg = git(MAIN, "merge-base", "--is-ancestor", head, "origin/main")
    in_main = (subprocess.run(["git", "-C", MAIN, "merge-base", "--is-ancestor", head, "origin/main"]).returncode == 0)
    rows.append({"path": path, "branch": branch, "head": head[:8], "dirty": dirty, "dirty_lines": st.count("\n") + 1 if st else 0,
                 "on_remote": on_remote, "in_main": in_main})
json.dump(rows, open("C:/claude-work/audit-out/clean/worktrees.json", "w"), indent=1)
safe = [r for r in rows if r.get("state") != "MISSING_DIR" and not r["dirty"] and r["on_remote"]]
dirty = [r for r in rows if r.get("dirty")]
local_only = [r for r in rows if r.get("state") != "MISSING_DIR" and not r["dirty"] and not r["on_remote"]]
missing = [r for r in rows if r.get("state") == "MISSING_DIR"]
print(f"total={len(rows)} safe_to_remove(clean+pushed)={len(safe)} dirty={len(dirty)} clean_but_local_only={len(local_only)} missing_dir={len(missing)}")
print("--- DIRTY:")
for r in dirty:
    print(f"  {r['path']} [{r['branch']}] {r['head']} dirty_lines={r['dirty_lines']} on_remote={r['on_remote']}")
print("--- CLEAN BUT HEAD NOT ON ANY REMOTE BRANCH:")
for r in local_only:
    print(f"  {r['path']} [{r['branch']}] {r['head']} in_main={r['in_main']}")
print("--- MISSING DIR:", [r["path"] for r in missing])
