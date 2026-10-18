"""All original document roles must actually execute and independently seal.

These tests use synthetic PDFs and in-memory signed-run stubs. No customer
drawings, private source bytes, frozen truth or score enter public CI.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

from tools import gpt3_owner_all_source_role_handoff as module


def _fake_sources(tmp_path, monkeypatch):
    project = module.PROJECTS[0]
    root = tmp_path / "owners"
    root.mkdir()
    manifests = tmp_path / "frozen" / "projects" / project
    manifests.mkdir(parents=True)
    docs = []
    for i in range(2):
        doc = fitz.open()
        doc.new_page()
        file = root / ("primary.pdf" if i == 0 else "structure.pdf")
        doc.save(file)
        doc.close()
        docs.append({
            "name": file.name, "role": ("architectural_drawings" if i == 0 else "structural_drawings"),
            "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
            "size_bytes": file.stat().st_size, "page_count": 1,
        })
    (manifests / "source_manifest.json").write_text(json.dumps({
        "project_id": project, "status": "INCOMPLETE",
        "source_package_complete": True, "source_documents": docs,
    }), encoding="utf-8")
    monkeypatch.setattr(module, "FROZEN_ROOT", tmp_path / "frozen")
    return project, root, docs


def test_both_original_roles_are_byte_page_and_digest_authenticated(tmp_path, monkeypatch):
    project, root, docs = _fake_sources(tmp_path, monkeypatch)
    roster = module.original_roster(project, root)
    assert len(roster) == 2
    assert [r["role"] for r in roster] == ["architectural_drawings", "structural_drawings"]
    assert [r["sha256"] for r in roster] == [x["sha256"] for x in docs]
    assert not any("expected_quantity" in r for r in roster)
    (root / "structure.pdf").write_bytes(b"tampered original source")
    with pytest.raises(ValueError, match="authentication"):
        module.original_roster(project, root)


def test_bad_source_bytes_prevent_any_production_execution_or_output(tmp_path, monkeypatch):
    project, root, _docs = _fake_sources(tmp_path, monkeypatch)
    (root / "structure.pdf").write_bytes(b"bad")
    called = []
    monkeypatch.setattr(module, "run_logged", lambda *a, **kw: called.append(True))
    out = tmp_path / "private-output"
    with pytest.raises(ValueError, match="authentication"):
        module.produce_all_source_roles(
            project_id=project, source_dir=root, output_dir=out,
        )
    assert called == []
    assert not out.exists()


def test_one_primary_seal_never_claims_complete_two_source_role_package(tmp_path, monkeypatch):
    project, root, docs = _fake_sources(tmp_path, monkeypatch)
    called = []

    def fake_runner(command, repo, logfile, **kwargs):
        called.append(command)
        dest = Path(command[command.index("--output-dir") + 1])
        if len(called) == 1:
            (dest / (project + ".json")).write_text("{}", encoding="utf-8")
            (dest / "production_summary.json").write_text(json.dumps({
                "status": "sealed", "combined_run_file": str(dest / (project + ".json")),
            }), encoding="utf-8")
        else:
            (dest / "production_summary.json").write_text(json.dumps({
                "status": "no_sealable_quantities",
            }), encoding="utf-8")
        return 0, "COMPLETED", {}

    monkeypatch.setattr(module, "run_logged", fake_runner)
    monkeypatch.setattr(module, "load_verified_sealed_run", lambda p: SimpleNamespace(
        project_id=project, source_sha256s=[docs[0]["sha256"]],
    ))
    out = tmp_path / "output"
    result = module.produce_all_source_roles(
        project_id=project, source_dir=root, output_dir=out,
    )
    assert len(called) == 2
    assert result["roles"][0]["sealed"] is True
    assert result["roles"][1]["sealed"] is False
    assert result["roles"][1]["first_failure"] == "role_producer_no_sealable_result"
    assert result["source_role_coverage_verified"] is False
    assert result["benchmark_score_granted"] is False
    assert result["official_four_project_accuracy"] is None
    assert not (out / "ALL_SOURCE_ROLES.sealed.json").exists()
    summary = json.loads((out / "SOURCE_ROLE_STATUS.json").read_text())
    assert summary == result
    assert str(root) not in json.dumps(summary)


def test_two_independently_authenticated_role_seals_can_compose_without_score(tmp_path, monkeypatch):
    project, root, docs = _fake_sources(tmp_path, monkeypatch)
    def fake_runner(command, repo, logfile, **kwargs):
        dest = Path(command[command.index("--output-dir") + 1])
        file = dest / (project + ".json")
        file.write_text("{}", encoding="utf-8")
        (dest / "production_summary.json").write_text(json.dumps({
            "status": "sealed", "combined_run_file": str(file),
        }), encoding="utf-8")
        return 0, "COMPLETED", {}

    def fake_load(path):
        index = int(path.parent.name.rsplit("_", 1)[-1]) - 1
        return SimpleNamespace(project_id=project, source_sha256s=[docs[index]["sha256"]])

    captured = []
    def fake_combine(paths, **kwargs):
        captured.extend(paths)
        assert kwargs["project_id"] == project
        return SimpleNamespace(
            source_sha256s=tuple(x["sha256"] for x in docs),
            to_json=lambda: '{"schema_version":"source-neutral-synthetic"}\n',
        )

    monkeypatch.setattr(module, "run_logged", fake_runner)
    monkeypatch.setattr(module, "load_verified_sealed_run", fake_load)
    monkeypatch.setattr(module, "combine_sealed_run_files", fake_combine)
    out = tmp_path / "output"
    result = module.produce_all_source_roles(
        project_id=project, source_dir=root, output_dir=out,
    )
    assert len(captured) == 2
    assert result["source_role_coverage_verified"] is True
    assert result["status"] == "ALL_ROLES_SEALED_CUSTOMER_AND_V2_PENDING"
    assert result["customer_bijection_verified"] is False
    assert result["benchmark_score_granted"] is False
    assert (out / "ALL_SOURCE_ROLES.sealed.json").is_file()
    assert not list(out.rglob("*.pdf"))


def test_cross_role_producer_envelope_conflicts_are_quarantined(tmp_path, monkeypatch):
    project, root, docs = _fake_sources(tmp_path, monkeypatch)
    def fake_runner(command, repo, logfile, **kwargs):
        dest = Path(command[command.index("--output-dir") + 1])
        file = dest / (project + ".json")
        file.write_text("{}", encoding="utf-8")
        (dest / "production_summary.json").write_text(json.dumps({
            "status": "sealed", "combined_run_file": str(file),
        }), encoding="utf-8")
        return 0, "COMPLETED", {}

    monkeypatch.setattr(module, "run_logged", fake_runner)
    monkeypatch.setattr(module, "load_verified_sealed_run", lambda p: SimpleNamespace(
        project_id=project, source_sha256s=[docs[0]["sha256"]],
    ))
    out = tmp_path / "output"
    result = module.produce_all_source_roles(
        project_id=project, source_dir=root, output_dir=out,
    )
    assert result["roles"][0]["sealed"] is True
    assert result["roles"][1]["sealed"] is False
    assert result["roles"][1]["first_failure"] == "original_role_seal_source_envelope_conflict"
    assert not (out / "ALL_SOURCE_ROLES.sealed.json").exists()


def test_secondary_receipt_invalidity_is_explicit_not_a_forged_success(tmp_path, monkeypatch):
    project, root, docs = _fake_sources(tmp_path, monkeypatch)
    def fake_runner(command, repo, logfile, **kwargs):
        dest = Path(command[command.index("--output-dir") + 1])
        file = dest / (project + ".json")
        file.write_text("{}", encoding="utf-8")
        (dest / "production_summary.json").write_text(json.dumps({
            "status": "sealed", "combined_run_file": str(file),
        }), encoding="utf-8")
        return 0, "COMPLETED", {}
    monkeypatch.setattr(module, "run_logged", fake_runner)
    monkeypatch.setattr(module, "load_verified_sealed_run", lambda _: (_ for _ in ()).throw(
        ValueError("corrupt synthetic cryptographic seal")
    ))
    out = tmp_path / "output"
    result = module.produce_all_source_roles(project_id=project, source_dir=root, output_dir=out)
    assert [r["first_failure"] for r in result["roles"]] == [
        "original_role_signed_receipt_invalid", "original_role_signed_receipt_invalid",
    ]
    assert not (out / "ALL_SOURCE_ROLES.sealed.json").exists()


def test_output_aliases_and_existing_evidence_are_rejected_before_producer(tmp_path, monkeypatch):
    project, root, _docs = _fake_sources(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="new private"):
        module.produce_all_source_roles(project_id=project, source_dir=root, output_dir=root / "bad")
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(ValueError, match="new private"):
        module.produce_all_source_roles(project_id=project, source_dir=root, output_dir=existing)
    assert not list(root.rglob("SOURCE_ROLE_STATUS.json"))


@pytest.mark.parametrize("family,timeout,private,free", [
    ("unknown", 10, 4, 1),
    ("all", 0, 4, 1),
    ("all", 10, 0, 1),
    ("all", 10, 4, -1),
])
def test_invalid_resource_policy_cannot_run_any_source_producers(tmp_path, family, timeout, private, free):
    with pytest.raises(ValueError):
        module.produce_all_source_roles(
            project_id=module.PROJECTS[0],
            source_dir=tmp_path,
            output_dir=tmp_path / "output",
            family_group=family, timeout_min=timeout,
            max_private_gb=private, min_free_commit_gb=free,
        )
