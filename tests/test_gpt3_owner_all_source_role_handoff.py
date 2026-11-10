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
        page = doc.new_page()
        page.insert_text((72, 72), f"synthetic-original-document-role-{i}")
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


def test_resource_abort_preserves_only_safe_numeric_usage(tmp_path, monkeypatch):
    project, root, _ = _fake_sources(tmp_path, monkeypatch)
    usage = {"peak_working_set_kb": 1024, "peak_private_kb": 2048,
             "min_system_free_commit_kb": "private path must not propagate",
             "unknown_field": "untrusted child source text"}
    monkeypatch.setattr(module, "run_logged", lambda *a, **k: (None, "MEMORY_LIMIT", usage))
    result = module.produce_all_source_roles(project_id=project, source_dir=root,
        output_dir=tmp_path/"private-results")
    for row in result["roles"]:
        assert row["resource_usage"] == {"peak_working_set_kb": 1024,
            "peak_private_kb": 2048, "min_system_free_commit_kb": None}
        assert row["sealed"] is False
        assert row["process_status"] == "MEMORY_LIMIT"
    assert "private path" not in json.dumps(result)
    assert "untrusted child" not in json.dumps(result)
    assert result["benchmark_score_granted"] is False


def _no_quantity_runner(calls):
    def run(command, repo, logfile, **kwargs):
        calls.append(command)
        dest = Path(command[command.index("--output-dir") + 1])
        (dest / "production_summary.json").write_text(json.dumps({
            "status": "no_sealable_quantities",
        }), encoding="utf-8")
        return 0, "COMPLETED", {}
    return run


