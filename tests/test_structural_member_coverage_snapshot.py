from __future__ import annotations

import copy
from pathlib import Path

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_structural_member_authority import (
    PhysicalStructuralMember,
    StructuralMemberResolution,
    StructuralMemberSelector,
)
from pb_structural_member_coverage_snapshot import (
    STRUCTURAL_COVERAGE_OWNING_AUTHORITY,
    STRUCTURAL_COVERAGE_PRODUCER,
    STRUCTURAL_MEMBER_ENUMERATION_IDENTITY_INVALID,
    STRUCTURAL_MEMBER_ENUMERATION_INCOMPLETE,
    structural_member_resolution_to_coverage_snapshot,
)
from pb_structural_member_quantity import build_structural_member_count_quantity
from pb_takeoff_coverage_registry import (
    CENSUS_DANGLING,
    COVERAGE_PARTIAL,
    ENUMERATION_COMPLETE,
    ENUMERATION_INCOMPLETE,
    CoverageRegistryRunManifestV1,
    QuantityEvidenceUniverseSnapshotV1,
    TakeoffOutputRowUniverseSnapshotV1,
    build_coverage_registry_v1,
)

SHA = "a" * 64


def selector(*, sha=SHA, kind="pier"):
    return StructuralMemberSelector(
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256=sha,
        snapshot_id="snap-1",
        decision_scope_id="scope-1",
        member_kind=kind,
    )


def member(mid, *, kind="pier", evidence=("ev-1",)):
    return PhysicalStructuralMember(
        physical_member_id=mid,
        member_kind=kind,
        observation_ids=(f"obs-{mid}",),
        source_evidence_ids=tuple(evidence),
        source_primitive_ids=(f"prim-{mid}",),
        page_ids=("1",),
        view_ids=("plan-1",),
        definition_ids=(),
    )


def resolved(*, members=None):
    members = tuple(members or (member("member-2"), member("member-1")))
    return StructuralMemberResolution(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("structural_member_scope_resolved",),
        selector=selector(),
        members=members,
        definitions=(),
        unresolved_observation_ids=(),
    )


def blocked(status=EvidenceResolutionStatus.ABSTAINED, reasons=("structural_member_scope_incomplete",)):
    return StructuralMemberResolution(
        status=status,
        reason_codes=tuple(reasons),
        selector=selector(),
        members=(),
        definitions=(),
        unresolved_observation_ids=("obs-1",),
    )


def test_corroborated_resolution_enumerates_complete_exact_member_ids():
    snap = structural_member_resolution_to_coverage_snapshot(
        resolved(), registry_run_id="run-1"
    )
    assert snap.producer == STRUCTURAL_COVERAGE_PRODUCER
    assert snap.owning_authority == STRUCTURAL_COVERAGE_OWNING_AUTHORITY
    assert snap.category == "pier"
    assert snap.source_document_id == "doc-1"
    assert snap.revision_id == "rev-1"
    assert snap.source_sha256 == SHA
    assert snap.registry_run_id == "run-1"
    assert snap.snapshot_id == "snap-1"
    assert snap.admitted_object_ids == ("member-1", "member-2")
    assert snap.enumeration_status == ENUMERATION_COMPLETE


@pytest.mark.parametrize(
    "status,reasons",
    [
        (EvidenceResolutionStatus.ABSTAINED, ("structural_member_scope_incomplete",)),
        (EvidenceResolutionStatus.CONFLICT, ("structural_member_relation_conflict",)),
        (EvidenceResolutionStatus.CANDIDATE, ("structural_member_registration_incomplete",)),
    ],
)
def test_non_corroborated_resolution_is_incomplete_never_zero_proof(status, reasons):
    snap = structural_member_resolution_to_coverage_snapshot(
        blocked(status=status, reasons=reasons), registry_run_id="run-1"
    )
    assert snap.admitted_object_ids == ()
    assert snap.enumeration_status == ENUMERATION_INCOMPLETE
    assert set(reasons) <= set(snap.reason_codes)
    assert STRUCTURAL_MEMBER_ENUMERATION_INCOMPLETE in snap.reason_codes


def test_malformed_corroborated_identity_is_incomplete_not_complete_empty():
    bad = resolved(members=(member(""),))
    snap = structural_member_resolution_to_coverage_snapshot(
        bad, registry_run_id="run-1"
    )
    assert snap.admitted_object_ids == ()
    assert snap.enumeration_status == ENUMERATION_INCOMPLETE
    assert STRUCTURAL_MEMBER_ENUMERATION_IDENTITY_INVALID in snap.reason_codes


def test_duplicate_member_ids_are_incomplete():
    bad = resolved(members=(member("m1"), member("m1")))
    snap = structural_member_resolution_to_coverage_snapshot(
        bad, registry_run_id="run-1"
    )
    assert snap.enumeration_status == ENUMERATION_INCOMPLETE
    assert snap.admitted_object_ids == ()


