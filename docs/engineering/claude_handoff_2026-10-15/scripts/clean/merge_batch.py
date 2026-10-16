"""Merge the verified batch, one PR at a time, in the integration order.

Stops at the first PR that is not mergeable / has a failing check / has moved from the head that was verified.
"""
import json, subprocess, sys, time

REPO = "BryceCurran86/PlanReader-3D"
# (number, exact head that the integration PR verified)
ORDER = [
    (2738, "6c6def6b"), (2809, "61fcb385"), (2802, "d87c4a36"), (2806, "4d4bca64"),
    (2693, "5ee56c40"), (2694, "45631368"), (2695, "b5a43303"), (2705, "318a7e1d"), (2706, "f4a679c6"),
]
APPLY = "--apply" in sys.argv

def gh(*a):
    r = subprocess.run(["gh", *a], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout + r.stderr).strip()

def view(n):
    rc, out = gh("pr", "view", str(n), "--repo", REPO, "--json", "number,state,isDraft,mergeable,mergeStateStatus,headRefOid,baseRefName,statusCheckRollup")
    return json.loads(out)

for n, head in ORDER:
    v = view(n)
    h = v["headRefOid"][:8]
    bad = [c for c in v["statusCheckRollup"] if c.get("conclusion") in ("FAILURE", "CANCELLED", "TIMED_OUT")]
    pend = [c for c in v["statusCheckRollup"] if c.get("status") != "COMPLETED"]
    print(f"#{n} state={v['state']} draft={v['isDraft']} merge={v['mergeable']}/{v['mergeStateStatus']} head={h} (verified {head}) failing={len(bad)} pending={len(pend)}")
    for _ in range(8):
        if v["mergeable"] != "UNKNOWN":
            break
        time.sleep(6)
        v = view(n)
    if v["state"] != "OPEN":
        print("   already", v["state"]); continue
    if h != head:
        print("   HEAD MOVED since verification -> stop"); sys.exit(2)
    if v["baseRefName"] != "main" or bad or pend:
        print("   not eligible -> stop"); sys.exit(2)
    if not APPLY:
        continue
    if v["isDraft"]:
        rc, out = gh("pr", "ready", str(n), "--repo", REPO); print("   ready:", out.splitlines()[-1] if out else rc)
        time.sleep(8)
        v = view(n)
        for _ in range(8):
            if v["mergeable"] != "UNKNOWN":
                break
            time.sleep(6)
            v = view(n)
    if v["mergeable"] != "MERGEABLE" or v["mergeStateStatus"] not in ("CLEAN", "UNSTABLE", "HAS_HOOKS"):
        print("   mergeability problem after ready:", v["mergeable"], v["mergeStateStatus"]); sys.exit(2)
    rc, out = gh("pr", "merge", str(n), "--repo", REPO, "--merge")
    print("   merge:", out.splitlines()[-1] if out else rc)
    if rc != 0:
        sys.exit(2)
    time.sleep(5)
print("done" if APPLY else "dry run ok (no merges)")
