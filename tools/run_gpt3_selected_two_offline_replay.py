"""Offline, no-private-GitHub-repo original-source two-project V2 replay.

Consumes the exact two previously SHA-pinned archived GitHub Actions ZIPs and
the owner's original PDFs in a private local directory. Extracts only DERIVED
signed evidence into an isolated temporary directory and independently checks
original PDF sizes/SHA, signed seals, customer bijections, frozen identity maps
and unchanged exact-project evaluator. Development only (51 targets): NEVER
publishes the official four-project/120-target accuracy.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from zipfile import ZipFile, BadZipFile

from scripts.report_full_plan_v2_readiness import _write_readiness_report
from tools.report_gpt3_selected_two_project_original_evidence import (
    build_selected_two_project_development_evidence,
)
from tools.report_gpt3_four_project_evidence import FROZEN_ROOT

# Original, independently pinned CI output archive digests (not PDF digests).
_LOT16_ZIP_SHA = "950e1074d270e6b1d4558b165e5345cf49b2ac0c962a3cc8edf420f11f67bd91"
_MARY_ZIP_SHA = "df0b3e42bf3b2b3aace43f155b7feec087dbfa5e55559ec7f16714577ef5e7b0"
_MAX_SINGLE_FILE = 64 * 1024 * 1024
_MAX_EXTRACTED = 256 * 1024 * 1024

_CASES = (
    {
        "project": "au_qld_lot16_power", "subdir": "lot16",
        "source": "1. Construction Plans - Lot 16 Power (REV E).pdf",
        "sealed": "production/source_sealed_run.json",
        "customer": "production/verified_customer_rows.json",
        "identity_map": "identity_map_with_1215.json",
        "exact_report": "exact_project_report.json",
    },
    {
        "project": "au_qld_maryborough_service_station",
        "subdir": "maryborough",
        "source": "Arch_Combined_Maryborough_Service_Station.pdf",
        "sealed": "source/production/source_sealed_run.json",
        "customer": "source/production/verified_customer_rows.json",
        "identity_map": "identity_map.json",
        "exact_report": "exact_project_report.json",
    },
)


def _digest(path: Path) -> str:
    h = sha256()
    with path.open("rb") as reader:
        for chunk in iter(lambda: reader.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _original(root: Path, project: str, name: str) -> Path:
    """Allow flat or project-scoped original path, but never choose conflict."""
    if Path(name).name != name or not name.lower().endswith(".pdf"):
        raise ValueError("original filename is not a canonical PDF basename")
    flat = root / name
    scoped = root / project / name
    choices = [p for p in (flat, scoped) if p.is_file()]
    if len(choices) != 1:
        if len(choices) == 2 and _digest(choices[0]) == _digest(choices[1]):
            return choices[0]
        raise ValueError("original PDF unavailable or ambiguous between flat and project-scoped paths")
    return choices[0]


def _unpack_pinned_derived_archive(archive: Path, destination: Path, digest: str) -> None:
    """Validate ZIP SHA and member universe before touching extracted evidence."""
    if not archive.is_file() or _digest(archive) != digest:
        raise ValueError("archived signed source package ZIP SHA mismatch")
    seen: set[str] = set()
    try:
        with ZipFile(archive, "r") as zf:
            files = []
            total = 0
            for member in zf.infolist():
                path = PurePosixPath(member.filename)
                if (
                    not member.filename or "\\" in member.filename
                    or path.is_absolute() or ".." in path.parts
                    or not path.parts or path.parts[0] in ("", ".")
                    or ":" in path.parts[0]
                ):
                    raise ValueError("unsafe derived source archive path")
                if member.is_dir():
                    continue
                # A ZIP Unix symlink must never follow outside temporary space.
                mode = (member.external_attr >> 16) & 0o170000
                if mode == 0o120000:
                    raise ValueError("derived source archive contains a symlink")
                if member.filename in seen:
                    raise ValueError("duplicate derived source archive member")
                seen.add(member.filename)
                if path.suffix.lower() == ".pdf":
                    raise ValueError("private source PDF cannot be shipped in a derived receipt archive")
                if member.file_size > _MAX_SINGLE_FILE:
                    raise ValueError("oversized derived source archive member")
                total += member.file_size
                if total > _MAX_EXTRACTED:
                    raise ValueError("derived source archive exceeds safe extraction limit")
                files.append((member, path))
            if not files:
                raise ValueError("derived source archive has no receipt files")
            for member, path in files:
                target = destination.joinpath(*path.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as reader, target.open("xb") as out:
                    shutil.copyfileobj(reader, out, length=1024 * 1024)
    except (BadZipFile, OSError) as exc:
        raise ValueError("archived signed source ZIP is unreadable") from exc


def _entries(root: Path, sources: Path) -> list[dict]:
    entries = []
    for case in _CASES:
        project, subdir = case["project"], case["subdir"]
        member_root = root / subdir
        manifest = FROZEN_ROOT / "projects" / project / "source_manifest.json"
        entries.append({
            "manifest": str(manifest),
            "original_files": [str(_original(sources, project, case["source"]))],
            "sealed": str(member_root / case["sealed"]),
            "customer": str(member_root / case["customer"]),
            "identity_map": str(member_root / case["identity_map"]),
            "exact_report": str(member_root / case["exact_report"]),
        })
    return entries


def _require_dev_only(report: dict) -> None:
    """Never rebrand selected results as the official four-project suite."""
    if (
        report.get("publication_status") != "SELECTED_PROJECT_DEVELOPMENT_ONLY"
        or report.get("selected_project_count") != 2
        or report.get("selected_denominator") != 51
        or report.get("official_four_project_suite_result") is not None
        or report.get("official_four_project_accuracy") is not None
        or report.get("full_four_project_publication_allowed") is not False
    ):
        raise ValueError("selected replay cannot publish four-project benchmark accuracy")


def run(
    *, sources: Path, lot16_archive: Path, maryborough_archive: Path, output: Path,
) -> dict:
    inputs = (sources, lot16_archive, maryborough_archive, FROZEN_ROOT)
    destination = output.resolve()
    if output.is_symlink() or output.exists() or any(
        destination == p.resolve() or destination.is_relative_to(p.resolve())
        for p in inputs if p.is_dir()
    ) or destination in (lot16_archive.resolve(), maryborough_archive.resolve()):
        raise ValueError("offline development output must be a new path outside all sources")
    # Stage only derived customer/producer files, never the original PDFs.
    with tempfile.TemporaryDirectory(prefix="gpt3-selected-private-") as tmp:
        stage = Path(tmp)
        _unpack_pinned_derived_archive(lot16_archive, stage / "lot16", _LOT16_ZIP_SHA)
        _unpack_pinned_derived_archive(maryborough_archive, stage / "maryborough", _MARY_ZIP_SHA)
        report = build_selected_two_project_development_evidence(_entries(stage, sources))
        _require_dev_only(report)
        _write_readiness_report(
            output, json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n",
            protected_roots=inputs + (stage,),
        )
        return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--lot16-archive", required=True, type=Path)
    parser.add_argument("--maryborough-archive", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    result = run(
        sources=args.source_dir, lot16_archive=args.lot16_archive,
        maryborough_archive=args.maryborough_archive, output=args.output,
    )
    print(json.dumps({
        "status": result["publication_status"],
        "selected_denominator": result["selected_denominator"],
        "selected_matched": result["matched_within_tolerance"],
        "official_four_project_accuracy": None,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
