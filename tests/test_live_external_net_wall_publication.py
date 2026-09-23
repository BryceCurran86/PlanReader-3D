from __future__ import annotations

import inspect

from pb_gross_wall_geometry_authority import (
    GrossWallGeometryAuthority,
    GrossWallGeometryRecord,
    GrossWallGeometryResult,
    GrossWallGeometrySelector,
    _AUTHORITY_SEAL as _GROSS_AUTHORITY_SEAL,
)
from pb_live_external_net_wall_publication import (
    LIVE_EXTERNAL_NET_WALL_DUPLICATE_WALL,
    LIVE_EXTERNAL_NET_WALL_LINEAGE_MISMATCH,
    LIVE_EXTERNAL_NET_WALL_NO_EXTERNAL_WALLS,
    LIVE_EXTERNAL_NET_WALL_RESOLVED,
    LIVE_EXTERNAL_NET_WALL_UPSTREAM_INCOMPLETE,
    compose_live_external_net_wall_publication,
)
from pb_live_gross_wall_geometry_composition import (
    LiveGrossWallGeometryComposition,
    LiveGrossWallTrace,
)
from pb_live_net_wall_boolean_composition import LiveNetWallBooleanComposition
from pb_live_whole_wall_role_composition import LiveWholeWallRoleComposition
from pb_migration_contracts import EvidenceResolutionStatus
from pb_net_wall_boolean_union_authority import (
    NetWallBooleanUnionAuthority,
    NetWallBooleanUnionRecord,
    NetWallBooleanUnionResult,
    NetWallBooleanUnionSelector,
    _AUTHORITY_SEAL as _NET_AUTHORITY_SEAL,
)
from pb_wall_role_authority import WallRoleClassification
from pb_whole_wall_role_authority import (
    WholeWallRoleAuthority,
    WholeWallRoleRecord,
    WholeWallRoleResult,
    WholeWallRoleSelector,
    _AUTHORITY_SEAL as _ROLE_AUTHORITY_SEAL,
    _RECORD_SEAL as _ROLE_RECORD_SEAL,
)


DOC = "doc-external-net"
REV = "rev-1"
SHA = "a" * 64
SNAP = "snap-1"
TARGET = "walls"


def _gross_selector(wall_id: str, page_id: str) -> GrossWallGeometrySelector:
    return GrossWallGeometrySelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=page_id,
        decision_scope_id=f"wall-source:page-{page_id}",
        physical_wall_id=wall_id,
    )


def _role_selector(wall_id: str, page_id: str) -> WholeWallRoleSelector:
    return WholeWallRoleSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=page_id,
        decision_scope_id=f"wall-source:page-{page_id}",
        physical_wall_id=wall_id,
    )


def _net_selector(wall_id: str, page_id: str) -> NetWallBooleanUnionSelector:
    return NetWallBooleanUnionSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=page_id,
        decision_scope_id=f"wall-source:page-{page_id}",
        physical_wall_id=wall_id,
        trade_scope_id=TARGET,
    )


