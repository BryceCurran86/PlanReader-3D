from __future__ import annotations

from types import SimpleNamespace

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_viewport_assignment_authority import (
    OpeningViewportAssignmentRecord,
    _floor_plan_scopes_for_opening,
    _geometry_inside_bbox,
)


def _opening(**overrides):
    data = {
        "document_id": "doc",
        "revision_id": "r1",
        "source_sha256": "a" * 64,
        "snapshot_id": "snap",
        "page_id": "1",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _scope(
    scope_id: str,
    bbox,
    *,
    view_type: str = "floor_plan",
    status=EvidenceResolutionStatus.CORROBORATED,
    document_id: str = "doc",
    revision_id: str = "r1",
    source_sha256: str = "a" * 64,
    snapshot_id: str = "snap",
    page_id: str = "1",
):
    return SimpleNamespace(
        document_id=document_id,
        revision_id=revision_id,
        source_sha256=source_sha256,
        snapshot_id=snapshot_id,
        page_id=page_id,
        status=status,
        scope_kind="viewport",
        viewport_view_type=view_type,
        viewport_id=f"view:{scope_id}",
        viewport_bbox=tuple(float(v) for v in bbox),
        decision_scope_id=scope_id,
        scope_complete=False,
        reason_codes=("physical_wall_candidate_scope_cropped_at_viewport_boundary",),
    )


def _authority(*scopes):
    return SimpleNamespace(_scopes={str(i): scope for i, scope in enumerate(scopes)})


def test_all_support_endpoints_inside_one_floor_plan_assigns_that_scope() -> None:
    opening = _opening()
    plan = _scope("plan", (0, 0, 100, 100))
    result = _floor_plan_scopes_for_opening(
        wall_authority=_authority(plan),
        opening=opening,
        support_geometries=((20, 20, 40, 20), (40, 20, 60, 20)),
    )
    assert result == (plan,)


def test_center_inside_but_endpoint_outside_does_not_assign() -> None:
    assert _geometry_inside_bbox((50, 50, 120, 50), (0, 0, 100, 100)) is False


def test_overlapping_floor_plan_scopes_remain_ambiguous_to_caller() -> None:
    opening = _opening()
    left = _scope("left", (0, 0, 100, 100))
    right = _scope("right", (20, 0, 120, 100))
    result = _floor_plan_scopes_for_opening(
        wall_authority=_authority(left, right),
        opening=opening,
        support_geometries=((30, 20, 50, 20),),
    )
    assert result == (left, right)


def test_elevation_scope_cannot_own_opening_for_plan_host_binding() -> None:
    opening = _opening()
    elevation = _scope("elev", (0, 0, 100, 100), view_type="elevation")
    result = _floor_plan_scopes_for_opening(
        wall_authority=_authority(elevation),
        opening=opening,
        support_geometries=((20, 20, 40, 20),),
    )
    assert result == ()


def test_stale_source_lineage_scope_is_not_eligible() -> None:
    opening = _opening()
    stale = _scope("stale", (0, 0, 100, 100), revision_id="old")
    result = _floor_plan_scopes_for_opening(
        wall_authority=_authority(stale),
        opening=opening,
        support_geometries=((20, 20, 40, 20),),
    )
    assert result == ()


def test_global_scope_incomplete_does_not_prevent_view_ownership_proposition() -> None:
    opening = _opening()
    plan = _scope("plan", (0, 0, 100, 100))
    assert plan.scope_complete is False
    result = _floor_plan_scopes_for_opening(
        wall_authority=_authority(plan),
        opening=opening,
        support_geometries=((20, 20, 40, 20),),
    )
    assert result == (plan,)


def test_assignment_record_is_producer_owned() -> None:
    try:
        OpeningViewportAssignmentRecord(
            record_id="r",
            document_id="doc",
            revision_id="r1",
            source_sha256="a" * 64,
            snapshot_id="snap",
            page_id="1",
            opening_identity_id="opening",
            viewport_id="view",
            wall_decision_scope_id="scope",
            source_observation_ids=("o1",),
            wall_scope_complete=False,
            wall_scope_reason_codes=(),
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=("opening_viewport_assignment_resolved",),
        )
    except TypeError as exc:
        assert "producer-owned" in str(exc)
    else:
        raise AssertionError("caller must not construct positive assignment record")
