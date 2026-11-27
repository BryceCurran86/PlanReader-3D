"""Tests for live fail-closed consumer bridges to the four staged #4755 room/finish/RCP modules."""
from __future__ import annotations

from pb_cross_view_ceiling_finish_authority import CrossViewCeilingFinishProducer
from pb_cross_view_floor_finish_authority import (
    build_green_exclusion_epoxy_linkage_consumer_shadow,
    build_room_finish_rcp_handoff_consumer_shadow,
    build_room_legend_linkage_consumer_shadow,
)
from pb_source_rcp_bubble_height_material_shadow import (
    RcpCeilingZonePolygon,
    RcpLineageRef,
    RcpMaterialHeightBubble,
)
from pb_source_room_finish_rcp_handoff_shadow import CrossViewRoomCeilingLinkInput


def test_live_rcp_bubble_height_material_consumer_bridge() -> None:
    lineage = RcpLineageRef(
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256="a" * 64,
        page_id="2",
        viewport_id="vp-rcp",
    )
    zone = RcpCeilingZonePolygon(
        zone_id="zone-1",
        lineage=lineage,
        polygon_pdf_pts=((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)),
    )
    bubble = RcpMaterialHeightBubble(
        bubble_id="bub-1",
        lineage=lineage,
        anchor_pt=(50.0, 50.0),
        lines=("CL1", "2700"),
    )
    report = CrossViewCeilingFinishProducer.publish_rcp_bubble_height_material_shadow(
        None,  # type: ignore[arg-type]
        rcp_zones=(zone,),
        rcp_bubbles=(bubble,),
    )
    assert len(report.associations) == 1
    assert getattr(report, "commercial_quantity_authority", False) is False


def test_live_green_legend_and_handoff_consumer_bridges() -> None:
    green = build_green_exclusion_epoxy_linkage_consumer_shadow(
        rooms=(),
        green_witnesses=(),
        label_observations=(),
    )
    assert getattr(green, "commercial_quantity_authority", False) is False

    legend = build_room_legend_linkage_consumer_shadow(
        legend_rows=(),
        room_faces=(),
        number_callouts=(),
    )
    assert getattr(legend, "commercial_quantity_authority", False) is False

    room_link = CrossViewRoomCeilingLinkInput(
        physical_room_id="room-1",
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256="a" * 64,
        floor_plan_page_id="1",
        floor_plan_viewport_id="vp-1",
        canonical_floor_id="floor-1",
        explicit_room_label="OFFICE",
        rcp_zone_id=None,
    )
    packet = build_room_finish_rcp_handoff_consumer_shadow(rooms=(room_link,))
    assert len(packet.records) == 1
    assert getattr(packet, "commercial_quantity_authority", False) is False
