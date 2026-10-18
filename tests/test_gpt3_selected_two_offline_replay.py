"""No-owner-secret, no-private-source-upload tests for offline original replay."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZipInfo

import pytest

from tools import run_gpt3_selected_two_offline_replay as offline


def _zip(path: Path, files: dict[str, bytes]) -> str:
    with ZipFile(path, "w") as z:
        for name, value in files.items():
            z.writestr(name, value)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_offline_derivation_stages_only_derived_receipts_not_original_pdf(tmp_path):
    archive = tmp_path / "derived.zip"
    sha = _zip(archive, {"source/production/source_sealed_run.json": b"{}"})
    stage = tmp_path / "unpacked"
    offline._unpack_pinned_derived_archive(archive, stage, sha)
    assert (stage / "source/production/source_sealed_run.json").read_bytes() == b"{}"
    assert not list(stage.rglob("*.pdf"))
    with pytest.raises(ValueError, match="SHA mismatch"):
        offline._unpack_pinned_derived_archive(archive, tmp_path / "bad", "0" * 64)


@pytest.mark.parametrize("filename", [
    "../outside.txt", "/root-escape", "C:/drive-alias.txt",
    r"a\b.txt", "original-source.PDF",
])
def test_offline_replay_rejects_traversal_drive_alternate_separator_and_pdf(tmp_path, filename):
    archive = tmp_path / "unsafe.zip"
    sha = _zip(archive, {filename: b"%PDF private data"})
    with pytest.raises(ValueError, match="unsafe|PDF"):
        offline._unpack_pinned_derived_archive(archive, tmp_path / "stage", sha)
    assert not (tmp_path / "outside.txt").exists()


def test_offline_replay_rejects_duplicate_entries_and_zip_symlink(tmp_path):
    duplicate = tmp_path / "duplicate.zip"
    with ZipFile(duplicate, "w") as z:
        z.writestr("x.json", "{}")
        z.writestr("x.json", "{}")
    with pytest.raises(ValueError, match="duplicate"):
        offline._unpack_pinned_derived_archive(
            duplicate, tmp_path / "stage1", hashlib.sha256(duplicate.read_bytes()).hexdigest()
        )
    symlink = tmp_path / "symlink.zip"
    with ZipFile(symlink, "w") as z:
        member = ZipInfo("secret.json")
        member.create_system = 3
        member.external_attr = 0o120777 << 16
        z.writestr(member, "outside/private")
    with pytest.raises(ValueError, match="symlink"):
        offline._unpack_pinned_derived_archive(
            symlink, tmp_path / "stage2", hashlib.sha256(symlink.read_bytes()).hexdigest()
        )


def test_offline_replay_source_lookup_fails_closed_for_conflicting_flat_scoped_original(tmp_path):
    original_root = tmp_path / "sources"
    project = "au_qld_lot16_power"
    name = offline._CASES[0]["source"]
    (original_root / project).mkdir(parents=True)
    (original_root / name).write_bytes(b"first PDF")
    (original_root / project / name).write_bytes(b"conflicting PDF")
    with pytest.raises(ValueError, match="ambiguous"):
        offline._original(original_root, project, name)
    (original_root / project / name).write_bytes(b"first PDF")
    assert offline._original(original_root, project, name) == original_root / name


@pytest.mark.parametrize("bad", [
    {"publication_status": "PUBLISHED"},
    {"selected_denominator": 120},
    {"official_four_project_accuracy": 0.95},
    {"full_four_project_publication_allowed": True},
])
def test_offline_replay_must_not_publish_a_four_project_score(bad):
    report = {
        "publication_status": "SELECTED_PROJECT_DEVELOPMENT_ONLY",
        "selected_project_count": 2,
        "selected_denominator": 51,
        "official_four_project_suite_result": None,
        "official_four_project_accuracy": None,
        "full_four_project_publication_allowed": False,
    }
    report.update(bad)
    with pytest.raises(ValueError, match="cannot publish"):
        offline._require_dev_only(report)


def test_offline_owner_replay_report_requires_unchanged_source_evaluator(monkeypatch, tmp_path):
    sources = tmp_path / "private-originals"
    sources.mkdir()
    for case in offline._CASES:
        (sources / case["source"]).write_bytes(b"%PDF-1.7 owner-only test bytes")
    lz = tmp_path / "lot16.zip"
    mz = tmp_path / "maryborough.zip"
    monkeypatch.setattr(offline, "_LOT16_ZIP_SHA", _zip(lz, {"production/source_sealed_run.json": b"{}"}))
    monkeypatch.setattr(offline, "_MARY_ZIP_SHA", _zip(mz, {"source/production/source_sealed_run.json": b"{}"}))
    called = []

    def fake_score(entries):
        assert len(entries) == 2
        assert all(Path(entry["original_files"][0]).is_file() for entry in entries)
        assert all(Path(entry["sealed"]).is_file() for entry in entries)
        called.append("source-gated-score")
        return {
            "publication_status": "SELECTED_PROJECT_DEVELOPMENT_ONLY",
            "selected_project_count": 2, "selected_denominator": 51,
            "matched_within_tolerance": 8,
            "official_four_project_suite_result": None,
            "official_four_project_accuracy": None,
            "full_four_project_publication_allowed": False,
        }

    monkeypatch.setattr(offline, "build_selected_two_project_development_evidence", fake_score)
    output = tmp_path / "unpublished-development-only.json"
    result = offline.run(
        sources=sources, lot16_archive=lz, maryborough_archive=mz, output=output,
    )
    assert called == ["source-gated-score"]
    assert json.loads(output.read_text()) == result
    assert result["official_four_project_accuracy"] is None
    assert all(f.read_bytes() == b"%PDF-1.7 owner-only test bytes"
               for f in sources.glob("*.pdf"))
    with pytest.raises(ValueError, match="new path"):
        offline.run(sources=sources, lot16_archive=lz, maryborough_archive=mz, output=output)
    with pytest.raises(ValueError, match="new path"):
        offline.run(
            sources=sources, lot16_archive=lz, maryborough_archive=mz,
            output=sources / "unsafe.json",
        )
