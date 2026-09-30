from __future__ import annotations

import copy
from dataclasses import fields

import pytest

from pb_editable_3d_correction_model import EditableGeometryObject
from pb_migration_contracts import QuantityEvidence
from pb_takeoff_output_authority import TakeoffOutputRow
from pb_takeoff_coverage_registry import (
    CENSUS_CONFLICTING_LINEAGE,
    CENSUS_DANGLING,
    CENSUS_LINKED,
    CENSUS_ORPHAN_UNBOUND,
    COVERAGE_ABSTAINED,
    COVERAGE_ACCOUNTED,
    COVERAGE_PARTIAL,
    COVERAGE_UNACCOUNTED,
    ENUMERATION_COMPLETE,
    ENUMERATION_INCOMPLETE,
    ENUMERATION_NOT_ENUMERATED,
    EXPECTED_FAMILY_COMPLETENESS_UNKNOWN,
    COVERAGE_BASIS_EXPLICIT_DEPENDENCIES_ONLY,
    CoverageObjectRecordV1,
    CoverageRegistryContractError,
    CoverageRegistryRunManifestV1,
    ProducerObjectUniverseSnapshotV1,
    QuantityEvidenceUniverseSnapshotV1,
    TakeoffOutputRowUniverseSnapshotV1,
    build_coverage_registry_v1,
)


SHA = "a" * 64
OBJECT_KEY = ("physical_wall", "wall")
QE_KEY = ("wall_quantity", "quantity_evidence")
ROW_KEY = ("takeoff_authority", "rows")


def manifest(
    *,
    object_keys=(OBJECT_KEY,),
    qe_keys=(QE_KEY,),
    row_keys=(ROW_KEY,),
    sha=SHA,
    revision="rev-1",
    run="run-1",
    snapshot="snap-1",
):
    return CoverageRegistryRunManifestV1(
        source_document_id="doc-1",
        revision_id=revision,
        source_sha256=sha,
        registry_run_id=run,
        snapshot_id=snapshot,
        expected_object_universe_keys=object_keys,
        expected_quantity_evidence_universe_keys=qe_keys,
        expected_takeoff_row_universe_keys=row_keys,
    )


def object_snapshot(
    ids=("wall-1",),
    *,
    status=ENUMERATION_COMPLETE,
    reasons=(),
    producer=OBJECT_KEY[0],
    category=OBJECT_KEY[1],
    authority="physical_wall_existence_authority",
    document="doc-1",
    sha=SHA,
    revision="rev-1",
    run="run-1",
    snapshot="snap-1",
):
    return ProducerObjectUniverseSnapshotV1(
        producer=producer,
        owning_authority=authority,
        category=category,
        source_document_id=document,
        revision_id=revision,
        source_sha256=sha,
        registry_run_id=run,
        snapshot_id=snapshot,
        admitted_object_ids=ids,
        enumeration_status=status,
        reason_codes=reasons,
    )


def qe_snapshot(
    ids=("q-1",),
    *,
    status=ENUMERATION_COMPLETE,
    reasons=(),
    producer=QE_KEY[0],
    source=QE_KEY[1],
    sha=SHA,
    revision="rev-1",
    run="run-1",
    snapshot="snap-1",
):
    return QuantityEvidenceUniverseSnapshotV1(
        producer=producer,
        source=source,
        source_document_id="doc-1",
        revision_id=revision,
        source_sha256=sha,
        registry_run_id=run,
        snapshot_id=snapshot,
        quantity_ids=ids,
        enumeration_status=status,
        reason_codes=reasons,
    )


def row_snapshot(
    ids=("q-1",),
    *,
    status=ENUMERATION_COMPLETE,
    reasons=(),
    source=ROW_KEY[0],
    collection=ROW_KEY[1],
    sha=SHA,
    revision="rev-1",
    run="run-1",
    snapshot="snap-1",
):
    return TakeoffOutputRowUniverseSnapshotV1(
        source=source,
        collection=collection,
        source_document_id="doc-1",
        revision_id=revision,
        source_sha256=sha,
        registry_run_id=run,
        snapshot_id=snapshot,
        quantity_ids=ids,
        enumeration_status=status,
        reason_codes=reasons,
    )


