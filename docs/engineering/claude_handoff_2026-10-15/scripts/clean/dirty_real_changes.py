import json, subprocess

rows = json.load(open("C:/claude-work/audit-out/clean/worktrees.json"))
out = []
for r in rows:
    if not r.get("dirty"):
        continue
    p = r["path"]
    # real content changes ignoring end-of-line differences, tracked files only
    d = subprocess.run(["git", "-C", p, "-c", "core.autocrlf=false", "diff", "--ignore-space-at-eol", "--ignore-cr-at-eol", "--name-only"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.split()
    s = subprocess.run(["git", "-C", p, "diff", "--cached", "--name-only"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.split()
    u = subprocess.run(["git", "-C", p, "ls-files", "--others", "--exclude-standard"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.split()
    out.append({"path": p, "branch": r["branch"], "pushed": r["on_remote"], "in_main": r.get("in_main"), "real_modified": len(d), "staged": len(s), "untracked": len(u)})
json.dump(out, open("C:/claude-work/audit-out/clean/dirty_real.json", "w"), indent=1)
noise = [o for o in out if o["real_modified"] == 0 and o["staged"] == 0 and o["untracked"] == 0]
real = [o for o in out if o not in noise]
print(f"dirty worktrees: {len(out)}; EOL-noise only: {len(noise)}; real changes/untracked: {len(real)}")
print("--- EOL noise only (safe to remove if pushed):")
for o in noise:
    print(f"   pushed={o['pushed']} {o['path'].replace('C:/Users/bryce/', '~/')} [{o['branch']}]")
print("--- real changes:")
for o in real:
    print(f"   modified={o['real_modified']} staged={o['staged']} untracked={o['untracked']} pushed={o['pushed']} {o['path'].replace('C:/Users/bryce/', '~/')} [{o['branch']}]")
