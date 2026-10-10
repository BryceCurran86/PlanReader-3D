"""RCP view claims must never bootstrap themselves into finish quantities."""
from types import SimpleNamespace as R
from tools.diag_gpt2_rcp_material_occurrence_gates import (
    scoped_rcp_material_occurrence_gate as gate,
)

def vp(kind="reflected_ceiling_plan",status="derived",box=(1,2,9,20)):
    return R(view_id="v9",view_type=kind,status=status,bounding_box=box)

def scope(*,complete=False,records=(),reasons=("source_material_viewport_unauthenticated",),status=None):
    from pb_migration_contracts import EvidenceResolutionStatus
    producer_status = status or (
        EvidenceResolutionStatus.CORROBORATED
        if complete else EvidenceResolutionStatus.ABSTAINED
    )
    return R(status=producer_status,scope_complete=complete,
             records=records,reason_codes=reasons)

def test_no_rcp_owner_even_if_material_scope_has_records():
    r=gate(vp("schedule"),scope(complete=True,records=(R(record_id="id",code="FPB"),)))
    assert r["first_unclosed_gate"]=="not_an_rcp_viewport"
    assert r["new_room_material_ownership_claim"] is False

def test_unresolved_rcp_is_not_semantic_authority():
    for status in ("unsupported","ambiguous"):
        r=gate(vp(status=status,box=None),scope())
        assert r["first_unclosed_gate"]=="source_rcp_viewport_unresolved"

def test_derived_rcp_with_incomplete_scope_abstains():
    r=gate(vp(),scope())
    assert r["first_unclosed_gate"]=="producer_source_occurrence_universe_incomplete"
    assert r["producer_reason_codes"]==["source_material_viewport_unauthenticated"]
    assert r["new_metric_quantity_claim"] is False

def test_empty_complete_scope_not_false_positive():
    r=gate(vp(),scope(complete=True))
    assert r["first_unclosed_gate"]=="producer_no_authenticated_occurrences"

def test_producer_records_still_require_real_room_owner():
    r=gate(vp(status="resolved"),scope(complete=True,records=(R(record_id="source-1",code="WFPB"),)))
    assert r["first_unclosed_gate"]=="producer_authenticated_occurrences_require_room_owner_before_quantity"
    assert r["producer_occurrence_record_ids"]==["source-1"]
    assert r["new_room_material_ownership_claim"] is False
    assert r["new_metric_quantity_claim"] is False


def test_conflicted_or_candidate_source_scope_never_authenticates_stale_occurrences():
    from pb_migration_contracts import EvidenceResolutionStatus
    for status in (
        EvidenceResolutionStatus.CONFLICT,
        EvidenceResolutionStatus.CANDIDATE,
        EvidenceResolutionStatus.ABSTAINED,
    ):
        r=gate(
            vp(),scope(complete=True, records=(R(record_id="stale", code="GRID"),),
                       status=status)
        )
        assert r["first_unclosed_gate"]=="producer_source_occurrence_scope_not_corroborated"
        assert r["producer_occurrence_record_ids"]==["stale"]
        assert r["producer_authenticated_record_ids"]==[]
        assert r["new_room_material_ownership_claim"] is False
        assert r["new_metric_quantity_claim"] is False


def test_producer_enum_corroboration_only_counts_authentic_records():
    from pb_migration_contracts import EvidenceResolutionStatus
    r=gate(
        vp(),
        scope(
            complete=True,
            records=(R(record_id="source-record",code="FPB"),),
            status=EvidenceResolutionStatus.CORROBORATED,
        ),
    )
    assert r["first_unclosed_gate"]=="producer_authenticated_occurrences_require_room_owner_before_quantity"
    assert r["producer_authenticated_record_ids"]==["source-record"]
    assert r["new_metric_quantity_claim"] is False
    for not_rcp in (vp(kind="schedule"),vp(status="unsupported",box=None)):
        row=gate(not_rcp,scope(complete=True,records=(R(record_id="x",code="FPB"),)))
        assert row["producer_authenticated_record_ids"]==[]
