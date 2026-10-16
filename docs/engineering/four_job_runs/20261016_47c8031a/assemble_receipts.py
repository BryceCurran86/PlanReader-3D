"""Assemble share-safe, hash-pinned receipts from one private launcher session.

Usage: python assemble_receipts.py SESSION_DIR OUT_DIR

Copies only derived producer artifacts (never a source PDF), replaces the owner's home path with <HOME>,
and writes RUN_RECEIPT.json plus SHA256SUMS. For every copied file both the hash of the private original and
the hash of the share-safe copy are recorded; for files with no path inside, the two are equal.
"""
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

session, out = Path(sys.argv[1]), Path(sys.argv[2])
home = str(Path.home())
variants = {home, home.replace("\\", "\\\\"), home.replace("\\", "/"), home.replace("\\", "\\\\\\\\")}
pattern = re.compile("|".join(re.escape(v) for v in sorted(variants, key=len, reverse=True)))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sanitize(data: bytes) -> bytes:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    return pattern.sub("<HOME>", text).encode("utf-8")


status = json.loads((session / "BENCHMARK_DIAGNOSTIC_STATUS.json").read_text(encoding="utf-8"))
out.mkdir(parents=True, exist_ok=True)
rows = []


def put(src: Path, dest_rel: str) -> None:
    raw = src.read_bytes()
    clean = sanitize(raw)
    dest = out / dest_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(clean)
    rows.append({"file": dest_rel.replace("\\", "/"), "private_original_sha256": sha(raw),
                 "share_safe_sha256": sha(clean), "bytes": len(clean)})


put(session / "SOURCE_SHA_VERIFICATION.json", "SOURCE_SHA_VERIFICATION.json")
put(session / "PREFLIGHT_STATUS.json", "PREFLIGHT_STATUS.json")
for project in [h["project_id"] for h in status["project_handoffs"]]:
    pre = session / "preflight" / f"{project}.json"
    if pre.is_file():
        put(pre, f"{project}/source_package_preflight.json")
    for name in ("preflight.log", "handoff.log"):
        log = session / "logs" / f"{project}.{name}"
        if log.is_file():
            put(log, f"{project}/{name}")
    folder = session / "project_outputs" / project
    if folder.is_dir():
        for path in sorted(folder.rglob("*")):
            if path.is_file() and path.name != ".source_closed_handoff.lock":
                put(path, f"{project}/outputs/{path.relative_to(folder).as_posix()}")

safe = json.loads(pattern.sub("<HOME>", json.dumps(status)))
receipt = {
    "schema": "four_job_owner_machine_run_receipt/1",
    "session": session.name,
    "repo_head": status.get("repo_head"),
    "requested_ref": status.get("requested_ref"),
    "launcher_version": status.get("launcher_version"),
    "limits": {"per_project_timeout_min": status.get("per_project_timeout_min"),
               "max_private_gb": status.get("max_private_gb"),
               "min_free_commit_gb": status.get("min_free_commit_gb")},
    "command": ("python RUN_FOUR_JOB_BENCHMARK_V2.py --ref <repo_head> --timeout-min "
                f"{status.get('per_project_timeout_min')} --max-private-gb {status.get('max_private_gb')} "
                f"--min-free-commit-gb {status.get('min_free_commit_gb')}"),
    "per_project_handoff_command": ("python -u -c <faulthandler bootstrap> -> tools.run_source_closed_project_handoff "
                                    "--pdf <primary architectural PDF in the private kit> --project-id <id> "
                                    "--family-group all --output-dir <session>/project_outputs/<id>"),
    "source_pdf_count": status.get("source_pdf_count"),
    "source_preflight": status.get("source_preflight"),
    "project_handoffs": safe["project_handoffs"],
    "official_four_project_coverage_accuracy": None,
    "full_suite_publication_status": "UNPUBLISHED",
    "explanation": status.get("explanation"),
    "files": rows,
}
(out / "RUN_RECEIPT.json").write_bytes((json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8"))
lines = [f"{sha((out / r['file']).read_bytes())}  {r['file']}" for r in sorted(rows, key=lambda r: r["file"])]
lines.append(f"{sha((out / 'RUN_RECEIPT.json').read_bytes())}  RUN_RECEIPT.json")
(out / "SHA256SUMS").write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
print(f"{len(rows)} files, receipt written to {out}")
