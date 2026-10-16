"""Which modules of the production handoff import closure are NOT covered by any signed-output retention workflow?

Static: AST import closure (module-level and function-level imports) of tools/run_source_closed_project_handoff.py over repo-local
.py files; then the path filters of the workflows that seal/compare source_sealed_run.json + verified_customer_rows.json.
Read-only, run on a checked-out tree.
"""
import ast, re, sys
from pathlib import Path

TREE = Path(sys.argv[1])
ENTRY = "tools/run_source_closed_project_handoff.py"
local = {p.stem: p for p in TREE.glob("*.py")}
local.update({"scripts." + p.stem: p for p in (TREE / "scripts").glob("*.py")})


def imports(path):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name.split(".")[0] if a.name.split(".")[0] != "scripts" else a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.add(node.module if node.module.startswith("scripts.") else node.module.split(".")[0])
    return out


seen, stack = set(), [TREE / ENTRY]
while stack:
    p = stack.pop()
    for name in imports(p):
        if name in local and name not in seen:
            seen.add(name)
            stack.append(local[name])
closure = sorted(m for m in seen if not m.startswith("scripts."))
print(f"import closure of {ENTRY}: {len(closure)} repo modules (+{len([m for m in seen if m.startswith('scripts.')])} scripts)")

# workflows that seal / compare the signed outputs
SEAL = ("source_sealed_run.json", "verified_customer_rows.json")
wf_dir = TREE / ".github" / "workflows"
retention = {}
for wf in sorted(wf_dir.glob("*.y*ml")):
    text = wf.read_text(encoding="utf-8", errors="replace")
    if not any(s in text for s in SEAL):
        continue
    m = re.search(r"^  pull_request:\s*\n((?:    .*\n|\n)*)", text, re.M)
    paths = []
    if m:
        pm = re.search(r"^    paths:\s*\n((?:      -.*\n)+)", m.group(1), re.M)
        if pm:
            paths = [re.sub(r"^\s*-\s*", "", l).strip().strip("'\"") for l in pm.group(1).splitlines()]
        has_pr = True
    else:
        has_pr = "pull_request" in text
    retention[wf.name] = (has_pr, paths, "Lot16" if "Lot 16" in text or "Lot16" in text or "lot16" in text else "",
                          "Maryborough" if "Maryborough" in text or "maryborough" in text else "")
print(f"\nretention workflows (reference source_sealed_run / verified_customer_rows): {len(retention)}")
for k, (pr, paths, l, m) in retention.items():
    print(f"  {k:62s} pull_request={pr!s:5} paths={len(paths):2d}  {l} {m}")


def covered_by(module, project):
    f = f"{module}.py"
    hits = []
    for wf, (pr, paths, l, m) in retention.items():
        if not pr:
            continue
        if project == "Lot16" and not l:
            continue
        if project == "Maryborough" and not m:
            continue
        if not paths or f in paths:
            hits.append(wf)
    return hits


for project in ("Lot16", "Maryborough"):
    unc = [m for m in closure if not covered_by(m, project)]
    print(f"\n{project}: {len(closure) - len(unc)} of {len(closure)} closure modules trigger at least one retention workflow; "
          f"{len(unc)} do NOT:")
    for m in unc:
        print("   ", m)