def quantity(
    qid="q-1",
    object_ids=("wall-1",),
    *,
    value=10.0,
    abstained=False,
    metadata=None,
):
    return QuantityEvidence(
        quantity_id=qid,
        family="wall_length",
        semantic_key=f"wall_length:{qid}",
        value=None if abstained else value,
        unit="M",
        input_entity_ids=object_ids,
        evidence_ids=("ev-1",),
        authority="physical_wall_length",
        status="abstained" if abstained else "corroborated",
        confidence=0.9,
        abstained=abstained,
        blocking_reasons=("measurement_refused",) if abstained else (),
        reason_codes=("explicit_refusal",) if abstained else (),
        metadata=dict(metadata or {}),
    )


def row(qid="q-1", *, geometry_ref="wall-1", revision_hash=None, value=10.0):
    return TakeoffOutputRow(
        quantity_id=qid,
        description=f"quantity {qid}",
        value=value,
        unit="M",
        geometry_ref=geometry_ref,
        revision_hash=revision_hash,
        is_publishable=False,
    )


def editable(
    object_id="wall-1",
    deps=(),
    *,
    geometry_ref="geom-wall-1",
    original_geometry_ref="geom-wall-1",
    revision_hash="edit-rev",
):
    return EditableGeometryObject(
        object_id=object_id,
        object_type="wall",
        source_file_id="source-file-1",
        source_page=1,
        source_sheet="A101",
        geometry_ref=geometry_ref,
        original_geometry_ref=original_geometry_ref,
        revision_hash=revision_hash,
        dependent_quantity_ids=list(deps),
    )


def build(
    *,
    m=None,
    objects=None,
    qes=None,
    rows=None,
    object_snaps=None,
    qe_snaps=None,
    row_snaps=None,
    editables=(),
    metadata=None,
):
    m = m or manifest()
    qes = list(qes if qes is not None else [quantity()])
    rows = list(rows if rows is not None else [row()])
    object_snaps = list(object_snaps if object_snaps is not None else [object_snapshot()])
    qe_snaps = list(qe_snaps if qe_snaps is not None else [qe_snapshot(tuple(q.quantity_id for q in qes))])
    row_snaps = list(row_snaps if row_snaps is not None else [row_snapshot(tuple(r.quantity_id for r in rows))])
    return build_coverage_registry_v1(
        manifest=m,
        object_universe_snapshots=object_snaps,
        quantity_evidence_universe_snapshots=qe_snaps,
        takeoff_output_row_universe_snapshots=row_snaps,
        quantity_evidence_by_universe={QE_KEY: qes} if QE_KEY in m.expected_quantity_evidence_universe_keys else {},
        takeoff_rows_by_universe={ROW_KEY: rows} if ROW_KEY in m.expected_takeoff_row_universe_keys else {},
        editable_objects=editables,
        object_metadata_by_id=metadata or {},
    )


def record_for(summary, object_id="wall-1"):
    return next(record for record in summary.object_records if record.object_id == object_id)


def test_frozen_coverage_object_record_schema():
    assert [field.name for field in fields(CoverageObjectRecordV1)] == [
        "object_id",
        "object_type",
        "producer",
        "owning_authority",
        "source_document_id",
        "revision_id",
        "source_sha256",
        "source_pages",
        "evidence_ids",
        "geometry_ids",
        "parent_host_ids",
        "quantity_ids",
        "takeoff_row_ids",
        "coverage_state",
        "reason_codes",
        "quantity_contribution",
        "unit",
        "provenance",
        "coverage_basis",
        "expected_family_completeness",
    ]


def test_positive_exact_join_without_editable_registration_is_accounted():
    summary = build()
    record = record_for(summary)
    assert record.coverage_state == COVERAGE_ACCOUNTED
    assert record.quantity_ids == ("q-1",)
    assert record.takeoff_row_ids == ("q-1",)
    assert record.quantity_contribution["q-1"] == 10.0
    assert record.coverage_basis == COVERAGE_BASIS_EXPLICIT_DEPENDENCIES_ONLY
    assert record.expected_family_completeness == EXPECTED_FAMILY_COMPLETENESS_UNKNOWN
    assert summary.quantity_ids_by_census_state[CENSUS_LINKED] == ("q-1",)


def test_zero_dependencies_can_never_be_accounted():
    summary = build(
        qes=[],
        rows=[],
        qe_snaps=[qe_snapshot(())],
        row_snaps=[row_snapshot(())],
    )
    record = record_for(summary)
    assert record.coverage_state == COVERAGE_UNACCOUNTED
    assert "no_explicit_object_quantity_relationship" in record.reason_codes


