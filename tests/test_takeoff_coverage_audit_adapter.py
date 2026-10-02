from __future__ import annotations

import copy

from pb_audit_coverage_record import CoverageState, DefaultCoverageProvider
from pb_audit_render import build_audit_scene, render_audit_html
from pb_canonical_building import CanonicalLevel, CanonicalWall, Vector2D
from pb_migration_contracts import QuantityEvidence
from pb_takeoff_coverage_audit_adapter import (
    REASON_NOT_IN_REGISTRY_UNIVERSE,
    RUNTIME_COVERAGE_AVAILABLE,
    RegistryCoverageRecordProviderV1,
    RuntimeCoverageStage,
    audit_registry_runtime_lifecycle,
    build_runtime_coverage_publication,
)
from pb_takeoff_coverage_registry import (
    COVERAGE_BASIS_EXPLICIT_DEPENDENCIES_ONLY,
    ENUMERATION_COMPLETE,
    EXPECTED_FAMILY_COMPLETENESS_UNKNOWN,
    CoverageRegistryRunManifestV1,
    ProducerObjectUniverseSnapshotV1,
    QuantityEvidenceUniverseSnapshotV1,
    TakeoffOutputRowUniverseSnapshotV1,
    build_coverage_registry_v1,
)
from pb_takeoff_output_authority import TakeoffOutputRow

SHA = "a" * 64
OBJ_KEY = ("physical_wall", "wall")
QE_KEY = ("wall_quantity", "shadow")
ROW_KEY = ("takeoff_rows", "shadow")


def summary_for(object_ids=("w1",), linked_ids=("w1",)):
    manifest = CoverageRegistryRunManifestV1(
        source_document_id="doc-1",
        revision_id="rev-1",
        source_sha256=SHA,
        registry_run_id="run-1",
        snapshot_id="snap-1",
        expected_object_universe_keys=(OBJ_KEY,),
        expected_quantity_evidence_universe_keys=(QE_KEY,),
        expected_takeoff_row_universe_keys=(ROW_KEY,),
    )
    object_snapshot = ProducerObjectUniverseSnapshotV1(
        producer=OBJ_KEY[0],
        owning_authority="physical_wall_existence_authority",
        category=OBJ_KEY[1],
        source_document_id="doc-1",
        revision_id="rev-1",
        source_sha256=SHA,
        registry_run_id="run-1",
        snapshot_id="snap-1",
        admitted_object_ids=tuple(object_ids),
        enumeration_status=ENUMERATION_COMPLETE,
    )
    qes = []
    rows = []
    if linked_ids:
        qes.append(
            QuantityEvidence(
                quantity_id="q-1",
                family="wall_length",
                semantic_key="wall_length:q-1",
                value=4.0,
                unit="M",
                input_entity_ids=tuple(linked_ids),
                evidence_ids=("ev-1",),
                authority="wall_length",
                status="corroborated",
                confidence=0.9,
            )
        )
        rows.append(
            TakeoffOutputRow(
                quantity_id="q-1",
                description="wall length",
                value=4.0,
                unit="M",
                geometry_ref=linked_ids[0],
                is_publishable=False,
            )
        )
    qe_snapshot = QuantityEvidenceUniverseSnapshotV1(
        producer=QE_KEY[0],
        source=QE_KEY[1],
        source_document_id="doc-1",
        revision_id="rev-1",
        source_sha256=SHA,
        registry_run_id="run-1",
        snapshot_id="snap-1",
        quantity_ids=tuple(q.quantity_id for q in qes),
        enumeration_status=ENUMERATION_COMPLETE,
    )
    row_snapshot = TakeoffOutputRowUniverseSnapshotV1(
        source=ROW_KEY[0],
        collection=ROW_KEY[1],
        source_document_id="doc-1",
        revision_id="rev-1",
        source_sha256=SHA,
        registry_run_id="run-1",
        snapshot_id="snap-1",
        quantity_ids=tuple(r.quantity_id for r in rows),
        enumeration_status=ENUMERATION_COMPLETE,
    )
    return build_coverage_registry_v1(
        manifest=manifest,
        object_universe_snapshots=(object_snapshot,),
        quantity_evidence_universe_snapshots=(qe_snapshot,),
        takeoff_output_row_universe_snapshots=(row_snapshot,),
        quantity_evidence_by_universe={QE_KEY: qes},
        takeoff_rows_by_universe={ROW_KEY: rows},
        object_metadata_by_id={
            oid: {
                "object_type": "wall",
                "geometry_ids": [oid],
                "source_pages": [1],
                "provenance": {"source": "synthetic"},
            }
            for oid in object_ids
        },
    )


