"""For every pair of open, non-conflicting PRs that touch a common file, trial-merge the two heads (git merge-tree, no checkout)
and report textual conflicts.  Read-only.  Heads are fetched as refs/remotes/origin/pr<N>."""
import itertools, json, re, subprocess

R = "BryceCurran86/PlanReader-3D"
REPO = "C:/Users/bryce/Documents/PB-PlanReader-3D"


def run(*a, cwd=None):
    return subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd)


prs = json.loads(run("gh", "pr", "list", "-R", R, "--state", "open", "--limit", "100",
                     "--json", "number,headRefOid,isDraft,mergeable,files,title").stdout)
refspecs = [f"+pull/{p['number']}/head:refs/remotes/origin/pr{p['number']}" for p in prs]
for i in range(0, len(refspecs), 25):
    run("git", "fetch", "-q", "origin", *refspecs[i:i + 25], cwd=REPO)

info = {p["number"]: ({f["path"] for f in p["files"]}, p) for p in prs if p["mergeable"] != "CONFLICTING"}
SKIP_SHARED = re.compile(r"^(\.github/workflows/.*|docs/.*)$")  # unique names; shared docs/workflows are rare and obvious
pairs = []
for a, b in itertools.combinations(sorted(info), 2):
    shared = {f for f in info[a][0] & info[b][0] if not SKIP_SHARED.match(f)}
    if shared:
        pairs.append((a, b, sorted(shared)))
print(f"{len(info)} non-conflicting open PRs; {len(pairs)} pairs share a non-doc/workflow file")
bad = []
for a, b, shared in pairs:
    r = run("git", "merge-tree", "--write-tree", "--name-only", f"origin/pr{a}", f"origin/pr{b}", cwd=REPO)
    conflict = r.returncode != 0
    status = "CONFLICT" if conflict else "clean"
    if conflict:
        files = [l for l in r.stdout.splitlines()[1:] if l and not l.startswith(("Auto-merging", "CONFLICT"))][:6]
        bad.append((a, b, shared, files))
    print(f"  #{a} x #{b}: {status}  shared={shared[:4]}")
print("\nTEXTUAL CONFLICTS:")
for a, b, shared, files in bad:
    print(f"  #{a} x #{b}: shared={shared} conflicted={files}")
