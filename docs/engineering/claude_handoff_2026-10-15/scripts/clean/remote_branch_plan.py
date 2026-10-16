import json, subprocess

REPO = "BryceCurran86/PlanReader-3D"

def gh(*a):
    r = subprocess.run(["gh", *a], capture_output=True, text=True, encoding="utf-8")
    return r.stdout

merged = json.loads(gh("pr", "list", "--repo", REPO, "--state", "merged", "--limit", "3000", "--json", "number,headRefName,headRepositoryOwner,mergedAt"))
openp = json.loads(gh("pr", "list", "--repo", REPO, "--state", "open", "--limit", "500", "--json", "number,headRefName,baseRefName"))
merged_heads = {p["headRefName"] for p in merged}
protected = {"main"}
for p in openp:
    protected.add(p["headRefName"])
    protected.add(p["baseRefName"])
remote_merged = [l.strip().replace("origin/", "", 1) for l in open("C:/claude-work/audit-out/clean/remote_merged.txt", encoding="utf-8")]
cand = [b for b in remote_merged if b in merged_heads and b not in protected]
skipped_open = [b for b in remote_merged if b in protected and b != "main"]
no_pr = [b for b in remote_merged if b not in merged_heads and b not in protected]
print("merged PRs:", len(merged), "open PRs:", len(openp))
print("remote branches merged into main:", len(remote_merged))
print("  deletable (head of a merged PR, not head/base of an open PR):", len(cand))
print("  protected (open PR head/base):", len(skipped_open), skipped_open[:10])
print("  merged-by-ancestry but no merged PR (left alone):", len(no_pr))
open("C:/claude-work/audit-out/clean/remote_delete.txt", "w", encoding="utf-8").write("\n".join(cand))
