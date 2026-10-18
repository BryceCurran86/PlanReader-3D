"""The four-project reporting path must never convert missing source into zero."""
from __future__ import annotations

from pathlib import Path

import pytest

from tools import report_gpt3_four_project_evidence as module
from tests.symlink_test_support import symlink_or_skip


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
        assert project["first_failing_authority_stage"] == "original_source_file_absent"


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
    assert observed["first_failing_authority_stage"] == "original_source_sha_rejected"
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
    assert observed["first_failing_authority_stage"] == "sealed_reconciliation_artifact_absent"
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
    with pytest.raises(ValueError, match="may not overwrite protected evidence"):
        module.main([*args, "--output", str(input_path)])
    assert input_path.read_text(encoding="utf-8") == "unchanged signed bytes"

    alias = tmp_path / "alias-to-signed"
    symlink_or_skip(alias, dirs["sealed_dir"], target_is_directory=True)
    with pytest.raises(ValueError, match="may not overwrite protected evidence"):
        module.main([*args, "--output", str(alias / "new-report.json")])
    assert not (dirs["sealed_dir"] / "new-report.json").exists()

    # Never allow a diagnostic to overwrite frozen benchmark truth.
    with pytest.raises(ValueError, match="may not overwrite protected evidence"):
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
        semantic_key = {
            "opening_area": "window_area:physical-source-id",
            "opening_count": "door_count:physical-source-id",
        }.get(family, "source-owned")
        fixture = _family_mapping_fixture(
            family=family, trade=trade, semantic_key=semantic_key,
        )
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



