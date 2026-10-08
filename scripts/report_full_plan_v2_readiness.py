"""Unpublished Full Plan V2 readiness diagnostics; never an accuracy score.

This read-only utility inspects frozen manifests and optional real production
files. It deliberately does not import, alter, or invoke the benchmark evaluator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

DEFAULT_ROOT = Path("benchmarks/frozen_holdout/full_plan_v2")


def _object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _source_sha_proof(manifest: dict, source_root: Path | None, project_id: str) -> tuple[bool, list[str]]:
    """Hash real source files against the frozen name, size, and SHA-256."""
    documents = manifest.get("source_documents")
    if not isinstance(documents, list) or not documents:
        return False, ["source_manifest_documents_missing"]
    if source_root is None:
        return False, ["source_files_not_supplied"]
    reasons: list[str] = []
    for document in documents:
        if not isinstance(document, dict):
            raise ValueError("source manifest document must be an object")
        name, expected_sha, expected_size = document.get("name"), document.get("sha256"), document.get("size_bytes")
        if not isinstance(name, str) or not name or Path(name).name != name:
            raise ValueError("source document name must be a plain filename")
        if not isinstance(expected_sha, str) or len(expected_sha) != 64:
            raise ValueError("source manifest sha256 invalid")
        source = source_root / project_id / name
        if not source.is_file():
            reasons.append(f"source_file_missing:{name}")
            continue
        if source.stat().st_size != expected_size:
            reasons.append(f"source_file_size_mismatch:{name}")
            continue
        digest = hashlib.sha256()
        with source.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected_sha.lower():
            reasons.append(f"source_file_sha_mismatch:{name}")
    return not reasons, reasons


def _sealed_run_proof(sealed_root: Path | None, project_id: str, expected_shas: set[str]) -> tuple[bool, int | None, list[str]]:
    """Verify complete production seal fingerprints, lineage and source envelope."""
    if sealed_root is None:
        return False, None, ["sealed_run_not_supplied"]
    path = sealed_root / project_id / "sealed_run.json"
    if not path.is_file():
        return False, None, ["sealed_run_missing"]
    from pb_source_closed_run_export import sealed_source_closed_run_from_dict

    try:
        sealed = sealed_source_closed_run_from_dict(_object(path))
    except (TypeError, ValueError, KeyError) as exc:
        return False, None, ["sealed_run_integrity_invalid"]
    if sealed.project_id != project_id:
        return False, len(sealed.quantities), ["sealed_run_project_mismatch"]
    reasons: list[str] = []
    if set(sealed.source_sha256s) != expected_shas:
        reasons.append("sealed_run_source_envelope_mismatch")
    if not sealed.quantities:
        reasons.append("sealed_run_empty")
    if any(not row.lineage_ok for row in sealed.quantities):
        reasons.append("sealed_run_lineage_conflict")
    if any(not row.object_identity_refs and not row.abstained for row in sealed.quantities):
        reasons.append("sealed_run_missing_physical_identity")
    return not reasons, len(sealed.quantities), reasons

def diagnostic_report(root: Path, produced_root: Path, source_root: Path | None = None, sealed_root: Path | None = None) -> dict:
    suite = _object(root / "manifest.json")
    project_ids = suite["projects"]
    required_count = suite["required_project_count"]
    if (
        not isinstance(project_ids, list)
        or not isinstance(required_count, int)
        or len(project_ids) != required_count
        or len(set(project_ids)) != required_count
    ):
        raise ValueError("invalid frozen suite project list")
    projects = []
    for project_id in project_ids:
        if not isinstance(project_id, str) or not project_id:
            raise ValueError("invalid frozen project id")
        manifest = _object(root / "projects" / project_id / "source_manifest.json")
        if manifest.get("project_id") != project_id:
            raise ValueError(f"frozen project identity mismatch: {project_id}")
        path = produced_root / project_id / "produced_items.json"
        exists = path.is_file()
        if exists:
            produced = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(produced, list) or any(not isinstance(x, dict) for x in produced):
                raise ValueError(f"{path} must contain a JSON list of objects")
            ids = [str(item["quantity_id"]) for item in produced]
        else:
            produced, ids = [], []
        duplicate_ids = sorted(k for k, count in Counter(ids).items() if count > 1)
        eligible = manifest.get("verified_takeoff_items", [])
        denominator = sum(item.get("denominator_eligible", True) is True for item in eligible)
        blockers = list(manifest.get("reason_codes") or ())
        source_verified, source_reasons = _source_sha_proof(manifest, source_root, project_id)
        blockers.extend(source_reasons)
        expected_shas = {doc["sha256"] for doc in manifest.get("source_documents", ())}
        seal_verified, sealed_count, seal_reasons = _sealed_run_proof(sealed_root, project_id, expected_shas)
        blockers.extend(seal_reasons)
        if manifest.get("status") != "VERIFIED":
            blockers.insert(0, "frozen_manifest_not_verified")
        if not exists:
            blockers.append("production_items_missing")
        if duplicate_ids:
            blockers.append("duplicate_produced_quantity_ids")
        if any(item.get("lineage_ok") is not True for item in produced):
            blockers.append("production_lineage_conflict_or_unverified")
        if not produced and exists:
            blockers.append("empty_produced_items_unverified")
        projects.append({
            "project_id": project_id,
            "manifest_status": manifest.get("status"),
            "denominator": denominator,
            "produced_file_present": exists,
            "produced_count": len(produced) if exists else None,
            "lineage_conflict_count": sum(item.get("lineage_ok") is not True for item in produced) if exists else None,
            "abstention_count": sum(item.get("abstained") is True for item in produced) if exists else None,
            "duplicate_quantity_ids": duplicate_ids,
            "source_sha_verified": source_verified,
            "sealed_run_verified": seal_verified,
            "sealed_quantity_count": sealed_count,
            "reconciliation_complete": False,
            "blockers": sorted(set(blockers)),
            "coverage_accuracy": None,
            "precision_adjusted_accuracy": None,
        })
    return {
        "report_type": "FULL_PLAN_V2_READINESS_DIAGNOSTIC",
        "publication_status": "UNPUBLISHED",
        "score_claim": False,
        "required_project_count": required_count,
        "projects": projects,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--produced-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--sealed-root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = diagnostic_report(args.benchmark_root, args.produced_root, args.source_root, args.sealed_root)
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
