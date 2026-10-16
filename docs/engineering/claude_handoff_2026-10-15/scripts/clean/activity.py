import json, os, subprocess, time

rows = json.load(open("C:/claude-work/audit-out/clean/worktrees.json"))
now = time.time()
for r in rows:
    if r.get("state") == "MISSING_DIR":
        continue
    p = subprocess.run(["git", "-C", r["path"], "rev-parse", "--git-dir"], capture_output=True, text=True).stdout.strip()
    gd = p if os.path.isabs(p) else os.path.join(r["path"], p)
    times = []
    for name in ("index", "HEAD", "ORIG_HEAD", "FETCH_HEAD", "logs/HEAD"):
        f = os.path.join(gd, name)
        if os.path.exists(f):
            times.append(os.path.getmtime(f))
    # newest tracked-file touch is expensive; use directory mtime of the worktree root too
    try:
        times.append(os.path.getmtime(r["path"]))
    except OSError:
        pass
    r["age_h"] = round((now - max(times)) / 3600, 1) if times else None
json.dump(rows, open("C:/claude-work/audit-out/clean/worktrees.json", "w"), indent=1)
recent = sorted([r for r in rows if r.get("age_h") is not None and r["age_h"] < 36], key=lambda r: r["age_h"])
print("worktrees touched in the last 36h:", len(recent))
for r in recent:
    print(f"  {r['age_h']:>6}h dirty={r.get('dirty')} pushed={r.get('on_remote')} {r['path'].replace('C:/Users/bryce/', '~/')} [{r['branch']}]")
old = [r for r in rows if r.get("age_h") is not None and r["age_h"] >= 36]
print("older than 36h:", len(old))
