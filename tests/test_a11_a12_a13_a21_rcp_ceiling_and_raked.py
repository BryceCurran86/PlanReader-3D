"""A11/A12/A13/A21 tests: RCP bubble material/height normalization, raked/stepped ceiling preservation, and cross-view handoff."""
from __future__ import annotations

import pytest

from pb_cross_view_floor_finish_authority import build_room_finish_rcp_handoff_consumer_shadow
from pb_source_rcp_bubble_height_material_shadow import (
    RcpCeilingZonePolygon,
    RcpLineageRef,
    RcpMaterialHeightBubble,
    associate_rcp_bubbles_to_ceiling_zones_shadow,
    parse_rcp_bubble_material_and_height,
)
from pb_source_room_finish_rcp_handoff_shadow import CrossViewRoomCeilingLinkInput

_SHA = "d" * 64


@pytest.mark.parametrize(
    ("lines", "expected_mat", "expected_flat", "expected_raked"),
    [
        (("GRID", "CH 2,700 mm"), "GRID", 2700, None),
        (("CL1", "FCL 2.7m"), "CL1", 2700, None),
        (("CL2", "RAKED 2,700\u20143,400"), "CL2", None, (2700, 3400)),
        (("TIM1", "SLOPED 2.7 TO 3.6M"), "TIM1", None, (2700, 3600)),
        (("BULKHEAD", "2.4\u00a0m AFFL"), "BULKHEAD", 2400, None),
    ],
)
def test_a11_a21_rcp_bubble_parses_thousands_decimal_metres_and_raked_ranges(
    lines: tuple[str, ...],
    expected_mat: str,
    expected_flat: int | None,
    expected_raked: tuple[int, int] | None,
) -> None:
    mat, flat, raked = parse_rcp_bubble_material_and_height(lines)
    assert mat == expected_mat
    assert flat == expected_flat
    assert raked == expected_raked


def test_a11_conflicting_flat_heights_in_one_bubble_abstain() -> None:
    mat, flat, raked = parse_rcp_bubble_material_and_height(("CL1", "2.7M / 3000mm"))
    assert mat == "CL1"
    assert flat is None
    assert raked is None


def test_a11_a21_stepped_bulkhead_and_raked_zones_never_flatten_heights() -> None:
    lineage = RcpLineageRef("doc-1", "rev-1", _SHA, "9", "vp-rcp")
    main_zone = RcpCeilingZonePolygon(
        zone_id="z-main",
        lineage=lineage,
        polygon_pdf_pts=((0.0, 0.0), (200.0, 0.0), (200.0, 200.0), (0.0, 200.0)),
    )
    bulkhead = RcpCeilingZonePolygon(
        zone_id="z-bulkhead",
        lineage=lineage,
        polygon_pdf_pts=((20.0, 20.0), (80.0, 20.0), (80.0, 80.0), (20.0, 80.0)),
        parent_zone_id="z-main",
        is_bulkhead_subzone=True,
    )
    raked_zone = RcpCeilingZonePolygon(
        zone_id="z-raked",
        lineage=lineage,
        polygon_pdf_pts=((220.0, 0.0), (320.0, 0.0), (320.0, 200.0), (220.0, 200.0)),
    )
    bubbles = (
        RcpMaterialHeightBubble("b-main", lineage, (150.0, 150.0), ("GRID", "2,700")),
        RcpMaterialHeightBubble("b-bh", lineage, (50.0, 50.0), ("BULKHEAD", "2.4m")),
        RcpMaterialHeightBubble("b-rk", lineage, (270.0, 100.0), ("CL2", "RAKED 2.7-3.4M")),
    )
    report = associate_rcp_bubbles_to_ceiling_zones_shadow(
        zones=(main_zone, bulkhead, raked_zone),
        bubbles=bubbles,
    )
    by_zone = {a.zone_id: a for a in report.associations}
    assert by_zone["z-main"].height_mm == 2700
    assert by_zone["z-bulkhead"].height_mm == 2400
    assert by_zone["z-raked"].raked_height_range_mm == (2700, 3400)
    assert report.distinct_heights_preserved_mm == (2400, 2700)
    assert report.commercial_authority_granted is False


def test_a12_a13_cross_view_room_finish_rcp_handoff_preserves_distinct_heights_and_non_promotion() -> None:
    lineage = RcpLineageRef("doc-1", "rev-1", _SHA, "9", "vp-rcp")
    zones = (
        RcpCeilingZonePolygon("z-1", lineage, ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0))),
        RcpCeilingZonePolygon("z-2", lineage, ((120.0, 0.0), (220.0, 0.0), (220.0, 100.0), (120.0, 100.0))),
    )
    bubbles = (
        RcpMaterialHeightBubble("b-1", lineage, (50.0, 50.0), ("GRID", "2,700")),
        RcpMaterialHeightBubble("b-2", lineage, (170.0, 50.0), ("FC1", "2.4m")),
    )
    rooms = (
        CrossViewRoomCeilingLinkInput("rm-1", "doc-1", "rev-1", _SHA, "7", "vp-plan", "fl-1", "OFFICE", "z-1"),
        CrossViewRoomCeilingLinkInput("rm-2", "doc-1", "rev-1", _SHA, "7", "vp-plan", "fl-2", "FOOD PREP", "z-2"),
    )
    packet = build_room_finish_rcp_handoff_consumer_shadow(
        rooms=rooms,
        rcp_zones=zones,
        rcp_bubbles=bubbles,
    )
    by_rm = {r.physical_room_id: r for r in packet.records}
    assert by_rm["rm-1"].rcp_material_code == "GRID"
    assert by_rm["rm-1"].rcp_ceiling_height_mm == 2700
    assert by_rm["rm-1"].cross_view_ceiling_ready is True
    assert by_rm["rm-2"].rcp_material_code == "FC1"
    assert by_rm["rm-2"].rcp_ceiling_height_mm == 2400
    assert by_rm["rm-2"].cross_view_ceiling_ready is True
    assert packet.commercial_authority_granted is False
