"""Aggregate original-source replay cost per shared entry command over UNIQUE workflows (minutes counted once per workflow).

Static: workflow text on origin/main.  Measured: job-level durations of each workflow's latest successful pull_request run
(jobs that are not unit-test / fastpath jobs).  Read-only.
"""
import collections, datetime as dt, json, re, subprocess

REPO = "C:/Users/bryce/Documents/PB-PlanReader-3D"
R = "BryceCurran86/PlanReader-3D"
REF = "origin/main"
PDF = re.compile(r"Lot 16 Power|10109b4b|Maryborough_Service_Station|b1be5353|3LAUREL|014e9f68|Q5446_Standard|5f29aa01", re.I)
ENTRY = re.compile(r"(?:python[0-9.]*\s+(?:-u\s+)?(?:-m\s+)?|^\s*)((?:tools|scripts|benchmarks)[/.][\w./]+?\.py|tools\.[\w.]+)", re.M)
SKIP_ENTRY = ("scripts.check_full_plan_v2_integrity", "scripts.check_provider_gold_isolation", "scripts.check_v2_truth_separation")


def run(*a):
    return subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=REPO).stdout


p = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00"))  # noqa: E731
runs = json.load(open("C:/claude-work/audit-out/runs500.json"))
latest = {}
for r in runs:
    if r["status"] == "completed" and r["conclusion"] == "success" and r["event"] == "pull_request":
        latest.setdefault(r["name"], r["databaseId"])


def heavy_minutes(run_id):
    out = run("gh", "api", f"repos/{R}/actions/runs/{run_id}/jobs", "--jq",
              '.jobs[]|select(.conclusion=="success")|[.name,.started_at,.completed_at]|@tsv')
    total = 0.0
    for line in out.splitlines():
        name, a, b = (line.split("\t") + ["", ""])[:3]
        if a and b and not re.search(r"focused|fastpath|^test$|\btest \(", name):
            total += (p(b) - p(a)).total_seconds() / 60
    return total


unique = {}
for path in run("git", "ls-tree", "--name-only", REF, ".github/workflows/").split():
    if not path.endswith((".yml", ".yaml")):
        continue
    text = run("git", "show", f"{REF}:{path}").replace("\r", "")
    if "pull_request" not in text or not PDF.search(text):
        continue
    name = (re.search(r"^name:\s*(.+)$", text, re.M) or [None, path])[1].strip().strip("'\"")
    entries = sorted({m.group(1).replace(".py", "").replace("/", ".") for m in ENTRY.finditer(text) if "pytest" not in m.group(0)})
    entries = [e for e in entries if e not in SKIP_ENTRY]
    if name not in unique:
        unique[name] = (heavy_minutes(latest[name]) if name in latest else 0.0, entries, path.split("/")[-1])

json.dump({k: list(v) for k, v in unique.items()}, open("C:/claude-work/audit-out/perf/workflow_heavy.json", "w"), indent=1)
heavy = {k: v for k, v in unique.items() if v[0] > 3}
print(f"unique workflows that mention an original source: {len(unique)}; with > 3 measured heavy minutes: {len(heavy)}")
print(f"total heavy minutes over those {len(heavy)} workflows (latest green run each): {sum(v[0] for v in heavy.values()):.0f}")
by_entry = collections.defaultdict(list)
for name, (mins, entries, fn) in heavy.items():
    for e in entries:
        by_entry[e].append((mins, name))
print("\nentry commands run by several heavy workflows:")
for e, items in sorted(by_entry.items(), key=lambda kv: -sum(m for m, _ in kv[1])):
    if len(items) >= 2:
        print(f"  {e:58s} {len(items):2d} workflows, {sum(m for m, _ in items):6.0f} min")