def wall(wid: str, *, height=2.4):
    return CanonicalWall(
        id=wid,
        start_point=Vector2D(0.0, 0.0),
        end_point=Vector2D(4.0, 0.0),
        height_m=height,
        thickness_m=0.2,
    )


def test_exact_registry_identity_maps_accounted_semantics_into_scene_and_hud():
    summary = summary_for()
    provider = RegistryCoverageRecordProviderV1(summary)
    scene = build_audit_scene([CanonicalLevel(id="L1", elevation_m=0.0, walls=[wall("w1")])], provider)

    rec = scene["objects"][0]["audit"]
    assert rec["coverage_state"] == "ACCOUNTED"
    assert rec["takeoff_row_ids"] == ["q-1"]
    assert rec["coverage_basis"] == COVERAGE_BASIS_EXPLICIT_DEPENDENCIES_ONLY
    assert rec["expected_family_completeness"] == EXPECTED_FAMILY_COMPLETENESS_UNKNOWN
    assert scene["coverage_semantics"] == {
        "coverage_basis": COVERAGE_BASIS_EXPLICIT_DEPENDENCIES_ONLY,
        "expected_family_completeness": EXPECTED_FAMILY_COMPLETENESS_UNKNOWN,
    }
    html = render_audit_html(scene, mode="audit")
    assert "ACCOUNTED = explicit dependencies only" in html
    assert "not complete trade/BOQ scope" in html


def test_scene_object_absent_from_registry_admission_is_abstained_not_unaccounted():
    provider = RegistryCoverageRecordProviderV1(summary_for())
    rec = provider.record_for(
        {
            "id": "w-lookalike",
            "type": "WALL",
            "geometry": {"basis": "canonical"},
            "source_pages": [1],
            "provenance": {"label": "same", "reported_value": 4.0},
        }
    )
    assert rec.coverage_state is CoverageState.ABSTAINED
    assert rec.reason_code == REASON_NOT_IN_REGISTRY_UNIVERSE
    assert rec.coverage_basis is None


def test_renderer_uncertainty_only_downgrades_registry_accounted_state():
    summary = summary_for()
    before = copy.deepcopy(summary.to_dict())
    provider = RegistryCoverageRecordProviderV1(summary)
    scene = build_audit_scene(
        [CanonicalLevel(id="L1", elevation_m=0.0, walls=[wall("w1", height=None)])],
        provider,
    )
    rec = scene["objects"][0]["audit"]
    assert rec["coverage_state"] == "PARTIAL"
    assert rec["reason_code"] == "scene_unresolved:height"
    assert rec["coverage_basis"] == COVERAGE_BASIS_EXPLICIT_DEPENDENCIES_ONLY
    assert summary.to_dict() == before


def test_not_drawable_registry_accounted_object_is_partial_and_keeps_semantics():
    summary = summary_for()
    provider = RegistryCoverageRecordProviderV1(summary)
    no_geometry = CanonicalWall(id="w1", height_m=2.4, thickness_m=0.2)
    scene = build_audit_scene([CanonicalLevel(id="L1", elevation_m=0.0, walls=[no_geometry])], provider)
    rec = scene["not_drawn"][0]["audit"]
    assert rec["coverage_state"] == "PARTIAL"
    assert rec["coverage_basis"] == COVERAGE_BASIS_EXPLICIT_DEPENDENCIES_ONLY
    assert rec["expected_family_completeness"] == EXPECTED_FAMILY_COMPLETENESS_UNKNOWN


def test_equal_label_value_page_and_near_geometry_cannot_link_different_id():
    provider = RegistryCoverageRecordProviderV1(summary_for())
    rec = provider.record_for(
        {
            "id": "w2",
            "type": "WALL",
            "geometry": {"basis": "canonical", "pts": [[0.0, 0.01], [4.0, 0.01]]},
            "source_pages": [1],
            "provenance": {
                "label": "w1",
                "quantity": 4.0,
                "source_page": 1,
                "nearest_geometry_id": "w1",
            },
        }
    )
    assert rec.coverage_state is CoverageState.ABSTAINED
    assert rec.takeoff_row_ids == ()


