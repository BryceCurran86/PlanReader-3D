"""Only authenticated source-drawn non-plan viewports can oppose a G17 hypothesis."""
from types import SimpleNamespace

import pytest

from pb_physical_opening_viewport_scope_shadow import (
    IN_AUTHENTICATED_FLOOR_PLAN, IN_AUTHENTICATED_NON_PLAN,
    OUTSIDE_AUTHENTICATED_VIEWPORTS, NO_AUTHENTICATED_VIEWPORT,
    EVIDENCE_DIRECTION_AGAINST_PROMOTION, EVIDENCE_DIRECTION_SCOPE_ONLY,
)
from tools.diag_gptmax_native_opening_viewport_scope import audit_native_candidate_viewports


def binding(oid, source_id, *, host=None):
    return SimpleNamespace(opening_identity_id=oid,
        representative_observation_id=source_id,
        host_wall_id=host, reason_codes=("no_authenticated_host_wall_band",))


def candidate(cid, sources, scope, direction="none", boundary=None,
              corroborated=True, view_type=None):
    return SimpleNamespace(candidate_id=cid,
        source_observation_ids=tuple(sources),
        scope=scope, evidence_direction=direction,
        boundary_source=boundary, existence_corroborated=corroborated,
        view_id="view:" + cid, view_type=view_type,
        structural_pattern="jamb_bounded_two_face_interruption")


def report(*candidates):
    return SimpleNamespace(candidate_scopes=candidates)


def test_authenticated_source_drawn_nonplan_view_opposes_promotion_without_deletion():
    x=report(candidate("title-grid", ("source-table",),
        IN_AUTHENTICATED_NON_PLAN,EVIDENCE_DIRECTION_AGAINST_PROMOTION,
        "vector_frame",view_type="schedule"))
    result=audit_native_candidate_viewports([binding("physical-table","source-table")],x)
    assert result[0]["first_unproved_or_opposing_scope"] == (
        "AUTHENTICATED_DRAWN_NONPLAN_VIEW_TYPED_OPPOSITION")
    assert not result[0]["original_existence_retracted"]
    assert not result[0]["physical_host_publication_allowed"]
    assert result[0]["host_wall_id"] is None


def test_floorplan_ownership_is_only_scope_not_host_proof():
    x=report(candidate("floor",("source-plan",),IN_AUTHENTICATED_FLOOR_PLAN,
        EVIDENCE_DIRECTION_SCOPE_ONLY,"vector_frame",view_type="floor_plan"))
    item=audit_native_candidate_viewports([binding("opening","source-plan")],x)[0]
    assert item["first_unproved_or_opposing_scope"]=="FLOORPLAN_SOURCE_SCOPE_ONLY"
    assert not item["physical_host_publication_allowed"]


def test_ambiguous_native_source_or_derived_nonplan_does_not_delete_opening():
    x=report(candidate("unproven",("amb",),IN_AUTHENTICATED_NON_PLAN,
        EVIDENCE_DIRECTION_AGAINST_PROMOTION,"title_partition",view_type="schedule"))
    item=audit_native_candidate_viewports([binding("opening","amb")],x)[0]
    assert item["first_unproved_or_opposing_scope"]=="VIEWPORT_OR_SOURCE_CANDIDATE_AMBIGUOUS"
    assert not item["original_existence_retracted"]
    z=report(candidate("unscoped",("amb",),NO_AUTHENTICATED_VIEWPORT))
    assert audit_native_candidate_viewports([binding("opening","amb")],z)[0][
        "first_unproved_or_opposing_scope"]=="VIEWPORT_OR_SOURCE_CANDIDATE_AMBIGUOUS"


def test_opposing_nonplan_competes_with_floorplan_and_cannot_choose_first_or_nearest():
    plan=candidate("plan",("source-shared",),IN_AUTHENTICATED_FLOOR_PLAN,
        EVIDENCE_DIRECTION_SCOPE_ONLY,"vector_frame",view_type="floor_plan")
    other=candidate("other",("source-shared",),IN_AUTHENTICATED_NON_PLAN,
        EVIDENCE_DIRECTION_AGAINST_PROMOTION,"vector_frame",view_type="schedule")
    for items in ((plan,other),(other,plan)):
        r=audit_native_candidate_viewports([binding("shared","source-shared")],report(*items))[0]
        assert r["first_unproved_or_opposing_scope"]=="VIEWPORT_OR_SOURCE_CANDIDATE_AMBIGUOUS"
        assert len(r["candidate_viewport_ids"])==2
        assert r["candidate_viewport_ids"]==["other","plan"]


def test_representative_not_bound_to_snapshot_candidate_abstains_not_missing_opening():
    x=report(candidate("other",("unrelated",),OUTSIDE_AUTHENTICATED_VIEWPORTS))
    item=audit_native_candidate_viewports([binding("physical","source-not-listed",host="existing-host")],x)[0]
    assert item["first_unproved_or_opposing_scope"]=="SOURCE_CANDIDATE_VIEWPORT_MEMBERSHIP_UNPROVEN"
    assert item["host_wall_id"]=="existing-host"
    assert not item["opening_count_publication_allowed"]


@pytest.mark.parametrize("mutation",["duplicated_candidate","malformed_source","duplicated_physical",
    "missing_source","blank_identity"])
def test_malformed_or_duplicate_source_records_fail_closed(mutation):
    x=report(candidate("one",("visible",),IN_AUTHENTICATED_FLOOR_PLAN,
      EVIDENCE_DIRECTION_SCOPE_ONLY,"vector_frame",view_type="floor_plan"))
    bindings=[binding("physical","visible")]
    if mutation=="duplicated_candidate":
        x=report(*x.candidate_scopes,*x.candidate_scopes)
    elif mutation=="malformed_source":
        x=report(candidate("one",("",),IN_AUTHENTICATED_FLOOR_PLAN))
    elif mutation=="duplicated_physical":
        bindings.append(binding("physical","visible"))
    elif mutation=="missing_source":
        bindings=[binding("physical","")]
    elif mutation=="blank_identity":
        bindings=[binding(" ","visible")]
    with pytest.raises((TypeError,ValueError)):
        audit_native_candidate_viewports(bindings,x)
