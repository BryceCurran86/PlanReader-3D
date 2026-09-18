"""Tests for Source-Derived Opening Universe Completeness and Count Authority (Item 23 / F.24)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple
import pytest

from pb_generic_opening_count_authority import (
    GENERIC_OPENING_COUNT_COMPLETENESS_NOT_SOURCE_AUTHENTICATED,
    GENERIC_OPENING_COUNT_RESOLVED,
    GENERIC_OPENING_COUNT_SCHEDULE_MISMATCH,
    GenericOpeningCountProducer,
    GenericOpeningCountSelector,
    _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL,
)
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_opening_universe_completeness_authority import (
    OpeningUniverseCompletenessAuthority,
    OpeningUniverseCompletenessRecord,
    SourceOpeningUniverseCompletenessProducer,
    _AUTHORITY_SEAL as UNIV_SEAL,
    build_opening_universe_member_from_indexed_primitive,
)
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    STRUCTURAL_OPENING_EXISTENCE_RESOLVED,
    PhysicalOpeningAuthority,
    PhysicalOpeningExistenceRecord,
    PhysicalOpeningProducer,
)
from pb_schedule_opening_instance_binding_authority import (
    BINDING_RESOLVED,
    ScheduleOpeningInstanceBindingAuthority,
    ScheduleOpeningInstanceBindingRecord,
    ScheduleOpeningInstanceBindingResult,
    _AUTHORITY_SEAL as BIND_SEAL,
    _record_key as _binding_record_key,
)
from pb_schedule_row_quantity_authority import (
    ScheduleRowQuantityProducer,
    ScheduleRowQuantitySelector,
)
from pb_source_observation_authority import (
    ObservationSelector,
    SourceDecodeCoverageRecord,
    SourceObservationProducer,
)
from pb_viewport_view_class_authority import (
    VIEW_KIND_FLOOR_PLAN,
    ViewportViewClassProducer,
    ViewportViewClassSelector,
)

DOC = "doc_test"
REV = "rev1"
SHA = "a" * 64
SNAP = "snap_test"
PAGE = "page_1"
SCOPE = "scope_plan_1"
VP = "viewport_p1_0"


@dataclass
class _Shim:
    primitive_id: str
    page_id: str
    geometry: Tuple[float, float, float, float]
    layer: str = "openings"
    clip_known: bool = True
    clip_present: bool = False
    clip: Optional[Tuple[float, float, float, float]] = None


def _make_physical(rec_id: str, obs_id: str) -> PhysicalOpeningExistenceRecord:
    return PhysicalOpeningExistenceRecord(
        record_id=rec_id,
        source_observation_ids=(obs_id,),
        source_lineage_root_ids=(f"root_{obs_id}",),
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        viewport_id=VP,
        semantic_class="opening",
        status=EvidenceResolutionStatus.CORROBORATED,
        proposition=PHYSICAL_OPENING_EXISTS,
        structural_pattern="door_swing_arc",
        diagnostic_confidence=1.0,
        blocking_reasons=(),
        structural_reason_codes=(STRUCTURAL_OPENING_EXISTENCE_RESOLVED,),
        producer_method="test",
        producer_version="1.0",
        producer_generation=1,
    )


def test_public_unsealed_completeness_is_rejected():
    record = OpeningUniverseCompletenessRecord(
        record_id="rec_u1",
        decision_scope_id=SCOPE,
        decision_scope_kind="floor_plan",
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_ids=(PAGE,),
        viewport_id=VP,
        enumeration_state="complete",
        source_decode_complete=True,
        semantic_enumeration_complete=True,
        decision_scope_complete=True,
        accounted_member_ids=(),
        universe_fingerprint="fp-1",
        reason_codes=(),
    )
    unsealed_auth = OpeningUniverseCompletenessAuthority({(DOC, REV, SHA, SNAP, SCOPE): record}, _seal=UNIV_SEAL)
    assert getattr(unsealed_auth, "_source_authentication_seal", None) is None

    src_auth = SourceObservationProducer(producer_method="test", producer_version="1.0").authority()
    phys_auth = PhysicalOpeningAuthority(src_auth)
    vp_producer = ViewportViewClassProducer.create()
    vp_producer.publish(ViewportViewClassSelector(DOC, REV, SHA, SNAP, VP), view_kind=VIEW_KIND_FLOOR_PLAN, evidence_observation_ids=("obs_vp",))
    vp_auth = vp_producer.authority()

    producer = GenericOpeningCountProducer.from_authorities(
        opening_universe_authority=unsealed_auth,
        physical_opening_authority=phys_auth,
        viewport_view_class_authority=vp_auth,
    )
    res = producer.publish(GenericOpeningCountSelector(DOC, REV, SHA, SNAP, SCOPE, opening_mark="D1"))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert GENERIC_OPENING_COUNT_COMPLETENESS_NOT_SOURCE_AUTHENTICATED in res.reason_codes


def test_source_authenticated_producer_attaches_seal_and_resolves_count():
    src_auth = SourceObservationProducer(producer_method="test", producer_version="1.0").authority()
    shim1 = _Shim("door_1", PAGE, (10.0, 10.0, 50.0, 50.0))
    shim2 = _Shim("door_2", PAGE, (60.0, 10.0, 100.0, 50.0))
    mem1 = build_opening_universe_member_from_indexed_primitive(shim1)
    mem2 = build_opening_universe_member_from_indexed_primitive(shim2)

    p_rec1 = _make_physical("phys_1", "obs_1")
    p_rec2 = _make_physical("phys_2", "obs_2")

    phys_producer = PhysicalOpeningProducer(src_auth)
    phys_producer.publish_physical_opening(p_rec1, member_id=mem1.member_id)
    phys_producer.publish_physical_opening(p_rec2, member_id=mem2.member_id)
    phys_auth = phys_producer.authority()

    vp_producer = ViewportViewClassProducer.create()
    vp_producer.publish(ViewportViewClassSelector(DOC, REV, SHA, SNAP, VP), view_kind=VIEW_KIND_FLOOR_PLAN, evidence_observation_ids=("obs_vp",))
    vp_auth = vp_producer.authority()

    coverage = SourceDecodeCoverageRecord(document_id=DOC, revision_id=REV, total_pages=1, decoded_pages=(0,), failed_pages=(), state="complete")
    univ_producer = SourceOpeningUniverseCompletenessProducer(producer_method="test", producer_version="1.0")
    univ_producer.publish_source_scope(
        decision_scope_id=SCOPE, decision_scope_kind="floor_plan",
        document_id=DOC, revision_id=REV, source_sha256=SHA, snapshot_id=SNAP,
        page_ids=(PAGE,), coverage=coverage, source_primitives=[shim1, shim2],
    )
    univ_auth = univ_producer.authority()
    assert getattr(univ_auth, "_source_authentication_seal", None) is _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL

    # Bind to D1
    bind_results = {}
    for p_rec in (p_rec1, p_rec2):
        b_key = _binding_record_key(DOC, REV, SHA, SNAP, SCOPE, p_rec.record_id)
        b_payload = {
            "document_id": DOC, "revision_id": REV, "source_sha256": SHA, "snapshot_id": SNAP,
            "page_id": PAGE, "decision_scope_id": SCOPE, "opening_record_id": p_rec.record_id,
            "tag_observation_id": p_rec.source_observation_ids[0], "tag_mark": "D1",
            "schedule_page_id": PAGE, "schedule_row_observation_ids": ("obs_sched_D1",),
            "schedule_row_type_mark": "D1", "schedule_row_width_mm": None, "schedule_row_height_mm": None,
        }
        b_rec = ScheduleOpeningInstanceBindingRecord(
            record_id=stable_contract_id("schedule_opening_instance_binding", b_payload, digest_chars=32),
            **b_payload
        )
        bind_results[b_key] = ScheduleOpeningInstanceBindingResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(BINDING_RESOLVED,),
            record=b_rec,
        )
    bind_auth = ScheduleOpeningInstanceBindingAuthority(bind_results, _seal=BIND_SEAL)

    producer = GenericOpeningCountProducer.from_authorities(
        opening_universe_authority=univ_auth,
        physical_opening_authority=phys_auth,
        viewport_view_class_authority=vp_auth,
        schedule_binding_authority=bind_auth,
    )
    res = producer.publish(GenericOpeningCountSelector(DOC, REV, SHA, SNAP, SCOPE, opening_mark="D1"))
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.count == 2
    assert GENERIC_OPENING_COUNT_RESOLVED in res.reason_codes


def test_schedule_corroboration_matches_declared_count():
    src_auth = SourceObservationProducer(producer_method="test", producer_version="1.0").authority()
    shim1 = _Shim("door_1", PAGE, (10.0, 10.0, 50.0, 50.0))
    shim2 = _Shim("door_2", PAGE, (60.0, 10.0, 100.0, 50.0))
    mem1 = build_opening_universe_member_from_indexed_primitive(shim1)
    mem2 = build_opening_universe_member_from_indexed_primitive(shim2)

    p_rec1 = _make_physical("phys_1", "obs_1")
    p_rec2 = _make_physical("phys_2", "obs_2")

    phys_producer = PhysicalOpeningProducer(src_auth)
    phys_producer.publish_physical_opening(p_rec1, member_id=mem1.member_id)
    phys_producer.publish_physical_opening(p_rec2, member_id=mem2.member_id)
    phys_auth = phys_producer.authority()

    vp_producer = ViewportViewClassProducer.create()
    vp_producer.publish(ViewportViewClassSelector(DOC, REV, SHA, SNAP, VP), view_kind=VIEW_KIND_FLOOR_PLAN, evidence_observation_ids=("obs_vp",))
    vp_auth = vp_producer.authority()

    coverage = SourceDecodeCoverageRecord(document_id=DOC, revision_id=REV, total_pages=1, decoded_pages=(0,), failed_pages=(), state="complete")
    univ_producer = SourceOpeningUniverseCompletenessProducer(producer_method="test", producer_version="1.0")
    univ_producer.publish_source_scope(
        decision_scope_id=SCOPE, decision_scope_kind="floor_plan",
        document_id=DOC, revision_id=REV, source_sha256=SHA, snapshot_id=SNAP,
        page_ids=(PAGE,), coverage=coverage, source_primitives=[shim1, shim2],
    )
    univ_auth = univ_producer.authority()

    # Schedule row declares 2 NO
    sched_producer = ScheduleRowQuantityProducer.create()
    sched_obs = ("sched_row_D1_2",)
    sched_sel = ScheduleRowQuantitySelector(DOC, REV, SHA, SNAP, PAGE, sched_obs)
    sched_producer.publish(sched_sel, declared_count=2, type_mark="D1", universe_complete=True)
    sched_auth = sched_producer.authority()

    bind_results = {}
    for p_rec in (p_rec1, p_rec2):
        b_key = _binding_record_key(DOC, REV, SHA, SNAP, SCOPE, p_rec.record_id)
        b_payload = {
            "document_id": DOC, "revision_id": REV, "source_sha256": SHA, "snapshot_id": SNAP,
            "page_id": PAGE, "decision_scope_id": SCOPE, "opening_record_id": p_rec.record_id,
            "tag_observation_id": p_rec.source_observation_ids[0], "tag_mark": "D1",
            "schedule_page_id": PAGE, "schedule_row_observation_ids": sched_obs,
            "schedule_row_type_mark": "D1", "schedule_row_width_mm": None, "schedule_row_height_mm": None,
        }
        b_rec = ScheduleOpeningInstanceBindingRecord(
            record_id=stable_contract_id("schedule_opening_instance_binding", b_payload, digest_chars=32),
            **b_payload
        )
        bind_results[b_key] = ScheduleOpeningInstanceBindingResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(BINDING_RESOLVED,),
            record=b_rec,
        )
    bind_auth = ScheduleOpeningInstanceBindingAuthority(bind_results, _seal=BIND_SEAL)

    producer = GenericOpeningCountProducer.from_authorities(
        opening_universe_authority=univ_auth,
        physical_opening_authority=phys_auth,
        viewport_view_class_authority=vp_auth,
        schedule_binding_authority=bind_auth,
        schedule_row_quantity_authority=sched_auth,
    )
    res = producer.publish(GenericOpeningCountSelector(DOC, REV, SHA, SNAP, SCOPE, opening_mark="D1"))
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.count == 2
    assert res.record.schedule_corroborated is True


def test_schedule_mismatch_fails_closed():
    src_auth = SourceObservationProducer(producer_method="test", producer_version="1.0").authority()
    shim1 = _Shim("door_1", PAGE, (10.0, 10.0, 50.0, 50.0))
    shim2 = _Shim("door_2", PAGE, (60.0, 10.0, 100.0, 50.0))
    mem1 = build_opening_universe_member_from_indexed_primitive(shim1)
    mem2 = build_opening_universe_member_from_indexed_primitive(shim2)

    p_rec1 = _make_physical("phys_1", "obs_1")
    p_rec2 = _make_physical("phys_2", "obs_2")

    phys_producer = PhysicalOpeningProducer(src_auth)
    phys_producer.publish_physical_opening(p_rec1, member_id=mem1.member_id)
    phys_producer.publish_physical_opening(p_rec2, member_id=mem2.member_id)
    phys_auth = phys_producer.authority()

    vp_producer = ViewportViewClassProducer.create()
    vp_producer.publish(ViewportViewClassSelector(DOC, REV, SHA, SNAP, VP), view_kind=VIEW_KIND_FLOOR_PLAN, evidence_observation_ids=("obs_vp",))
    vp_auth = vp_producer.authority()

    coverage = SourceDecodeCoverageRecord(document_id=DOC, revision_id=REV, total_pages=1, decoded_pages=(0,), failed_pages=(), state="complete")
    univ_producer = SourceOpeningUniverseCompletenessProducer(producer_method="test", producer_version="1.0")
    univ_producer.publish_source_scope(
        decision_scope_id=SCOPE, decision_scope_kind="floor_plan",
        document_id=DOC, revision_id=REV, source_sha256=SHA, snapshot_id=SNAP,
        page_ids=(PAGE,), coverage=coverage, source_primitives=[shim1, shim2],
    )
    univ_auth = univ_producer.authority()

    # Schedule row declares 5 NO (mismatch with 2 physical doors)
    sched_producer = ScheduleRowQuantityProducer.create()
    sched_obs = ("sched_row_D1_5",)
    sched_sel = ScheduleRowQuantitySelector(DOC, REV, SHA, SNAP, PAGE, sched_obs)
    sched_producer.publish(sched_sel, declared_count=5, type_mark="D1", universe_complete=True)
    sched_auth = sched_producer.authority()

    bind_results = {}
    for p_rec in (p_rec1, p_rec2):
        b_key = _binding_record_key(DOC, REV, SHA, SNAP, SCOPE, p_rec.record_id)
        b_payload = {
            "document_id": DOC, "revision_id": REV, "source_sha256": SHA, "snapshot_id": SNAP,
            "page_id": PAGE, "decision_scope_id": SCOPE, "opening_record_id": p_rec.record_id,
            "tag_observation_id": p_rec.source_observation_ids[0], "tag_mark": "D1",
            "schedule_page_id": PAGE, "schedule_row_observation_ids": sched_obs,
            "schedule_row_type_mark": "D1", "schedule_row_width_mm": None, "schedule_row_height_mm": None,
        }
        b_rec = ScheduleOpeningInstanceBindingRecord(
            record_id=stable_contract_id("schedule_opening_instance_binding", b_payload, digest_chars=32),
            **b_payload
        )
        bind_results[b_key] = ScheduleOpeningInstanceBindingResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(BINDING_RESOLVED,),
            record=b_rec,
        )
    bind_auth = ScheduleOpeningInstanceBindingAuthority(bind_results, _seal=BIND_SEAL)

    producer = GenericOpeningCountProducer.from_authorities(
        opening_universe_authority=univ_auth,
        physical_opening_authority=phys_auth,
        viewport_view_class_authority=vp_auth,
        schedule_binding_authority=bind_auth,
        schedule_row_quantity_authority=sched_auth,
    )
    res = producer.publish(GenericOpeningCountSelector(DOC, REV, SHA, SNAP, SCOPE, opening_mark="D1"))
    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert res.record is None
    assert GENERIC_OPENING_COUNT_SCHEDULE_MISMATCH in res.reason_codes


def test_physical_opening_producer_registers_by_alias():
    src_auth = SourceObservationProducer(producer_method="test", producer_version="1.0").authority()
    phys_producer = PhysicalOpeningProducer(src_auth)
    p_rec = _make_physical("phys_abc", "obs_xyz")
    phys_producer.publish_physical_opening(p_rec, member_id="mem_123")
    phys_auth = phys_producer.authority()

    for query_id in ("phys_abc", "obs_xyz", "mem_123"):
        sel = ObservationSelector(DOC, REV, SHA, SNAP, query_id)
        res = phys_auth.prove_existence(sel)
        assert res.status is EvidenceResolutionStatus.CORROBORATED
        assert res.existence_record is not None
        assert res.existence_record.record_id == "phys_abc"


def test_pipeline_end_to_end_lamu():
    from pathlib import Path
    import fitz
    from pb_source_opening_count_pipeline import run_source_opening_count_pipeline
    from pb_raster_schedule_extractor import GenericScheduleTableExtractor

    pdf_path = Path("benchmarks/sources/lamu-ishakani-ecd-classrooms-boq.pdf")
    if not pdf_path.exists():
        pytest.skip("Lamu benchmark source not found")

    doc = fitz.open(str(pdf_path))
    extractor = GenericScheduleTableExtractor()
    rows = extractor.extract_from_document(doc, pages=[40])
    res = run_source_opening_count_pipeline(
        doc=doc,
        dwg_pages=[40],
        document_id="lamu",
        revision_id="rev1",
        source_sha256="a" * 64,
        schedule_rows=rows,
    )
    assert "D1" in res
    assert res["D1"].count == 2
    assert res["D1"].schedule_corroborated is True
    assert "door" in res
    assert res["door"].count == 2