def test_abstention_only_is_abstained_without_numeric_row():
    summary = build(
        qes=[quantity(abstained=True)],
        rows=[],
        qe_snaps=[qe_snapshot(("q-1",))],
        row_snaps=[row_snapshot(())],
    )
    record = record_for(summary)
    assert record.coverage_state == COVERAGE_ABSTAINED
    assert record.quantity_contribution["q-1"] is None
    assert summary.quantity_ids_by_census_state[CENSUS_LINKED] == ("q-1",)


def test_resolved_plus_dangling_dependency_is_partial():
    q1 = quantity("q-1")
    q2 = quantity("q-2")
    summary = build(
        qes=[q1, q2],
        rows=[row("q-1")],
        qe_snaps=[qe_snapshot(("q-1", "q-2"))],
        row_snaps=[row_snapshot(("q-1",))],
    )
    record = record_for(summary)
    assert record.coverage_state == COVERAGE_PARTIAL
    assert any("takeoff_row_missing:q-2" == reason for reason in record.reason_codes)
    assert summary.quantity_ids_by_census_state[CENSUS_DANGLING] == ("q-2",)


def test_editable_dangling_quantity_id_is_visible_and_partial():
    summary = build(
        qes=[],
        rows=[],
        qe_snaps=[qe_snapshot(())],
        row_snaps=[row_snapshot(())],
        editables=[editable(deps=("q-dangling",))],
    )
    record = record_for(summary)
    assert record.coverage_state == COVERAGE_PARTIAL
    assert record.quantity_ids == ("q-dangling",)
    assert summary.quantity_ids_by_census_state[CENSUS_DANGLING] == ("q-dangling",)


def test_stale_revision_is_partial_and_conflicting_lineage_census():
    summary = build(
        editables=[editable(revision_hash="new-rev")],
        rows=[row(revision_hash="old-rev")],
    )
    record = record_for(summary)
    assert record.coverage_state == COVERAGE_PARTIAL
    assert any(reason.startswith("takeoff_row_revision_stale:") for reason in record.reason_codes)
    assert summary.quantity_ids_by_census_state[CENSUS_CONFLICTING_LINEAGE] == ("q-1",)


def test_geometry_conflict_is_partial_and_never_repaired_by_proximity():
    summary = build(rows=[row(geometry_ref="near-but-not-exact")])
    record = record_for(summary)
    assert record.coverage_state == COVERAGE_PARTIAL
    assert any(reason.startswith("takeoff_row_geometry_lineage_conflict:") for reason in record.reason_codes)
    assert summary.quantity_ids_by_census_state[CENSUS_CONFLICTING_LINEAGE] == ("q-1",)


def test_duplicate_quantity_id_fails_closed_as_conflicting():
    duplicate = quantity("q-1", value=11.0)
    summary = build(
        qes=[quantity("q-1"), duplicate],
        qe_snaps=[qe_snapshot(("q-1",))],
    )
    record = record_for(summary)
    assert record.coverage_state == COVERAGE_PARTIAL
    assert any(reason.startswith("duplicate_or_conflicting_quantity_evidence_id:") for reason in record.reason_codes)
    assert summary.quantity_ids_by_census_state[CENSUS_CONFLICTING_LINEAGE] == ("q-1",)


def test_missing_expected_object_producer_is_not_enumerated_not_zero():
    m = manifest()
    summary = build(
        m=m,
        qes=[],
        rows=[],
        object_snaps=[],
        qe_snaps=[qe_snapshot(())],
        row_snaps=[row_snapshot(())],
    )
    assert summary.object_records == ()
    assert summary.object_universe_snapshots[0].enumeration_status == ENUMERATION_NOT_ENUMERATED
    assert not summary.object_universe_complete
    assert "object_universe_not_complete" in summary.reason_codes


def test_missing_expected_quantity_evidence_universe_is_nonconclusive():
    summary = build(
        qes=[],
        rows=[],
        qe_snaps=[],
        row_snaps=[row_snapshot(())],
    )
    assert summary.quantity_evidence_universe_snapshots[0].enumeration_status == ENUMERATION_NOT_ENUMERATED
    assert not summary.quantity_census_conclusive
    assert "quantity_census_not_conclusive" in summary.reason_codes


def test_missing_expected_takeoff_row_universe_is_nonconclusive():
    summary = build(
        qes=[],
        rows=[],
        qe_snaps=[qe_snapshot(())],
        row_snaps=[],
    )
    assert summary.takeoff_output_row_universe_snapshots[0].enumeration_status == ENUMERATION_NOT_ENUMERATED
    assert not summary.quantity_census_conclusive
    assert "quantity_census_not_conclusive" in summary.reason_codes


