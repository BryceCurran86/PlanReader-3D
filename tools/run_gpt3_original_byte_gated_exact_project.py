"""Require actual original-source bytes before invoking unchanged V2 project reconciliation.

This is a project-only source-evidence wrapper. It cannot publish the complete
four-project 120-object suite score or modify frozen benchmark references.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from scripts.report_full_plan_v2_readiness import _write_readiness_report
from tools.gpt3_signed_v2_family_trade_integrity import (
    require_signed_v2_family_trade_integrity,
)

FROZEN_ROOT = (
    Path(__file__).resolve().parents[1]
    / "benchmarks" / "frozen_holdout" / "full_plan_v2"
)


def _strict_original_json_object(path: Path) -> dict[str, Any]:
    """Do not let a duplicated source identity be overwritten before validation.

    The frozen scorer remains unchanged. This wrapper rejects ambiguous
    external on-disk manifest, sealed run and identity-map JSON *before* it
    invokes that scorer or credits the original-source SHA receipt.
    """
    def unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"original signed source JSON has duplicate key: {key}")
            result[key] = value
        return result

    value = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys
    )
    if type(value) is not dict:
        raise ValueError("original signed source JSON must be an object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _original_sha_gate(
    manifest: dict[str, Any], original_files: Sequence[Path],
) -> tuple[bool, list[str], list[str]]:
    """Match *all* supplied original PDF bytes and names to frozen manifest."""
    documents = manifest.get("source_documents")
    if not isinstance(documents, list) or not documents:
        return False, ["source_manifest_document_universe_invalid"], []
    expected: dict[str, tuple[str, int]] = {}
    for document in documents:
        if not isinstance(document, dict):
            return False, ["source_manifest_document_universe_invalid"], []
        name = document.get("name")
        sha = document.get("sha256")
        size = document.get("size_bytes")
        if (
            not isinstance(name, str) or not name
            or Path(name).name != name or name in expected
            or not isinstance(sha, str) or len(sha) != 64
            or type(size) is not int or size < 0
        ):
            return False, ["source_manifest_document_universe_invalid"], []
        expected[name] = (sha, size)

    actual_names = [p.name for p in original_files]
    if len(set(actual_names)) != len(actual_names) or set(actual_names) != set(expected):
        return False, ["original_source_file_universe_mismatch"], []
    actual_hashes: list[str] = []
    for path in original_files:
        try:
            if not path.is_file():
                return False, [f"original_source_missing:{path.name}"], []
            expected_sha, expected_size = expected[path.name]
            if path.stat().st_size != expected_size:
                return False, [f"original_source_size_mismatch:{path.name}"], []
            actual_sha = _sha256(path)
        except OSError:
            return False, [f"original_source_unreadable:{path.name}"], []
        if actual_sha != expected_sha:
            return False, [f"original_source_sha_mismatch:{path.name}"], []
        actual_hashes.append(actual_sha)
    if len(set(actual_hashes)) != len(actual_hashes):
        return False, ["duplicate_original_source_sha"], []
    return True, [], sorted(actual_hashes)


def _unchanged_frozen_exact_report(
    manifest_path: Path, sealed_run_path: Path, identity_map_path: Path,
) -> dict:
    """Load the existing frozen reporting implementation without modifying it."""
    entrypoint = FROZEN_ROOT / "run_exact_project_reconciliation.py"
    spec = importlib.util.spec_from_file_location(
        "_gpt3_original_byte_gated_frozen_v2_report", entrypoint,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unchanged frozen exact-project reporter unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.build_exact_project_report(
        manifest_path=manifest_path,
        sealed_run_path=sealed_run_path,
        identity_map_path=identity_map_path,
    )


def build_original_byte_gated_project_report(
    *, manifest_path: Path, sealed_run_path: Path,
    identity_map_path: Path, original_files: Sequence[Path],
) -> dict:
    manifest_sha_before = _sha256(manifest_path)
    manifest = _strict_original_json_object(manifest_path)
    project_id = manifest.get("project_id")
    if not isinstance(project_id, str) or not project_id:
        raise ValueError("frozen project manifest has invalid project identity")
    # Never accept a caller-written or fixture manifest as benchmark authority.
    canonical_manifest = (
        FROZEN_ROOT / "projects" / project_id / "source_manifest.json"
    ).resolve()
    if manifest_path.resolve() != canonical_manifest:
        raise ValueError("must use exact frozen Full Plan V2 project manifest")
    if not original_files:
        return {
            "project_id": project_id, "publication_status": "UNPUBLISHED",
            "score_claim": False, "reconciliation_complete": False,
            "original_source_sha_verified": False,
            "source_sha256s": [],
            "reason_codes": ["original_source_files_not_supplied"],
            "project_evaluation": None,
        }

    verified, reasons, hashes = _original_sha_gate(manifest, original_files)
    if not verified:
        return {
            "project_id": project_id, "publication_status": "UNPUBLISHED",
            "score_claim": False, "reconciliation_complete": False,
            "original_source_sha_verified": False,
            "source_sha256s": [],
            "reason_codes": reasons,
            "project_evaluation": None,
        }
    if (
        manifest.get("status") != "VERIFIED"
        or manifest.get("source_package_complete") is not True
        or manifest.get("reason_codes")
    ):
        return {
            "project_id": project_id, "publication_status": "UNPUBLISHED",
            "score_claim": False, "reconciliation_complete": False,
            "original_source_sha_verified": True,
            "source_sha256s": hashes,
            "reason_codes": sorted(set(
                ["frozen_project_universe_incomplete"]
                + list(manifest.get("reason_codes") or ())
            )),
            "project_evaluation": None,
        }
    try:
        sealed_before = _sha256(sealed_run_path)
        identity_before = _sha256(identity_map_path)
        sealed_claim = _strict_original_json_object(sealed_run_path)
        identity_claim = _strict_original_json_object(identity_map_path)
    except (OSError, ValueError, TypeError, UnicodeError):
        return {
            "project_id": project_id, "publication_status": "UNPUBLISHED",
            "score_claim": False, "reconciliation_complete": False,
            "original_source_sha_verified": True,
            "source_sha256s": hashes,
            "reason_codes": ["sealed_or_identity_source_artifact_unavailable"],
            "project_evaluation": None,
        }
    # The unchanged frozen per-project reporter accepts SHA *subsets* for a
    # diagnostic. The project-only external source-publication gate must
    # require EVERY original source document in both signed production
    # envelopes. A partially ingested six-PDF source package cannot publish.
    required_hashes = set(hashes)
    claimed_envelopes = [
        sealed_claim.get("source_sha256s"),
        identity_claim.get("source_sha256s"),
    ]
    if any(
        type(value) is not list or len(value) != len(required_hashes)
        or any(type(sha) is not str or len(sha) != 64 for sha in value)
        or len(set(value)) != len(value) or set(value) != required_hashes
        for value in claimed_envelopes
    ):
        return {
            "project_id": project_id, "publication_status": "UNPUBLISHED",
            "score_claim": False, "reconciliation_complete": False,
            "original_source_sha_verified": True,
            "source_sha256s": hashes,
            "reason_codes": ["signed_production_source_package_incomplete"],
            "project_evaluation": None,
        }

    # An independently supplied identity map must not reclassify a genuine
    # producer-owned floor_area as tiling/ceiling, or a window as a door.
    # Signed source documents and complete original source envelopes were
    # already authenticated above. Check before invoking frozen scoring.
    require_signed_v2_family_trade_integrity(
        verified_items=manifest.get("verified_takeoff_items") or (),
        sealed_quantities=sealed_claim.get("quantities") or (),
        identity_bindings=identity_claim.get("bindings") or (),
    )
    # It is safe to consult the unchanged frozen evaluator only after the
    # immutable manifest says this project's source/denominator is complete.
    report = _unchanged_frozen_exact_report(
        manifest_path, sealed_run_path, identity_map_path,
    )
    after_ok, after_reasons, after_hashes = _original_sha_gate(manifest, original_files)
    try:
        artifacts_unchanged = (
            _sha256(sealed_run_path) == sealed_before
            and _sha256(identity_map_path) == identity_before
            and _sha256(manifest_path) == manifest_sha_before
        )
    except OSError:
        artifacts_unchanged = False
    if not after_ok or after_hashes != hashes or not artifacts_unchanged:
        return {
            "project_id": project_id, "publication_status": "UNPUBLISHED",
            "score_claim": False, "reconciliation_complete": False,
            "original_source_sha_verified": False,
            "source_sha256s": [],
            "reason_codes": after_reasons or ["source_or_signed_artifact_changed_during_reconciliation"],
            "project_evaluation": None,
        }
    if (
        report.get("source_sha_verified") is not True
        or report.get("reconciliation_complete") is not True
        or report.get("project_id") != project_id
    ):
        raise ValueError("unchanged frozen reconciliation rejected signed source identity")
    return {
        "project_id": project_id,
        "publication_status": "PROJECT_ONLY_FOUR_PROJECT_SUITE_UNPUBLISHED",
        "score_claim": False,
        "reconciliation_complete": True,
        "original_source_sha_verified": True,
        "source_sha256s": hashes,
        "reason_codes": ["full_four_project_suite_publication_not_proven"],
        "project_evaluation": report,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--sealed-run", type=Path, required=True)
    parser.add_argument("--identity-map", type=Path, required=True)
    parser.add_argument("--source", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    # Validate output *before* reading potentially huge original PDF bytes.
    # A diagnostic must never replace an unrelated source or customer artifact.
    if args.output.is_symlink():
        raise ValueError("original-byte project report cannot follow output symlinks")
    if args.output.exists():
        try:
            existing = _strict_original_json_object(args.output)
        except (OSError, ValueError, TypeError, UnicodeError) as exc:
            raise ValueError("original-byte project report cannot overwrite unrelated evidence") from exc
        if existing.get("project_id") is None or (
            existing.get("publication_status") not in ("PUBLISHED", "UNPUBLISHED")
            or "score_claim" not in existing
        ):
            raise ValueError("original-byte project report cannot overwrite unrelated evidence")
    report = build_original_byte_gated_project_report(
        manifest_path=args.manifest, sealed_run_path=args.sealed_run,
        identity_map_path=args.identity_map, original_files=args.source,
    )
    _write_readiness_report(
        args.output, json.dumps(report, indent=2, sort_keys=True) + "\n",
        protected_roots=(
            FROZEN_ROOT, args.manifest, args.sealed_run,
            args.identity_map, *args.source,
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
