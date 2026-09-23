from __future__ import annotations

from types import MappingProxyType

from pb_gross_wall_geometry_authority import (
    GrossWallGeometryAuthority,
    GrossWallGeometryRecord,
    GrossWallGeometryResult,
    GrossWallGeometrySelector,
    _AUTHORITY_SEAL as GROSS_AUTHORITY_SEAL,
)
from pb_live_gross_wall_geometry_composition import (
    LiveGrossWallGeometryComposition,
    LiveGrossWallTrace,
)
from pb_live_whole_wall_role_composition import (
    LIVE_WHOLE_WALL_ROLE_PARTIAL,
    LIVE_WHOLE_WALL_ROLE_RESOLVED,
    compose_live_whole_wall_roles,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_wall_role_authority import WallRoleClassification
from tests.test_whole_wall_role_authority import _source_roles


def _gross_composition(tmp_path, *, selector_present: bool = True):
    published, wall_authority, by_role = _source_roles(tmp_path)
    wall_id = "whole-wall-external"
    members = (
        by_role[WallRoleClassification.EXTERNAL][0],
        by_role[WallRoleClassification.INTERNAL][0],
    )
    selector = GrossWallGeometrySelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        decision_scope_id="wall-source:page-1",
        physical_wall_id=wall_id,
    )
    record = GrossWallGeometryRecord(
        record_id="gross-whole-wall-external",
        document_id=selector.document_id,
        revision_id=selector.revision_id,
        source_sha256=selector.source_sha256,
        snapshot_id=selector.snapshot_id,
        page_id=selector.page_id,
        decision_scope_id=selector.decision_scope_id,
        physical_wall_id=wall_id,
        wall_local_frame_id="frame-whole-wall-external",
        length_m=4.0,
        height_m=3.0,
        gross_area_m2=12.0,
        polygon_wkb_hex="01030000",
        member_wall_candidate_ids=members,
    )
    authority = GrossWallGeometryAuthority(
        {
            selector.key: GrossWallGeometryResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=("test_gross_resolved",),
                record=record,
            )
        },
        _seal=GROSS_AUTHORITY_SEAL,
    )
    trace = LiveGrossWallTrace(
        physical_wall_id=wall_id,
        page_id="1",
        decision_scope_id="wall-source:page-1",
        registration_target_page_ids=(),
        registration_record_ids=(),
        height_status="firm",
        height_m=3.0,
        height_reason_codes=(),
        scale_status=EvidenceResolutionStatus.CORROBORATED,
        scale_record_id="scale-1",
        scale_reason_codes=(),
        gross_status=EvidenceResolutionStatus.CORROBORATED,
        gross_record_id=record.record_id,
        gross_reason_codes=("test_gross_resolved",),
    )
    composition = LiveGrossWallGeometryComposition(
        revision_id=published.revision.revision_id,
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("test_live_gross_resolved",),
        traces=(trace,),
        physical_wall_candidate_authority=wall_authority,
        cross_sheet_registration_authority=None,
        physical_scale_authority=None,
        wall_height_authority=None,
        gross_wall_geometry_authority=authority,
        gross_selectors=MappingProxyType(
            {wall_id: selector} if selector_present else {}
        ),
    )
    return composition, wall_id


def test_live_role_composition_replays_exact_gross_wall_universe(tmp_path) -> None:
    gross, wall_id = _gross_composition(tmp_path)

    result = compose_live_whole_wall_roles(gross_wall_composition=gross)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (LIVE_WHOLE_WALL_ROLE_RESOLVED,)
    assert result.whole_wall_role_authority is not None
    assert tuple(result.role_selectors) == (wall_id,)
    assert len(result.traces) == 1
    trace = result.traces[0]
    assert trace.physical_wall_id == wall_id
    assert trace.role is WallRoleClassification.EXTERNAL
    assert trace.record_id is not None


def test_live_role_composition_refuses_missing_gross_selector_join(tmp_path) -> None:
    gross, _wall_id = _gross_composition(tmp_path, selector_present=False)

    result = compose_live_whole_wall_roles(gross_wall_composition=gross)

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert LIVE_WHOLE_WALL_ROLE_PARTIAL in result.reason_codes
    assert any(
        reason.startswith("gross_role_selector_mismatch:")
        for reason in result.reason_codes
    )
    assert result.traces == ()
