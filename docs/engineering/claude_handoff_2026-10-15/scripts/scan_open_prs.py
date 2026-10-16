import json, re, subprocess, sys
R = "BryceCurran86/PlanReader-3D"
def gh(*a):
    return subprocess.run(["gh", *a, "-R", R], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
prs = json.loads(gh("pr", "list", "--state", "open", "--limit", "80", "--json", "number,title,headRefName,isDraft,files,mergeable"))
PROD = re.compile(r"^pb_[a-z0-9_]+\.py$")
BENCH = re.compile(r"^(benchmarks/|scripts/check_(full_plan_v2_integrity|v2_truth_separation|provider_gold_isolation|benchmark_gold_separation)\.py|tests/benchmarks/)")
SUSP = [
    ("project/benchmark literal in production diff", re.compile(r"^\+(?!\+\+).*(Maryborough|Lot16|3Laurel|Q5446|KSTVET|Murera|Ghazi|full_plan_v2|reference_takeoff|object_universe)", re.I)),
    ("hardcoded 64-hex SHA in production diff", re.compile(r"^\+(?!\+\+).*['\"][0-9a-f]{64}['\"]")),
    ("takeoff_eligible/deduction_authority set True", re.compile(r"^\+(?!\+\+).*(takeoff_eligible|deduction_authority)\s*=\s*True")),
    ("global snap / cap constant touched", re.compile(r"^\+(?!\+\+).*(20000|20_000|W2_SNAP|snap_tol)")),
    ("default/assumed scale or count fallback", re.compile(r"^\+(?!\+\+).*(default_scale|assumed_scale|count\s*=\s*1\b|default_ceiling_height)")),
    ("stable id / rekey", re.compile(r"^\+(?!\+\+).*(stable_contract_id\(|rekey|re_key|remap)")),
]
rows = []
for p in prs:
    n = p["number"]
    files = [f["path"] for f in p["files"]]
    prod = [f for f in files if PROD.match(f)]
    bench = [f for f in files if BENCH.match(f)]
    other_py = [f for f in files if f.endswith(".py") and not PROD.match(f) and not f.startswith(("tests/", "tools/"))]
    flags = []
    if prod and bench:
        flags.append("PRODUCTION+BENCHMARK-DEFINING in one PR")
    elif bench:
        flags.append("touches benchmark-defining files")
    if prod:
        diff = gh("pr", "diff", str(n))
        cur = None
        hits = {}
        for line in diff.splitlines():
            if line.startswith("diff --git"):
                cur = line.split(" b/")[-1]
            if cur and PROD.match(cur):
                for label, rx in SUSP:
                    if rx.search(line):
                        hits.setdefault(label, []).append((cur, line[1:100]))
        for label, items in hits.items():
            flags.append(f"{label}: {len(items)} e.g. {items[0]}")
    rows.append((n, p["isDraft"], p["headRefName"].split("/")[0], p["title"][:70], prod, bench, flags))
for n, d, lane, title, prod, bench, flags in sorted(rows):
    if prod or bench or flags:
        print(f"#{n} draft={d} lane={lane} | {title}")
        if prod: print("   production modules:", prod)
        if bench: print("   benchmark-defining:", bench)
        for f in flags: print("   FLAG:", f)
print("\nPRs with no production module and no benchmark-defining file (tools/tests/docs/workflows only):",
      sorted(n for n, d, l, t, prod, bench, fl in rows if not prod and not bench))
