from __future__ import annotations

import copy
from pathlib import Path

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_structural_member_authority import (
    STRUCTURAL_MEMBER_SCOPE_INCOMPLETE,
    PhysicalStructuralMember,
    StructuralMemberResolution,
    StructuralMemberSelector,
)
from pb_structural_member_quantity import (
    STRUCTURAL_MEMBER_COUNT_FAMILY,
    STRUCTURAL_MEMBER_COUNT_FORMULA,
    STRUCTURAL_MEMBER_COUNT_NOT_CORROBORATED,
    build_structural_member_count_quantity,
)
from pb_takeoff_coverage_registry import (
    CENSUS_DANGLING,
    COVERAGE_PARTIAL,
    ENUMERATION_COMPLETE,
    CoverageRegistryRunManifestV1,
    ProducerObjectUniverseSnapshotV1,
    QuantityEvidenceUniverseSnapshotV1,
    TakeoffOutputRowUniverseSnapshotV1,
    build_coverage_registry_v1,
)


SHA = "a" * 64


def selector(kind="pier", scope="scope-1"):
    return StructuralMemberSelector(
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256=SHA,
        snapshot_id="snap-1",
        decision_scope_id=scope,
        member_kind=kind,
    )


def member(mid, *, evidence=("ev-1",), observation=("obs-1",), page=("1",), view=("plan-1",)):
    return PhysicalStructuralMember(
        physical_member_id=mid,
        member_kind="pier",
        observation_ids=tuple(observation),
        source_evidence_ids=tuple(evidence),
        source_primitive_ids=(f"prim-{mid}",),
        page_ids=tuple(page),
        view_ids=tuple(view),
        definition_ids=(),
    )


def resolution(
    *,
    members=(None,),
    status=EvidenceResolutionStatus.CORROBORATED,
    reasons=("structural_member_scope_resolved",),
):
    if members == (None,):
        members = (
            member("member-2", evidence=("ev-2",), observation=("obs-2",)),
            member("member-1", evidence=("ev-1", "ev-shared"), observation=("obs-1",)),
        )
    return StructuralMemberResolution(
        status=status,
        reason_codes=tuple(reasons),
        selector=selector(),
        members=tuple(members),
        definitions=(),
        unresolved_observation_ids=(),
    )


def test_corroborated_resolution_emits_exact_aggregate_quantity_link():
    qty = build_structural_member_count_quantity(resolution())
    assert qty.family == STRUCTURAL_MEMBER_COUNT_FAMILY
    assert qty.semantic_key == "structural_member_count:pier:scope-1"
    assert qty.value == 2.0
    assert qty.unit == "NO"
    assert qty.input_entity_ids == ("member-1", "member-2")
    assert qty.formula == STRUCTURAL_MEMBER_COUNT_FORMULA
    assert qty.evidence_ids == ("ev-1", "ev-2", "ev-shared")
    assert qty.authority == "model_derived"
    assert qty.status == "firm"
    assert qty.confidence == 1.0
    assert not qty.abstained
    assert qty.metadata["physical_member_ids"] == ["member-1", "member-2"]
    assert qty.metadata["document_id"] == "doc-1"
    assert qty.metadata["revision_id"] == "rev-1"
    assert qty.metadata["source_sha256"] == SHA
    assert qty.metadata["snapshot_id"] == "snap-1"


def test_quantity_id_and_payload_are_input_order_invariant():
    left = resolution(
        members=(
            member("member-1", evidence=("ev-b", "ev-a")),
            member("member-2", evidence=("ev-c",)),
        )
    )
    right = resolution(
        members=(
            member("member-2", evidence=("ev-c",)),
            member("member-1", evidence=("ev-a", "ev-b")),
        )
    )
    a = build_structural_member_count_quantity(left)
    b = build_structural_member_count_quantity(right)
    assert a.quantity_id == b.quantity_id
    assert a.input_entity_ids == b.input_entity_ids
    assert a.evidence_ids == b.evidence_ids
    assert a.to_dict() == b.to_dict()