def test_incomplete_quantity_universe_cannot_produce_conclusive_zero():
    summary = build(
        qes=[],
        rows=[],
        qe_snaps=[
            qe_snapshot(
                (),
                status=ENUMERATION_INCOMPLETE,
                reasons=("producer_scope_incomplete",),
            )
        ],
        row_snaps=[row_snapshot(())],
    )
    assert summary.quantity_counts_by_census_state[CENSUS_ORPHAN_UNBOUND] == 0
    assert not summary.quantity_census_conclusive
    assert summary.quantity_evidence_universe_snapshots[0].reason_codes == (
        "producer_scope_incomplete",
    )


def test_unexpected_universe_key_fails_run_closed():
    bad = object_snapshot(producer="unexpected", category="wall")
    with pytest.raises(CoverageRegistryContractError, match="unexpected_universe_key"):
        build(object_snaps=[bad])


@pytest.mark.parametrize(
    "field,value",
    [
        ("document", "doc-other"),
        ("sha", "b" * 64),
        ("revision", "rev-other"),
        ("run", "run-other"),
        ("snapshot", "snap-other"),
    ],
)
def test_run_lineage_conflicts_fail_closed(field, value):
    kwargs = {field: value}
    bad = object_snapshot(**kwargs)
    with pytest.raises(CoverageRegistryContractError, match="coverage_registry_run_lineage_conflict"):
        build(object_snaps=[bad])


def test_input_order_invariance():
    m = manifest()
    object_snap = object_snapshot(("wall-2", "wall-1"))
    q1 = quantity("q-1", ("wall-1",), value=10.0)
    q2 = quantity("q-2", ("wall-2",), value=20.0)
    rows = [row("q-1", geometry_ref="wall-1", value=10.0), row("q-2", geometry_ref="wall-2", value=20.0)]
    first = build(
        m=m,
        qes=[q1, q2],
        rows=rows,
        object_snaps=[object_snap],
        qe_snaps=[qe_snapshot(("q-1", "q-2"))],
        row_snaps=[row_snapshot(("q-1", "q-2"))],
    )
    second = build(
        m=m,
        qes=[q2, q1],
        rows=list(reversed(rows)),
        object_snaps=[object_snapshot(("wall-1", "wall-2"))],
        qe_snaps=[qe_snapshot(("q-2", "q-1"))],
        row_snaps=[row_snapshot(("q-2", "q-1"))],
    )
    assert first.to_dict() == second.to_dict()


def test_registry_does_not_mutate_inputs():
    q = quantity()
    r = row()
    e = editable(deps=("q-1",))
    metadata = {"wall-1": {"geometry_ids": ["geom-wall-1"], "provenance": {"label": "W1"}}}
    q_before = q.to_dict()
    r_before = r.to_dict()
    e_before = e.to_dict()
    metadata_before = copy.deepcopy(metadata)
    build(qes=[q], rows=[r], editables=[e], metadata=metadata)
    assert q.to_dict() == q_before
    assert r.to_dict() == r_before
    assert e.to_dict() == e_before
    assert metadata == metadata_before


def test_evidence_only_metadata_not_in_admitted_snapshot_cannot_mint_object():
    summary = build(
        qes=[],
        rows=[],
        object_snaps=[object_snapshot(("wall-1",))],
        qe_snaps=[qe_snapshot(())],
        row_snaps=[row_snapshot(())],
        metadata={"evidence-only": {"no_instance_creation": True, "object_type": "observation"}},
    )
    assert tuple(record.object_id for record in summary.object_records) == ("wall-1",)


def test_admitted_evidence_only_record_fails_closed():
    with pytest.raises(CoverageRegistryContractError, match="evidence_only_object_cannot_be_admitted"):
        build(
            qes=[],
            rows=[],
            qe_snaps=[qe_snapshot(())],
            row_snaps=[row_snapshot(())],
            metadata={"wall-1": {"no_instance_creation": True}},
        )


@pytest.mark.parametrize(
    "metadata,row_kwargs",
    [
        ({"wall-1": {"label": "SAME"}}, {}),
        ({"wall-1": {"reported_value": 10.0}}, {}),
        ({"wall-1": {"source_pages": [1]}}, {}),
    ],
)
def test_label_value_or_page_coincidence_cannot_create_object_quantity_link(metadata, row_kwargs):
    orphan_q = quantity("q-1", object_ids=(), value=10.0, metadata={"label": "SAME", "source_page": 1})
    summary = build(
        qes=[orphan_q],
        rows=[row("q-1", geometry_ref=None, **row_kwargs)],
        metadata=metadata,
    )
    record = record_for(summary)
    assert record.coverage_state == COVERAGE_UNACCOUNTED
    assert summary.quantity_ids_by_census_state[CENSUS_ORPHAN_UNBOUND] == ("q-1",)


