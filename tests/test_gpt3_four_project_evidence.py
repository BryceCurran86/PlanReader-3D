"""The four-project reporting path must never convert missing source into zero."""
from __future__ import annotations

from pathlib import Path

import pytest

from tools import report_gpt3_four_project_evidence as module


def _dirs(tmp_path: Path) -> dict:
    return {
        "source_dir": tmp_path / "source",
        "sealed_dir": tmp_path / "sealed",
        "identity_map_dir": tmp_path / "identity",
        "customer_dir": tmp_path / "customer",
    }


def test_missing_original_sources_keep_all_120_items_unpublished(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("unavailable source may not invoke frozen evaluator")
    monkeypatch.setattr(module, "evaluate_suite_v2", forbidden)
    result = module.build_four_project_evidence_ledger(**_dirs(tmp_path))
    assert result["publication_status"] == "UNPUBLISHED"
    assert result["official_suite_result"] is None
    assert result["coverage_accuracy"] is None
    assert result["precision_adjusted_accuracy"] is None
    assert result["required_project_count"] == 4
    assert result["frozen_denominator"] == 120
    assert len(result["projects"]) == 4
    assert sorted(x["denominator"] for x in result["projects"]) == [6, 24, 27, 63]
    for project in result["projects"]:
        assert project["publication_status"] == "UNAVAILABLE"
        assert project["source_sha_verified"] is False
        assert project["customer_bijection_verified"] is False
        assert project["reconciliation_complete"] is False
        assert project["exact_project_report"] is None


def test_present_but_corrupt_original_bytes_report_conflict_not_zero(tmp_path):
    dirs = _dirs(tmp_path)
    manifest = module.load_suite_manifests(module.FROZEN_ROOT)[0]
    project_root = dirs["source_dir"] / manifest.project_id
    project_root.mkdir(parents=True)
    for doc in manifest.source_documents:
        (project_root / doc.name).write_bytes(b"%PDF-fake-not-original")
    result = module.build_four_project_evidence_ledger(**dirs)
    observed = next(x for x in result["projects"] if x["project_id"] == manifest.project_id)
    assert observed["publication_status"] == "CONFLICT"
    assert observed["source_sha_verified"] is False
    assert observed["reconciliation_complete"] is False
    assert observed["exact_project_report"] is None
    assert any(
        reason.startswith("original_source_size_mismatch:")
        or reason.startswith("original_source_sha_mismatch:")
        for reason in observed["reason_codes"]
    )
    assert result["publication_status"] == "UNPUBLISHED"
    assert result["coverage_accuracy"] is None


def test_verified_source_without_signed_run_stays_unavailable(tmp_path, monkeypatch):
    dirs = _dirs(tmp_path)
    manifest = module.load_suite_manifests(module.FROZEN_ROOT)[0]
    project_root = dirs["source_dir"] / manifest.project_id
    project_root.mkdir(parents=True)
    for doc in manifest.source_documents:
        (project_root / doc.name).write_bytes(b"%PDF-test-fixture")
    # The source gate is simulated ONLY to exercise the downstream absence.
    # No real SHA proof or quantity is created from these test-only bytes.
    monkeypatch.setattr(
        module, "_original_sha_gate",
        lambda raw, paths: (True, [], [d.sha256 for d in manifest.source_documents]),
    )
    result = module.build_four_project_evidence_ledger(**dirs)
    observed = next(x for x in result["projects"] if x["project_id"] == manifest.project_id)
    assert observed["source_sha_verified"] is True
    assert observed["publication_status"] == "UNAVAILABLE"
    assert "signed_production_evidence_unavailable" in observed["reason_codes"]
    assert observed["customer_bijection_verified"] is False
    assert observed["exact_project_report"] is None
    assert result["official_suite_result"] is None


def test_malformed_customer_rows_fail_closed(tmp_path):
    path = tmp_path / "customer.json"
    path.write_text('[{"quantity_id": "q1"}, {"quantity_id": ""}]', encoding="utf-8")
    with pytest.raises(ValueError, match="canonical quantity identity"):
        module._json_customer_rows(path)
    path.write_text('{"quantity_id": "q1"}', encoding="utf-8")
    with pytest.raises(ValueError, match="JSON array"):
        module._json_customer_rows(path)


def test_malformed_signed_evidence_fails_closed(tmp_path):
    path = tmp_path / "signed.json"
    path.write_text('[]', encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        module._json_object(path)


def test_source_byte_change_between_preflight_and_score_fails(tmp_path):
    import hashlib
    original = tmp_path / "original.pdf"
    original.write_bytes(b"%PDF-real-original")
    initial = original.read_bytes()
    digest = hashlib.sha256(initial).hexdigest()
    manifest = {
        "source_documents": [{
            "name": "original.pdf", "sha256": digest,
            "size_bytes": len(initial),
        }],
    }
    frozen = tmp_path / "manifest.json"
    frozen.write_text('{"immutable": true}', encoding="utf-8")
    initial_files = {frozen: module._sha256(frozen)}
    module._assert_inputs_unchanged(
        manifest=manifest, originals=[original],
        expected_hashes=[digest], signed_hashes=initial_files,
    )
    original.write_bytes(b"%PDF-fake-original")
    with pytest.raises(ValueError, match="original source changed"):
        module._assert_inputs_unchanged(
            manifest=manifest, originals=[original],
            expected_hashes=[digest], signed_hashes=initial_files,
        )


def test_signed_customer_or_frozen_manifest_change_after_score_fails(tmp_path):
    import hashlib
    original = tmp_path / "original.pdf"
    original.write_bytes(b"%PDF-fixed-source")
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    manifest = {
        "source_documents": [{
            "name": "original.pdf", "sha256": digest,
            "size_bytes": original.stat().st_size,
        }],
    }
    signed = [tmp_path / item for item in (
        "source_manifest.json", "sealed.json", "identity.json", "customer.json"
    )]
    for path in signed:
        path.write_text('{"valid":true}', encoding="utf-8")
    fingerprints = {path: module._sha256(path) for path in signed}
    for modified in signed:
        modified.write_text('{"valid":false}', encoding="utf-8")
        with pytest.raises(ValueError, match="changed during reconciliation"):
            module._assert_inputs_unchanged(
                manifest=manifest, originals=[original],
                expected_hashes=[digest], signed_hashes=fingerprints,
            )
        modified.write_text('{"valid":true}', encoding="utf-8")
    module._assert_inputs_unchanged(
        manifest=manifest, originals=[original],
        expected_hashes=[digest], signed_hashes=fingerprints,
    )


def test_report_destination_cannot_overwrite_signed_inputs_or_alias(tmp_path):
    dirs = _dirs(tmp_path)
    input_path = dirs["sealed_dir"] / "signed-run.json"
    input_path.parent.mkdir(parents=True)
    input_path.write_text("unchanged signed bytes", encoding="utf-8")
    args = [
        "--source-dir", str(dirs["source_dir"]),
        "--sealed-dir", str(dirs["sealed_dir"]),
        "--identity-map-dir", str(dirs["identity_map_dir"]),
        "--customer-dir", str(dirs["customer_dir"]),
    ]
    with pytest.raises(ValueError, match="may not overwrite evidence"):
        module.main([*args, "--output", str(input_path)])
    assert input_path.read_text(encoding="utf-8") == "unchanged signed bytes"

    alias = tmp_path / "alias-to-signed"
    alias.symlink_to(dirs["sealed_dir"], target_is_directory=True)
    with pytest.raises(ValueError, match="may not overwrite evidence"):
        module.main([*args, "--output", str(alias / "new-report.json")])
    assert not (dirs["sealed_dir"] / "new-report.json").exists()

    # Never allow a diagnostic to overwrite frozen benchmark truth.
    with pytest.raises(ValueError, match="may not overwrite evidence"):
        module.main([
            *args, "--output",
            str(module.FROZEN_ROOT / "manifest.json"),
        ])


def test_read_only_report_writes_safely_outside_inputs(tmp_path):
    dirs = _dirs(tmp_path)
    output = tmp_path / "reports" / "inventory.json"
    code = module.main([
        "--source-dir", str(dirs["source_dir"]),
        "--sealed-dir", str(dirs["sealed_dir"]),
        "--identity-map-dir", str(dirs["identity_map_dir"]),
        "--customer-dir", str(dirs["customer_dir"]),
        "--output", str(output),
    ])
    assert code == 2
    import json
    parsed = json.loads(output.read_text(encoding="utf-8"))
    assert parsed["frozen_denominator"] == 120
    assert parsed["publication_status"] == "UNPUBLISHED"


def test_flat_and_scoped_original_packages_are_both_supported(tmp_path):
    from types import SimpleNamespace
    name = "original-architectural.pdf"
    doc = (SimpleNamespace(name=name),)
    flat = tmp_path / name
    flat.write_bytes(b"%PDF-same-source")
    selected, conflicts = module._resolve_original_paths(tmp_path, "project-x", doc)
    assert selected == [flat]
    assert conflicts == []

    scoped = tmp_path / "project-x" / name
    scoped.parent.mkdir()
    scoped.write_bytes(flat.read_bytes())
    selected, conflicts = module._resolve_original_paths(tmp_path, "project-x", doc)
    assert selected == [scoped]
    assert conflicts == []


def test_conflicting_flat_and_scoped_pdfs_fail_before_scoring(tmp_path):
    from types import SimpleNamespace
    name = "original-architectural.pdf"
    doc = (SimpleNamespace(name=name),)
    flat = tmp_path / name
    scoped = tmp_path / "project-x" / name
    scoped.parent.mkdir()
    flat.write_bytes(b"%PDF-authentic-source")
    scoped.write_bytes(b"%PDF-contradictory-source")
    chosen, reasons = module._resolve_original_paths(tmp_path, "project-x", doc)
    assert chosen == [scoped]  # returned only for audit; caller MUST refuse it
    assert reasons == ["conflicting_flat_and_scoped_original:" + name]


def _signed_receipts(*pairs):
    from types import SimpleNamespace
    quantities = tuple(SimpleNamespace(quantity_id=qid, abstained=abstain) for qid, abstain in pairs)
    valid = tuple(sorted(qid for qid, abstain in pairs if not abstain))
    return (
        SimpleNamespace(project_id="project", quantities=quantities),
        SimpleNamespace(
            project_id="project",
            sealed_quantity_count=len(pairs),
            valid_quantity_count=len(valid),
            abstained_quantity_count=len(pairs)-len(valid),
            customer_row_count=len(valid),
            verified_quantity_ids=valid,
        ),
        [{"quantity_id":qid} for qid in valid],
    )


def test_signed_firm_and_abstained_quantities_only_publish_firm_customer_rows():
    sealed, verification, rows = _signed_receipts(
        ("firm-finish", False), ("abstain-floor", True), ("firm-opening", False),
    )
    assert module._verify_customer_counts(sealed, verification, rows) is None


def test_all_abstained_signed_quantities_require_zero_customer_rows():
    sealed, verification, rows = _signed_receipts(
        ("abstain-wall", True), ("abstain-opening", True),
    )
    assert module._verify_customer_counts(sealed, verification, rows) is None


def test_abstained_customer_leak_and_missing_firm_bijection_are_rejected():
    sealed, verification, rows = _signed_receipts(
        ("firm-floor", False), ("abstain-finish", True),
    )
    with pytest.raises(ValueError, match="customer projection"):
        module._verify_customer_counts(
            sealed, verification,
            [*rows, {"quantity_id": "abstain-finish"}],
        )
    with pytest.raises(ValueError, match="customer projection"):
        module._verify_customer_counts(sealed, verification, [])


def test_duplicate_quantity_identity_across_firm_and_abstain_is_conflict():
    sealed, verification, rows = _signed_receipts(
        ("same-id", False), ("same-id", True),
    )
    with pytest.raises(ValueError, match="duplicate or conflicting"):
        module._verify_customer_counts(sealed, verification, rows)


def test_inaccurate_signed_verification_receipts_fail_closed():
    from types import SimpleNamespace
    sealed, verification, rows = _signed_receipts(
        ("firm-area", False), ("abstain-ceiling", True),
    )
    wrong = SimpleNamespace(**{
        **vars(verification),
        "abstained_quantity_count": 0,
    })
    with pytest.raises(ValueError, match="customer projection"):
        module._verify_customer_counts(sealed, wrong, rows)


def test_cross_project_duplicate_signed_quantity_ids_never_publish():
    from types import SimpleNamespace
    a = SimpleNamespace(quantities=(
        SimpleNamespace(quantity_id="shared-q"),
        SimpleNamespace(quantity_id="a-only"),
    ))
    b = SimpleNamespace(quantities=(
        SimpleNamespace(quantity_id="shared-q"),
    ))
    seen = {}
    module._enforce_cross_project_quantity_uniqueness(
        a, project_id="project-a", seen=seen,
    )
    with pytest.raises(ValueError, match="cross-project"):
        module._enforce_cross_project_quantity_uniqueness(
            b, project_id="project-b", seen=seen,
        )
    assert seen == {"shared-q": "project-a", "a-only": "project-a"}


def test_cross_project_unique_ids_are_retained_and_duplicates_are_atomic():
    from types import SimpleNamespace
    a = SimpleNamespace(quantities=(
        SimpleNamespace(quantity_id="a"),
        SimpleNamespace(quantity_id="a"),
    ))
    seen = {}
    with pytest.raises(ValueError, match="duplicate"):
        module._enforce_cross_project_quantity_uniqueness(
            a, project_id="project-a", seen=seen,
        )
    assert seen == {}
    b = SimpleNamespace(quantities=(SimpleNamespace(quantity_id="b"),))
    module._enforce_cross_project_quantity_uniqueness(
        b, project_id="project-b", seen=seen,
    )
    assert seen == {"b": "project-b"}


def test_full_four_project_success_passes_required_source_and_completion_receipts(
    tmp_path, monkeypatch,
):
    """Synthetic sources only; no frozen truth or benchmark results are altered."""
    import hashlib
    import json
    from dataclasses import dataclass
    from types import SimpleNamespace

    dirs = _dirs(tmp_path)
    frozen = tmp_path / "synthetic-frozen"
    manifests = []
    for i in range(4):
        project_id = f"test-project-{i}"
        name = f"test-original-{i}.pdf"
        original = dirs["source_dir"] / name
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_bytes(f"%PDF-test-synthetic-{i}".encode("ascii"))
        sha = hashlib.sha256(original.read_bytes()).hexdigest()
        document = SimpleNamespace(name=name, sha256=sha)
        manifests.append(SimpleNamespace(
            project_id=project_id, source_documents=(document,),
            verified_items=tuple(
                SimpleNamespace(
                    item_id=f"synthetic-{i}-{j}",
                    trade_category="flooring",
                    denominator_eligible=True,
                ) for j in range(30)
            ),
            status="VERIFIED", source_package_complete=True, reason_codes=(),
        ))
        canonical = frozen / "projects" / project_id / "source_manifest.json"
        canonical.parent.mkdir(parents=True)
        canonical.write_text(json.dumps({
            "project_id": project_id,
            "source_documents": [{
                "name": name, "size_bytes": original.stat().st_size,
                "sha256": sha,
            }],
        }), encoding="utf-8")
        for key, suffix in (
            ("sealed_dir", ".json"),
            ("identity_map_dir", ".identity_map.json"),
            ("customer_dir", ".customer_rows.json"),
        ):
            path = dirs[key] / (project_id + suffix)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "[]" if key == "customer_dir" else json.dumps({
                    "project_id": project_id, "source_sha256s": [sha],
                }),
                encoding="utf-8",
            )

    monkeypatch.setattr(module, "FROZEN_ROOT", frozen)
    monkeypatch.setattr(module, "load_suite_manifests", lambda root: manifests)
    monkeypatch.setattr(
        module, "sealed_source_closed_run_from_dict",
        lambda data: SimpleNamespace(
            project_id=data["project_id"],
            source_sha256s=data["source_sha256s"],
            quantities=(),
            to_dict=lambda: data,
        ),
    )
    monkeypatch.setattr(
        module, "identity_map_from_dict",
        lambda data: SimpleNamespace(
            project_id=data["project_id"], source_sha256s=data["source_sha256s"],
            bindings=(),
        ),
    )
    monkeypatch.setattr(
        module, "verify_sealed_customer_output",
        lambda sealed, rows: SimpleNamespace(
            project_id=sealed.project_id, sealed_quantity_count=0,
            valid_quantity_count=0, abstained_quantity_count=0,
            customer_row_count=0, verified_quantity_ids=(),
        ),
    )
    monkeypatch.setattr(module, "reconcile_sealed_run_v2", lambda *a: ())
    monkeypatch.setattr(
        module, "_unchanged_frozen_exact_report",
        lambda path, *_: {
            "project_id": path.parent.name,
            "source_sha_verified": True,
            "reconciliation_complete": True,
            "denominator": 30,
        },
    )

    @dataclass
    class SyntheticSuiteResult:
        publication_status: str = "PUBLISHED"
        coverage_accuracy: float = 0.0
        precision_adjusted_accuracy: float = 0.0

    calls = []
    def strict_evaluator(manifests, scored, **kwargs):
        calls.append(kwargs)
        assert len(scored) == 4
        assert kwargs["required_project_count"] == 4
        assert kwargs["reconciliation_complete_by_project"] == {
            item.project_id: True for item in manifests
        }
        assert kwargs["evaluated_source_sha256s_by_project"] == {
            item.project_id: (item.source_documents[0].sha256,)
            for item in manifests
        }
        return SyntheticSuiteResult()

    monkeypatch.setattr(module, "evaluate_suite_v2", strict_evaluator)
    report = module.build_four_project_evidence_ledger(**dirs)
    assert len(calls) == 1
    assert report["publication_status"] == "PUBLISHED"
    assert report["frozen_denominator"] == 120
    assert all(x["publication_status"] == "PROJECT_VERIFIED" for x in report["projects"])
    assert report["coverage_accuracy"] == 0.0


def _family_mapping_fixture(
    *, family, trade, semantic_key="source-owned", bound_family="same",
    mapped_refs=("physical-source-id",), quantity_refs=("physical-source-id",),
):
    from types import SimpleNamespace
    item = SimpleNamespace(
        item_id="benchmark-target", trade_category=trade,
        denominator_eligible=True,
    )
    sealed = SimpleNamespace(quantities=(
        SimpleNamespace(
            family=family, semantic_key=semantic_key,
            object_identity_refs=quantity_refs,
        ),
    ))
    binding = SimpleNamespace(
        benchmark_item_id="benchmark-target",
        production_object_identity_refs=mapped_refs,
        production_family=family if bound_family == "same" else bound_family,
    )
    return (
        SimpleNamespace(verified_items=(item,)),
        sealed,
        SimpleNamespace(bindings=(binding,)),
    )


def test_generic_floor_area_cannot_be_mapped_to_tiled_finish_or_ceiling():
    for trade in ("tiling", "ceilings", "painting", "doors", "windows"):
        fixture = _family_mapping_fixture(family="floor_area", trade=trade)
        with pytest.raises(ValueError, match="reclassified"):
            module._enforce_mapped_production_family_trade(*fixture)


def test_genuine_floor_area_and_finished_floor_keep_distinct_allowed_trades():
    for family, trade in (
        ("floor_area", "flooring"),  # eg independent figured alfresco floor
        ("floor_finish_area", "tiling"),  # source-authenticated FT3 tile
        ("floor_finish_area", "flooring"),
        ("ceiling_area", "ceilings"),
        ("opening_area", "windows"),
        ("opening_count", "doors"),
    ):
        fixture = _family_mapping_fixture(family=family, trade=trade)
        assert module._enforce_mapped_production_family_trade(*fixture) is None


def test_source_owned_window_cannot_be_reclassified_as_door_by_identity_map():
    window = _family_mapping_fixture(
        family="opening_area", trade="doors",
        semantic_key="window_area:physical-source-id",
    )
    with pytest.raises(ValueError, match="opening kind"):
        module._enforce_mapped_production_family_trade(*window)
    correct = _family_mapping_fixture(
        family="opening_area", trade="windows",
        semantic_key="window_area:physical-source-id",
    )
    assert module._enforce_mapped_production_family_trade(*correct) is None


def test_bound_production_family_must_be_explicit_and_correct():
    for altered in (None, "opening_area"):
        fixture = _family_mapping_fixture(
            family="floor_finish_area", trade="tiling", bound_family=altered,
        )
        with pytest.raises(ValueError, match="explicit original production family"):
            module._enforce_mapped_production_family_trade(*fixture)


def test_unmapped_production_floor_remains_unmapped_without_reclassification():
    fixture = _family_mapping_fixture(
        family="floor_area", trade="tiling",
        mapped_refs=("unrelated-source-object",),
    )
    assert module._enforce_mapped_production_family_trade(*fixture) is None


def test_existing_original_lot16_sealed_identity_mapping_remains_compatible():
    """Real committed producer-signed source evidence; never fixture-mint quantities."""
    import json
    from pb_source_closed_run_export import sealed_source_closed_run_from_dict
    root = Path(__file__).resolve().parents[1]
    inputs = root / "docs/engineering/lot16_original_identity_reconciliation_20261012"
    sealed = sealed_source_closed_run_from_dict(
        json.loads((inputs / "source_sealed_run.json").read_text(encoding="utf-8"))
    )
    mapping = module.identity_map_from_dict(
        json.loads((inputs / "identity_map.json").read_text(encoding="utf-8"))
    )
    manifests = module.load_suite_manifests(module.FROZEN_ROOT)
    manifest = next(m for m in manifests if m.project_id == sealed.project_id)
    assert module._enforce_mapped_production_family_trade(
        manifest, sealed, mapping,
    ) is None
