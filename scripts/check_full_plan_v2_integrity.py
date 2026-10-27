"""Fail closed when active Full Plan V2 truth is internally inconsistent.

This is the active benchmark-integrity gate. It validates only the V2 full-plan,
independently source-closed truth framework. The retired legacy benchmark
engines/public-tender gold are intentionally not imported or executed.
"""
from __future__ import annotations

import hashlib
import json
import os
from stat import S_ISDIR, S_ISREG
from pathlib import Path
import re
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.frozen_holdout.full_plan_v2.manifest_io import (
    SCHEMA_VERSION, load_project_manifest, load_suite_manifests,
)

DEFAULT_ROOT = Path("benchmarks/frozen_holdout/full_plan_v2")
DEFAULT_SOURCE_DIR = REPO_ROOT / "documents" / "sources"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_WIN_DEVICE_NAMES = frozenset({"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"})
_WIN_PORT_DEVICE_RE = re.compile(r"^(?:COM|LPT)[1-9¹²³]$")


def _safe_path_component(value: Any) -> bool:
    """Require a portable single filename component before joining trusted roots.

    Frozen suite project IDs and pinned document names are untrusted JSON
    strings until validated. Reject POSIX/Windows traversal, drive/ADS names,
    illegal Win32 characters, device basenames and trailing-dot/space aliases.
    """
    if (
        not isinstance(value, str)
        or not value
        or value in (".", "..")
        or value != value.strip()
        or value.endswith(".")
        or any(char in value for char in '/\\:<>"|?*')
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        return False
    # Win32 reserves device basenames even with extensions. Treat spaces
    # before an extension as an alias, e.g. "CON .pdf" must also fail.
    stem = value.split(".", 1)[0].rstrip(" ").upper()
    return stem not in _WIN_DEVICE_NAMES and _WIN_PORT_DEVICE_RE.fullmatch(stem) is None


def _unique_json_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject ambiguous JSON objects instead of silently taking the last key."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object member")
        result[key] = value
    return result


def _regular_entry(path: Path, *, directory: bool = False) -> bool:
    """Reject symlinked or nonregular frozen metadata entries without following them."""
    try:
        mode = path.lstat().st_mode
    except OSError:
        return False
    return S_ISDIR(mode) if directory else S_ISREG(mode)


def _json(path: Path) -> Any:
    """Read one stable, regular frozen JSON inode without following final symlinks.

    The canonical manifest parser is unchanged; this strict integrity preflight
    never grants source or customer authority to an aliased JSON file.
    """
    try:
        before = path.lstat()
    except OSError as exc:
        raise ValueError("frozen JSON cannot be inspected") from exc
    if not S_ISREG(before.st_mode):
        raise ValueError("frozen JSON is not a regular file")
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        with os.fdopen(os.open(path, flags), "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not S_ISREG(opened.st_mode):
                raise ValueError("frozen JSON changed during verification")
            raw = stream.read()
            completed = os.fstat(stream.fileno())
        after = path.lstat()
    except OSError as exc:
        raise ValueError("frozen JSON changed or became inaccessible") from exc
    if len(raw) != before.st_size or any(
        getattr(snapshot, field) != getattr(before, field)
        for snapshot in (opened, completed, after)
        for field in _SOURCE_IDENTITY_FIELDS
    ):
        raise ValueError("frozen JSON changed during verification")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_json_members)