@pytest.mark.parametrize(
    "payload",
    [
        '{"source_sha256":"a","source_sha256":"b"}',
        '{"quantities":[{"quantity_id":"first","quantity_id":"second"}]}',
        '{"metadata":{"revision_id":"old","revision_id":"new"}}',
        '{"fingerprint":"good","fingerprint":"bad"}',
    ],
)
def test_four_project_signed_input_rejects_duplicate_original_json_keys(tmp_path, payload):
    original = tmp_path / "signed.json"
    original.write_text(payload, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate key"):
        module._json_object(original)


@pytest.mark.parametrize(
    "payload",
    [
        '[{"quantity_id":"q-original","quantity_id":"q-swap"}]',
        '[{"quantity_id":"q","commercial_projection_provenance":{"quantity":{"quantity_id":"q","quantity_id":"foreign"}}}]',
        '[{"quantity_id":"q","source_sha256":"one","source_sha256":"two"}]',
    ],
)
def test_four_project_customer_input_rejects_nested_duplicate_json_keys(tmp_path, payload):
    original = tmp_path / "customer.json"
    original.write_text(payload, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate key"):
        module._json_customer_rows(original)


def test_four_project_strict_json_preserves_legitimate_original_receipts(tmp_path):
    original = tmp_path / "signed.json"
    original.write_text(
        '{"schema_version":"1.0.0","source_sha256":"a","quantities":'
        '[{"quantity_id":"q1","source_sha256":"b"}]}', encoding="utf-8",
    )
    assert module._json_object(original)["quantities"][0]["quantity_id"] == "q1"
    original.write_text(
        '[{"quantity_id":"q1","commercial_projection_provenance":'
        '{"adapter":"commercial_takeoff","quantity":{"quantity_id":"q1"}}}]',
        encoding="utf-8",
    )
    assert module._json_customer_rows(original)[0]["quantity_id"] == "q1"
    # Empty private package still fails closed independently of JSON parsing.
    ledger = module.build_four_project_evidence_ledger(**_dirs(tmp_path))
    assert ledger["publication_status"] == "UNPUBLISHED"
    assert ledger["frozen_denominator"] == 120
    assert ledger["official_suite_result"] is None


@pytest.mark.parametrize("family", (
    "unknown_area", "wall_surface_area", "", "floor_ara",
))
def test_mapped_unknown_source_family_cannot_claim_arbitrary_frozen_trade(family):
    fixture = _family_mapping_fixture(
        family=family, trade="tiling", semantic_key="source-owned",
    )
    with pytest.raises(ValueError, match="no verified benchmark trade semantics"):
        module._enforce_mapped_production_family_trade(*fixture)


@pytest.mark.parametrize("family,trade,semantic_key", (
    ("opening_area", "windows", "opening_area:physical-source-id"),
    ("opening_area", "doors", "source-owned"),
    ("opening_area", "doors", "window_count:physical-source-id"),
    ("opening_count", "doors", "door_area:physical-source-id"),
    ("opening_count", "windows", "opening_count:physical-source-id"),
))
def test_mapped_untyped_or_wrong_measurement_kind_opening_is_rejected(
    family, trade, semantic_key
):
    fixture = _family_mapping_fixture(
        family=family, trade=trade, semantic_key=semantic_key,
    )
    with pytest.raises(ValueError, match="no source-owned door/window kind"):
        module._enforce_mapped_production_family_trade(*fixture)


def test_unmapped_unknown_source_family_remains_unmapped_and_not_misclassified():
    fixture = _family_mapping_fixture(
        family="wall_surface_area", trade="painting",
        mapped_refs=("different-source-identity",),
    )
    assert module._enforce_mapped_production_family_trade(*fixture) is None


def test_manual_estimator_rows_do_not_change_verified_automated_customer_bijection(tmp_path):
    import json
    from pb_source_closed_run_export import sealed_source_closed_run_from_dict
    from pb_customer_output_verification import verify_sealed_customer_output

    root = Path(__file__).resolve().parents[1]
    source = root / "docs/engineering/lot16_original_signed_eight_row_20261015/production"
    sealed = sealed_source_closed_run_from_dict(json.loads(
        (source / "source_sealed_run.json").read_text(encoding="utf-8")
    ))
    originals = json.loads(
        (source / "verified_customer_rows.json").read_text(encoding="utf-8")
    )
    manual = {"description": "Manual estimator note", "trade": "review", "amount": 200}
    mixed = [*originals, manual]
    path = tmp_path / "customer.json"
    path.write_text(json.dumps(mixed), encoding="utf-8")
    parsed = module._json_customer_rows(path, allow_manual=True)
    verified = verify_sealed_customer_output(sealed, parsed)
    assert verified.customer_row_count == 8
    assert module._verify_customer_counts(sealed, verified, parsed) is None
    assert len(parsed) == 9
    assert sealed.fingerprint == sealed_source_closed_run_from_dict(
        json.loads((source / "source_sealed_run.json").read_text(encoding="utf-8"))
    ).fingerprint


@pytest.mark.parametrize("bad", [
    {"quantity_id": "", "description": "not a manual row"},
    {"quantity_id": None, "description": "not a manual row"},
    {"commercial_projection_provenance": {}, "description": "damaged"},
])
def test_manual_row_exclusion_cannot_hide_damaged_automated_identity(tmp_path, bad):
    import json
    path = tmp_path / "customer.json"
    path.write_text(json.dumps([bad]), encoding="utf-8")
    with pytest.raises(ValueError, match="canonical quantity identity"):
        module._json_customer_rows(path, allow_manual=True)


def test_manual_row_with_machine_source_reference_still_rejected_by_v1_verifier(tmp_path):
    import json
    from pb_source_closed_run_export import sealed_source_closed_run_from_dict
    from pb_customer_output_verification import (
        verify_sealed_customer_output, CustomerOutputVerificationError,
    )
    root = Path(__file__).resolve().parents[1]
    old = root / "docs/engineering/lot16_original_signed_eight_row_20261015/production"
    sealed = sealed_source_closed_run_from_dict(json.loads(
        (old / "source_sealed_run.json").read_text(encoding="utf-8")
    ))
    customers = json.loads((old / "verified_customer_rows.json").read_text(encoding="utf-8"))
    automated = {
        "description": "Damaged automated estimator row",
        "commercial_projection_provenance": {"adapter": "commercial_takeoff"},
    }
    # Embedded machine adapter claim with no quantity cannot be treated as manual.
    with pytest.raises((ValueError, CustomerOutputVerificationError)):
        verify_sealed_customer_output(sealed, [*customers, automated])


def test_manual_input_option_never_weakens_default_machine_only_reader(tmp_path):
    import json
    path = tmp_path / "mixed-rows.json"
    path.write_text(json.dumps([
        {"quantity_id": "machine-q"},
        {"notes": "genuine manual estimator note"},
    ]), encoding="utf-8")
    with pytest.raises(ValueError, match="canonical quantity identity"):
        module._json_customer_rows(path)
    accepted = module._json_customer_rows(path, allow_manual=True)
    assert len(accepted) == 2
    assert accepted[0]["quantity_id"] == "machine-q"
    assert "quantity_id" not in accepted[1]


def test_missing_original_source_roles_are_source_manifest_owned_and_share_safe(tmp_path):
    dirs = _dirs(tmp_path)
    manifests = module.load_suite_manifests(module.FROZEN_ROOT)
    lot16 = next(m for m in manifests if len(m.source_documents) == 2)
    result = module.build_four_project_evidence_ledger(**dirs)
    row = next(x for x in result["projects"] if x["project_id"] == lot16.project_id)
    assert row["missing_original_source_document_count"] == 2
    assert row["missing_original_source_document_roles"] == sorted(
        doc.role for doc in lot16.source_documents
    )
    assert all("/" not in role and "\\" not in role
               for role in row["missing_original_source_document_roles"])
    assert row["source_sha_verified"] is False
    assert row["exact_project_report"] is None
    assert result["official_suite_result"] is None


def test_one_supplied_source_does_not_claim_complete_twodoc_source_preflight(tmp_path):
    dirs = _dirs(tmp_path)
    manifests = module.load_suite_manifests(module.FROZEN_ROOT)
    lot16 = next(m for m in manifests if len(m.source_documents) == 2)
    project = dirs["source_dir"] / lot16.project_id
    project.mkdir(parents=True)
    supplied = lot16.source_documents[0]
    (project / supplied.name).write_bytes(b"%PDF-test-unverified")
    report = module.build_four_project_evidence_ledger(**dirs)
    row = next(x for x in report["projects"] if x["project_id"] == lot16.project_id)
    assert row["missing_original_source_document_count"] == 1
    assert row["missing_original_source_document_roles"] == [lot16.source_documents[1].role]
    assert row["source_sha_verified"] is False
    assert row["publication_status"] == "UNAVAILABLE"
    assert report["coverage_accuracy"] is None


def test_signed_and_customer_dependency_roster_only_after_full_original_source_gate(
    tmp_path, monkeypatch,
):
    dirs = _dirs(tmp_path)
    manifest = module.load_suite_manifests(module.FROZEN_ROOT)[0]
    src = dirs["source_dir"] / manifest.project_id
    src.mkdir(parents=True)
    for doc in manifest.source_documents:
        (src / doc.name).write_bytes(b"%PDF-source-neutral-test")
    # Bypass only the original SHA gate in a synthetic fixture; production
    # cannot label these untrusted bytes as a real source.
    monkeypatch.setattr(module, "_original_sha_gate",
                        lambda m, files: (True, [], [d.sha256 for d in manifest.source_documents]))
    result = module.build_four_project_evidence_ledger(**dirs)
    target = next(row for row in result["projects"] if row["project_id"] == manifest.project_id)
    assert target["source_sha_verified"] is True
    assert target["reconciliation_input_presence_status"] == "MISSING"
    assert target["missing_signed_reconciliation_artifacts"] == [
        "sealed_run", "identity_map", "customer_rows"
    ]
    assert target["customer_bijection_verified"] is False
    assert target["reconciliation_complete"] is False
    assert result["coverage_accuracy"] is None


def test_unavailable_source_never_claims_signed_files_missing_or_verified(tmp_path):
    report = module.build_four_project_evidence_ledger(**_dirs(tmp_path))
    for target in report["projects"]:
        assert target["source_sha_verified"] is False
        assert target["reconciliation_input_presence_status"] == "NOT_CHECKED_SOURCE_UNAVAILABLE"
        assert target["missing_signed_reconciliation_artifacts"] == []
        assert target["exact_project_report"] is None
    assert report["publication_status"] == "UNPUBLISHED"


def test_first_failing_stage_rejects_corrupt_signed_run_before_identity_or_customer(tmp_path, monkeypatch):
    dirs = _dirs(tmp_path)
    manifest = module.load_suite_manifests(module.FROZEN_ROOT)[0]
    root = dirs["source_dir"] / manifest.project_id
    root.mkdir(parents=True)
    for doc in manifest.source_documents:
        (root / doc.name).write_bytes(b"%PDF-synthetic-source-only")
    monkeypatch.setattr(
        module, "_original_sha_gate",
        lambda raw, files: (True, [], [d.sha256 for d in manifest.source_documents]),
    )
    for path in (
        dirs["sealed_dir"] / (manifest.project_id + ".json"),
        dirs["identity_map_dir"] / (manifest.project_id + ".identity_map.json"),
        dirs["customer_dir"] / (manifest.project_id + ".customer_rows.json"),
    ):
        path.parent.mkdir(parents=True)
        path.write_text('{"not":"a signed run"}', encoding="utf-8")
    observed = module.build_four_project_evidence_ledger(**dirs)
    row = next(q for q in observed["projects"] if q["project_id"] == manifest.project_id)
    assert row["publication_status"] == "CONFLICT"
    assert row["first_failing_authority_stage"] == "sealed_source_run_parse_or_signature"
    assert row["reconciliation_input_presence_status"] == "REJECTED"
    assert row["source_sha_verified"] is True
    assert row["customer_bijection_verified"] is False
    assert row["exact_project_report"] is None
    assert observed["coverage_accuracy"] is None
    assert observed["official_suite_result"] is None


def test_first_failing_stage_uses_only_fixed_share_safe_identifiers(tmp_path):
    report = module.build_four_project_evidence_ledger(**_dirs(tmp_path))
    for row in report["projects"]:
        stage = row["first_failing_authority_stage"]
        assert type(stage) is str and stage.replace("_", "").isascii()
        assert "/" not in stage and "\\\\" not in stage
        assert "original" in stage or "source" in stage
        assert row["denominator"] > 0
    assert report["frozen_denominator"] == 120
    assert report["publication_status"] == "UNPUBLISHED"


def test_full_four_project_cli_refuses_existing_report_before_original_pdf_and_seal_reads(
    tmp_path, monkeypatch,
):
    dirs = _dirs(tmp_path)
    report = tmp_path / "already-owned-customer.json"
    report.write_text('{"customer":"preserve"}', encoding="utf-8")
    monkeypatch.setattr(
        module, "build_four_project_evidence_ledger",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("unsafe output path must fail before source/quantity reads")
        ),
    )
    args = [
        "--source-dir", str(dirs["source_dir"]),
        "--sealed-dir", str(dirs["sealed_dir"]),
        "--identity-map-dir", str(dirs["identity_map_dir"]),
        "--customer-dir", str(dirs["customer_dir"]),
        "--output", str(report),
    ]
    with pytest.raises(FileExistsError, match="new path"):
        module.main(args)
    assert report.read_text(encoding="utf-8") == '{"customer":"preserve"}'


def test_full_four_project_cli_refuses_reusing_even_its_own_previous_diagnostic(tmp_path):
    dirs = _dirs(tmp_path)
    report = tmp_path / "first-source-readiness.json"
    args = [
        "--source-dir", str(dirs["source_dir"]),
        "--sealed-dir", str(dirs["sealed_dir"]),
        "--identity-map-dir", str(dirs["identity_map_dir"]),
        "--customer-dir", str(dirs["customer_dir"]),
        "--output", str(report),
    ]
    assert module.main(args) == 2
    original = report.read_bytes()
    with pytest.raises(FileExistsError, match="new path"):
        module.main(args)
    assert report.read_bytes() == original
    assert not list(tmp_path.glob(".gpt3-original-report-*.tmp"))


def test_full_four_project_cli_competing_writer_does_not_replace_existing_file(
    tmp_path, monkeypatch,
):
    from tools import gpt3_safe_original_report_output as safe
    dirs = _dirs(tmp_path)
    report = tmp_path / "racing-report.json"
    original_link = safe.os.link

    def competing_writer(temp, target):
        from pathlib import Path
        Path(target).write_text('{"another-run":"already-published"}')
        return original_link(temp, target)

    monkeypatch.setattr(safe.os, "link", competing_writer)
    with pytest.raises(FileExistsError):
        module.main([
            "--source-dir", str(dirs["source_dir"]),
            "--sealed-dir", str(dirs["sealed_dir"]),
            "--identity-map-dir", str(dirs["identity_map_dir"]),
            "--customer-dir", str(dirs["customer_dir"]),
            "--output", str(report),
        ])
    assert report.read_text(encoding="utf-8") == '{"another-run":"already-published"}'
    assert not list(tmp_path.glob(".gpt3-original-report-*.tmp"))


def test_full_four_project_report_output_cannot_follow_symlink_to_customer_file(tmp_path):
    dirs = _dirs(tmp_path)
    customer = tmp_path / "customer-lines.json"
    customer.write_text('{"valid":"customer-output"}')
    alias = tmp_path / "report-alias.json"
    symlink_or_skip(alias, customer)
    with pytest.raises(FileExistsError, match="new path"):
        module.main([
            "--source-dir", str(dirs["source_dir"]),
            "--sealed-dir", str(dirs["sealed_dir"]),
            "--identity-map-dir", str(dirs["identity_map_dir"]),
            "--customer-dir", str(dirs["customer_dir"]),
            "--output", str(alias),
        ])
    assert customer.read_text() == '{"valid":"customer-output"}'
