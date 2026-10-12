from __future__ import annotations

from types import SimpleNamespace
import inspect
import json

import pytest

import tools.run_gpt3_maryborough_original_floor_score_input as module


SHA = "a" * 64


def _quantity(
    qid: str,
    physical: str,
    canonical: str,
    *,
    value: float = 10.0,
):
    return SimpleNamespace(
        project_id=module.PROJECT,
        quantity_id=qid,
        source_sha256=SHA,
        family="floor_area",
        unit="m2",
        value=value,
        abstained=False,
        lineage_ok=True,
        object_identity_refs=(physical,),
        trace_canonical_entity_ids=tuple(sorted((physical, canonical))),
        evidence_ids=("source-evidence",),
        fingerprint="b" * 64,
        source_page="7",
        authority="documented_dimension",
    )


def _row(qid: str, physical: str, canonical: str):
    return {
        "quantity_id": qid,
        "project_id": module.PROJECT,
        "source_sha256": SHA,
        "canonical_entity_ids": list(sorted((physical, canonical))),
        "quantity_family": "floor_area",
        "quantity_status": "To review",
        "origin": "AI",
        "row_role": "floor_area",
    }


def _valid():
    q1 = _quantity("floor-area-1", "physical-floor-1", "canonical-floor-1")
    q2 = _quantity(
        "floor-area-2",
        "physical-floor-2",
        "canonical-floor-2",
        value=12.0,
    )
    sealed = SimpleNamespace(
        project_id=module.PROJECT,
        source_sha256s=(SHA,),
        quantities=(q1, q2),
        run_id="source-run",
        fingerprint="c" * 64,
    )
    rows = (
        _row(q1.quantity_id, q1.object_identity_refs[0], "canonical-floor-1"),
        _row(q2.quantity_id, q2.object_identity_refs[0], "canonical-floor-2"),
    )
    verified = SimpleNamespace(
        verified_quantity_ids=(q1.quantity_id, q2.quantity_id),
        valid_quantity_count=2,
        customer_row_count=2,
    )
    return sealed, rows, verified


def test_signed_source_floor_inventory_remains_unmapped_and_unscored():
    sealed, rows, verified = _valid()
    receipt = module._validate_sealed_customer_handoff(
        sealed,
        rows,
        verified,
        SHA,
    )

    assert receipt["quantity_count"] == 2
    assert receipt["benchmark_score_granted"] is False
    assert receipt["benchmark_accuracy"] is None
    assert receipt["frozen_v2_reconciliation_complete"] is False
    assert receipt["identity_map_status"] == (
        "INDEPENDENT_ORIGINAL_SOURCE_BINDINGS_REQUIRED"
    )
    assert {
        row["physical_floor_surface_id"]
        for row in receipt["source_floor_identities"]
    } == {"physical-floor-1", "physical-floor-2"}


def test_duplicate_physical_floor_identity_fails_closed():
    sealed, rows, verified = _valid()
    q1, q2 = sealed.quantities
    duplicated = SimpleNamespace(
        **{
            **q2.__dict__,
            "object_identity_refs": q1.object_identity_refs,
            "trace_canonical_entity_ids": tuple(
                sorted((q1.object_identity_refs[0], "canonical-floor-2"))
            ),
        }
    )
    bad_sealed = SimpleNamespace(
        **{**sealed.__dict__, "quantities": (q1, duplicated)}
    )
    bad_rows = (
        rows[0],
        _row(q2.quantity_id, q1.object_identity_refs[0], "canonical-floor-2"),
    )
    with pytest.raises(ValueError, match="identity/lineage"):
        module._validate_sealed_customer_handoff(
            bad_sealed,
            bad_rows,
            verified,
            SHA,
        )


def test_customer_trace_identity_mismatch_fails_closed():
    sealed, rows, verified = _valid()
    bad = list(rows)
    bad[0] = {**bad[0], "canonical_entity_ids": ["wrong-floor"]}
    with pytest.raises(ValueError, match="customer row identity"):
        module._validate_sealed_customer_handoff(
            sealed,
            tuple(bad),
            verified,
            SHA,
        )


def test_original_source_is_authenticated_by_manifest_name_size_and_sha(
    tmp_path,
):
    pdf = tmp_path / "Maryborough.pdf"
    pdf.write_bytes(b"original-source")
    import hashlib

    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "project_id": module.PROJECT,
                "source_documents": [
                    {
                        "name": pdf.name,
                        "role": "architectural_drawings",
                        "sha256": digest,
                        "size_bytes": pdf.stat().st_size,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    assert module._verify_original_source(pdf, manifest) == digest
    pdf.write_bytes(b"changed-source")
    with pytest.raises(ValueError):
        module._verify_original_source(pdf, manifest)


def test_score_input_publication_is_create_only(tmp_path):
    path = tmp_path / "signed.json"
    module._publish_new(path, {"first": True})
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        module._publish_new(path, {"first": False})
    assert path.read_bytes() == original


def test_source_runner_contains_no_reference_quantity_or_frozen_object_matching():
    source = inspect.getsource(module)
    for forbidden in (
        "reference_takeoff",
        "expected_quantity",
        "benchmark_item_id",
        "frozen_benchmark_object_ref",
        "matched_within_tolerance",
    ):
        assert forbidden not in source
