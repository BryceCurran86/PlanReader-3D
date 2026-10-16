"""Cancel QUEUED Actions runs whose head commit is no longer the head of the branch's open PR (or whose PR is gone).

Only queued runs are touched; in-progress runs and runs on current heads are left alone. Cancelling a superseded run never
removes exact-head evidence: the current head's runs are the only ones a review reads.
"""
import json, subprocess, sys

REPO = "BryceCurran86/PlanReader-3D"
APPLY = "--apply" in sys.argv

def gh(*a):
    r = subprocess.run(["gh", *a], capture_output=True, text=True, encoding="utf-8")
    return r.stdout

prs = json.loads(gh("pr", "list", "--repo", REPO, "--state", "open", "--limit", "300", "--json", "number,headRefName,headRefOid"))
head_by_branch = {p["headRefName"]: p["headRefOid"] for p in prs}
runs = json.loads(gh("run", "list", "--repo", REPO, "--status", "queued", "--limit", "300", "--json", "databaseId,headBranch,headSha,name,event"))
stale, keep = [], 0
for r in runs:
    b, sha = r["headBranch"], r["headSha"]
    if b == "main":
        keep += 1
        continue
    cur = head_by_branch.get(b)
    if cur is None or cur != sha:
        stale.append(r)
    else:
        keep += 1
print(f"queued={len(runs)} keep={keep} stale={len(stale)}")
by_branch = {}
for r in stale:
    by_branch.setdefault(r["headBranch"], []).append(r)
for b, rs in sorted(by_branch.items(), key=lambda kv: -len(kv[1])):
    print(f"  {len(rs):3d} {b} (current open-PR head: {(head_by_branch.get(b) or 'none')[:8]})")
if APPLY:
    n = 0
    for r in stale:
        out = subprocess.run(["gh", "run", "cancel", str(r["databaseId"]), "--repo", REPO], capture_output=True, text=True)
        if out.returncode == 0:
            n += 1
    print("cancelled", n)