def test_nearest_or_nonexact_geometry_cannot_create_link():
    orphan_q = quantity("q-1", object_ids=())
    summary = build(
        qes=[orphan_q],
        rows=[row("q-1", geometry_ref="geometry-near-wall-1")],
        metadata={"wall-1": {"geometry_ids": ["geometry-wall-1"]}},
    )
    assert record_for(summary).coverage_state == COVERAGE_UNACCOUNTED
    assert summary.quantity_ids_by_census_state[CENSUS_ORPHAN_UNBOUND] == ("q-1",)


def test_roof_covering_quantity_without_input_entity_ids_remains_orphan_unbound():
    roof = QuantityEvidence(
        quantity_id="roof-q",
        family="roof_covering",
        semantic_key="roof_covering",
        value=25.0,
        unit="SM",
        input_entity_ids=(),
        evidence_ids=("roof-ev",),
        authority="source_native_elevation_vector_pitch",
        status="corroborated",
        confidence=0.85,
    )
    summary = build(
        qes=[roof],
        rows=[row("roof-q", geometry_ref=None, value=25.0)],
        qe_snaps=[qe_snapshot(("roof-q",))],
        row_snaps=[row_snapshot(("roof-q",))],
    )
    assert record_for(summary).coverage_state == COVERAGE_UNACCOUNTED
    assert summary.quantity_ids_by_census_state[CENSUS_ORPHAN_UNBOUND] == ("roof-q",)


def test_structural_member_without_generic_quantity_link_is_unaccounted():
    m = manifest(object_keys=(("structural_member", "column"),))
    snap = object_snapshot(
        ("member-1",),
        producer="structural_member",
        category="column",
        authority="StructuralMemberAuthority",
    )
    summary = build(
        m=m,
        qes=[],
        rows=[],
        object_snaps=[snap],
        qe_snaps=[qe_snapshot(())],
        row_snaps=[row_snapshot(())],
        metadata={"member-1": {"object_type": "column", "evidence_ids": ["ev-member"]}},
    )
    assert record_for(summary, "member-1").coverage_state == COVERAGE_UNACCOUNTED


def test_supplied_record_not_declared_by_universe_snapshot_is_rejected():
    with pytest.raises(CoverageRegistryContractError, match="record_not_in_enumeration_snapshot"):
        build(
            qes=[quantity("q-extra")],
            qe_snaps=[qe_snapshot(("q-1",))],
            rows=[],
            row_snaps=[row_snapshot(())],
        )


def test_missing_declared_quantity_record_is_dangling_when_object_depends_on_it():
    summary = build(
        qes=[],
        rows=[],
        qe_snaps=[qe_snapshot(("q-missing",))],
        row_snaps=[row_snapshot(("q-missing",))],
        editables=[editable(deps=("q-missing",))],
    )
    assert record_for(summary).coverage_state == COVERAGE_PARTIAL
    assert summary.quantity_ids_by_census_state[CENSUS_DANGLING] == ("q-missing",)


def test_object_metadata_lineage_conflict_is_rejected():
    with pytest.raises(CoverageRegistryContractError, match="admitted_object_metadata_lineage_conflict"):
        build(metadata={"wall-1": {"source_sha256": "b" * 64}})


def test_summary_maps_are_read_only():
    summary = build()
    with pytest.raises(TypeError):
        summary.object_counts_by_coverage_state[COVERAGE_ACCOUNTED] = 99


def test_quantity_evidence_universe_lineage_conflict_fails_closed():
    bad_qe_snapshot = qe_snapshot((), sha="b" * 64)
    with pytest.raises(CoverageRegistryContractError, match="coverage_registry_run_lineage_conflict"):
        build(
            qes=[],
            rows=[],
            qe_snaps=[bad_qe_snapshot],
            row_snaps=[row_snapshot(())],
        )


def test_takeoff_row_universe_lineage_conflict_fails_closed():
    bad_row_snapshot = row_snapshot((), revision="rev-other")
    with pytest.raises(CoverageRegistryContractError, match="coverage_registry_run_lineage_conflict"):
        build(
            qes=[],
            rows=[],
            qe_snaps=[qe_snapshot(())],
            row_snaps=[bad_row_snapshot],
        )


