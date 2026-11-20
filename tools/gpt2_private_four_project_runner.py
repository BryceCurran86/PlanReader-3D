"""Private original-source gate and exact-head original PlanReader handoff.

No frozen-truth, benchmark scoring, source bytes or customer values are read
by this guard. It verifies *only* the source_documents role in the four
immutable source manifests before invoking the existing production issuer.
Use only on an authorized private runner; never log original PDF names/paths.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any

from tools.diag_gpt1_source_pdf_package_preflight import check_source_pdf_package

PROJECTS = (
    "au_qld_3laurel",
    "au_qld_lot16_power",
    "au_qld_maryborough_service_station",
    "au_qld_q5446_armstrong32_harlequin",
)
_EXPECTED_COUNTS = (1, 2, 1, 6)
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_REPO = Path(__file__).resolve().parents[1]
_MANIFESTS = _REPO / "benchmarks/frozen_holdout/full_plan_v2/projects"


class PrivateSourceGateError(ValueError):
    """A generic failure; private names and path details are never printed."""


def _source_root_from_argument(root: Path | None) -> Path:
    if root is None:
        configured = os.getenv("PLANREADER_PRIVATE_SOURCE_ROOT", "")
        if not configured.strip():
            raise PrivateSourceGateError("private_source_root_not_configured")
        root = Path(configured)
    if not isinstance(root, Path):
        raise PrivateSourceGateError("invalid_private_source_root")
    try:
        # An aliased root can point into another tenant's source collection.
        if root.is_symlink() or not root.is_dir() or root.resolve(strict=True) != root.absolute():
            raise PrivateSourceGateError("private_source_root_not_trusted")
    except OSError as exc:
        raise PrivateSourceGateError("private_source_root_unavailable") from exc
    return root


def verify_private_original_roster(
    source_root: Path | None = None,
    *,
    manifest_root: Path = _MANIFESTS,
) -> dict[str, Any]:
    """Verify the unchanged four-project/ten-PDF roster without exposing names.

    Fails closed on malformed/duplicate metadata, private source aliases,
    unreadable data, SHA/byte count or page count mismatch. The authoritative
    per-file verifier lives in diag_gpt1_source_pdf_package_preflight.
    """
    root = _source_root_from_argument(source_root)
    identities: dict[str, tuple[str, int, int, str]] = {}
    primary: dict[str, Path] = {}
    fingerprint_rows: list[tuple[str, str, str, int, int]] = []
    try:
        for project, expected_count in zip(PROJECTS, _EXPECTED_COUNTS):
            manifest = manifest_root / project / "source_manifest.json"
            raw = json.loads(manifest.read_text(encoding="utf-8"))
            documents = raw["source_documents"]
            if (
                raw.get("project_id") != project
                or type(documents) is not list or len(documents) != expected_count
            ):
                raise PrivateSourceGateError("private_source_manifest_roster_invalid")
            result = check_source_pdf_package(manifest, root)
            if (
                result["expected_source_document_count"] != expected_count
                or result["verified_source_document_count"] != expected_count
                or not result["actual_source_package_runtime_complete"]
            ):
                raise PrivateSourceGateError("private_source_package_not_verified")
            architects: list[str] = []
            for doc in documents:
                name, sha, size = doc["name"], doc["sha256"], doc["size_bytes"]
                count, role = doc["page_count"], doc["role"]
                key = name.casefold()
                identity = (sha, size, count, name)
                if key in identities and identities[key] != identity:
                    raise PrivateSourceGateError("private_source_manifest_identity_conflict")
                identities[key] = identity
                fingerprint_rows.append((project, role, sha, size, count))
                if role == "architectural_drawings":
                    architects.append(name)
            if len(architects) != 1:
                raise PrivateSourceGateError("private_source_architectural_role_missing")
            primary[project] = root / architects[0]
    except PrivateSourceGateError:
        raise
    except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
        # Never place private path, filename, document identity or drawing text
        # from an underlying I/O error into a public issue or CI log.
        raise PrivateSourceGateError("private_source_manifest_or_roster_invalid") from exc
    if len(identities) != 10 or len(fingerprint_rows) != 10:
        raise PrivateSourceGateError("private_source_roster_count_mismatch")
    fingerprint = hashlib.sha256(json.dumps(sorted(fingerprint_rows), separators=(",", ":")).encode()).hexdigest()
    return {
        "verified": True,
        "source_documents_verified": 10,
        "projects_verified": 4,
        "source_manifest_fingerprint": fingerprint,
        "architectural_inputs": primary,  # PRIVATE in-memory, never JSON/log
        "commercial_quantity_publication_granted": False,
        "benchmark_score_granted": False,
    }


def _verify_exact_checkout(expected_sha: str, *, repo: Path = _REPO) -> None:
    if type(expected_sha) is not str or _SHA.fullmatch(expected_sha) is None:
        raise PrivateSourceGateError("expected_checkout_sha_invalid")
    try:
        actual = subprocess.check_output(
            ("git", "-C", str(repo), "rev-parse", "HEAD"),
            stderr=subprocess.DEVNULL, timeout=10, text=True,
        ).strip()
        if actual != expected_sha:
            raise PrivateSourceGateError("checkout_head_mismatch")
        # Uncommitted code could invalidate the exact-head test receipt.
        dirty = subprocess.check_output(
            ("git", "-C", str(repo), "status", "--porcelain", "--untracked-files=no"),
            stderr=subprocess.DEVNULL, timeout=10, text=True,
        )
        if dirty.strip():
            raise PrivateSourceGateError("checkout_tracked_files_modified")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        raise PrivateSourceGateError("checkout_head_cannot_be_authenticated") from exc


def run_verified_private_handoff(
    *,
    project_id: str,
    expected_head_sha: str,
    output_dir: Path,
    source_root: Path | None = None,
    family_group: str = "all",
    source_plan_page_index: int | None = None,
) -> dict[str, Any]:
    """Invoke existing production source→issuer only after complete private gate.

    No benchmark denominator or scoring logic is reachable here. On failure,
    the caller never mistakes an archived/synthetic source for accepted ink.
    """
    if project_id not in PROJECTS:
        raise PrivateSourceGateError("project_not_in_frozen_source_roster")
    if not isinstance(output_dir, Path):
        raise PrivateSourceGateError("private_output_directory_required")
    if family_group not in ("all", "core", "surfaces", "floor_area"):
        raise PrivateSourceGateError("invalid_family_group")
    if source_plan_page_index is not None and (
        type(source_plan_page_index) is not int or source_plan_page_index < 0
        or family_group not in ("core", "floor_area")
    ):
        raise PrivateSourceGateError("invalid_partial_plan_scope")
    # Authenticate the checked-out code BEFORE reading any private source.
    # An untrusted PR may never gain source access by supplying its own SHA.
    _verify_exact_checkout(expected_head_sha)
    roster = verify_private_original_roster(source_root)
    source = roster["architectural_inputs"][project_id]
    private_root = source.parent.resolve(strict=True)
    # Resolve ancestor symlinks too; a direct is_symlink() misses an aliased
    # parent that could redirect new outputs over source PDFs or frozen truth.
    output_absolute = output_dir.resolve(strict=False)
    repo_root = _REPO.resolve(strict=True)
    if output_absolute == private_root or private_root in output_absolute.parents:
        raise PrivateSourceGateError("output_inside_private_original_source_root")
    if output_absolute == repo_root or repo_root in output_absolute.parents:
        raise PrivateSourceGateError("output_inside_public_checkout")
    from tools.run_source_closed_project_handoff import generate_project_handoff
    result = generate_project_handoff(
        pdf_path=source,
        project_id=project_id,
        workspace_id=1,
        output_dir=output_dir,
        family_group=family_group,
        source_plan_page_index=source_plan_page_index,
    )
    # The original roster must still be present and byte-identical after the
    # producer; do not mark a changed source as an accepted replay.
    after = verify_private_original_roster(source_root)
    if after["source_manifest_fingerprint"] != roster["source_manifest_fingerprint"]:
        raise PrivateSourceGateError("private_source_roster_changed_during_run")
    return {
        "source_roster_verified": True,
        "original_source_pipeline_executed": True,
        "source_manifest_fingerprint": roster["source_manifest_fingerprint"],
        "production_run_status": str(result.get("status") or "UNKNOWN"),
        "benchmark_score_granted": False,
        "verified_customer_quantity_granted_by_preflight": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, help="private root; defaults to PLANREADER_PRIVATE_SOURCE_ROOT")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--project", choices=PROJECTS)
    parser.add_argument("--expected-head-sha")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--family-group", choices=("all", "core", "surfaces", "floor_area"), default="all")
    parser.add_argument("--source-plan-page-index", type=int)
    args = parser.parse_args(argv)
    try:
        if args.preflight_only:
            if args.project or args.expected_head_sha or args.output_dir or args.source_plan_page_index is not None:
                raise PrivateSourceGateError("preflight_only_cannot_run_production")
            receipt = verify_private_original_roster(args.source_root)
            safe = {k: v for k, v in receipt.items() if k != "architectural_inputs"}
        else:
            if not args.project or not args.expected_head_sha or args.output_dir is None:
                raise PrivateSourceGateError("private_run_requires_project_head_and_output")
            safe = run_verified_private_handoff(
                project_id=args.project,
                expected_head_sha=args.expected_head_sha,
                output_dir=args.output_dir,
                source_root=args.source_root,
                family_group=args.family_group,
                source_plan_page_index=args.source_plan_page_index,
            )
    except PrivateSourceGateError as exc:
        print(json.dumps({"status": "SOURCE_BLOCKED", "reason": str(exc), "benchmark_score_granted": False}))
        return 2
    print(json.dumps(safe, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