def test_native_input_audit_cannot_replace_missing_quantity_seals(tmp_path, monkeypatch):
    from tools.gpt3_native_source_execution_coverage import verify_native_source_execution_coverage
    project, root, docs = _fake_sources(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(module, "run_logged", _no_quantity_runner(calls))
    out = tmp_path / "audited-output"
    result = module.produce_all_source_roles(
        project_id=project, source_dir=root, output_dir=out,
        record_native_source_input_coverage=True,
    )
    assert len(calls) == len(docs) == 2
    assert result["native_source_input_coverage_verified"] is True
    assert result["source_role_coverage_verified"] is False
    assert result["customer_bijection_verified"] is False
    assert result["benchmark_score_granted"] is False
    assert result["official_four_project_accuracy"] is None
    assert result["status"] == "SOURCE_ROLES_INCOMPLETE"
    assert not (out / "ALL_SOURCE_ROLES.sealed.json").exists()
    for row, source in zip(result["roles"], docs):
        assert row["sealed"] is False
        assert row["first_failure"] == "role_producer_no_sealable_result"
        assert row["native_source_input_coverage_verified"] is True
        receipt = row["native_source_input_coverage"]
        assert verify_native_source_execution_coverage(
            receipt, pdf_path=root / source["name"], expected_sha256=source["sha256"],
            expected_page_count=source["page_count"],
        ) == receipt
        assert receipt["semantic_enumeration_complete"] is None
        assert receipt["decision_scope_complete"] is None
        assert receipt["commercial_projection_allowed"] is False
    encoded = json.dumps(result)
    assert str(root) not in encoded and "synthetic-original-document-role" not in encoded
    assert json.loads((out / "SOURCE_ROLE_STATUS.json").read_text()) == result
    assert all("--record-native-source-input-coverage" not in command for command in calls)


def test_legacy_role_commands_and_reports_do_not_activate_native_audit(tmp_path, monkeypatch):
    from tools import gpt3_native_source_execution_coverage as native
    project, root, _docs = _fake_sources(tmp_path, monkeypatch)
    def forbidden(**kwargs):
        pytest.fail("default native audit activated")
    monkeypatch.setattr(native, "build_native_source_execution_coverage", forbidden)
    monkeypatch.setattr(native, "verify_native_source_execution_coverage", forbidden)
    calls = []
    monkeypatch.setattr(module, "run_logged", _no_quantity_runner(calls))
    result = module.produce_all_source_roles(
        project_id=project, source_dir=root, output_dir=tmp_path / "legacy-output",
    )
    assert "native_source_input_coverage_verified" not in result
    assert all("native_source_input_coverage" not in row for row in result["roles"])
    assert len(calls) == 2 and all(command[2] == "tools.run_source_closed_project_handoff" for command in calls)


@pytest.mark.parametrize("flag", (0, 1, "true", None, [], {}))
def test_native_audit_flag_requires_an_explicit_boolean(tmp_path, monkeypatch, flag):
    monkeypatch.setattr(module, "original_roster", lambda *args: pytest.fail("source preflight started"))
    out = tmp_path / "invalid-flag-output"
    with pytest.raises(ValueError, match="explicit boolean"):
        module.produce_all_source_roles(
            project_id=module.PROJECTS[0], source_dir=tmp_path, output_dir=out,
            record_native_source_input_coverage=flag,
        )
    assert not out.exists()


def test_failed_native_decode_stops_before_any_quantity_producer(tmp_path, monkeypatch):
    from tools import gpt3_native_source_execution_coverage as native
    project, root, _docs = _fake_sources(tmp_path, monkeypatch)
    def failed(**kwargs):
        raise ValueError("synthetic native page unavailable")
    monkeypatch.setattr(native, "build_native_source_execution_coverage", failed)
    monkeypatch.setattr(module, "run_logged", lambda *args, **kwargs: pytest.fail("child started"))
    out = tmp_path / "failed-native-output"
    with pytest.raises(ValueError, match="native page unavailable"):
        module.produce_all_source_roles(
            project_id=project, source_dir=root, output_dir=out,
            record_native_source_input_coverage=True,
        )
    attempt = json.loads((out / "SOURCE_ROLE_STATUS.json").read_text())
    assert attempt["native_source_input_coverage_verified"] is False
    assert attempt["source_role_coverage_verified"] is False and attempt["roles"] == []
    assert not (out / "ALL_SOURCE_ROLES.sealed.json").exists()


@pytest.mark.parametrize("same_bytes", (True, False))
def test_post_child_input_or_inode_change_cannot_retain_a_native_audit(tmp_path, monkeypatch, same_bytes):
    project, root, _docs = _fake_sources(tmp_path, monkeypatch)
    def changed(command, repo, logfile, **kwargs):
        source = Path(command[command.index("--pdf") + 1])
        replacement = root / "replacement.pdf"
        replacement.write_bytes(source.read_bytes() if same_bytes else b"changed source")
        replacement.replace(source)
        return 0, "COMPLETED", {}
    monkeypatch.setattr(module, "run_logged", changed)
    out = tmp_path / "changed-native-output"
    with pytest.raises(ValueError, match="digest mismatch|changed during role production"):
        module.produce_all_source_roles(
            project_id=project, source_dir=root, output_dir=out,
            record_native_source_input_coverage=True,
        )
    attempt = json.loads((out / "SOURCE_ROLE_STATUS.json").read_text())
    assert attempt["native_source_input_coverage_verified"] is False
    assert attempt["source_role_coverage_verified"] is False
    assert not (out / "ALL_SOURCE_ROLES.sealed.json").exists()


@pytest.mark.parametrize("enabled", (False, True))
def test_cli_forwards_only_explicit_input_audit_and_retains_incomplete_exit(tmp_path, monkeypatch, capsys, enabled):
    called = []
    def produce(**kwargs):
        called.append(kwargs)
        result = {"status": "SOURCE_ROLES_INCOMPLETE", "project_id": kwargs["project_id"],
                  "roles": [], "expected_source_document_roles": 2,
                  "source_role_coverage_verified": False}
        if enabled:
            result["native_source_input_coverage_verified"] = True
        return result
    monkeypatch.setattr(module, "produce_all_source_roles", produce)
    args = ["--project-id", module.PROJECTS[0], "--source-dir", str(tmp_path),
            "--output-dir", str(tmp_path / "cli-output")]
    if enabled:
        args.append("--record-native-source-input-coverage")
    assert module.main(args) == 2
    console = json.loads(capsys.readouterr().out)
    assert console["sealed_roles"] == 0 and console["official_four_project_accuracy"] is None
    if enabled:
        assert called[0]["record_native_source_input_coverage"] is True
        assert console["native_source_input_coverage_verified"] is True
    else:
        assert "record_native_source_input_coverage" not in called[0]
        assert "native_source_input_coverage_verified" not in console


@pytest.mark.parametrize("native,glyph", ((True, False), (False, True), (True, True)))
def test_source_text_controls_reach_each_generic_role_without_granting_seals(tmp_path, monkeypatch, native, glyph):
    project, root, _docs = _fake_sources(tmp_path, monkeypatch)
    called = []
    monkeypatch.setattr(module, "run_logged", _no_quantity_runner(called))
    requested = {"source_native_finish_text_shadow": native, "source_glyph_ledger_text_trust": glyph}
    out = tmp_path / "controlled-output"
    result = module.produce_all_source_roles(
        project_id=project, source_dir=root, output_dir=out, **requested,
    )
    assert len(called) == 2
    for command, row in zip(called, result["roles"]):
        assert ("--source-native-finish-text-shadow" in command) is native
        assert ("--source-glyph-ledger-text-trust" in command) is glyph
        assert row["source_controls"] == {"status": "FORWARDED", "forwarded": requested}
        assert row["sealed"] is False and row["customer_bijection_verified"] is False
    assert result["requested_source_controls"] == requested
    assert result["source_role_coverage_verified"] is False
    assert result["benchmark_score_granted"] is False
    assert result["official_four_project_accuracy"] is None
    assert not (out / "ALL_SOURCE_ROLES.sealed.json").exists()


@pytest.mark.parametrize("name", ("source_native_finish_text_shadow", "source_glyph_ledger_text_trust"))
@pytest.mark.parametrize("value", (0, 1, "true", None, [], {}))
def test_source_text_control_rejects_non_boolean_before_source_io(tmp_path, monkeypatch, name, value):
    monkeypatch.setattr(module, "original_roster", lambda *args: pytest.fail("source I/O started"))
    out = tmp_path / "bad-control"
    with pytest.raises(ValueError, match="explicit booleans"):
        module.produce_all_source_roles(
            project_id=module.PROJECTS[0], source_dir=tmp_path, output_dir=out, **{name: value},
        )
    assert not out.exists()


def test_legacy_source_text_controls_do_not_change_commands_or_report(tmp_path, monkeypatch):
    project, root, _docs = _fake_sources(tmp_path, monkeypatch)
    called = []
    monkeypatch.setattr(module, "run_logged", _no_quantity_runner(called))
    result = module.produce_all_source_roles(project_id=project, source_dir=root, output_dir=tmp_path / "legacy")
    assert "requested_source_controls" not in result
    assert all("source_controls" not in row for row in result["roles"])
    assert all("--source-native-finish-text-shadow" not in cmd and "--source-glyph-ledger-text-trust" not in cmd for cmd in called)


def test_source_owned_issuer_gets_no_unsupported_generic_parser_flags(tmp_path, monkeypatch):
    project, root, _docs = _fake_sources(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(module, "run_logged", _no_quantity_runner(calls))
    monkeypatch.setattr(module, "source_owned_role_module", lambda *args, **kwargs: "tools.q5446_source_role_customer_runtime")
    result = module.produce_all_source_roles(
        project_id=project, source_dir=root, output_dir=tmp_path / "registered",
        source_native_finish_text_shadow=True, source_glyph_ledger_text_trust=True,
    )
    for command, row in zip(calls, result["roles"]):
        assert not any(arg in command for arg in ("--source-native-finish-text-shadow", "--source-glyph-ledger-text-trust"))
        assert row["source_controls"] == {"status": "NOT_APPLICABLE_SOURCE_OWNED_ISSUER", "forwarded": {
            "source_native_finish_text_shadow": False, "source_glyph_ledger_text_trust": False,
        }}
    assert result["source_role_coverage_verified"] is False


def test_unknown_issuer_cannot_silently_drop_requested_source_controls(tmp_path, monkeypatch):
    project, root, _docs = _fake_sources(tmp_path, monkeypatch)
    monkeypatch.setattr(module, "source_owned_role_module", lambda *args, **kwargs: "tools.unknown_source_issuer")
    monkeypatch.setattr(module, "run_logged", lambda *args, **kwargs: pytest.fail("unsupported child started"))
    out = tmp_path / "unknown"
    with pytest.raises(ValueError, match="unsupported by registered role producer"):
        module.produce_all_source_roles(
            project_id=project, source_dir=root, output_dir=out, source_native_finish_text_shadow=True,
        )
    attempted = json.loads((out / "SOURCE_ROLE_STATUS.json").read_text())
    assert attempted["roles"] == [] and attempted["source_role_coverage_verified"] is False
    assert not (out / "ALL_SOURCE_ROLES.sealed.json").exists()


@pytest.mark.parametrize("flag", ("source_native_finish_text_shadow", "source_glyph_ledger_text_trust"))
def test_cli_forwards_only_requested_source_text_control(tmp_path, monkeypatch, capsys, flag):
    called = []
    def produce(**kwargs):
        called.append(kwargs)
        return {"status": "SOURCE_ROLES_INCOMPLETE", "project_id": kwargs["project_id"],
                "roles": [], "expected_source_document_roles": 2, "source_role_coverage_verified": False}
    monkeypatch.setattr(module, "produce_all_source_roles", produce)
    assert module.main(["--project-id", module.PROJECTS[0], "--source-dir", str(tmp_path),
                        "--output-dir", str(tmp_path / "cli"), "--" + flag.replace("_", "-")]) == 2
    assert called[0][flag] is True
    other = "source_glyph_ledger_text_trust" if flag == "source_native_finish_text_shadow" else "source_native_finish_text_shadow"
    assert other not in called[0]
    assert json.loads(capsys.readouterr().out)["official_four_project_accuracy"] is None


def _synthetic_role_seal(project, sha, *, abstained=False):
    import pb_quantity_takeoff_adapter as adapter
    from pb_migration_contracts import QuantityEvidence
    from pb_source_closed_run_export import seal_source_closed_run
    quantity = QuantityEvidence(
        quantity_id="synthetic-primary-quantity", family="floor_area", semantic_key="floor.area",
        value=None if abstained else 12.5, unit="m²", input_entity_ids=("synthetic-physical-floor",),
        formula="documented_area", formula_version="1", evidence_ids=("synthetic-evidence",),
        authority="documented_dimension", status="abstained" if abstained else "corroborated",
        confidence=0.99, abstained=abstained,
        blocking_reasons=("synthetic insufficient evidence",) if abstained else (),
        metadata={"workspace_id": 7, "project_id": project, "document_id": "synthetic-primary",
                  "source_sha256": sha, "revision_id": "synthetic-rev",
                  "section": "Floors", "location": "Level 1"},
    )
    trace = adapter.CommercialTakeoffSourceTrace(
        workspace_id=7, project_id=project, document_id="synthetic-primary", source_sha256=sha,
        source_page="1", viewport_id="synthetic-viewport", revision_id="synthetic-rev",
        current_revision_id="synthetic-rev", evidence_ids=("synthetic-evidence",),
        canonical_entity_ids=("synthetic-physical-floor",),
    )
    traces = {quantity.quantity_id: trace}
    run = seal_source_closed_run((quantity,), project_id=project, traces_by_quantity_id=traces)
    rows = [] if abstained else adapter.quantities_to_takeoff_output_rows(
        (quantity,), traces_by_quantity_id=traces,
        authorities_by_quantity_id={
            quantity.quantity_id: adapter.CommercialMeasurementAuthority(method="direct_evidence"),
        },
    )
    return run, rows


def _empty_generic_summary(project, source, root):
    pages = list(range(1, source["page_count"] + 1))
    return {
        "status": "no_sealable_quantities", "project_id": project,
        "source_path": str(root / source["name"]), "source_sha256": source["sha256"],
        "page_count": source["page_count"], "family_group": "all",
        "complete_project_handoff": True, "source_positive_partial_page": None,
        "execution_pages": pages, "semantic_execution_pages": pages,
        "family_counts": {name: 0 for name in module._ALL_GROUP_FAMILY_COUNTS},
        "family_run_ids": {}, "family_run_files": {},
        "combined_run_file": None, "combined_run_id": None, "combined_quantity_count": 0,
        "verified_customer_row_count": 0, "customer_rows_verified": False, "customer_rows_file": None,
        "floor_finish_customer_rows_verified": False, "ceiling_customer_rows_verified": False,
        "full_project_customer_first_gate": "NO_SEALED_PROJECT",
    }


def _role_runner(project, docs, root, *, primary="genuine", secondary=lambda summary: summary):
    names = [source["name"] for source in docs]

    def run(command, repo, logfile, **kwargs):
        dest = Path(command[command.index("--output-dir") + 1])
        index = names.index(Path(command[command.index("--pdf") + 1]).name)
        summary = _empty_generic_summary(project, docs[index], root)
        if index == 0 and primary != "empty":
            sealed, rows = _synthetic_role_seal(project, docs[0]["sha256"], abstained=primary == "abstained")
            file, customer = dest / (project + ".json"), dest / "verified_customer_rows.json"
            file.write_text(sealed.to_json(), encoding="utf-8")
            customer.write_text(json.dumps(rows, sort_keys=True), encoding="utf-8")
            summary = {"status": "sealed", "combined_run_file": str(file),
                       "customer_rows_verified": True, "customer_rows_file": str(customer)}
        elif index == 1:
            summary = secondary(summary)
        (dest / "production_summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return 0, "COMPLETED", {}
    return run


def _receipt_path(out, role_number):
    return out / ("source_role_%02d" % role_number) / module.SOURCE_ROLE_ABSTENTION_FILE


def test_abstention_receipt_closes_a_fully_decoded_empty_supporting_role_beside_a_genuine_seal(tmp_path, monkeypatch):
    from pb_combine_source_closed_runs import load_verified_sealed_run
    from pb_customer_output_verification import verify_sealed_customer_output
    project, root, docs = _fake_sources(tmp_path, monkeypatch)
    monkeypatch.setattr(module, "run_logged", _role_runner(project, docs, root))
    out = tmp_path / "abstention-output"
    result = module.produce_all_source_roles(
        project_id=project, source_dir=root, output_dir=out,
        record_native_source_input_coverage=True, source_role_abstention_receipts=True,
    )
    assert result["status"] == "ALL_ROLES_CLOSED_WITH_SOURCE_ABSTENTION_CUSTOMER_VERIFIED_V2_PENDING"
    assert result["source_role_coverage_verified"] is True
    assert result["customer_bijection_verified"] is True
    assert result["source_role_abstention_count"] == 1
    assert result["benchmark_score_granted"] is False
    assert result["official_four_project_accuracy"] is None
    primary, supporting = result["roles"]
    assert primary["sealed"] is True and "source_role_abstained" not in primary
    assert supporting["sealed"] is False and supporting["source_role_abstained"] is True
    assert supporting["first_failure"] is None and supporting["customer_bijection_verified"] is True

    combined = load_verified_sealed_run(out / "ALL_SOURCE_ROLES.sealed.json")
    assert set(combined.source_sha256s) == {source["sha256"] for source in docs}
    abstained = [row for row in combined.quantities if row.abstained]
    genuine = [row for row in combined.quantities if not row.abstained]
    assert [(row.family, row.value, row.unit, row.source_sha256, row.object_identity_refs)
            for row in abstained] == [("source_role_abstention", None, "document", docs[1]["sha256"], ())]
    assert abstained[0].blocking_reasons == ("source_role_no_sealable_quantity",)
    assert abstained[0].source_page == "1-1" and abstained[0].lineage_ok is True
    assert [(row.quantity_id, row.value) for row in genuine] == [("synthetic-primary-quantity", 12.5)]
    customer_rows = json.loads((out / "ALL_SOURCE_ROLES.customer_rows.json").read_text(encoding="utf-8"))
    verified = verify_sealed_customer_output(combined, customer_rows)
    assert verified.verified_quantity_ids == ("synthetic-primary-quantity",)
    assert verified.abstained_quantity_count == 1 and verified.customer_row_count == 1

    receipt = load_verified_sealed_run(_receipt_path(out, 2))
    assert receipt.to_dict() == module.build_source_role_abstention_run(
        project_id=project, sha256=docs[1]["sha256"], page_count=1,
        native_input=supporting["native_source_input_coverage"],
    ).to_dict()
    assert not _receipt_path(out, 1).exists()
    for text in (json.dumps(result), _receipt_path(out, 2).read_text(encoding="utf-8")):
        assert str(root) not in text and "synthetic-original-document-role" not in text
        assert "structure.pdf" not in text
    assert json.loads((out / "SOURCE_ROLE_STATUS.json").read_text()) == result
    assert not list(out.rglob("*.pdf"))


def test_abstention_receipts_are_off_by_default(tmp_path, monkeypatch):
    project, root, docs = _fake_sources(tmp_path, monkeypatch)
    monkeypatch.setattr(module, "run_logged", _role_runner(project, docs, root))
    out = tmp_path / "default-output"
    result = module.produce_all_source_roles(
        project_id=project, source_dir=root, output_dir=out,
        record_native_source_input_coverage=True,
    )
    assert result["status"] == "SOURCE_ROLES_INCOMPLETE"
    assert result["roles"][1]["first_failure"] == "role_producer_no_sealable_result"
    assert all("source_role_abstained" not in row for row in result["roles"])
    assert "source_role_abstention_receipts" not in result
    assert "source_role_abstention_count" not in result
    assert not _receipt_path(out, 2).exists()
    assert not (out / "ALL_SOURCE_ROLES.sealed.json").exists()


@pytest.mark.parametrize("native,family", ((False, "all"), (True, "core"), (True, "surfaces"), (True, "floor_area")))
def test_abstention_receipts_require_native_coverage_and_every_family(tmp_path, monkeypatch, native, family):
    monkeypatch.setattr(module, "original_roster", lambda *args: pytest.fail("source I/O started"))
    out = tmp_path / "bad-receipt-policy"
    with pytest.raises(ValueError, match="abstention receipts require"):
        module.produce_all_source_roles(
            project_id=module.PROJECTS[0], source_dir=tmp_path, output_dir=out, family_group=family,
            record_native_source_input_coverage=native, source_role_abstention_receipts=True,
        )
    assert not out.exists()


@pytest.mark.parametrize("flag", (0, 1, "true", None, [], {}))
def test_abstention_receipt_flag_requires_an_explicit_boolean(tmp_path, monkeypatch, flag):
    monkeypatch.setattr(module, "original_roster", lambda *args: pytest.fail("source I/O started"))
    out = tmp_path / "bad-receipt-flag"
    with pytest.raises(ValueError, match="explicit boolean"):
        module.produce_all_source_roles(
            project_id=module.PROJECTS[0], source_dir=tmp_path, output_dir=out,
            record_native_source_input_coverage=True, source_role_abstention_receipts=flag,
        )
    assert not out.exists()


_NOT_AN_EXACT_EMPTY_RUN = {
    "complexity_blocked": lambda s: {**s, "status": "source_complexity_blocked"},
    "status_missing": lambda s: {k: v for k, v in s.items() if k != "status"},
    "partial_page": lambda s: {**s, "complete_project_handoff": False, "source_positive_partial_page": 1},
    "unexecuted_page": lambda s: {**s, "execution_pages": []},
    "unexecuted_semantic_page": lambda s: {**s, "semantic_execution_pages": []},
    "page_count": lambda s: {**s, "page_count": 2},
    "family_subset": lambda s: {**s, "family_group": "core"},
    "nonzero_family": lambda s: {**s, "family_counts": {**s["family_counts"], "opening_area": 1}},
    "nonzero_extra_family": lambda s: {**s, "family_counts": {**s["family_counts"], "wall_net_area": 1}},
    "unexamined_family": lambda s: {**s, "family_counts": {
        k: v for k, v in s["family_counts"].items() if k != "ceiling_area"}},
    "boolean_count": lambda s: {**s, "family_counts": {**s["family_counts"], "floor_area": False}},
    "foreign_source": lambda s: {**s, "source_sha256": "0" * 64},
    "foreign_project": lambda s: {**s, "project_id": "another_project"},
    "combined_file": lambda s: {**s, "combined_run_file": "elsewhere.json"},
    "combined_count_missing": lambda s: {k: v for k, v in s.items() if k != "combined_quantity_count"},
    "family_run": lambda s: {**s, "family_run_files": {"floor_area": "floor.json"}},
    "customer_rows": lambda s: {**s, "customer_rows_verified": True},
    "finish_rows": lambda s: {**s, "floor_finish_customer_rows_verified": True},
    "ceiling_rows": lambda s: {**s, "ceiling_customer_rows_verified": True},
}


@pytest.mark.parametrize("mutation", sorted(_NOT_AN_EXACT_EMPTY_RUN))
def test_only_an_exact_complete_empty_generic_run_earns_a_receipt(tmp_path, monkeypatch, mutation):
    project, root, docs = _fake_sources(tmp_path, monkeypatch)
    monkeypatch.setattr(module, "run_logged", _role_runner(
        project, docs, root, secondary=_NOT_AN_EXACT_EMPTY_RUN[mutation],
    ))
    out = tmp_path / "near-miss-output"
    result = module.produce_all_source_roles(
        project_id=project, source_dir=root, output_dir=out,
        record_native_source_input_coverage=True, source_role_abstention_receipts=True,
    )
    supporting = result["roles"][1]
    assert supporting["sealed"] is False and "source_role_abstained" not in supporting
    assert supporting["first_failure"] == "role_producer_no_sealable_result"
    assert supporting["customer_bijection_verified"] is False
    assert result["source_role_abstention_count"] == 0
    assert result["status"] == "SOURCE_ROLES_INCOMPLETE"
    assert result["source_role_coverage_verified"] is False
    assert not _receipt_path(out, 2).exists()
    assert not (out / "ALL_SOURCE_ROLES.sealed.json").exists()


@pytest.mark.parametrize("outcome", ((1, "COMPLETED"), (None, "TIMEOUT"), (None, "MEMORY_LIMIT")))
def test_an_unfinished_child_never_earns_a_receipt(tmp_path, monkeypatch, outcome):
    project, root, docs = _fake_sources(tmp_path, monkeypatch)
    complete = _role_runner(project, docs, root)

    def run(command, repo, logfile, **kwargs):
        complete(command, repo, logfile, **kwargs)
        return (*outcome, {}) if "structure.pdf" in command[command.index("--pdf") + 1] else (0, "COMPLETED", {})
    monkeypatch.setattr(module, "run_logged", run)
    out = tmp_path / "unfinished-output"
    result = module.produce_all_source_roles(
        project_id=project, source_dir=root, output_dir=out,
        record_native_source_input_coverage=True, source_role_abstention_receipts=True,
    )
    assert result["roles"][1]["first_failure"] == "role_producer_did_not_complete"
    assert "source_role_abstained" not in result["roles"][1]
    assert result["status"] == "SOURCE_ROLES_INCOMPLETE"
    assert not _receipt_path(out, 2).exists()


@pytest.mark.parametrize("primary", ("empty", "abstained"))
def test_receipts_without_a_genuine_sealed_quantity_never_close_a_project(tmp_path, monkeypatch, primary):
    project, root, docs = _fake_sources(tmp_path, monkeypatch)
    monkeypatch.setattr(module, "run_logged", _role_runner(project, docs, root, primary=primary))
    out = tmp_path / "receipts-only-output"
    result = module.produce_all_source_roles(
        project_id=project, source_dir=root, output_dir=out,
        record_native_source_input_coverage=True, source_role_abstention_receipts=True,
    )
    assert result["status"] == "SOURCE_ROLES_INCOMPLETE"
    assert result["source_role_coverage_verified"] is False
    assert result["customer_bijection_verified"] is False
    assert result["source_role_abstention_first_failure"] == "no_role_sealed_a_genuine_quantity"
    assert result["roles"][0]["sealed"] is (primary == "abstained")
    assert result["roles"][1]["source_role_abstained"] is True
    assert not (out / "ALL_SOURCE_ROLES.sealed.json").exists()
    assert not (out / "ALL_SOURCE_ROLES.customer_rows.json").exists()


def test_a_tampered_receipt_is_invalid_not_a_closed_role(tmp_path, monkeypatch):
    project, root, docs = _fake_sources(tmp_path, monkeypatch)
    monkeypatch.setattr(module, "run_logged", _role_runner(project, docs, root))
    write = module._write_exclusive

    def tampering_write(path, content):
        if path.name == module.SOURCE_ROLE_ABSTENTION_FILE:
            payload = json.loads(content)
            payload["quantities"][0]["value"] = 1.0
            content = json.dumps(payload)
        write(path, content)
    monkeypatch.setattr(module, "_write_exclusive", tampering_write)
    out = tmp_path / "tampered-output"
    result = module.produce_all_source_roles(
        project_id=project, source_dir=root, output_dir=out,
        record_native_source_input_coverage=True, source_role_abstention_receipts=True,
    )
    assert result["roles"][1]["first_failure"] == "source_role_abstention_receipt_invalid"
    assert "source_role_abstained" not in result["roles"][1]
    assert result["status"] == "SOURCE_ROLES_INCOMPLETE"
    assert not (out / "ALL_SOURCE_ROLES.sealed.json").exists()


@pytest.mark.parametrize("damage", ("partial", "failed_page", "short_pages", "foreign_sha", "fingerprint", "revision"))
def test_incomplete_or_foreign_native_coverage_cannot_issue_a_receipt(tmp_path, monkeypatch, damage):
    from tools import gpt3_native_source_execution_coverage as native
    project, root, docs = _fake_sources(tmp_path, monkeypatch)
    monkeypatch.setattr(module, "run_logged", _role_runner(project, docs, root))
    verify = native.verify_native_source_execution_coverage

    def damaged(receipt, **kwargs):
        actual = json.loads(json.dumps(verify(receipt, **kwargs)))
        if kwargs["expected_sha256"] == docs[1]["sha256"]:
            coverage = actual["coverage"]
            if damage == "partial":
                coverage["state"] = "partial"
            elif damage == "failed_page":
                coverage["failed_pages"] = [1]
            elif damage == "short_pages":
                coverage["decoded_pages"] = []
            elif damage == "foreign_sha":
                actual["source_sha256"] = docs[0]["sha256"]
            elif damage == "fingerprint":
                actual["fingerprint"] = "not-a-digest"
            else:
                coverage["revision_id"] = " "
        return actual
    monkeypatch.setattr(native, "verify_native_source_execution_coverage", damaged)
    out = tmp_path / "damaged-native-output"
    result = module.produce_all_source_roles(
        project_id=project, source_dir=root, output_dir=out,
        record_native_source_input_coverage=True, source_role_abstention_receipts=True,
    )
    assert result["roles"][1]["first_failure"] == "source_role_abstention_receipt_invalid"
    assert result["status"] == "SOURCE_ROLES_INCOMPLETE"
    assert not _receipt_path(out, 2).exists()
    assert not (out / "ALL_SOURCE_ROLES.sealed.json").exists()


def test_sha_owned_issuers_never_earn_a_generic_abstention_receipt(tmp_path, monkeypatch):
    project, root, docs = _fake_sources(tmp_path, monkeypatch)
    monkeypatch.setattr(module, "run_logged", _role_runner(project, docs, root))
    monkeypatch.setattr(module, "source_owned_role_module",
                        lambda *args, **kwargs: "tools.q5446_source_role_customer_runtime")
    out = tmp_path / "issuer-output"
    result = module.produce_all_source_roles(
        project_id=project, source_dir=root, output_dir=out,
        record_native_source_input_coverage=True, source_role_abstention_receipts=True,
    )
    assert result["roles"][1]["first_failure"] == "role_producer_no_sealable_result"
    assert "source_role_abstained" not in result["roles"][1]
    assert result["status"] == "SOURCE_ROLES_INCOMPLETE"
    assert not _receipt_path(out, 2).exists()


def test_abstention_receipt_is_deterministic_value_free_and_does_not_mutate_coverage(tmp_path, monkeypatch):
    import copy
    from tools.gpt3_native_source_execution_coverage import build_native_source_execution_coverage
    project, root, docs = _fake_sources(tmp_path, monkeypatch)
    coverage = build_native_source_execution_coverage(
        pdf_path=root / docs[1]["name"], expected_sha256=docs[1]["sha256"], expected_page_count=1,
    )
    before = copy.deepcopy(coverage)
    first = module.build_source_role_abstention_run(
        project_id=project, sha256=docs[1]["sha256"], page_count=1, native_input=coverage,
    )
    again = module.build_source_role_abstention_run(
        project_id=project, sha256=docs[1]["sha256"], page_count=1, native_input=copy.deepcopy(coverage),
    )
    assert coverage == before
    assert first.to_json() == again.to_json()
    (row,) = first.quantities
    assert row.abstained is True and row.value is None and row.object_identity_refs == ()
    assert row.status == "abstained" and row.confidence == 0.0
    assert row.document_id == coverage["coverage"]["document_id"]
    assert row.revision_id == coverage["coverage"]["revision_id"]
    other = build_native_source_execution_coverage(
        pdf_path=root / docs[0]["name"], expected_sha256=docs[0]["sha256"], expected_page_count=1,
    )
    foreign = module.build_source_role_abstention_run(
        project_id=project, sha256=docs[0]["sha256"], page_count=1, native_input=other,
    )
    assert foreign.quantities[0].quantity_id != row.quantity_id
    with pytest.raises(ValueError, match="complete native decode coverage"):
        module.build_source_role_abstention_run(
            project_id=project, sha256=docs[0]["sha256"], page_count=1, native_input=coverage,
        )
    with pytest.raises(ValueError, match="complete native decode coverage"):
        module.build_source_role_abstention_run(
            project_id=project, sha256=docs[1]["sha256"], page_count=2, native_input=coverage,
        )


@pytest.mark.parametrize("enabled", (False, True))
def test_cli_forwards_only_explicit_abstention_receipts(tmp_path, monkeypatch, capsys, enabled):
    called = []
    def produce(**kwargs):
        called.append(kwargs)
        result = {"status": "SOURCE_ROLES_INCOMPLETE", "project_id": kwargs["project_id"],
                  "roles": [], "expected_source_document_roles": 2,
                  "source_role_coverage_verified": False, "native_source_input_coverage_verified": True}
        if enabled:
            result["source_role_abstention_count"] = 0
        return result
    monkeypatch.setattr(module, "produce_all_source_roles", produce)
    args = ["--project-id", module.PROJECTS[0], "--source-dir", str(tmp_path),
            "--output-dir", str(tmp_path / "cli"), "--record-native-source-input-coverage"]
    if enabled:
        args.append("--source-role-abstention-receipts")
    assert module.main(args) == 2
    console = json.loads(capsys.readouterr().out)
    if enabled:
        assert called[0]["source_role_abstention_receipts"] is True
        assert console["source_role_abstentions"] == 0
    else:
        assert "source_role_abstention_receipts" not in called[0]
        assert "source_role_abstentions" not in console