def test_duplicate_takeoff_row_quantity_id_fails_closed_as_conflicting():
    summary = build(
        rows=[row("q-1", value=10.0), row("q-1", value=11.0)],
        row_snaps=[row_snapshot(("q-1",))],
    )
    record = record_for(summary)
    assert record.coverage_state == COVERAGE_PARTIAL
    assert any(
        reason.startswith("duplicate_or_conflicting_takeoff_row_quantity_id:")
        for reason in record.reason_codes
    )
    assert summary.quantity_ids_by_census_state[CENSUS_CONFLICTING_LINEAGE] == ("q-1",)


def test_conflicting_exact_object_links_are_conflicting_lineage_in_reverse_census():
    m = manifest(object_keys=(("physical_wall", "wall"),))
    snap = object_snapshot(("wall-1", "wall-2"))
    q = quantity("q-1", object_ids=("wall-1",))
    summary = build(
        m=m,
        qes=[q],
        rows=[row("q-1", geometry_ref="wall-1")],
        object_snaps=[snap],
        qe_snaps=[qe_snapshot(("q-1",))],
        row_snaps=[row_snapshot(("q-1",))],
        editables=[editable("wall-2", deps=("q-1",), geometry_ref="wall-2", original_geometry_ref="wall-2")],
    )
    assert record_for(summary, "wall-2").coverage_state == COVERAGE_PARTIAL
    assert summary.quantity_ids_by_census_state[CENSUS_CONFLICTING_LINEAGE] == ("q-1",)
    assert summary.quantity_ids_by_census_state[CENSUS_LINKED] == ()


def test_abstained_dependency_with_clean_downstream_row_is_partial_not_pure_abstained():
    summary = build(
        qes=[quantity(abstained=True)],
        rows=[row("q-1", geometry_ref="wall-1")],
        qe_snaps=[qe_snapshot(("q-1",))],
        row_snaps=[row_snapshot(("q-1",))],
    )
    record = record_for(summary)
    assert record.coverage_state == COVERAGE_PARTIAL
    assert "quantity_abstained:q-1" in record.reason_codes


def test_conflicting_exact_object_link_poison_applies_to_all_linked_object_records():
    m = manifest(object_keys=(("physical_wall", "wall"),))
    snap = object_snapshot(("wall-1", "wall-2"))
    q = quantity("q-1", object_ids=("wall-1",))
    summary = build(
        m=m,
        qes=[q],
        rows=[row("q-1", geometry_ref="wall-1")],
        object_snaps=[snap],
        qe_snaps=[qe_snapshot(("q-1",))],
        row_snaps=[row_snapshot(("q-1",))],
        editables=[editable("wall-2", deps=("q-1",), geometry_ref="wall-2", original_geometry_ref="wall-2")],
    )
    assert record_for(summary, "wall-1").coverage_state == COVERAGE_PARTIAL
    assert record_for(summary, "wall-2").coverage_state == COVERAGE_PARTIAL
    assert "quantity_evidence_object_link_conflict:q-1" in record_for(summary, "wall-1").reason_codes
    assert summary.quantity_ids_by_census_state[CENSUS_CONFLICTING_LINEAGE] == ("q-1",)


def test_frozen_record_allows_any_finite_numeric_quantity_contribution():
    record = CoverageObjectRecordV1(
        object_id="obj-1",
        object_type="wall",
        producer="producer",
        owning_authority="authority",
        source_document_id="doc-1",
        revision_id="rev-1",
        source_sha256=SHA,
        source_pages=(),
        evidence_ids=(),
        geometry_ids=(),
        parent_host_ids=(),
        quantity_ids=("q-adjustment",),
        takeoff_row_ids=(),
        coverage_state=COVERAGE_PARTIAL,
        reason_codes=("synthetic_contract_probe",),
        quantity_contribution={"q-adjustment": -1.0},
        unit={"q-adjustment": "M"},
        provenance={},
    )
    assert record.quantity_contribution["q-adjustment"] == -1.0


def test_incomplete_object_universe_makes_reverse_census_nonconclusive():
    summary = build(
        qes=[],
        rows=[],
        object_snaps=[],
        qe_snaps=[qe_snapshot(())],
        row_snaps=[row_snapshot(())],
    )
    assert not summary.object_universe_complete
    assert not summary.quantity_census_conclusive
    assert "quantity_census_not_conclusive" in summary.reason_codes
