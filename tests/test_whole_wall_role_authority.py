from __future__ import annotations

import inspect

from pb_gross_wall_geometry_authority import (
    GrossWallGeometryAuthority,
    GrossWallGeometryRecord,
    GrossWallGeometryResult,
    GrossWallGeometrySelector,
    _AUTHORITY_SEAL as GROSS_AUTHORITY_SEAL,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_wall_role_authority import WallRoleClassification, WallRoleProducer, WallRoleSelector
from pb_whole_wall_role_authority import (
    WHOLE_WALL_ROLE_LINEAGE_MISMATCH,
    WHOLE_WALL_ROLE_MEMBERSHIP_UNAVAILABLE,
    WHOLE_WALL_ROLE_RESOLVED,
    WholeWallRoleProducer,
    WholeWallRoleSelector,
)
from tests.test_source_wall_topology_authority_v1 import _source_wall_scope, _write_plan


def _source_roles(tmp_path):
    path = tmp_path / "whole-wall-role-two-room.pdf"
    _write_plan(path, with_partition=True)
    published, wall_authority, scope = _source_wall_scope(path)

    role_producer = WallRoleProducer.from_source_topology(
        physical_wall_candidate_authority=wall_authority
    )
    by_role: dict[WallRoleClassification, list[str]] = {}
    for candidate in scope.records:
        result = role_producer.publish(
            WallRoleSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                page_id="1",
                decision_scope_id="wall-source:page-1",
                physical_wall_id=candidate.wall_candidate_id,
            )
        )
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.record is not None
        ):
            by_role.setdefault(result.record.role, []).append(
                result.record.physical_wall_id
            )

    assert by_role.get(WallRoleClassification.EXTERNAL)
    assert by_role.get(WallRoleClassification.INTERNAL)
    return published, wall_authority, by_role


def _selector(published, wall_id: str) -> WholeWallRoleSelector:
    return WholeWallRoleSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        decision_scope_id="wall-source:page-1",
        physical_wall_id=wall_id,
    )


def _gross_authority(
    selector: WholeWallRoleSelector,
    members: tuple[str, ...],
    *,
    record_wall_id: str | None = None,
) -> GrossWallGeometryAuthority:
    gross_selector = GrossWallGeometrySelector(
        document_id=selector.document_id,
        revision_id=selector.revision_id,
        source_sha256=selector.source_sha256,
        snapshot_id=selector.snapshot_id,
        page_id=selector.page_id,
        decision_scope_id=selector.decision_scope_id,
        physical_wall_id=selector.physical_wall_id,
    )
    record = GrossWallGeometryRecord(
        record_id=f"gross-{selector.physical_wall_id}",
        document_id=selector.document_id,
        revision_id=selector.revision_id,
        source_sha256=selector.source_sha256,
        snapshot_id=selector.snapshot_id,
        page_id=selector.page_id,
        decision_scope_id=selector.decision_scope_id,
        physical_wall_id=record_wall_id or selector.physical_wall_id,
        wall_local_frame_id=f"frame-{selector.physical_wall_id}",
        length_m=4.0,
        height_m=3.0,
        gross_area_m2=12.0,
        polygon_wkb_hex="01030000",
        member_wall_candidate_ids=members,
    )
    return GrossWallGeometryAuthority(
        {
            gross_selector.key: GrossWallGeometryResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=("test_authenticated_gross",),
                record=record,
            )
        },
        _seal=GROSS_AUTHORITY_SEAL,
    )


def test_whole_wall_external_when_authenticated_faces_include_external_and_internal(
    tmp_path,
) -> None:
    published, wall_authority, by_role = _source_roles(tmp_path)
    target = _selector(published, "whole-wall-external")
    members = (
        by_role[WallRoleClassification.EXTERNAL][0],
        by_role[WallRoleClassification.INTERNAL][0],
    )
    producer = WholeWallRoleProducer.from_authorities(
        physical_wall_candidate_authority=wall_authority,
        gross_wall_geometry_authority=_gross_authority(target, members),
    )

    result = producer.publish(target)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (WHOLE_WALL_ROLE_RESOLVED,)
    assert result.record is not None
    assert result.record.role is WallRoleClassification.EXTERNAL
    assert result.record.physical_wall_id == target.physical_wall_id
    assert result.record.member_wall_candidate_ids == tuple(sorted(members))
    assert len(result.record.member_wall_role_record_ids) == 2


def test_whole_wall_internal_when_every_authenticated_member_is_internal(
    tmp_path,
) -> None:
    published, wall_authority, by_role = _source_roles(tmp_path)
    target = _selector(published, "whole-wall-internal")
    members = (by_role[WallRoleClassification.INTERNAL][0],)
    producer = WholeWallRoleProducer.from_authorities(
        physical_wall_candidate_authority=wall_authority,
        gross_wall_geometry_authority=_gross_authority(target, members),
    )

    result = producer.publish(target)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    assert result.record.role is WallRoleClassification.INTERNAL


def test_whole_wall_role_refuses_gross_record_without_sealed_member_provenance(
    tmp_path,
) -> None:
    published, wall_authority, _by_role = _source_roles(tmp_path)
    target = _selector(published, "whole-wall-no-members")
    producer = WholeWallRoleProducer.from_authorities(
        physical_wall_candidate_authority=wall_authority,
        gross_wall_geometry_authority=_gross_authority(target, ()),
    )

    result = producer.publish(target)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert WHOLE_WALL_ROLE_MEMBERSHIP_UNAVAILABLE in result.reason_codes


def test_whole_wall_role_refuses_cross_wall_gross_record(
    tmp_path,
) -> None:
    published, wall_authority, by_role = _source_roles(tmp_path)
    target = _selector(published, "whole-wall-A")
    producer = WholeWallRoleProducer.from_authorities(
        physical_wall_candidate_authority=wall_authority,
        gross_wall_geometry_authority=_gross_authority(
            target,
            (by_role[WallRoleClassification.EXTERNAL][0],),
            record_wall_id="whole-wall-B",
        ),
    )

    result = producer.publish(target)

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.record is None
    assert WHOLE_WALL_ROLE_LINEAGE_MISMATCH in result.reason_codes


def test_whole_wall_role_public_writer_has_no_role_or_membership_inputs() -> None:
    signature = inspect.signature(WholeWallRoleProducer.publish)
    assert set(signature.parameters) == {"self", "selector"}
    selector_signature = inspect.signature(WholeWallRoleSelector)
    forbidden = {
        "role",
        "classification",
        "member_ids",
        "member_wall_candidate_ids",
        "is_external",
        "is_internal",
        "perimeter_rank",
        "thickness",
    }
    assert not (forbidden & set(selector_signature.parameters))
