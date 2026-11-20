"""Source-neutral tests: never put private PDFs or their hashes in public CI."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from tools import run_verified_planreader_sources as src


def _archive(tmp_path: Path, *, tamper: bool = False, count: int = 18,
             unsafe: bool = False) -> Path:
    archive_path = tmp_path / "owner-private-sources.zip"
    projects = list(src.PROJECT_PAGES)
    entries = []
    with zipfile.ZipFile(archive_path, "w") as archive:
        for index in range(count):
            project = projects[index] if index < len(projects) else "Q5446"
            role = "architectural" if index < len(projects) else f"reference_{index}"
            name = f"documents/sources/fake_{index}.pdf"
            if unsafe and index == 0:
                name = "documents/sources/../../escape.pdf"
            raw = b"%PDF-1.7\n" + bytes([index]) * (index + 3)
            entry = {
                "project": project, "role": role,
                "relative_path": name, "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw), "pages": 1,
            }
            entries.append(entry)
            if tamper and index == 4:
                raw = b"TAMPERED" + raw
            archive.writestr(name, raw)
        manifest = {
            "expected_total": 18,
            "verified_file_count": count,
            "missing_file_count": 18-count,
            "available_files": entries,
        }
        archive.writestr(src.ARCHIVE_MANIFEST, json.dumps(manifest))
    return archive_path


def test_full_cached_source_inventory_is_reusable(tmp_path):
    archive = _archive(tmp_path)
    manifest, architecturals = src._validate_archive(archive)
    assert manifest["verified_file_count"] == 18
    assert set(architecturals) == set(src.PROJECT_PAGES)
    assert src.run(["--bundle", str(archive), "--check-only"]) == 0


def test_source_tampering_fails_before_trace(tmp_path):
    with pytest.raises(src.PrivateSourceBlocked, match="hash_or_size_mismatch"):
        src._validate_archive(_archive(tmp_path, tamper=True))


def test_missing_original_pdfs_cannot_pass(tmp_path):
    with pytest.raises(src.PrivateSourceBlocked, match="incomplete_original_source_inventory"):
        src._validate_archive(_archive(tmp_path, count=17))


def test_zip_path_traversal_rejected(tmp_path):
    with pytest.raises(src.PrivateSourceBlocked, match="unsafe_private_source_archive_path"):
        src._validate_archive(_archive(tmp_path, unsafe=True))


def test_bundled_discovery_does_not_need_user_reupload(tmp_path, monkeypatch):
    archive = _archive(tmp_path)
    monkeypatch.setattr(src, "_candidates", lambda explicit=None: [archive])
    selected, manifest, sources = src.resolve_private_sources()
    assert selected == archive
    assert len(manifest["available_files"]) == 18
    assert len(sources) == 5


def test_no_source_never_invokes_wrong_diagnostic(tmp_path, monkeypatch):
    monkeypatch.setattr(src, "_candidates", lambda explicit=None: [])
    with pytest.raises(src.PrivateSourceBlocked, match="ChatGPT_Library_bundle"):
        src.resolve_private_sources()
    assert src.run(["--bundle", str(tmp_path / "missing.zip"), "--check-only"]) == 2


def test_entrypoint_calls_existing_canonical_runner_not_diagnostic():
    content = (Path(__file__).resolve().parents[1] / "tools" /
               "run_verified_planreader_sources.py").read_text(encoding="utf-8")
    assert "from tools.run_canonical_source_native_preview import _git_head, run_preview" in content
    assert "run_preview(" in content
    assert "trace_external_footprint_first(" not in content
    assert "run_inside_face_footprint_runtime_stage(" not in content
    assert '"official_benchmark_scored": False' in content