from __future__ import annotations

from dataclasses import asdict
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PKG_DIR = ROOT / "benchmarks" / "frozen_holdout" / "full_plan_v2"
PKG = "_planreader_full_plan_v2_empty_report"
spec = importlib.util.spec_from_file_location(
    PKG,
    PKG_DIR / "__init__.py",
    submodule_search_locations=[str(PKG_DIR)],
)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[PKG] = module
spec.loader.exec_module(module)

manifest_io = importlib.import_module(f"{PKG}.manifest_io")
development = importlib.import_module(f"{PKG}.development_scoreboard")

PROJECT = "au_qld_maryborough_service_station"
PROJECT_DIR = PKG_DIR / "projects" / PROJECT
PDF = ROOT / "documents" / "sources" / "Arch_Combined_Maryborough_Service_Station.pdf"


def main() -> None:
    manifest = manifest_io.load_project_manifest(PROJECT_DIR / "source_manifest.json")
    result = development.evaluate_development_project_v2(
        manifest,
        (),
        execution_present=True,
    )
    digest = hashlib.sha256(PDF.read_bytes()).hexdigest()
    expected = {doc.sha256 for doc in manifest.source_documents}
    report = {
        "project_id": manifest.project_id,
        "source_sha_verified": digest in expected,
        "source_sha256s": [digest],
        "reconciliation_complete": True,
        "denominator": result.truth_denominator,
        "matched_within_tolerance": result.matched_within_tolerance,
        "matched_outside_tolerance": result.matched_outside_tolerance,
        "missed": result.missed,
        "partial": result.partial,
        "unresolved": result.unresolved,
        "unsupported_extra": result.unsupported_extra,
        "coverage_accuracy": result.observed_accuracy,
        "precision_adjusted_accuracy": result.precision_adjusted_accuracy,
        "abstained_outputs": result.abstained_outputs,
        "lineage_conflicts": result.lineage_conflicts,
        "produced_items": [],
        "sealed_run_id": None,
        "sealed_run_fingerprint": None,
        "no_sealable_quantities": True,
    }
    out = Path("artifacts/gpt3-maryborough-focused-surfaces/maryborough.exact-report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