def _collect_object_refs(value: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, dict):
        ref = value.get("object_ref")
        if isinstance(ref, str) and ref.strip():
            refs.add(ref.strip())
        for child in value.values():
            refs.update(_collect_object_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.update(_collect_object_refs(child))
    return refs


_SOURCE_IDENTITY_FIELDS = (
    "st_dev", "st_ino", "st_mode", "st_nlink", "st_size",
    "st_mtime_ns", "st_ctime_ns",
)


def _present_source_digest(path: Path) -> tuple[str, int] | None:
    """Hash a present regular original through one stable no-follow descriptor.

    Only a genuinely absent original may be omitted from a public checkout.
    An unreadable path, symlink, nonregular file or changed inode must fail the
    integrity gate rather than being reported as an absent private source.
    """
    try:
        before = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ValueError("cannot be inspected") from exc
    if not S_ISREG(before.st_mode):
        raise ValueError("is not a regular file")
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        with os.fdopen(os.open(path, flags), "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not S_ISREG(opened.st_mode):
                raise ValueError("changed during integrity verification")
            digest = hashlib.sha256()
            size = 0
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
            completed = os.fstat(stream.fileno())
        after = path.lstat()
    except OSError as exc:
        raise ValueError("changed or became inaccessible during integrity verification") from exc
    if size != before.st_size or any(
        getattr(snapshot, field) != getattr(before, field)
        for snapshot in (opened, completed, after)
        for field in _SOURCE_IDENTITY_FIELDS
    ):
        raise ValueError("changed during integrity verification")
    return digest.hexdigest(), size


def source_document_failures(manifests: Any, source_dir: Path = DEFAULT_SOURCE_DIR) -> list[str]:
    """Verify pinned originals that are present; skip only genuinely absent ones.

    Private originals intentionally absent from the public checkout are not a
    successful source-positive replay. Present but inaccessible/nonregular
    originals cannot be silently treated as absent on Python 3.13 or 3.14.
    """
    failures: list[str] = []
    for manifest in manifests:
        for source in manifest.source_documents:
            if not _safe_path_component(source.name):
                failures.append(f"{manifest.project_id}: unsafe source document name")
                continue
            try:
                checked = _present_source_digest(source_dir / source.name)
            except ValueError as exc:
                failures.append(
                    f"{manifest.project_id}: source document {source.name} {exc}"
                )
                continue
            if checked is None:
                continue
            actual_sha, actual_size = checked
            if actual_sha != source.sha256:
                failures.append(
                    f"{manifest.project_id}: source document {source.name} SHA mismatch "
                    f"(manifest={source.sha256}, actual={actual_sha})"
                )
            if actual_size != source.size_bytes:
                failures.append(
                    f"{manifest.project_id}: source document {source.name} size mismatch "
                    f"(manifest={source.size_bytes}, actual={actual_size})"
                )
    return failures


def reference_document_failures(manifest: Any, project: Path) -> list[str]:
    """Authenticate every required frozen reference through one stable inode.

    Unlike private originals, a missing reference is ALWAYS a failure. A
    symlink, nonregular file, inaccessible descriptor or raced replacement
    must not be accepted on the strength of a separate path.stat size check.
    """
    failures: list[str] = []
    for reference in manifest.reference_takeoff_documents:
        if not _safe_path_component(reference.name):
            failures.append(f"{manifest.project_id}: unsafe reference document name")
            continue
        path = project / reference.name
        try:
            checked = _present_source_digest(path)
        except ValueError as exc:
            failures.append(f"{manifest.project_id}: {reference.name} {exc}")
            continue
        if checked is None:
            failures.append(
                f"{manifest.project_id}: missing pinned reference document {reference.name}"
            )
            continue
        actual_sha, actual_size = checked
        if actual_sha != reference.sha256:
            failures.append(
                f"{manifest.project_id}: {reference.name} SHA mismatch "
                f"(manifest={reference.sha256}, actual={actual_sha})"
            )
        if actual_size != reference.size_bytes:
            failures.append(
                f"{manifest.project_id}: {reference.name} size mismatch "
                f"(manifest={reference.size_bytes}, actual={actual_size})"
            )
    return failures


def validate_suite(root: Path = DEFAULT_ROOT, source_dir: Path = DEFAULT_SOURCE_DIR) -> list[str]:
    failures: list[str] = []

    try:
        suite = _json(root / "manifest.json")
        if str(suite.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("suite manifest has unsupported schema_version")
        raw_project_ids = suite.get("projects", ())
        if not isinstance(raw_project_ids, list) or any(
            not _safe_path_component(project_id) for project_id in raw_project_ids
        ):
            raise ValueError("unsafe project id in suite manifest")
        required = int(suite.get("required_project_count", 0))
        if required <= 0 or len(raw_project_ids) != required:
            raise ValueError("suite project list must exactly equal required_project_count")
        if len(set(raw_project_ids)) != len(raw_project_ids):
            raise ValueError("suite project ids must be unique")
        # Do not ask load_suite_manifests to re-read an untrusted suite path:
        # it would join a second, potentially changed project-id list.
        # Use the existing project parser on only our validated components.
        manifests = []
        if not _regular_entry(root / "projects", directory=True):
            raise ValueError("frozen projects directory is missing or aliased")
        for project_id in raw_project_ids:
            manifest_path = root / "projects" / project_id / "source_manifest.json"
            if not _regular_entry(manifest_path.parent, directory=True):
                raise ValueError(f"project directory is missing or aliased: {project_id}")
            # The canonical loader accepts duplicate JSON keys (last-wins).
            # Reject ambiguous members, including nested source/verified-item
            # records, before allowing that loader to mint manifest authority.
            _json(manifest_path)
            manifest = load_project_manifest(manifest_path)
            if manifest.project_id != project_id:
                raise ValueError(f"project manifest identity mismatch: {project_id}")
            manifests.append(manifest)
    except Exception as exc:
        return [f"suite/manifest validation failed: {exc}"]

    project_ids = tuple(raw_project_ids)
    required = int(suite.get("required_project_count", 0))
    if required != len(project_ids) or required <= 0:
        failures.append("required_project_count must exactly match configured V2 projects")
    if len(project_ids) != len(set(project_ids)):
        failures.append("configured V2 project ids must be unique")

    for manifest in manifests:
        project = root / "projects" / manifest.project_id
        for required_name in (
            "source_manifest.json",
            "reference_takeoff.json",
            "object_universe.json",
            "verification_report.json",
            "unresolved_items.json",
        ):
            if not _regular_entry(project / required_name):
                failures.append(f"{manifest.project_id}: missing {required_name} or unsafe file type")

        for source in manifest.source_documents:
            if not _safe_path_component(source.name):
                # source_document_failures reports this without opening the path.
                continue
            if not _SHA256_RE.fullmatch(source.sha256):
                failures.append(f"{manifest.project_id}: invalid source SHA-256 for {source.name}")
            if source.size_bytes <= 0:
                failures.append(f"{manifest.project_id}: invalid source size for {source.name}")

        failures.extend(reference_document_failures(manifest, project))

        object_path = project / "object_universe.json"
        if object_path.is_file():
            try:
                known_refs = _collect_object_refs(_json(object_path))
            except Exception as exc:
                failures.append(f"{manifest.project_id}: object_universe invalid JSON: {exc}")
                known_refs = set()
            expected_refs = {
                ref
                for item in manifest.verified_items
                for ref in item.expected_object_refs
            }
            missing = sorted(expected_refs - known_refs)
            if missing:
                failures.append(
                    f"{manifest.project_id}: verified truth references missing canonical/object "
                    f"records: {', '.join(missing)}"
                )

    failures.extend(source_document_failures(manifests, source_dir))
    return failures


def main(argv: list[str] | None = None) -> int:
    args = list(argv or sys.argv[1:])
    root = Path(args[0]) if args else DEFAULT_ROOT
    failures = validate_suite(root)
    if failures:
        print("Full Plan V2 integrity check failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    print("Full Plan V2 integrity check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
