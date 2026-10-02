from __future__ import annotations

import hashlib
import json

import pytest

from benchmarks.frozen_holdout.full_plan_v2.evaluator import (
    PROJECT_VERIFIED,
    ProjectBenchmarkManifestV2,
    SourceDocumentV2,
    VerifiedTakeoffItemV2,
    evaluate_project_v2,
)
from benchmarks.frozen_holdout.full_plan_v2.sealed_reconciliation import (
    V2ProductionIdentityBinding,
    V2ProductionIdentityMap,
    reconcile_sealed_run_v2,
)


SHA = "a" * 64


def manifest() -> ProjectBenchmarkManifestV2:
    item = VerifiedTakeoffItemV2(
        item_id="project-a-floor",
        project_id="project-a",
        description="Verified floor area",
        trade_category="tiling",
        unit="m2",
        expected_quantity=10.0,
        tolerance_policy_id="relative-tolerance-v1",
        tolerance_fraction=0.05,
        expected_object_refs=("benchmark:floor:food-prep",),
        source_document_refs=("reference_takeoff.json",),
        source_location_refs=("A140:verified-floor",),
    )
    return ProjectBenchmarkManifestV2(
        project_id="project-a",
        status=PROJECT_VERIFIED,
        source_package_complete=True,
        source_documents=(
            SourceDocumentV2(
                name="plans.pdf",
                role="architectural_drawings",
                sha256=SHA,
                size_bytes=100,
                page_count=2,
            ),
        ),
        reference_takeoff_documents=(
            SourceDocumentV2(
                name="reference_takeoff.json",
                role="independent_verified_reference_takeoff",
                sha256="b" * 64,
                size_bytes=100,
            ),
        ),
        verified_items=(item,),
    )


def identity_map(
    refs: tuple[str, ...] = ("canonical-floor-1",),
) -> V2ProductionIdentityMap:
    return V2ProductionIdentityMap(
        project_id="project-a",
        source_sha256s=(SHA,),
        bindings=(
            V2ProductionIdentityBinding(
                benchmark_item_id="project-a-floor",
                production_object_identity_refs=refs,
                production_family="room_area",
            ),
        ),
    )


def _fingerprint(payload: dict) -> str:
    text = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sealed_quantity(
    *,
    refs: tuple[str, ...] = ("canonical-floor-1",),
    value: float | None = 10.0,
    lineage_ok: bool = True,
    abstained: bool = False,
    family: str = "room_area",
) -> dict:
    payload = {
        "schema_version": "1.0.0",
        "project_id": "project-a",
        "quantity_id": "qty-1",
        "family": family,
        "semantic_key": "anything-not-used-for-matching",
        "value": value,
        "unit": "m2",
        "status": "firm" if not abstained else "abstained",
        "authority": "figured_dimension",
        "confidence": 1.0,
        "abstained": abstained,
        "document_id": "doc-a",
        "source_sha256": SHA,
        "source_page": "A140 / p2",
        "viewport_id": "vp-a140",
        "revision_id": "rev-a",
        "object_identity_refs": list(refs),
        "trace_canonical_entity_ids": list(refs),
        "evidence_ids": ["ev-1"],
        "trace_evidence_ids": ["ev-1"],
        "blocking_reasons": ["source_open"] if abstained else [],
        "reason_codes": [],
        "lineage_ok": lineage_ok,
        "lineage_reason_codes": [] if lineage_ok else ["identity_conflict"],
    }
    return {**payload, "fingerprint": _fingerprint(payload)}


def sealed_run(row: dict | None = None, *, source_sha: str = SHA) -> dict:
    payload = {
        "schema_version": "1.0.0",
        "run_id": "source_closed_run_test",
        "project_id": "project-a",
        "source_sha256s": [source_sha],
        "revision_ids": ["rev-a"],
        "quantities": [row or sealed_quantity()],
    }
    return {**payload, "fingerprint": _fingerprint(payload)}