@pytest.mark.parametrize(
    "status,reasons",
    [
        (EvidenceResolutionStatus.ABSTAINED, (STRUCTURAL_MEMBER_SCOPE_INCOMPLETE,)),
        (EvidenceResolutionStatus.CONFLICT, ("structural_member_count_conflict",)),
        (EvidenceResolutionStatus.CANDIDATE, ("structural_member_registration_incomplete",)),
    ],
)
def test_non_corroborated_resolution_emits_typed_abstention(status, reasons):
    qty = build_structural_member_count_quantity(
        resolution(members=(), status=status, reasons=reasons)
    )
    assert qty.abstained
    assert qty.value is None
    assert qty.input_entity_ids == ()
    assert qty.status == "blocked"
    assert STRUCTURAL_MEMBER_COUNT_NOT_CORROBORATED in qty.blocking_reasons
    assert set(reasons) <= set(qty.blocking_reasons)
    assert qty.metadata["physical_member_ids"] == []


def test_corroborated_resolution_without_physical_ids_fails_closed():
    bad = PhysicalStructuralMember(
        physical_member_id="",
        member_kind="pier",
        observation_ids=("obs-1",),
        source_evidence_ids=("ev-1",),
        source_primitive_ids=("p1",),
        page_ids=("1",),
        view_ids=("v1",),
        definition_ids=(),
    )
    qty = build_structural_member_count_quantity(resolution(members=(bad,)))
    assert qty.abstained
    assert qty.value is None
    assert qty.input_entity_ids == ()
    assert "structural_member_physical_identity_invalid" in qty.blocking_reasons


def test_quantity_projection_does_not_mutate_resolution():
    source = resolution()
    before = copy.deepcopy(source)
    build_structural_member_count_quantity(source)
    assert source == before


def test_registry_gets_exact_structural_object_links_but_stays_partial_without_row():
    source = resolution()
    qty = build_structural_member_count_quantity(source)
    manifest = CoverageRegistryRunManifestV1(
        source_document_id="doc-1",
        revision_id="rev-1",
        source_sha256=SHA,
        registry_run_id="run-1",
        snapshot_id="snap-1",
        expected_object_universe_keys=(("structural_member", "pier"),),
        expected_quantity_evidence_universe_keys=(("structural_member_quantity", "shadow"),),
        expected_takeoff_row_universe_keys=(("takeoff_rows", "shadow"),),
    )
    objects = ProducerObjectUniverseSnapshotV1(
        producer="structural_member",
        owning_authority="StructuralMemberAuthority",
        category="pier",
        source_document_id="doc-1",
        revision_id="rev-1",
        source_sha256=SHA,
        registry_run_id="run-1",
        snapshot_id="snap-1",
        admitted_object_ids=qty.input_entity_ids,
        enumeration_status=ENUMERATION_COMPLETE,
    )
    qes = QuantityEvidenceUniverseSnapshotV1(
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
    rows = TakeoffOutputRowUniverseSnapshotV1(
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
        object_universe_snapshots=(objects,),
        quantity_evidence_universe_snapshots=(qes,),
        takeoff_output_row_universe_snapshots=(rows,),
        quantity_evidence_by_universe={
            ("structural_member_quantity", "shadow"): (qty,)
        },
        takeoff_rows_by_universe={("takeoff_rows", "shadow"): ()},
        object_metadata_by_id={
            member_id: {"object_type": "pier", "evidence_ids": ["source"]}
            for member_id in qty.input_entity_ids
        },
    )
    assert tuple(record.object_id for record in summary.object_records) == (
        "member-1",
        "member-2",
    )
    assert all(record.coverage_state == COVERAGE_PARTIAL for record in summary.object_records)
    assert all(record.quantity_ids == (qty.quantity_id,) for record in summary.object_records)
    assert summary.quantity_ids_by_census_state[CENSUS_DANGLING] == (qty.quantity_id,)


def test_same_numeric_text_or_schedule_count_is_not_an_input_to_quantity_builder():
    source = resolution()
    qty = build_structural_member_count_quantity(source)
    # There is deliberately no count/text/schedule argument. The authoritative
    # value is exactly the published physical-member set.
    assert qty.value == float(len(source.members))
    assert qty.value == 2.0


def test_module_is_shadow_only_no_live_non_test_importers():
    root = Path(__file__).resolve().parents[1]
    offenders = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root)
        if rel.parts and rel.parts[0] == "tests":
            continue
        if path.name == "pb_structural_member_quantity.py":
            continue
        text = path.read_text(encoding="utf-8-sig")
        if "pb_structural_member_quantity" in text or "build_structural_member_count_quantity" in text:
            offenders.append(str(rel))
    assert offenders == []