def test_registry_provider_input_order_invariant():
    summary = summary_for(object_ids=("w2", "w1"), linked_ids=("w1",))
    provider = RegistryCoverageRecordProviderV1(summary)
    a = provider.record_for({"id": "w1", "type": "WALL", "geometry": {"basis": "canonical"}})
    b = provider.record_for({"geometry": {"basis": "canonical"}, "type": "WALL", "id": "w1"})
    assert a == b


def test_default_provider_behavior_remains_without_registry_semantics():
    scene = build_audit_scene(
        [CanonicalLevel(id="L1", elevation_m=0.0, walls=[wall("w1")])],
        DefaultCoverageProvider(),
    )
    assert scene["objects"][0]["audit"]["coverage_basis"] is None
    assert scene["coverage_semantics"] == {
        "coverage_basis": None,
        "expected_family_completeness": None,
    }


def test_w10_authority_flags_are_not_mutated_by_registry_adapter():
    w = wall("w1")
    assert w.takeoff_eligible is False
    assert w.deduction_authority is False
    before = copy.deepcopy(w.to_dict())
    build_audit_scene(
        [CanonicalLevel(id="L1", elevation_m=0.0, walls=[w])],
        RegistryCoverageRecordProviderV1(summary_for()),
    )
    assert w.to_dict() == before
    assert w.takeoff_eligible is False
    assert w.deduction_authority is False


def test_runtime_lifecycle_reaches_published_only_when_customer_row_exists():
    summary = summary_for()
    report = audit_registry_runtime_lifecycle(
        summary,
        published_takeoff_rows=[
            {
                "id": 91,
                "source_reference": "PB Auto Geometry v1.2.19 · structural:q-1",
            }
        ],
    )

    assert report.status == RUNTIME_COVERAGE_AVAILABLE
    assert report.stage_counts == {
        "DETECTED": 1,
        "AUTHENTICATED": 1,
        "CANONICALIZED": 1,
        "QUANTIFIED": 1,
        "PUBLISHED": 1,
    }
    obj = report.object_reports[0]
    assert obj.highest_stage_reached is RuntimeCoverageStage.PUBLISHED
    assert obj.died_at_stage is None
    assert obj.death_reason is None


def test_runtime_lifecycle_quantified_object_fails_closed_without_customer_row():
    report = audit_registry_runtime_lifecycle(
        summary_for(),
        published_takeoff_rows=[],
    )

    assert report.stage_counts["QUANTIFIED"] == 1
    assert report.stage_counts["PUBLISHED"] == 0
    obj = report.object_reports[0]
    assert obj.highest_stage_reached is RuntimeCoverageStage.QUANTIFIED
    assert obj.died_at_stage is RuntimeCoverageStage.PUBLISHED
    assert obj.death_reason == "customer_takeoff_row_not_found"


def test_runtime_publication_without_live_registry_is_unavailable_not_zero():
    payload = build_runtime_coverage_publication(
        (),
        published_takeoff_rows=[{"source_reference": "anything"}],
    )

    assert payload["status"] == "unavailable"
    assert payload["expected_family_completeness"] == "UNKNOWN"
    assert payload["stage_counts"] == {
        "DETECTED": None,
        "AUTHENTICATED": None,
        "CANONICALIZED": None,
        "QUANTIFIED": None,
        "PUBLISHED": None,
    }


def test_customer_runtime_is_only_approved_live_adapter_importer():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    offenders = []
    approved = {"pb_auto_geometry_v1219.py"}
    for path in root.rglob("*.py"):
        rel = path.relative_to(root)
        if rel.parts and rel.parts[0] == "tests":
            continue
        if path.name == "pb_takeoff_coverage_audit_adapter.py":
            continue
        text = path.read_text(encoding="utf-8-sig")
        if (
            "pb_takeoff_coverage_audit_adapter" in text
            or "RegistryCoverageRecordProviderV1" in text
        ) and str(rel).replace("\\", "/") not in approved:
            offenders.append(str(rel))
    assert offenders == []
