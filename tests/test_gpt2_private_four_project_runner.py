"""Only synthetic documents: no private originals or benchmark truth in tests."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import fitz
import pytest

from tools import gpt2_private_four_project_runner as gate


def roster(tmp_path):
    roots = tmp_path / "sources"
    manifests = tmp_path / "manifests"
    roots.mkdir()
    examples = []
    for project, count in zip(gate.PROJECTS, (1, 2, 1, 6)):
        rows = []
        (manifests / project).mkdir(parents=True)
        for i in range(count):
            name = f"synthetic_{len(examples)}.pdf"
            with fitz.open() as doc:
                page = doc.new_page()
                page.insert_text((40, 40), f"generic source {i}")
                content = doc.tobytes()
            (roots / name).write_bytes(content)
            row = {
                "name": name,
                "role": "architectural_drawings" if i == 0 else "source_role_" + str(i),
                "sha256": sha256(content).hexdigest(),
                "size_bytes": len(content),
                "page_count": 1,
            }
            rows.append(row)
            examples.append(name)
        (manifests / project / "source_manifest.json").write_text(
            json.dumps({
                "project_id": project,
                "source_documents": rows,
                "reference_takeoff_documents": [{"name": "must-not-open.json"}],
                "verified_takeoff_items": [{"expected_quantity": 2345}],
            })
        )
    return roots, manifests, examples


def test_all_ten_synthetic_sources_authenticate_without_granting_score(tmp_path):
    roots, manifests, names = roster(tmp_path)
    result = gate.verify_private_original_roster(roots, manifest_root=manifests)
    assert result["verified"] is True
    assert result["source_documents_verified"] == 10
    assert result["projects_verified"] == 4
    assert len(result["architectural_inputs"]) == 4
    assert result["benchmark_score_granted"] is False
    assert result["commercial_quantity_publication_granted"] is False
    # Reproducible despite different directory listing order.
    assert result["source_manifest_fingerprint"] == gate.verify_private_original_roster(
        roots, manifest_root=manifests
    )["source_manifest_fingerprint"]


def test_one_missing_pdf_fails_whole_roster(tmp_path):
    roots, manifests, names = roster(tmp_path)
    (roots / names[4]).unlink()
    with pytest.raises(gate.PrivateSourceGateError, match="private_source_package_not_verified"):
        gate.verify_private_original_roster(roots, manifest_root=manifests)


def test_same_size_modification_fails_sha(tmp_path):
    roots, manifests, names = roster(tmp_path)
    path = roots / names[7]
    content = bytearray(path.read_bytes())
    content[-15] ^= 1
    path.write_bytes(content)
    with pytest.raises(gate.PrivateSourceGateError, match="private_source_package_not_verified"):
        gate.verify_private_original_roster(roots, manifest_root=manifests)


def test_symlink_source_refused(tmp_path):
    roots, manifests, names = roster(tmp_path)
    original = roots / names[2]
    outside = tmp_path / "elsewhere.pdf"
    original.replace(outside)
    try:
        original.symlink_to(outside)
    except OSError:
        pytest.skip("symlink unavailable")
    with pytest.raises(gate.PrivateSourceGateError, match="private_source_package_not_verified"):
        gate.verify_private_original_roster(roots, manifest_root=manifests)


def test_symlink_root_refused(tmp_path):
    roots, manifests, names = roster(tmp_path)
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(roots, target_is_directory=True)
    except OSError:
        pytest.skip("symlink unavailable")
    with pytest.raises(gate.PrivateSourceGateError, match="private_source_root_not_trusted"):
        gate.verify_private_original_roster(alias, manifest_root=manifests)


def test_missing_environment_refused_without_guessing_path(tmp_path, monkeypatch):
    monkeypatch.delenv("PLANREADER_PRIVATE_SOURCE_ROOT", raising=False)
    with pytest.raises(gate.PrivateSourceGateError, match="private_source_root_not_configured"):
        gate.verify_private_original_roster(None, manifest_root=tmp_path)


def test_incorrect_manifest_count_fails_before_source_promotion(tmp_path):
    roots, manifests, names = roster(tmp_path)
    p = manifests / gate.PROJECTS[0] / "source_manifest.json"
    row = json.loads(p.read_text())
    row["source_documents"] = row["source_documents"] * 2
    p.write_text(json.dumps(row))
    with pytest.raises(gate.PrivateSourceGateError, match="private_source_manifest_roster_invalid"):
        gate.verify_private_original_roster(roots, manifest_root=manifests)


def test_duplicate_architectural_role_is_not_issued(tmp_path):
    roots, manifests, names = roster(tmp_path)
    p = manifests / gate.PROJECTS[1] / "source_manifest.json"
    row = json.loads(p.read_text())
    row["source_documents"][1]["role"] = "architectural_drawings"
    p.write_text(json.dumps(row))
    with pytest.raises(gate.PrivateSourceGateError, match="private_source_architectural_role_missing"):
        gate.verify_private_original_roster(roots, manifest_root=manifests)


def test_missing_exact_head_cannot_run_real_measurement(tmp_path, monkeypatch):
    roots, manifests, names = roster(tmp_path)
    real = gate.verify_private_original_roster
    monkeypatch.setattr(gate, "verify_private_original_roster", lambda root=None: real(root, manifest_root=manifests))
    out = tmp_path / "production"
    with pytest.raises(gate.PrivateSourceGateError, match="expected_checkout_sha_invalid"):
        gate.run_verified_private_handoff(
            project_id=gate.PROJECTS[0], expected_head_sha="not-a-commit",
            source_root=roots, output_dir=out,
        )
    assert not out.exists()


def test_verified_run_calls_original_handoff_with_exact_architectural_source(tmp_path, monkeypatch):
    roots, manifests, names = roster(tmp_path)
    real = gate.verify_private_original_roster
    monkeypatch.setattr(gate, "verify_private_original_roster", lambda root=None: real(root, manifest_root=manifests))
    monkeypatch.setattr(gate, "_verify_exact_checkout", lambda expected_head_sha: None)
    from tools import run_source_closed_project_handoff as original
    calls = []
    def fake_handoff(**kwargs):
        calls.append(kwargs)
        return {"status": "ABSTAINED"}
    monkeypatch.setattr(original, "generate_project_handoff", fake_handoff)
    result = gate.run_verified_private_handoff(
        project_id=gate.PROJECTS[0], expected_head_sha="a" * 40,
        source_root=roots, output_dir=tmp_path / "output", family_group="core",
    )
    assert len(calls) == 1
    assert calls[0]["pdf_path"] == roots / names[0]
    assert calls[0]["family_group"] == "core"
    assert result["production_run_status"] == "ABSTAINED"
    assert not result["benchmark_score_granted"]


def test_race_mutated_source_invalidates_post_run_receipt(tmp_path, monkeypatch):
    roots, manifests, names = roster(tmp_path)
    real = gate.verify_private_original_roster
    monkeypatch.setattr(gate, "verify_private_original_roster", lambda root=None: real(root, manifest_root=manifests))
    monkeypatch.setattr(gate, "_verify_exact_checkout", lambda expected_head_sha: None)
    from tools import run_source_closed_project_handoff as original
    def mutate(**kwargs):
        (roots / names[2]).write_bytes(b"different original")
        return {"status": "COMPLETED"}
    monkeypatch.setattr(original, "generate_project_handoff", mutate)
    with pytest.raises(gate.PrivateSourceGateError, match="private_source_package_not_verified"):
        gate.run_verified_private_handoff(
            project_id=gate.PROJECTS[0], expected_head_sha="a" * 40,
            source_root=roots, output_dir=tmp_path / "output",
        )


def test_private_root_can_never_be_production_output(tmp_path, monkeypatch):
    roots, manifests, names = roster(tmp_path)
    real = gate.verify_private_original_roster
    monkeypatch.setattr(gate, "verify_private_original_roster", lambda root=None: real(root, manifest_root=manifests))
    monkeypatch.setattr(gate, "_verify_exact_checkout", lambda expected_head_sha: None)
    with pytest.raises(gate.PrivateSourceGateError, match="output_inside_private_original_source_root"):
        gate.run_verified_private_handoff(
            project_id=gate.PROJECTS[0], expected_head_sha="a" * 40,
            source_root=roots, output_dir=roots / "results",
        )


def test_preflight_stdout_redacts_source_names_and_never_scores(tmp_path, monkeypatch, capsys):
    roots, manifests, names = roster(tmp_path)
    real = gate.verify_private_original_roster
    monkeypatch.setattr(gate, "verify_private_original_roster", lambda root=None: real(root, manifest_root=manifests))
    rc = gate.main(["--preflight-only", "--source-root", str(roots)])
    receipt = capsys.readouterr().out
    assert rc == 0
    assert json.loads(receipt)["source_documents_verified"] == 10
    assert not any(name in receipt for name in names)
    assert '"benchmark_score_granted": false' in receipt


def test_preflight_only_rejects_production_args(tmp_path, monkeypatch, capsys):
    roots, manifests, names = roster(tmp_path)
    assert gate.main(["--preflight-only", "--project", gate.PROJECTS[0], "--source-root", str(roots)]) == 2
    assert "preflight_only_cannot_run_production" in capsys.readouterr().out


def test_wrong_project_fails_without_touching_files(tmp_path):
    out = tmp_path / "output"
    with pytest.raises(gate.PrivateSourceGateError, match="project_not_in_frozen_source_roster"):
        gate.run_verified_private_handoff(
            project_id="acacia-not-in-frozen120", expected_head_sha="a" * 40,
            output_dir=out,
        )
    assert not out.exists()


def test_aliased_output_parent_cannot_write_into_private_root(tmp_path, monkeypatch):
    roots, manifests, names = roster(tmp_path)
    alias = tmp_path / "output_alias"
    try:
        alias.symlink_to(roots, target_is_directory=True)
    except OSError:
        pytest.skip("symlink unavailable")
    real = gate.verify_private_original_roster
    monkeypatch.setattr(gate, "verify_private_original_roster", lambda root=None: real(root, manifest_root=manifests))
    monkeypatch.setattr(gate, "_verify_exact_checkout", lambda expected_head_sha: None)
    with pytest.raises(gate.PrivateSourceGateError, match="output_inside_private_original_source_root"):
        gate.run_verified_private_handoff(
            project_id=gate.PROJECTS[0], expected_head_sha="a" * 40,
            source_root=roots, output_dir=alias / "nested_results",
        )
    assert not (roots / "nested_results").exists()


def test_checkout_authenticated_before_any_private_source_read(tmp_path, monkeypatch):
    roots, manifests, names = roster(tmp_path)
    calls = []
    def private_roster_must_not_be_opened(root=None):
        calls.append("PRIVATE_READ_ATTEMPTED")
        raise AssertionError("untrusted code attempted a private source read")
    monkeypatch.setattr(gate, "verify_private_original_roster", private_roster_must_not_be_opened)
    with pytest.raises(gate.PrivateSourceGateError, match="expected_checkout_sha_invalid"):
        gate.run_verified_private_handoff(
            project_id=gate.PROJECTS[0], expected_head_sha="not-a-commit",
            source_root=roots, output_dir=tmp_path / "external_results",
        )
    assert calls == []
