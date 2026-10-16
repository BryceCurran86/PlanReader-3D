"""Measurement helper: which workflows does a PR touching a given file trigger, and what do they cost?

Reads the workflow files of a git ref (argv[1]) and the recent-run cache runs500.json for typical wall-clock durations.
"""
import fnmatch, json, re, subprocess, sys, collections, datetime as dt

REF = sys.argv[1]
FILES = sys.argv[2:]
GIT = ["git", "-C", "C:/Users/bryce/Documents/PB-PlanReader-3D"]


def sh(*a):
    return subprocess.run(GIT + list(a), capture_output=True, text=True, encoding="utf-8", errors="replace", check=True).stdout


names = [n for n in sh("ls-tree", "--name-only", REF, ".github/workflows/").split() if n.endswith((".yml", ".yaml"))]
runs = json.load(open("C:/claude-work/audit-out/runs500.json"))
dur = collections.defaultdict(list)
for r in runs:
    if r["status"] == "completed" and r["conclusion"] == "success" and r["event"] == "pull_request":
        p = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        dur[r["name"]].append((p(r["updatedAt"]) - p(r["startedAt"])).total_seconds() / 60)


def glob_match(pattern, path):
    # GitHub path filter: * does not cross /, ** does
    rx = re.escape(pattern).replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
    return re.fullmatch(rx, path) is not None


def parse(text):
    """Very small parser for the on.pull_request.paths list (no yaml dependency)."""
    name = re.search(r"^name:\s*(.+)$", text, re.M)
    name = name.group(1).strip().strip("'\"") if name else ""
    on_m = re.search(r"^on:\s*\n(.*?)(?=^\S)", text, re.M | re.S)
    block = on_m.group(1) if on_m else ""
    pr = re.search(r"^  pull_request:\s*\n((?:    .*\n|\n)*)", block, re.M)
    has_pr = bool(pr) or re.search(r"^\s*pull_request\s*:?\s*$|\bpull_request\b", block) is not None
    paths = []
    ignore = []
    if pr:
        body = pr.group(1)
        for key, lst in (("paths", paths), ("paths-ignore", ignore)):
            m = re.search(r"^    %s:\s*\n((?:      -.*\n)+)" % key, body, re.M)
            if m:
                lst += [re.sub(r"^\s*-\s*", "", l).strip().strip("'\"") for l in m.group(1).splitlines()]
    return name, has_pr, paths, ignore


rows = []
for n in names:
    text = sh("show", f"{REF}:{n}")
    name, has_pr, paths, ignore = parse(text)
    rows.append((n, name, has_pr, paths, ignore))

for f in FILES:
    hits = []
    for n, name, has_pr, paths, ignore in rows:
        if not has_pr:
            continue
        if paths:
            ok = any(glob_match(p, f) for p in paths)
        else:
            ok = True
        if ok and ignore and any(glob_match(p, f) for p in ignore):
            ok = False
        if ok:
            d = dur.get(name, [])
            hits.append((sum(d) / len(d) if d else 0.0, name, n, len(d), "unfiltered" if not paths else "paths"))
    hits.sort(reverse=True)
    print(f"\n### {f}: {len(hits)} workflows trigger; sum of typical run durations {sum(h[0] for h in hits):.0f} min "
          f"(runs with no sample counted 0; matrix jobs run in parallel and are not multiplied)")
    for h in hits[:40]:
        print(f"  {h[0]:6.1f} min  n={h[3]:2d}  {h[4]:10s} {h[1][:80]}")