def _chain(
    *,
    role_a: WallRoleClassification = WallRoleClassification.EXTERNAL,
    role_b: WallRoleClassification = WallRoleClassification.INTERNAL,
    net_a: float = 12.5,
    net_b: float = 8.0,
):
    walls = (("wall-A", "1", role_a, net_a), ("wall-B", "2", role_b, net_b))

    gross_results = {}
    gross_selectors = {}
    gross_traces = []
    role_results = {}
    role_selectors = {}
    net_by_page = {}
    net_selectors = {}

    for wall_id, page_id, role, net_area in walls:
        gross_selector = _gross_selector(wall_id, page_id)
        gross_record = GrossWallGeometryRecord(
            record_id=f"gross-{wall_id}",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=page_id,
            decision_scope_id=f"wall-source:page-{page_id}",
            physical_wall_id=wall_id,
            wall_local_frame_id=f"frame-{wall_id}",
            length_m=5.0,
            height_m=3.0,
            gross_area_m2=15.0,
            polygon_wkb_hex="01030000",
            member_wall_candidate_ids=(f"candidate-{wall_id}",),
        )
        gross_results[gross_selector.key] = GrossWallGeometryResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=("test-gross",),
            record=gross_record,
        )
        gross_selectors[wall_id] = gross_selector
        gross_traces.append(
            LiveGrossWallTrace(
                physical_wall_id=wall_id,
                page_id=page_id,
                decision_scope_id=f"wall-source:page-{page_id}",
                registration_target_page_ids=(),
                registration_record_ids=(),
                height_status="corroborated",
                height_m=3.0,
                height_reason_codes=("test-height",),
                scale_status=EvidenceResolutionStatus.CORROBORATED,
                scale_record_id=f"scale-{page_id}",
                scale_reason_codes=("test-scale",),
                gross_status=EvidenceResolutionStatus.CORROBORATED,
                gross_record_id=gross_record.record_id,
                gross_reason_codes=("test-gross",),
            )
        )

        role_selector = _role_selector(wall_id, page_id)
        role_record = WholeWallRoleRecord(
            record_id=f"role-{wall_id}",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=page_id,
            decision_scope_id=f"wall-source:page-{page_id}",
            physical_wall_id=wall_id,
            gross_geometry_record_id=gross_record.record_id,
            member_wall_candidate_ids=(f"candidate-{wall_id}",),
            member_wall_role_record_ids=(f"member-role-{wall_id}",),
            role=role,
            _seal=_ROLE_RECORD_SEAL,
        )
        role_results[role_selector.key] = WholeWallRoleResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=("test-role",),
            record=role_record,
        )
        role_selectors[wall_id] = role_selector

        net_selector = _net_selector(wall_id, page_id)
        net_record = NetWallBooleanUnionRecord(
            record_id=f"net-{wall_id}",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=page_id,
            decision_scope_id=f"wall-source:page-{page_id}",
            physical_wall_id=wall_id,
            gross_geometry_record_id=gross_record.record_id,
            opening_universe_record_id=f"universe-{page_id}",
            deduction_record_ids=(),
            union_geometry_id=f"union-{wall_id}",
            net_area_m2=net_area,
            gross_area_m2=15.0,
            void_union_area_m2=15.0 - net_area,
            net_geometry_wkb_hex="01030000",
            physical_void_record_ids=(),
            trade_scope_id=TARGET,
        )
        net_result = NetWallBooleanUnionResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=("test-net",),
            record=net_record,
        )
        net_by_page[page_id] = NetWallBooleanUnionAuthority(
            {net_selector.key: net_result},
            _seal=_NET_AUTHORITY_SEAL,
        )
        net_selectors[(wall_id, TARGET)] = net_selector

    gross_authority = GrossWallGeometryAuthority(
        gross_results,
        _seal=_GROSS_AUTHORITY_SEAL,
    )
    gross = LiveGrossWallGeometryComposition(
        revision_id=REV,
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("live_gross_wall_composition_resolved",),
        traces=tuple(gross_traces),
        physical_wall_candidate_authority=None,
        cross_sheet_registration_authority=None,
        physical_scale_authority=None,
        wall_height_authority=None,
        gross_wall_geometry_authority=gross_authority,
        gross_selectors=gross_selectors,
    )
    roles = LiveWholeWallRoleComposition(
        revision_id=REV,
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("live_whole_wall_role_composition_resolved",),
        traces=(),
        whole_wall_role_authority=WholeWallRoleAuthority(
            role_results,
            _seal=_ROLE_AUTHORITY_SEAL,
        ),
        role_selectors=role_selectors,
    )
    net = LiveNetWallBooleanComposition(
        revision_id=REV,
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("live_net_wall_boolean_composition_resolved",),
        traces=(),
        net_wall_authorities=net_by_page,
        net_wall_selectors=net_selectors,
    )
    return gross, net, roles


