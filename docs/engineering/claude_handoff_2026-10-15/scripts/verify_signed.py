"""Independent re-verification of archived sealed runs + customer rows with a chosen code tree (argv[1]).

Loads with the strict readiness JSON parser, cryptographically re-verifies the sealed run, verifies the customer bijection,
recomputes the SHA-256 of every original PDF named by the sealed run envelope from the repository bytes, and prints a stable summary.
"""
import hashlib, json, sys
from pathlib import Path

tree = sys.argv[1]
sys.path.insert(0, tree)
sys.modules["rapidocr"] = None
sys.modules["onnxruntime"] = None
from scripts.report_full_plan_v2_readiness import _parse_evidence_json  # noqa: E402
from pb_customer_output_verification import verify_sealed_customer_output  # noqa: E402
from pb_source_closed_run_export import sealed_source_closed_run_from_dict  # noqa: E402

ROOT = Path("C:/claude-work/audit-out/gpt3rev")
CASES = {
    "lot16": (ROOT / "lot16/production/source_sealed_run.json", ROOT / "lot16/production/verified_customer_rows.json"),
    "maryborough": (ROOT / "mary/source/production/source_sealed_run.json", ROOT / "mary/source/production/verified_customer_rows.json"),
}
pdfs = {}
for p in Path(tree, "documents/sources").glob("*.pdf"):
    pdfs[hashlib.sha256(p.read_bytes()).hexdigest()] = p.name
out = {}
for name, (sealed_path, rows_path) in CASES.items():
    sealed = sealed_source_closed_run_from_dict(_parse_evidence_json(sealed_path.read_text(encoding="utf-8")))
    rows = _parse_evidence_json(rows_path.read_text(encoding="utf-8"))
    verified = verify_sealed_customer_output(sealed, rows)
    qs = []
    for q in sealed.quantities:
        qs.append({"quantity_id": q.quantity_id, "family": getattr(q, "family", None), "value": getattr(q, "value", None), "unit": getattr(q, "unit", None),
                   "status": str(getattr(q, "status", "")), "authority": getattr(q, "authority", None), "abstained": getattr(q, "abstained", None)})
    out[name] = {
        "run_id": sealed.run_id, "fingerprint": sealed.fingerprint, "project_id": sealed.project_id,
        "source_sha256s": list(sealed.source_sha256s), "source_sha_present_in_repo_pdfs": {s: pdfs.get(s) for s in sealed.source_sha256s},
        "revision_ids": list(sealed.revision_ids), "sealed_quantity_count": len(sealed.quantities),
        "verified_quantity_ids": list(verified.verified_quantity_ids), "customer_row_count": len(rows),
        "quantities": sorted(qs, key=lambda r: r["quantity_id"]),
    }
print(json.dumps(out, indent=1, sort_keys=True, default=str))