def test_member_kind_mismatch_is_incomplete():
    bad = resolved(members=(member("m1", kind="column"),))
    snap = structural_member_resolution_to_coverage_snapshot(
        bad, registry_run_id="run-1"
    )
    assert snap.enumeration_status == ENUMERATION_INCOMPLETE
    assert snap.admitted_object_ids == ()


def test_snapshot_is_input_order_invariant():
    left = resolved(members=(member("m2"), member("m1")))
    right = resolved(members=(member("m1"), member("m2")))
    a = structural_member_resolution_to_coverage_snapshot(left, registry_run_id="run-1")
    b = structural_member_resolution_to_coverage_snapshot(right, registry_run_id="run-1")
    assert a == b


def test_invalid_source_lineage_is_rejected_by_frozen_snapshot_contract():
    bad = StructuralMemberResolution(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("structural_member_scope_resolved",),
        selector=selector(sha="bad"),
        members=(member("m1"),),
        definitions=(),
        unresolved_observation_ids=(),
    )
    with pytest.raises(ValueError, match="SHA-256"):
        structural_member_resolution_to_coverage_snapshot(bad, registry_run_id="run-1")


def test_empty_registry_run_id_is_rejected():
    with pytest.raises(ValueError, match="registry_run_id"):
        structural_member_resolution_to_coverage_snapshot(
            resolved(), registry_run_id=""
        )


def test_snapshot_and_quantity_agree_on_exact_physical_member_ids():
    source = resolved()
    snap = structural_member_resolution_to_coverage_snapshot(
        source, registry_run_id="run-1"
    )
    qty = build_structural_member_count_quantity(source)
    assert snap.admitted_object_ids == qty.input_entity_ids
    assert qty.value == float(len(snap.admitted_object_ids))


def test_combined_registry_run_is_partial_and_dangling_without_takeoff_row():
    source = resolved()
    obj_snap = structural_member_resolution_to_coverage_snapshot(
        source, registry_run_id="run-1"
    )
    qty = build_structural_member_count_quantity(source)
    manifest = CoverageRegistryRunManifestV1(
        source_document_id="doc-1",
        revision_id="rev-1",
        source_sha256=SHA,
        registry_run_id="run-1",
        snapshot_id="snap-1",
        expected_object_universe_keys=(
            (STRUCTURAL_COVERAGE_PRODUCER, "pier"),
        ),
        expected_quantity_evidence_universe_keys=(
            ("structural_member_quantity", "shadow"),
        ),
        expected_takeoff_row_universe_keys=(("takeoff_rows", "shadow"),),
    )
    qe_snap = QuantityEvidenceUniverseSnapshotV1(
        producer="structural_member_quantity",
        source="shadow",
        source_document_id="doc-1",
        revision_id="rev-1",
        source_sha256=SHA,
        registry_run_id="run-1",
        snapshot_id="snap-1",
        quantity_ids=(qty.quantity_id,),
        enumeration_status=ENUMERATION_COMPLETE,
    )
    row_snap = TakeoffOutputRowUniverseSnapshotV1(
        source="takeoff_rows",
        collection="shadow",
        source_document_id="doc-1",
        revision_id="rev-1",
        source_sha256=SHA,
        registry_run_id="run-1",
        snapshot_id="snap-1",
        quantity_ids=(),
        enumeration_status=ENUMERATION_COMPLETE,
    )
    summary = build_coverage_registry_v1(
        manifest=manifest,
        object_universe_snapshots=(obj_snap,),
        quantity_evidence_universe_snapshots=(qe_snap,),
        takeoff_output_row_universe_snapshots=(row_snap,),
        quantity_evidence_by_universe={
            ("structural_member_quantity", "shadow"): (qty,)
        },
        takeoff_rows_by_universe={("takeoff_rows", "shadow"): ()},
        object_metadata_by_id={
            object_id: {"object_type": "pier"}
            for object_id in obj_snap.admitted_object_ids
        },
    )
    assert all(
        record.coverage_state == COVERAGE_PARTIAL
        for record in summary.object_records
    )
    assert summary.quantity_ids_by_census_state[CENSUS_DANGLING] == (
        qty.quantity_id,
    )


def test_snapshot_projection_does_not_mutate_resolution():
    source = resolved()
    before = copy.deepcopy(source)
    structural_member_resolution_to_coverage_snapshot(source, registry_run_id="run-1")
    assert source == before


def test_module_has_no_live_non_test_importers():
    root = Path(__file__).resolve().parents[1]
    offenders = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root)
        if rel.parts and rel.parts[0] == "tests":
            continue
        if path.name == "pb_structural_member_coverage_snapshot.py":
            continue
        text = path.read_text(encoding="utf-8-sig")
        if (
            "pb_structural_member_coverage_snapshot" in text
            or "structural_member_resolution_to_coverage_snapshot" in text
        ):
            offenders.append(str(rel))
    assert offenders == []
