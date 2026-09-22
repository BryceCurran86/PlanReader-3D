from __future__ import annotations

from pb_net_wall_boolean_union_authority import (
    NetWallBooleanUnionAuthority,
    NetWallBooleanUnionSelector,
    _AUTHORITY_SEAL,
)
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def test_extractor_retains_authenticated_net_wall_dependencies() -> None:
    authority = NetWallBooleanUnionAuthority({}, _seal=_AUTHORITY_SEAL)
    selector = NetWallBooleanUnionSelector(
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256="a" * 64,
        snapshot_id="snap-1",
        page_id="1",
        decision_scope_id="wall-source:page-1",
        physical_wall_id="perimeter_walling",
        trade_scope_id="walling",
    )

    extractor = GenericPlanReaderExtractor(
        net_wall_authority=authority,
        net_wall_selectors={"perimeter_walling": selector},
    )

    assert extractor.net_wall_authority is authority
    assert extractor.net_wall_selectors == {"perimeter_walling": selector}
    assert extractor.live_net_wall_shadow["status"] == "abstained"
    assert extractor.live_net_wall_shadow["reason"] == "not_collected"


def test_extractor_copies_selector_mapping_at_boundary() -> None:
    authority = NetWallBooleanUnionAuthority({}, _seal=_AUTHORITY_SEAL)
    selector = NetWallBooleanUnionSelector(
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256="a" * 64,
        snapshot_id="snap-1",
        page_id="1",
        decision_scope_id="wall-source:page-1",
        physical_wall_id="perimeter_walling",
        trade_scope_id="walling",
    )
    supplied = {"perimeter_walling": selector}

    extractor = GenericPlanReaderExtractor(
        net_wall_authority=authority,
        net_wall_selectors=supplied,
    )
    supplied.clear()

    assert extractor.net_wall_selectors == {"perimeter_walling": selector}
