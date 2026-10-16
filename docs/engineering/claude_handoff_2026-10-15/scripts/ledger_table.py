"""Build the exact-head integration ledger rows for every open PR from live GitHub + git data.  Read-only."""
import json, re, subprocess, sys

R = "BryceCurran86/PlanReader-3D"
REPO = "C:/Users/bryce/Documents/PB-PlanReader-3D"


def run(*a, cwd=None):
    return subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd)


main = run("git", "rev-parse", "origin/main", cwd=REPO).stdout.strip()
_heads = json.loads(run("gh", "pr", "list", "-R", R, "--state", "open", "--limit", "100", "--json", "number").stdout)
for _i in range(0, len(_heads), 25):
    run("git", "fetch", "-q", "origin", *[f"+pull/{h['number']}/head:refs/remotes/origin/pr{h['number']}" for h in _heads[_i:_i + 25]], cwd=REPO)
prs = json.loads(run("gh", "pr", "list", "-R", R, "--state", "open", "--limit", "100",
                     "--json", "number,title,headRefName,headRefOid,baseRefOid,isDraft,mergeable,files,author").stdout)
PROD = re.compile(r"^(pb_[a-z0-9_]+\.py|tools/run_source_closed_project_handoff\.py)$")
rows = []
for p in sorted(prs, key=lambda x: x["number"]):
    n = p["number"]
    files = [f["path"] for f in p["files"]]
    prod = [f for f in files if PROD.match(f)]
    live = [f for f in prod if not f.startswith("pb_g17_") or f in ("pb_g17_plan_wall_scope_shadow.py",)]
    chk = run("gh", "pr", "checks", str(n), "-R", R).stdout
    cnt = {"pass": 0, "fail": 0, "pending": 0, "skipping": 0}
    failing = []
    for line in chk.splitlines():
        parts = line.split("\t")
        if len(parts) > 1 and parts[1] in cnt:
            cnt[parts[1]] += 1
            if parts[1] == "fail":
                failing.append(parts[0])
    mt = run("git", "merge-tree", "--write-tree", main, f"origin/pr{n}", cwd=REPO)
    clean = mt.returncode == 0
    rows.append(dict(number=n, lane=p["headRefName"].split("/")[0], title=p["title"][:72], head=p["headRefOid"][:8],
                     base=p["baseRefOid"][:8], base_is_main=p["baseRefOid"] == main, draft=p["isDraft"],
                     github_mergeable=p["mergeable"], merge_tree_clean=clean, production=prod,
                     docs_only=all(f.startswith("docs/") for f in files), checks=cnt, failing=failing))
json.dump(dict(main=main[:8], rows=rows), open("C:/claude-work/audit-out/gpt3rev/ledger_rows.json", "w"), indent=1)
for r in rows:
    c = r["checks"]
    print(f"#{r['number']:<5} {r['lane']:<11} {r['head']} base={'main' if r['base_is_main'] else r['base']} "
          f"{'D' if r['draft'] else 'R'} mt={'clean' if r['merge_tree_clean'] else 'CONFLICT'} "
          f"p{c['pass']}/f{c['fail']}/w{c['pending']} {'PROD' if r['production'] else ('docs' if r['docs_only'] else 'tools')}  {r['title'][:58]}"
          + (f"  FAIL:{r['failing'][:3]}" if r['failing'] else ""))
