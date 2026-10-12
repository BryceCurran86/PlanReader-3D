"""GPT3 Lot16 signed-readiness, original-PDF and anti-false-match tests."""
from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from pb_source_closed_run_export import SealedSourceClosedQuantity, _build_sealed_run
from tools import diag_gpt3_lot16_identity_readiness as readiness


def _fixture(tmp_path: Path, monkeypatch, *, quantities: int = 1):
    original = tmp_path / "Lot16 original.pdf"
    original.write_bytes(b"%PDF-1.7\nsynthetic original receipt\n")
    sha = hashlib.sha256(original.read_bytes()).hexdigest()
    manifest = tmp_path / "source_manifest.json"
    manifest.write_text(json.dumps({
        "project_id": readiness.PROJECT,
        "status": "INCOMPLETE",
        "source_package_complete": True,
        "source_documents": [
            {"name": original.name, "size_bytes": original.stat().st_size,
             "sha256": sha, "role": "architectural_drawings"},
            {"name": "structural.pdf", "size_bytes": 1234,
             "sha256": "f" * 64, "role": "structural_drawings"},
        ],
        "verified_takeoff_items": [
            {"item_id": "ref-1", "denominator_eligible": True,
             "expected_object_refs": ["lot16:opening:p3:1218_sgw:01"],
             "expected_quantity": 2.16},
            {"item_id": "ref-2", "denominator_eligible": True,
             "expected_object_refs": ["lot16:opening:p3:1218_sgw:02"],
             "expected_quantity": 2.16},
            {"item_id": "not-core", "denominator_eligible": False,
             "expected_object_refs": ["lot16:extra:not-counted"],
             "expected_quantity": 99},
        ],
    }), encoding="utf-8")
    monkeypatch.setattr(readiness, "MANIFEST", manifest)
    items = []
    for index in range(quantities):
        physical = "physical_opening_existence_" + ("%032x" % (index + 1))
        items.append(SealedSourceClosedQuantity(
            project_id=readiness.PROJECT,
            quantity_id=f"q-{index}", family="opening_area",
            semantic_key=f"opening-semantic-{index}", value=2.16,
            unit="m2", status="corroborated", authority="documented_dimension",
            confidence=1.0, abstained=False,
            document_id="architectural-source", source_sha256=sha,
            source_page="3", viewport_id="source_page3_plan",
            revision_id="revE", object_identity_refs=(physical,),
            trace_canonical_entity_ids=(physical,),
            evidence_ids=(f"source_dimension_receipt_{index}",),
            trace_evidence_ids=(f"source_dimension_receipt_{index}",),
            blocking_reasons=(), reason_codes=(), lineage_ok=True,
            lineage_reason_codes=(),
        ))
    run = _build_sealed_run(items, project_id=readiness.PROJECT)
    sealed_file = tmp_path / "source_sealed_run.json"
    sealed_file.write_text(run.to_json(), encoding="utf-8")
    customers = tmp_path / "verified_customer_rows.json"
    customers.write_text(json.dumps([
        {"quantity_id": row.quantity_id} for row in items
    ]), encoding="utf-8")
    monkeypatch.setattr(
        readiness, "verify_sealed_customer_output",
        lambda _run, _rows: SimpleNamespace(
            valid_quantity_count=len(_rows),
            verified_quantity_ids=tuple(row["quantity_id"] for row in _rows),
        ),
    )
    return manifest, original, sealed_file, customers, run


def _report(fixture, *, original_pdf=True):
    manifest, original, sealed_file, customers, _run = fixture
    return readiness.build_unpublished_lot16_identity_readiness(
        manifest_path=manifest,
        sealed_run_path=sealed_file,
        customer_rows_path=customers,
        original_pdf=original if original_pdf else None,
    )


def test_two_equal_area_physical_openings_never_become_frozen_matches(
    tmp_path, monkeypatch,
):
    data = _fixture(tmp_path, monkeypatch, quantities=2)
    result = _report(data)
    assert result["original_architectural_pdf_bytes_verified"] is True
    assert result["source_firm_sealed_quantity_count"] == 2
    assert result["customer_verified_quantity_count"] == 2
    assert result["source_package_document_count"] == 2
    assert result["sealed_source_document_count"] == 1
    assert result["full_source_package_verified"] is False
    assert result["frozen_denominator_item_count"] == 2
    assert result["frozen_item_ids_not_yet_physically_bound"] == ["ref-1", "ref-2"]
    assert result["frozen_object_refs_not_yet_physically_bound"] == [
        "lot16:opening:p3:1218_sgw:01", "lot16:opening:p3:1218_sgw:02",
    ]
    assert result["benchmark_score_granted"] is False
    assert result["benchmark_status"] == "NOT_EVALUATED"
    assert result["coverage_accuracy"] is None
    assert result["matched_within_tolerance"] is None
    assert all(
        item["benchmark_item_id"] is None and item["crosswalk_status"] == "UNPROVEN"
        for item in result["source_physical_openings_requiring_independent_crosswalk"]
    )
    assert "expected_quantity" not in json.dumps(result)
    assert "2.16" not in json.dumps(result)