def test_exact_production_identity_reconciles_to_verified_v2_object() -> None:
    produced = reconcile_sealed_run_v2(
        manifest(),
        sealed_run(),
        identity_map(),
    )
    assert len(produced) == 1
    assert produced[0].object_refs == ("benchmark:floor:food-prep",)
    assert produced[0].trade_category == "tiling"
    result = evaluate_project_v2(manifest(), produced)
    assert result.matched_within_tolerance == 1
    assert result.unsupported_extra == 0


def test_same_number_wrong_identity_is_missed_and_unsupported_extra() -> None:
    produced = reconcile_sealed_run_v2(
        manifest(),
        sealed_run(sealed_quantity(refs=("different-canonical-floor",))),
        identity_map(),
    )
    result = evaluate_project_v2(manifest(), produced)
    assert result.matched_within_tolerance == 0
    assert result.missed == 1
    assert result.unsupported_extra == 1


def test_semantic_key_description_or_numeric_similarity_never_drive_matching() -> None:
    row = sealed_quantity(refs=("canonical-floor-1",), value=10.0)
    row["semantic_key"] = "totally-different-room-label"
    row_without_fingerprint = dict(row)
    row_without_fingerprint.pop("fingerprint")
    row["fingerprint"] = _fingerprint(row_without_fingerprint)
    produced = reconcile_sealed_run_v2(
        manifest(),
        sealed_run(row),
        identity_map(),
    )
    assert produced[0].object_refs == ("benchmark:floor:food-prep",)


def test_lineage_conflict_survives_reconciliation() -> None:
    produced = reconcile_sealed_run_v2(
        manifest(),
        sealed_run(sealed_quantity(lineage_ok=False)),
        identity_map(),
    )
    assert produced[0].lineage_ok is False
    result = evaluate_project_v2(manifest(), produced)
    assert result.matched_within_tolerance == 0


def test_abstention_stays_none_and_never_becomes_zero() -> None:
    produced = reconcile_sealed_run_v2(
        manifest(),
        sealed_run(sealed_quantity(value=None, abstained=True)),
        identity_map(),
    )
    assert produced[0].abstained is True
    assert produced[0].value is None
    result = evaluate_project_v2(manifest(), produced)
    assert result.missed == 1
    assert result.unsupported_extra == 0


def test_unmapped_production_quantity_is_counted_as_unsupported_extra() -> None:
    produced = reconcile_sealed_run_v2(
        manifest(),
        sealed_run(sealed_quantity(refs=("unmapped-floor",))),
        identity_map(),
    )
    assert produced[0].object_refs == ("production-unmapped:unmapped-floor",)
    result = evaluate_project_v2(manifest(), produced)
    assert result.unsupported_extra == 1


def test_wrong_source_package_hash_fails_closed() -> None:
    run = sealed_run(source_sha="c" * 64)
    with pytest.raises(ValueError, match="source hashes"):
        reconcile_sealed_run_v2(manifest(), run, identity_map())


def test_tampered_quantity_fingerprint_fails_closed() -> None:
    row = sealed_quantity()
    row["value"] = 999.0
    run = sealed_run(row)
    with pytest.raises(ValueError, match="quantities\[0\] fingerprint"):
        reconcile_sealed_run_v2(manifest(), run, identity_map())


def test_unknown_benchmark_item_binding_fails_closed() -> None:
    mapping = V2ProductionIdentityMap(
        project_id="project-a",
        source_sha256s=(SHA,),
        bindings=(
            V2ProductionIdentityBinding(
                benchmark_item_id="not-a-real-item",
                production_object_identity_refs=("canonical-floor-1",),
            ),
        ),
    )
    with pytest.raises(ValueError, match="unknown denominator item"):
        reconcile_sealed_run_v2(manifest(), sealed_run(), mapping)


def test_duplicate_production_identity_bindings_fail_closed() -> None:
    with pytest.raises(ValueError, match="production identity bindings"):
        V2ProductionIdentityMap(
            project_id="project-a",
            source_sha256s=(SHA,),
            bindings=(
                V2ProductionIdentityBinding(
                    benchmark_item_id="item-a",
                    production_object_identity_refs=("canonical-floor-1",),
                ),
                V2ProductionIdentityBinding(
                    benchmark_item_id="item-b",
                    production_object_identity_refs=("canonical-floor-1",),
                ),
            ),
        )
