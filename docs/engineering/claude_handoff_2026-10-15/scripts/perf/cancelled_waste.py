"""Runner minutes spent by runs that ended `cancelled` (superseded by a newer push), from job-level timestamps.  Read-only."""
import collections, datetime as dt, json, subprocess

R = "BryceCurran86/PlanReader-3D"
runs = json.load(open("C:/claude-work/audit-out/runs500.json"))
cancelled = [r for r in runs if r["status"] == "completed" and r["conclusion"] == "cancelled"]
p = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
by_branch, by_wf = collections.Counter(), collections.Counter()
total_cancel_min = 0.0
for r in cancelled:
    out = subprocess.run(["gh", "api", f"repos/{R}/actions/runs/{r['databaseId']}/jobs", "--paginate", "--jq",
                          ".jobs[]|[.started_at,.completed_at]|@tsv"], capture_output=True, text=True).stdout
    minutes = 0.0
    for line in out.splitlines():
        a, _, b = line.partition("\t")
        if a and b and a != "null" and b != "null":
            minutes += (p(b) - p(a)).total_seconds() / 60
    total_cancel_min += minutes
    by_branch[r["headBranch"]] += minutes
    by_wf[r["name"]] += minutes
print(f"{len(cancelled)} cancelled runs of {len(runs)}; runner-minutes burned before cancellation: {total_cancel_min:.0f}")
print("by workflow:")
for k, v in by_wf.most_common(8):
    print(f"  {v:7.1f}  {k}")
print("by branch:")
for k, v in by_branch.most_common(8):
    print(f"  {v:7.1f}  {k}")