def test_readiness_without_original_bytes_never_claims_original_sha_verified(
    tmp_path, monkeypatch,
):
    result = _report(_fixture(tmp_path, monkeypatch), original_pdf=False)
    assert result["original_architectural_pdf_bytes_verified"] is False
    assert result["full_source_package_verified"] is False


@pytest.mark.parametrize("tamper", ["bytes", "name", "size"])
def test_original_pdf_must_equal_the_frozen_original(tmp_path, monkeypatch, tamper):
    data = _fixture(tmp_path, monkeypatch)
    manifest, original, *_ = data
    if tamper == "bytes":
        original.write_bytes(b"changed same length source"[:original.stat().st_size].ljust(
            original.stat().st_size, b"X"
        ))
    elif tamper == "name":
        target = original.with_name("foreign.pdf")
        original.rename(target)
        original = target
    else:
        original.write_bytes(original.read_bytes() + b"b")
    with pytest.raises(ValueError, match="original PDF"):
        readiness.build_unpublished_lot16_identity_readiness(
            manifest_path=manifest, sealed_run_path=data[2],
            customer_rows_path=data[3], original_pdf=original,
        )


def test_changed_source_manifest_cannot_launder_source_seal(tmp_path, monkeypatch):
    manifest, _original, sealed, customers, _run = _fixture(tmp_path, monkeypatch)
    record = json.loads(manifest.read_text())
    record["source_documents"][0]["sha256"] = "0" * 64
    manifest.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="frozen Lot16 architectural SHA"):
        readiness.build_unpublished_lot16_identity_readiness(
            manifest_path=manifest, sealed_run_path=sealed,
            customer_rows_path=customers,
        )


def test_signed_seal_mutation_is_rejected(tmp_path, monkeypatch):
    data = _fixture(tmp_path, monkeypatch)
    sealed_file = data[2]
    payload = json.loads(sealed_file.read_text())
    payload["quantities"][0]["value"] = 999.0
    sealed_file.write_text(json.dumps(payload))
    with pytest.raises(Exception, match="fingerprint"):
        _report(data)


@pytest.mark.parametrize("override", [
    {"family": "opening_count"},
    {"status": "abstained", "abstained": True, "value": None},
    {"status": "candidate"},
    {"lineage_ok": False, "lineage_reason_codes": ("source_conflict",)},
    {"object_identity_refs": ("unowned_abc",)},
    {"object_identity_refs": ("physical_opening_existence_a", "physical_opening_existence_b")},
])
def test_not_firm_or_unowned_opening_never_yields_identity_work_order(
    tmp_path, monkeypatch, override,
):
    fixture = _fixture(tmp_path, monkeypatch)
    run = fixture[4]
    replaced = replace(run.quantities[0], **override)
    updated = _build_sealed_run([replaced], project_id=readiness.PROJECT)
    fixture[2].write_text(updated.to_json())
    with pytest.raises(ValueError, match="FIRM source identity|nonphysical"):
        _report(fixture)


def test_same_physical_id_in_two_different_signed_semantics_is_rejected(
    tmp_path, monkeypatch,
):
    fixture = _fixture(tmp_path, monkeypatch)
    q = fixture[4].quantities[0]
    duplicate = replace(q, quantity_id="q-other", semantic_key="other-family-occurrence")
    run = _build_sealed_run([q, duplicate], project_id=readiness.PROJECT)
    fixture[2].write_text(run.to_json())
    fixture[3].write_text(json.dumps([
        {"quantity_id": "q-0"}, {"quantity_id": "q-other"}
    ]))
    with pytest.raises(ValueError, match="duplicate/nonphysical"):
        _report(fixture)


def test_customer_quantity_id_conflict_is_rejected(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path, monkeypatch)
    fixture[3].write_text(json.dumps([{"quantity_id": "wrong"}]))
    with pytest.raises(ValueError, match="bijection"):
        _report(fixture)


def test_external_manifest_path_rejected_before_reading_signed_artifacts(
    tmp_path, monkeypatch,
):
    fixture = _fixture(tmp_path, monkeypatch)
    replacement = tmp_path / "pretend-frozen-manifest.json"
    replacement.write_bytes(fixture[0].read_bytes())
    with pytest.raises(ValueError, match="exact frozen"):
        readiness.build_unpublished_lot16_identity_readiness(
            manifest_path=replacement, sealed_run_path=fixture[2],
            customer_rows_path=fixture[3],
        )


def test_duplicate_customer_json_field_cannot_shadow_quantity_id(
    tmp_path, monkeypatch,
):
    fixture = _fixture(tmp_path, monkeypatch)
    fixture[3].write_text(
        '[{"quantity_id":"q-0","quantity_id":"other"}]', encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate JSON key"):
        _report(fixture)