def test_duplicate_physical_member_ids_fail_closed():
    dup = resolution(
        members=(
            member("member-1", observation=("obs-1",)),
            member("member-1", observation=("obs-2",)),
        )
    )
    qty = build_structural_member_count_quantity(dup)
    assert qty.abstained
    assert qty.value is None
    assert qty.input_entity_ids == ()
    assert "structural_member_physical_identity_invalid" in qty.blocking_reasons


def test_member_kind_mismatch_fails_closed():
    wrong = PhysicalStructuralMember(
        physical_member_id="member-1",
        member_kind="column",
        observation_ids=("obs-1",),
        source_evidence_ids=("ev-1",),
        source_primitive_ids=("p1",),
        page_ids=("1",),
        view_ids=("v1",),
        definition_ids=(),
    )
    qty = build_structural_member_count_quantity(resolution(members=(wrong,)))
    assert qty.abstained
    assert qty.value is None
    assert qty.input_entity_ids == ()


def test_live_secondary_support_authority_projects_exact_physical_ids_into_quantity():
    from pb_secondary_area_support_evidence import SecondaryAreaSupportEvidence
    from pb_secondary_support_structural_member_adapter import (
        build_secondary_support_structural_member_authority,
    )

    source = SecondaryAreaSupportEvidence(
        zone_type="verandah",
        support_kind="pillar",
        support_count=4,
        bay_count=3,
        bay_spans_m=(3.3, 3.4, 3.3),
        source_pages=(54,),
        chain_ids=("chain-a",),
        zone_bbox=(0.0, 0.0, 10.0, 10.0),
        support_bbox=(0.0, 10.0, 10.0, 12.0),
        zone_text="VERANDAH",
        support_text="",
        support_symbol_ids=("g1", "g2", "g3", "g4"),
        evidence_mode="physical_symbol",
        confidence=0.97,
    )
    authority_result = build_secondary_support_structural_member_authority(
        evidence=source,
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256=SHA,
        snapshot_id="snap-1",
        decision_scope_id="secondary:verandah",
        view_id="plan-54",
        view_complete=True,
    ).resolution
    assert authority_result.status is EvidenceResolutionStatus.CORROBORATED

    qty = build_structural_member_count_quantity(authority_result)
    physical_ids = tuple(sorted(m.physical_member_id for m in authority_result.members))
    assert qty.value == 4.0
    assert qty.input_entity_ids == physical_ids
    assert len(qty.input_entity_ids) == 4
    assert qty.metadata["member_kind"] == "pillar"
    assert qty.metadata["decision_scope_id"] == "secondary:verandah"


def test_invalid_selector_lineage_abstains_even_if_resolution_claims_corroborated():
    bad_selector = StructuralMemberSelector(
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256="not-a-sha",
        snapshot_id="snap-1",
        decision_scope_id="scope-1",
        member_kind="pier",
    )
    bad = StructuralMemberResolution(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("structural_member_scope_resolved",),
        selector=bad_selector,
        members=(member("member-1"),),
        definitions=(),
        unresolved_observation_ids=(),
    )
    qty = build_structural_member_count_quantity(bad)
    assert qty.abstained
    assert qty.value is None
    assert qty.input_entity_ids == ()
    assert "structural_member_selector_lineage_invalid" in qty.blocking_reasons


def test_invalid_resolution_status_abstains_instead_of_raising():
    bad = StructuralMemberResolution(
        status="corroborated",  # type: ignore[arg-type]
        reason_codes=(),
        selector=selector(),
        members=(member("member-1"),),
        definitions=(),
        unresolved_observation_ids=(),
    )
    qty = build_structural_member_count_quantity(bad)
    assert qty.abstained
    assert qty.value is None
    assert qty.input_entity_ids == ()
    assert "structural_member_resolution_status_invalid" in qty.blocking_reasons