def test_external_net_wall_publication_sums_only_source_proven_external_walls() -> None:
    gross, net, roles = _chain()

    result = compose_live_external_net_wall_publication(
        gross_wall_composition=gross,
        net_wall_composition=net,
        whole_wall_role_composition=roles,
        target_scope_id=TARGET,
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (LIVE_EXTERNAL_NET_WALL_RESOLVED,)
    assert result.external_wall_ids == ("wall-A",)
    assert result.quantity_evidence is not None
    assert result.quantity_evidence.semantic_key == "perimeter_walling"
    assert result.quantity_evidence.family == "wall_net_area"
    assert result.quantity_evidence.value == 12.5
    assert result.quantity_evidence.abstained is False
    assert "wall-B" not in result.quantity_evidence.input_entity_ids


def test_multiple_external_walls_are_aggregated_deterministically() -> None:
    gross, net, roles = _chain(
        role_a=WallRoleClassification.EXTERNAL,
        role_b=WallRoleClassification.EXTERNAL,
        net_a=12.5,
        net_b=8.0,
    )
    result = compose_live_external_net_wall_publication(
        gross_wall_composition=gross,
        net_wall_composition=net,
        whole_wall_role_composition=roles,
        target_scope_id=TARGET,
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.external_wall_ids == ("wall-A", "wall-B")
    assert result.quantity_evidence is not None
    assert result.quantity_evidence.value == 20.5


def test_incomplete_gross_scope_cannot_publish() -> None:
    gross, net, roles = _chain()
    gross = LiveGrossWallGeometryComposition(
        revision_id=gross.revision_id,
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=("live_gross_wall_coverage_incomplete",),
        traces=gross.traces,
        physical_wall_candidate_authority=gross.physical_wall_candidate_authority,
        cross_sheet_registration_authority=gross.cross_sheet_registration_authority,
        physical_scale_authority=gross.physical_scale_authority,
        wall_height_authority=gross.wall_height_authority,
        gross_wall_geometry_authority=gross.gross_wall_geometry_authority,
        gross_selectors=gross.gross_selectors,
    )
    result = compose_live_external_net_wall_publication(
        gross_wall_composition=gross,
        net_wall_composition=net,
        whole_wall_role_composition=roles,
        target_scope_id=TARGET,
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert LIVE_EXTERNAL_NET_WALL_UPSTREAM_INCOMPLETE in result.reason_codes
    assert result.quantity_evidence is None


def test_missing_exact_net_selector_cannot_borrow_another_wall() -> None:
    gross, net, roles = _chain()
    selectors = dict(net.net_wall_selectors)
    selectors.pop(("wall-A", TARGET))
    net = LiveNetWallBooleanComposition(
        revision_id=net.revision_id,
        status=net.status,
        reason_codes=net.reason_codes,
        traces=net.traces,
        net_wall_authorities=net.net_wall_authorities,
        net_wall_selectors=selectors,
    )
    result = compose_live_external_net_wall_publication(
        gross_wall_composition=gross,
        net_wall_composition=net,
        whole_wall_role_composition=roles,
        target_scope_id=TARGET,
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert LIVE_EXTERNAL_NET_WALL_UPSTREAM_INCOMPLETE in result.reason_codes
    assert result.quantity_evidence is None


def test_role_selector_lineage_mismatch_is_conflict() -> None:
    gross, net, roles = _chain()
    selectors = dict(roles.role_selectors)
    selectors["wall-A"] = WholeWallRoleSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id="99",
        decision_scope_id="wall-source:page-99",
        physical_wall_id="wall-A",
    )
    roles = LiveWholeWallRoleComposition(
        revision_id=roles.revision_id,
        status=roles.status,
        reason_codes=roles.reason_codes,
        traces=roles.traces,
        whole_wall_role_authority=roles.whole_wall_role_authority,
        role_selectors=selectors,
    )
    result = compose_live_external_net_wall_publication(
        gross_wall_composition=gross,
        net_wall_composition=net,
        whole_wall_role_composition=roles,
        target_scope_id=TARGET,
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert LIVE_EXTERNAL_NET_WALL_LINEAGE_MISMATCH in result.reason_codes
    assert result.quantity_evidence is None


def test_no_external_role_never_converts_internal_walls_to_perimeter_quantity() -> None:
    gross, net, roles = _chain(
        role_a=WallRoleClassification.INTERNAL,
        role_b=WallRoleClassification.INTERNAL,
    )
    result = compose_live_external_net_wall_publication(
        gross_wall_composition=gross,
        net_wall_composition=net,
        whole_wall_role_composition=roles,
        target_scope_id=TARGET,
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (LIVE_EXTERNAL_NET_WALL_NO_EXTERNAL_WALLS,)
    assert result.quantity_evidence is None


def test_duplicate_gross_whole_wall_identity_fails_closed() -> None:
    gross, net, roles = _chain()
    gross = LiveGrossWallGeometryComposition(
        revision_id=gross.revision_id,
        status=gross.status,
        reason_codes=gross.reason_codes,
        traces=(gross.traces[0], gross.traces[0]),
        physical_wall_candidate_authority=gross.physical_wall_candidate_authority,
        cross_sheet_registration_authority=gross.cross_sheet_registration_authority,
        physical_scale_authority=gross.physical_scale_authority,
        wall_height_authority=gross.wall_height_authority,
        gross_wall_geometry_authority=gross.gross_wall_geometry_authority,
        gross_selectors=gross.gross_selectors,
    )
    result = compose_live_external_net_wall_publication(
        gross_wall_composition=gross,
        net_wall_composition=net,
        whole_wall_role_composition=roles,
        target_scope_id=TARGET,
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.reason_codes == (LIVE_EXTERNAL_NET_WALL_DUPLICATE_WALL,)
    assert result.quantity_evidence is None


def test_publication_boundary_has_no_caller_wall_role_or_area_inputs() -> None:
    parameters = set(
        inspect.signature(compose_live_external_net_wall_publication).parameters
    )
    forbidden = {
        "wall_id",
        "wall_ids",
        "external_wall_ids",
        "roles",
        "role",
        "gross_area_m2",
        "net_area_m2",
        "opening_area_m2",
        "coverage_complete",
        "perimeter_m",
        "quantity",
    }
    assert not (parameters & forbidden)
