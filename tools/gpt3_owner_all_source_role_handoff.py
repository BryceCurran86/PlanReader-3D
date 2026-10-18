"""Owner-only, role-complete source-closed project handoff.

Unlike four_job_windows_launcher (primary architectural PDF only), this opt-in
runner independently produces every frozen original SOURCE DOCUMENT role. It
never invents a multi-PDF source SHA or blesses a missing producer. It uses the
existing sealed-run verifier and composer only when *every* original document
produced an actual canonical seal; absent/empty secondary documents remain
unsealed negative evidence, not a source-complete or scored result.

No PDF is uploaded or copied; all output stays under an owner-chosen private
destination, and no evaluator/benchmark mapping is invoked.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any

import fitz

from pb_combine_source_closed_runs import (
    combine_sealed_run_files, load_verified_sealed_run,
)
from tools.four_job_windows_launcher import PROJECTS, run_logged
from tools.report_gpt3_four_project_evidence import FROZEN_ROOT, _json_object

_SHA = re.compile(r"^[0-9a-f]{64}$")


def _sha256(path: Path) -> str:
    h = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _source(root: Path, project_id: str, name: str) -> Path:
    if (
        type(name) is not str or name != Path(name).name
        or name in (".", "..") or "/" in name or "\\" in name
        or not name.lower().endswith(".pdf")
    ):
        raise ValueError("source manifest includes an unsafe PDF name")
    choices = (root / name, root / project_id / name)
    found = [p for p in choices if p.is_file() and not p.is_symlink()]
    if any(p.is_symlink() for p in choices):
        raise ValueError("source document symlink cannot be authenticated")
    if len(found) == 2:
        if _sha256(found[0]) != _sha256(found[1]):
            raise ValueError("conflicting flat and project-scope source copies")
        return found[0]
    if len(found) != 1:
        raise FileNotFoundError("original source document role is absent")
    return found[0]


def original_roster(project_id: str, root: Path) -> list[dict[str, Any]]:
    if project_id not in PROJECTS or root.is_symlink() or not root.is_dir():
        raise ValueError("invalid original source project or directory")
    manifest_path = FROZEN_ROOT / "projects" / project_id / "source_manifest.json"
    manifest = _json_object(manifest_path)
    if manifest.get("project_id") != project_id:
        raise ValueError("frozen project identifier mismatch")
    documents = manifest.get("source_documents")
    if type(documents) is not list or not documents:
        raise ValueError("frozen source document role universe missing")
    seen: set[str] = set()
    roster = []
    for row in documents:
        if type(row) is not dict:
            raise ValueError("invalid frozen source role declaration")
        name, role = row.get("name"), row.get("role")
        digest, count, size = row.get("sha256"), row.get("page_count"), row.get("size_bytes")
        if (
            type(name) is not str or name.casefold() in seen
            or type(role) is not str or not role.strip()
            or type(digest) is not str or not _SHA.fullmatch(digest)
            or type(count) is not int or count < 1
            or type(size) is not int or size < 1
        ):
            raise ValueError("malformed original source role declaration")
        seen.add(name.casefold())
        path = _source(root, project_id, name)
        if path.stat().st_size != size or _sha256(path) != digest:
            raise ValueError("frozen original PDF byte authentication rejected source")
        with fitz.open(path) as pdf:
            if len(pdf) != count:
                raise ValueError("original PDF page count differs from frozen source")
        roster.append({
            "role": role, "sha256": digest, "page_count": count,
            "path": path,
        })
    return roster


def _write_summary(path: Path, report: dict) -> None:
    # Report is share-safe: no PDF bytes, local filenames, home paths, customer
    # notes or material is allowed. Only project ID, SHA, roles and status.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_exclusive(path: Path, content: str) -> None:
    if path.exists() or path.is_symlink():
        raise FileExistsError("sealed cross-role output already exists")
    stage: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", dir=path.parent, prefix=".source-roles-", suffix=".tmp",
            encoding="utf-8", delete=False,
        ) as handle:
            stage = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(stage, path)
    finally:
        if stage is not None:
            stage.unlink(missing_ok=True)


def produce_all_source_roles(
    *, project_id: str, source_dir: Path, output_dir: Path,
    family_group: str = "all", timeout_min: int = 180,
    max_private_gb: float = 10, min_free_commit_gb: float = 3,
) -> dict[str, Any]:
    if family_group not in ("all", "core", "surfaces", "floor_area"):
        raise ValueError("invalid canonical source producer family")
    if (
        type(timeout_min) is not int or timeout_min < 1
        or not 0 < max_private_gb < 100000
        or not 0 <= min_free_commit_gb < 100000
    ):
        raise ValueError("unsafe source role resource limits")
    # Validate all original bytes before creating any source producer output.
    roster = original_roster(project_id, source_dir)
    dest = output_dir.resolve()
    inputs = (source_dir.resolve(), FROZEN_ROOT.resolve())
    if (
        output_dir.exists() or output_dir.is_symlink()
        or any(dest == root or dest.is_relative_to(root) for root in inputs)
    ):
        raise ValueError("owner source role output must be a new private location")
    output_dir.mkdir(parents=True, exist_ok=False)
    report: dict[str, Any] = {
        "schema_version": "gpt3-owner-original-role-attempt-v1",
        "project_id": project_id,
        "expected_source_document_roles": len(roster),
        "source_sha_verified": True,
        "roles": [],
        "source_role_coverage_verified": False,
        "customer_bijection_verified": False,
        "benchmark_score_granted": False,
        "official_four_project_accuracy": None,
        "status": "INCOMPLETE",
    }
    sealed: list[Path] = []
    for index, role in enumerate(roster):
        role_dir = output_dir / ("source_role_%02d" % (index + 1))
        role_dir.mkdir(parents=True)
        command = [
            sys.executable, "-m", "tools.run_source_closed_project_handoff",
            "--pdf", str(role["path"]), "--project-id", project_id,
            "--family-group", family_group, "--output-dir", str(role_dir),
        ]
        rc, status, _usage = run_logged(
            command, Path(__file__).resolve().parents[1],
            output_dir / ("source_role_%02d.log" % (index + 1)),
            timeout_s=timeout_min * 60, track_memory=True,
            max_private_mb=int(max_private_gb * 1024),
            min_free_commit_mb=int(min_free_commit_gb * 1024),
        )
        row = {
            "role": role["role"], "sha256": role["sha256"],
            "process_status": status, "process_exit_code": rc,
            "sealed": False,
            "first_failure": None,
        }
        if rc == 0 and status == "COMPLETED":
            summary_file = role_dir / "production_summary.json"
            if summary_file.is_file():
                summary = _json_object(summary_file)
                file = summary.get("combined_run_file")
                if summary.get("status") == "sealed" and type(file) is str:
                    sealed_file = Path(file)
                    if (
                        sealed_file.resolve().parent == role_dir.resolve()
                        and sealed_file.is_file() and not sealed_file.is_symlink()
                    ):
                        try:
                            signed = load_verified_sealed_run(sealed_file)
                        except (OSError, TypeError, ValueError, RuntimeError):
                            row["first_failure"] = "original_role_signed_receipt_invalid"
                        else:
                            if (
                                signed.project_id == project_id
                                and set(signed.source_sha256s) == {role["sha256"]}
                            ):
                                sealed.append(sealed_file)
                                row["sealed"] = True
                            else:
                                row["first_failure"] = "original_role_seal_source_envelope_conflict"
                    else:
                        row["first_failure"] = "role_seal_output_path_untrusted"
                else:
                    row["first_failure"] = "role_producer_no_sealable_result"
            else:
                row["first_failure"] = "role_producer_summary_missing"
        else:
            row["first_failure"] = "role_producer_did_not_complete"
        report["roles"].append(row)
        _write_summary(output_dir / "SOURCE_ROLE_STATUS.json", report)
        # Only original roles that produce a genuine, individually authentic
        # run are allowed in the cross-document signer. Missing roles veto
        # aggregate publication: do not stuff their SHA into an envelope.
    if len(sealed) == len(roster):
        combined = combine_sealed_run_files(sealed, project_id=project_id)
        expected = {x["sha256"] for x in roster}
        if set(combined.source_sha256s) != expected:
            raise ValueError("combined original-role SHA universe mismatch")
        _write_exclusive(output_dir / "ALL_SOURCE_ROLES.sealed.json", combined.to_json())
        report["source_role_coverage_verified"] = True
        report["status"] = "ALL_ROLES_SEALED_CUSTOMER_AND_V2_PENDING"
    else:
        report["status"] = "SOURCE_ROLES_INCOMPLETE"
    _write_summary(output_dir / "SOURCE_ROLE_STATUS.json", report)
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-id", required=True, choices=PROJECTS)
    p.add_argument("--source-dir", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--family-group", choices=("all", "core", "surfaces", "floor_area"), default="all")
    p.add_argument("--timeout-min", type=int, default=180)
    p.add_argument("--max-private-gb", type=float, default=10)
    p.add_argument("--min-free-commit-gb", type=float, default=3)
    args = p.parse_args(argv)
    report = produce_all_source_roles(
        project_id=args.project_id, source_dir=args.source_dir,
        output_dir=args.output_dir, family_group=args.family_group,
        timeout_min=args.timeout_min, max_private_gb=args.max_private_gb,
        min_free_commit_gb=args.min_free_commit_gb,
    )
    print(json.dumps({
        "status": report["status"],
        "project_id": report["project_id"],
        "sealed_roles": sum(row["sealed"] for row in report["roles"]),
        "required_roles": report["expected_source_document_roles"],
        "official_four_project_accuracy": None,
    }, sort_keys=True))
    return 0 if report["source_role_coverage_verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
