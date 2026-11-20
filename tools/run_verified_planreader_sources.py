"""Run the REAL original PlanReader native preview using cached private owner PDFs.

One command, no repeated uploads, no diagnostic substitution. This launcher
never scores frozen120 or publishes private inputs to CI/GitHub.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARCHIVE_MANIFEST = "PlanReader_private_source_manifest_18_of_18_20261120.json"
# Independent owner inventory, hashed as canonical sorted [SHA-256, size]
# pairs. The ZIP's own manifest locates members and cannot authorize bytes.
_OWNER_ORIGINAL_ROSTER_SHA256 = "5cbb15a57170bd3f015f6386c5595c391938bdd9f6c410a1cc139d6db848665f"
_ARCHITECTURAL_SOURCE_SHA256 = {
    "3Laurel": "014e9f68b377bef4fb556de61b83a94388792dfa4bfb8ea981644f9c323e9e2e",
    "Lot16": "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844",
    "Maryborough": "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007",
    "Q5446": "5f29aa0122d72e2cc8886b3f19239ff32865c8d705eee99f785c389ca27fb7f0",
    "Acacia": "435a6b610fea904f2b27dc330667d92a25919ada3368e5905e58ff92e047f37a",
}
PROJECT_PAGES = {
    "3Laurel": (2,),  # Rev3 page 3; zero based
    "Lot16": (2, 3),  # architectural floor plan source pages 3 and 4
    "Maryborough": (6,),  # A110, original page 7
    "Q5446": (0, 1),  # ground and first floor
    "Acacia": (1,),  # original page 2
}


class PrivateSourceBlocked(ValueError):
    """Lack of correct bytes is a BLOCKED run, not zero accuracy."""


def _candidates(explicit: Path | None = None) -> list[Path]:
    if explicit is not None:
        return [explicit]
    value = os.environ.get("PLANREADER_PRIVATE_SOURCE_BUNDLE", "").strip()
    if value:
        return [Path(value).expanduser()]
    roots = [Path.cwd(), ROOT, Path("/mnt/data"), Path.home() / "Downloads"]
    extra = os.environ.get("PLANREADER_PRIVATE_SOURCE_CACHE", "").strip()
    if extra:
        roots.insert(0, Path(extra).expanduser())
    seen: set[Path] = set()
    found: list[Path] = []
    for root in roots:
        if root.is_dir():
            for item in root.glob("*source*.zip"):
                if item.is_file() and "planreader" in item.name.lower():
                    path = item.resolve()
                    if path not in seen:
                        seen.add(path)
                        found.append(path)
    return found


def _validate_archive(path: Path) -> tuple[dict, dict[str, dict]]:
    if not path.is_file():
        raise PrivateSourceBlocked("owner_private_source_archive_not_found")
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len({name.casefold() for name in names}) != len(names):
                raise PrivateSourceBlocked("duplicate_archive_paths_rejected")
            manifest_member = archive.getinfo(ARCHIVE_MANIFEST)
            if manifest_member.file_size > 64 * 1024:
                raise PrivateSourceBlocked("oversized_original_source_manifest")
            manifest = json.loads(archive.read(manifest_member))
            if not isinstance(manifest, dict):
                raise PrivateSourceBlocked("invalid_original_source_inventory")
            entries = manifest.get("available_files")
            if (
                manifest.get("expected_total") != 18
                or manifest.get("verified_file_count") != 18
                or manifest.get("missing_file_count") != 0
                or not isinstance(entries, list) or len(entries) != 18
            ):
                raise PrivateSourceBlocked("incomplete_original_source_inventory")
            indexed: dict[str, dict] = {}
            checked: set[str] = set()
            roster: list[tuple[str, int]] = []
            for item in entries:
                if not isinstance(item, dict):
                    raise PrivateSourceBlocked("invalid_original_source_record")
                name = item.get("relative_path")
                namepath = PurePosixPath(str(name))
                if (type(name) is not str or name != namepath.as_posix()
                        or "\\" in name or ":" in name or ".." in namepath.parts
                        or not name.startswith("documents/sources/")
                        or namepath.suffix.lower() != ".pdf"):
                    raise PrivateSourceBlocked("unsafe_private_source_archive_path")
                project, role = item.get("project"), item.get("role")
                if type(project) is not str or project not in PROJECT_PAGES:
                    raise PrivateSourceBlocked("unknown_original_source_project")
                if type(role) is not str or not role.strip():
                    raise PrivateSourceBlocked("invalid_original_source_role")
                if name.casefold() in checked:
                    raise PrivateSourceBlocked("duplicate_source_record")
                checked.add(name.casefold())
                size = item.get("bytes")
                if type(size) is not int or size <= 0:
                    raise PrivateSourceBlocked("invalid_original_file_size")
                expected = item.get("sha256", "")
                if not isinstance(expected, str) or not re.fullmatch("[a-f0-9]{64}", expected):
                    raise PrivateSourceBlocked("invalid_original_file_sha")
                roster.append((expected, size))
                if role == "architectural":
                    if project in indexed:
                        raise PrivateSourceBlocked("multiple_original_architectural_sources")
                    if expected != _ARCHITECTURAL_SOURCE_SHA256[project]:
                        raise PrivateSourceBlocked("wrong_original_architectural_source")
                    indexed[project] = item
            if set(indexed) != set(PROJECT_PAGES):
                raise PrivateSourceBlocked("missing_original_architectural_project")
            roster_bytes = json.dumps(sorted(roster), separators=(",", ":")).encode("utf-8")
            if hashlib.sha256(roster_bytes).hexdigest() != _OWNER_ORIGINAL_ROSTER_SHA256:
                raise PrivateSourceBlocked("original_source_roster_mismatch")

            for item in entries:
                member = archive.getinfo(item["relative_path"])
                if member.file_size != item["bytes"]:
                    raise PrivateSourceBlocked("original_file_hash_or_size_mismatch")
                digest = hashlib.sha256()
                with archive.open(member) as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                if digest.hexdigest() != item["sha256"]:
                    raise PrivateSourceBlocked("original_file_hash_or_size_mismatch")
            return manifest, indexed
    except (OSError, zipfile.BadZipFile, KeyError, ValueError) as exc:
        if isinstance(exc, PrivateSourceBlocked):
            raise
        raise PrivateSourceBlocked("unreadable_or_unverified_source_archive") from exc


def resolve_private_sources(bundle: Path | None = None) -> tuple[Path, dict, dict[str, dict]]:
    valid = []
    for path in _candidates(bundle):
        try:
            manifest, selected = _validate_archive(path)
            identity = tuple(sorted((e["project"], e["role"], e["sha256"]) for e in manifest["available_files"]))
            valid.append((path, manifest, selected, identity))
        except PrivateSourceBlocked:
            if bundle is not None or os.environ.get("PLANREADER_PRIVATE_SOURCE_BUNDLE"):
                raise
    if not valid:
        raise PrivateSourceBlocked(
            "no_verified_18_file_bundle_in_execution_environment; "
            "look_up_the_existing_ChatGPT_Library_bundle_instead_of_requesting_reupload"
        )
    if len({v[3] for v in valid}) != 1:
        raise PrivateSourceBlocked("conflicting_verified_source_revisions_specify_bundle")
    return valid[0][0], valid[0][1], valid[0][2]


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Single correct original PlanReader native trace + existing private sources")
    parser.add_argument("--bundle", type=Path, help="Private archive (auto-detected if mounted)")
    parser.add_argument("--project", action="append", choices=list(PROJECT_PAGES),
                        help="Limit to project; default is all five")
    parser.add_argument("--expected-head-sha", help="Optional expected exact HEAD SHA")
    parser.add_argument("--out-dir", type=Path, help="Private receipt output directory")
    parser.add_argument("--check-only", action="store_true", help="Verify cached source bytes without code checkout")
    args = parser.parse_args(argv)
    try:
        archive_path, manifest, source_rows = resolve_private_sources(args.bundle)
        print(f"SOURCE_PREFLIGHT_PASS: {len(manifest['available_files'])}/18 original files verified; no reupload required")
        if args.check_only:
            print("SOURCE_ONLY: no tracing or official benchmark was run")
            return 0
        # Refuse silently substituted diagnostics or an incomplete checkout.
        from tools.run_canonical_source_native_preview import _git_head, run_preview
        head = _git_head(ROOT)
        if args.expected_head_sha and head != args.expected_head_sha:
            raise PrivateSourceBlocked("wrong_exact_checkout_HEAD")
        projects = list(dict.fromkeys(args.project or PROJECT_PAGES.keys()))
        output = args.out_dir or Path(tempfile.mkdtemp(prefix="planreader-private-receipts-"))
        output.mkdir(parents=True, exist_ok=True)
        results = []
        with zipfile.ZipFile(archive_path) as z:
            with tempfile.TemporaryDirectory(prefix="planreader-original-PDF-") as scratch:
                for project in projects:
                    item = source_rows[project]
                    pdf = Path(scratch) / f"source_{project}.pdf"
                    with z.open(item["relative_path"]) as src, pdf.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
                    for page_index in PROJECT_PAGES[project]:
                        try:
                            receipt = run_preview(
                                pdf, page_index=page_index,
                                expected_source_sha256=item["sha256"],
                                expected_head_sha=head,
                                out_dir=output / f"{project}_p{page_index+1}",
                            )
                            result = json.loads(receipt.read_text())
                            results.append({"project": project, "page": page_index+1,
                                            "status": result["external_wall_trace_status"],
                                            "reason": result["external_wall_trace_reason"],
                                            "route_verified": True})
                        except Exception as exc:
                            results.append({"project": project, "page": page_index+1,
                                            "status": "BLOCKED", "reason": type(exc).__name__,
                                            "route_verified": False})
        report = {"code_HEAD": head, "preview_only": True, "official_benchmark_scored": False,
                  "source_preflight": "18/18 PASS", "results": results}
        (output / "run_summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"CANONICAL_PREVIEW_REPORT: {output / 'run_summary.json'}")
        return 1 if any(not row["route_verified"] for row in results) else 0
    except (PrivateSourceBlocked, OSError, ValueError, RuntimeError, ImportError) as exc:
        print(f"SOURCE_REUSE_BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(run())
