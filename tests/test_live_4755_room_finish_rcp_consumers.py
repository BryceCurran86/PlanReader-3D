"""Live invocation & authority-boundary validation for the four #4807/#4755 shadow bridges (A27).

Verifies:
1. Positive, negative, ambiguity, and cross-revision fail-closed behavior across
   two structurally distinct room/drawing styles (commercial cold-room + numbered
   room legend + RCP material/height bubble; standard office with missing/ambiguous RCP).
2. Strict non-promotion: every bridge enforces ``commercial_quantity_authority is False``
   and raises ``RuntimeError`` if an underlying report ever attempts to claim
   commercial authority.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from pb_cross_view_ceiling_finish_authority import CrossViewCeilingFinishProducer
from pb_cross_view_floor_finish_authority import (
    build_green_exclusion_epoxy_linkage_consumer_shadow,
    build_room_finish_rcp_handoff_consumer_shadow,
    build_room_legend_linkage_consumer_shadow,
)
from pb_source_green_exclusion_epoxy_linkage_shadow import (
    CLASS_EPOXY_LABEL_ONLY,
    CLASS_EXCLUSION_LABEL_ONLY,
    FloorExclusionRoomCandidate,
    FloorFinishLabelObservation,
)
from pb_source_rcp_bubble_height_material_shadow import (
    RcpCeilingZonePolygon,
    RcpLineageRef,
    RcpMaterialHeightBubble,
)
from pb_source_room_finish_rcp_handoff_shadow import CrossViewRoomCeilingLinkInput
from pb_source_room_legend_linkage_shadow import (
    PhysicalRoomFaceCandidate,
    RoomLegendTableRowInput,
    RoomNumberBubbleCandidate,
)

_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SQUARE = ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0))
_SQUARE_2 = ((120.0, 0.0), (220.0, 0.0), (220.0, 100.0), (120.0, 100.0))


def test_live_rcp_bubble_bridge_positive_ambiguity_and_authority_guard() -> None:
    lineage = RcpLineageRef(
        document_id="doc-commercial",
        revision_id="rev-1",
        source_sha256=_SHA_A,
        page_id="2",
        viewport_id="vp-rcp",
    )
    zone_clean = RcpCeilingZonePolygon(
        zone_id="zone-clean",
        lineage=lineage,
        polygon_pdf_pts=_SQUARE,
    )
    zone_ambig = RcpCeilingZonePolygon(
        zone_id="zone-ambig",
        lineage=lineage,
        polygon_pdf_pts=_SQUARE_2,
    )
    bubble_clean = RcpMaterialHeightBubble(
        bubble_id="bub-1",
        lineage=lineage,
        anchor_pt=(50.0, 50.0),
        lines=("CL1", "2700"),
    )
    # Two conflicting heights inside zone_ambig -> must fail closed, never invent
    bubble_conflict_a = RcpMaterialHeightBubble(
        bubble_id="bub-2a",
        lineage=lineage,
        anchor_pt=(150.0, 40.0),
        lines=("CL1", "2700"),
    )
    bubble_conflict_b = RcpMaterialHeightBubble(
        bubble_id="bub-2b",
        lineage=lineage,
        anchor_pt=(180.0, 60.0),
        lines=("CL2", "3000"),
    )

    report = CrossViewCeilingFinishProducer.publish_rcp_bubble_height_material_shadow(
        object(),  # type: ignore[arg-type]
        rcp_zones=(zone_clean, zone_ambig),
        rcp_bubbles=(bubble_clean, bubble_conflict_a, bubble_conflict_b),
    )
    assert getattr(report, "commercial_authority_granted", False) is False
    assert getattr(report, "shadow_only", False) is True
    by_zone = {a.zone_id: a for a in report.associations}
    assert set(by_zone.keys()) == {"zone-clean", "zone-ambig"}
    assert by_zone["zone-clean"].height_mm == 2700
    assert by_zone["zone-clean"].material_code == "CL1"
    assert by_zone["zone-clean"].resolved is True
    assert by_zone["zone-ambig"].abstained is True
    assert by_zone["zone-ambig"].resolved is False

    for bad_report in (
        SimpleNamespace(commercial_authority_granted=True, shadow_only=True),
        SimpleNamespace(commercial_authority_granted=False, shadow_only=False),
    ):
        with patch(
            "pb_source_rcp_bubble_height_material_shadow.associate_rcp_bubbles_to_ceiling_zones_shadow",
            return_value=bad_report,
        ):
            with pytest.raises(RuntimeError, match="never grant commercial authority"):
                CrossViewCeilingFinishProducer.publish_rcp_bubble_height_material_shadow(
                    object(),  # type: ignore[arg-type]
                    rcp_zones=(zone_clean,),
                    rcp_bubbles=(bubble_clean,),
                )


def test_live_green_exclusion_epoxy_bridge_populated_and_authority_guard() -> None:
    room_epoxy = FloorExclusionRoomCandidate(
        canonical_floor_id="floor-cold",
        physical_floor_surface_id="surf-cold",
        source_room_face_record_id="rf-cold",
        document_id="doc-commercial",
        revision_id="rev-1",
        source_sha256=_SHA_A,
        page_id="1",
        viewport_id="vp-plan",
        polygon_pdf_pts=_SQUARE,
    )
    room_excl = FloorExclusionRoomCandidate(
        canonical_floor_id="floor-nic",
        physical_floor_surface_id="surf-nic",
        source_room_face_record_id="rf-nic",
        document_id="doc-commercial",
        revision_id="rev-1",
        source_sha256=_SHA_A,
        page_id="1",
        viewport_id="vp-plan",
        polygon_pdf_pts=_SQUARE_2,
    )
    obs_epoxy = FloorFinishLabelObservation(
        observation_id="obs-ep",
        document_id="doc-commercial",
        revision_id="rev-1",
        source_sha256=_SHA_A,
        page_id="1",
        viewport_id="vp-plan",
        raw_text="EPOXY FLOORING",
        anchor_pt_pdf_pts=(50.0, 50.0),
    )
    obs_nic = FloorFinishLabelObservation(
        observation_id="obs-nic",
        document_id="doc-commercial",
        revision_id="rev-1",
        source_sha256=_SHA_A,
        page_id="1",
        viewport_id="vp-plan",
        raw_text="BY OTHERS",
        anchor_pt_pdf_pts=(170.0, 50.0),
    )
    report = build_green_exclusion_epoxy_linkage_consumer_shadow(
        rooms=(room_epoxy, room_excl),
        green_witnesses=(),
        label_observations=(obs_epoxy, obs_nic),
    )
    assert report.commercial_quantity_allowed is False
    assert report.customer_write_allowed is False
    assert report.specialty_authority_granted is False
    by_floor = {r.canonical_floor_id: r for r in report.room_records}
    assert by_floor["floor-cold"].classification == CLASS_EPOXY_LABEL_ONLY
    assert by_floor["floor-nic"].classification == CLASS_EXCLUSION_LABEL_ONLY

    for bad_report in (
        SimpleNamespace(commercial_quantity_allowed=True),
        SimpleNamespace(customer_write_allowed=True),
        SimpleNamespace(specialty_authority_granted=True),
    ):
        with patch(
            "pb_source_green_exclusion_epoxy_linkage_shadow.link_green_exclusions_and_epoxy_labels",
            return_value=bad_report,
        ):
            with pytest.raises(RuntimeError, match="never grant commercial authority"):
                build_green_exclusion_epoxy_linkage_consumer_shadow(
                    rooms=(room_epoxy,),
                    green_witnesses=(),
                    label_observations=(obs_epoxy,),
                )


def test_live_room_legend_bridge_populated_cross_revision_and_authority_guard() -> None:
    legend_rows = (
        RoomLegendTableRowInput(
            document_id="doc-commercial",
            revision_id="rev-1",
            source_sha256=_SHA_A,
            legend_page_id="1",
            legend_viewport_id="vp-legend",
            observation_ids=("obs-hdr",),
            cells=("ROOM LEGEND",),
        ),
        RoomLegendTableRowInput(
            document_id="doc-commercial",
            revision_id="rev-1",
            source_sha256=_SHA_A,
            legend_page_id="1",
            legend_viewport_id="vp-legend",
            observation_ids=("obs-cols",),
            cells=("ROOM NO", "ROOM NAME"),
        ),
        RoomLegendTableRowInput(
            document_id="doc-commercial",
            revision_id="rev-1",
            source_sha256=_SHA_A,
            legend_page_id="1",
            legend_viewport_id="vp-legend",
            observation_ids=("obs-r1",),
            cells=("101", "COOL ROOM"),
        ),
    )
    room_match = PhysicalRoomFaceCandidate(
        room_face_id="rf-101",
        document_id="doc-commercial",
        revision_id="rev-1",
        source_sha256=_SHA_A,
        plan_page_id="1",
        plan_viewport_id="vp-plan",
        polygon_pdf_pts=_SQUARE,
        room_face_evidence_ids=("ev-101",),
    )
    room_wrong_rev = PhysicalRoomFaceCandidate(
        room_face_id="rf-stale",
        document_id="doc-commercial",
        revision_id="rev-2",
        source_sha256=_SHA_B,
        plan_page_id="1",
        plan_viewport_id="vp-plan",
        polygon_pdf_pts=_SQUARE_2,
        room_face_evidence_ids=("ev-stale",),
    )
    callout_ok = RoomNumberBubbleCandidate(
        callout_id="cal-101",
        observation_id="obs-b101",
        document_id="doc-commercial",
        revision_id="rev-1",
        source_sha256=_SHA_A,
        plan_page_id="1",
        plan_viewport_id="vp-plan",
        raw_text="101",
        anchor_pt_pdf_pts=(50.0, 50.0),
    )
    callout_wrong_rev = RoomNumberBubbleCandidate(
        callout_id="cal-101-stale",
        observation_id="obs-b101-stale",
        document_id="doc-commercial",
        revision_id="rev-2",
        source_sha256=_SHA_B,
        plan_page_id="1",
        plan_viewport_id="vp-plan",
        raw_text="101",
        anchor_pt_pdf_pts=(170.0, 50.0),
    )
    report = build_room_legend_linkage_consumer_shadow(
        legend_rows=legend_rows,
        room_faces=(room_match, room_wrong_rev),
        number_callouts=(callout_ok, callout_wrong_rev),
    )
    assert report.commercial_authority_granted is False
    assert report.floor_area_authority_granted is False
    by_face = {r.room_face_id: r for r in report.room_links}
    assert by_face["rf-101"].linked_room_name == "COOL ROOM"
    # Cross-revision room must fail closed (never inherit rev-1 legend name)
    assert by_face["rf-stale"].linked_room_name is None

    for bad_report in (
        SimpleNamespace(commercial_authority_granted=True, floor_area_authority_granted=False),
        SimpleNamespace(commercial_authority_granted=False, floor_area_authority_granted=True),
    ):
        with patch(
            "pb_source_room_legend_linkage_shadow.link_room_legend_to_physical_rooms",
            return_value=bad_report,
        ):
            with pytest.raises(RuntimeError, match="never grant commercial authority"):
                build_room_legend_linkage_consumer_shadow(
                    legend_rows=legend_rows,
                    room_faces=(room_match,),
                    number_callouts=(callout_ok,),
                )


def test_live_room_finish_rcp_handoff_bridge_two_styles_and_authority_guard() -> None:
    room_commercial = CrossViewRoomCeilingLinkInput(
        physical_room_id="room-cold",
        document_id="doc-commercial",
        revision_id="rev-1",
        source_sha256=_SHA_A,
        floor_plan_page_id="1",
        floor_plan_viewport_id="vp-plan",
        canonical_floor_id="floor-cold",
        explicit_room_label="COOL ROOM",
        rcp_zone_id="zone-cold",
    )
    room_residential = CrossViewRoomCeilingLinkInput(
        physical_room_id="room-office",
        document_id="doc-commercial",
        revision_id="rev-1",
        source_sha256=_SHA_A,
        floor_plan_page_id="1",
        floor_plan_viewport_id="vp-plan",
        canonical_floor_id="floor-office",
        explicit_room_label="OFFICE",
        rcp_zone_id=None,
    )
    lineage = RcpLineageRef(
        document_id="doc-commercial",
        revision_id="rev-1",
        source_sha256=_SHA_A,
        page_id="2",
        viewport_id="vp-rcp",
    )
    zone = RcpCeilingZonePolygon(
        zone_id="zone-cold",
        lineage=lineage,
        polygon_pdf_pts=_SQUARE,
    )
    bubble = RcpMaterialHeightBubble(
        bubble_id="bub-cold",
        lineage=lineage,
        anchor_pt=(50.0, 50.0),
        lines=("CL1", "2400"),
    )
    packet = build_room_finish_rcp_handoff_consumer_shadow(
        rooms=(room_commercial, room_residential),
        rcp_zones=(zone,),
        rcp_bubbles=(bubble,),
    )
    assert packet.commercial_authority_granted is False
    assert packet.shadow_only is True
    by_room = {r.physical_room_id: r for r in packet.records}
    assert set(by_room.keys()) == {"room-cold", "room-office"}
    assert by_room["room-cold"].rcp_ceiling_height_mm == 2400
    assert by_room["room-office"].rcp_ceiling_height_mm is None

    for bad_packet in (
        SimpleNamespace(commercial_authority_granted=True, shadow_only=True),
        SimpleNamespace(commercial_authority_granted=False, shadow_only=False),
    ):
        with patch(
            "pb_source_room_finish_rcp_handoff_shadow.assemble_room_finish_rcp_handoff_shadow",
            return_value=bad_packet,
        ):
            with pytest.raises(RuntimeError, match="never grant commercial authority"):
                build_room_finish_rcp_handoff_consumer_shadow(rooms=(room_commercial,))
