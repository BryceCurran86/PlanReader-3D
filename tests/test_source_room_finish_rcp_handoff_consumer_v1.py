"""Order 7 consumer tests: generic room legend, green exclusion/epoxy, RCP distinct heights & Gap C."""

from __future__ import annotations

from pathlib import Path

from pb_source_green_exclusion_epoxy_linkage_shadow import (
    FinishLegendDefinitionInput,
    FloorExclusionRoomCandidate,
    FloorFinishLabelObservation,
)
from pb_source_green_hatch_room_exclusion import SourceGreenHatchRoomWitness
from pb_source_rcp_bubble_height_material_shadow import (
    RcpCeilingZonePolygon,
    RcpLineageRef,
    RcpMaterialHeightBubble,
)
from pb_source_room_finish_rcp_handoff_shadow import (
    CrossViewRoomCeilingLinkInput,
    assemble_room_finish_rcp_handoff_shadow,
)
from pb_source_room_legend_linkage_shadow import (
    PhysicalRoomFaceCandidate,
    RoomLegendTableRowInput,
    RoomNumberBubbleCandidate,
)
from tools.audit_no_job_specific_shared_rules import audit_shared_source


_SHA = "2" * 64


def test_generic_cross_view_room_finish_rcp_handoff_addresses_gap_c_and_preserves_distinct_heights() -> None:
    """Verifies generic cross-view pairing decoupled from single block_no, preserving distinct heights & green quarantine."""
    rcp_lin = RcpLineageRef("doc_arch", "rev_01", _SHA, "page_09", "vp_rcp")

    rooms = (
        CrossViewRoomCeilingLinkInput("room_01", "doc_arch", "rev_01", _SHA, "page_07", "vp_plan"),
        CrossViewRoomCeilingLinkInput("room_02", "doc_arch", "rev_01", _SHA, "page_07", "vp_plan", explicit_room_label="PREP ZONE"),
        CrossViewRoomCeilingLinkInput("room_03_cold", "doc_arch", "rev_01", _SHA, "page_07", "vp_plan", canonical_floor_id="floor_03_cold", explicit_room_label="COLD STORAGE"),
        CrossViewRoomCeilingLinkInput("room_04_raked", "doc_arch", "rev_01", _SHA, "page_07", "vp_plan", explicit_room_label="ENTRY FOYER"),
    )

    # Numbered bubble + room legend resolves room_01 -> "BACK OFFICE"
    legend_rows = (
        RoomLegendTableRowInput("doc_arch", "rev_01", _SHA, "page_07", "vp_legend", ("obs_hdr",), ("NO.", "ROOM NAME")),
        RoomLegendTableRowInput("doc_arch", "rev_01", _SHA, "page_07", "vp_legend", ("obs_101",), ("101", "BACK OFFICE")),
    )
    room_faces = (
        PhysicalRoomFaceCandidate(
            room_face_id="room_01",
            document_id="doc_arch",
            revision_id="rev_01",
            source_sha256=_SHA,
            plan_page_id="page_07",
            plan_viewport_id="vp_plan",
            polygon_pdf_pts=((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)),
            room_face_evidence_ids=("ev_face_01",),
        ),
    )
    room_bubbles = (
        RoomNumberBubbleCandidate("bub_101", "doc_arch", "rev_01", _SHA, "page_07", "vp_plan", "obs_bub_101", "101", (50.0, 50.0)),
    )

    # Green hatch witness on room_03_cold + epoxy/coldroom specialty finish label
    excl_rooms = (
        FloorExclusionRoomCandidate(
            canonical_floor_id="floor_03_cold",
            physical_floor_surface_id="phys_floor_03_cold",
            source_room_face_record_id="room_03_cold",
            document_id="doc_arch",
            revision_id="rev_01",
            source_sha256=_SHA,
            page_id="page_07",
            viewport_id="vp_plan",
            polygon_pdf_pts=((230.0, 0.0), (320.0, 0.0), (320.0, 100.0), (230.0, 100.0)),
        ),
    )
    green_witness = SourceGreenHatchRoomWitness(
        witness_id="gw_03",
        canonical_floor_id="floor_03_cold",
        physical_floor_surface_id="phys_floor_03_cold",
        source_room_face_record_id="room_03_cold",
        source_sha256=_SHA,
        page_id="page_07",
        native_path_ids=(101, 102, 103),
    )
    finish_labels = (
        FloorFinishLabelObservation(
            observation_id="obs_ep1",
            document_id="doc_arch",
            revision_id="rev_01",
            source_sha256=_SHA,
            page_id="page_07",
            viewport_id="vp_plan",
            raw_text="EP1",
            anchor_pt_pdf_pts=(275.0, 50.0),
        ),
        FloorFinishLabelObservation(
            observation_id="obs_cold_txt",
            document_id="doc_arch",
            revision_id="rev_01",
            source_sha256=_SHA,
            page_id="page_07",
            viewport_id="vp_plan",
            raw_text="EPOXY COLDROOM FLOOR",
            anchor_pt_pdf_pts=(275.0, 62.0),
        ),
    )
    finish_defs = (
        FinishLegendDefinitionInput(
            definition_id="def_ep1",
            document_id="doc_arch",
            revision_id="rev_01",
            source_sha256=_SHA,
            legend_page_id="page_11",
            finish_code="EP1",
            description="Epoxy resin non-slip coldroom floor finish",
        ),
    )

    # Separate RCP zones with explicitly distinct heights (2700, 3000, raked 2700-3400)
    rcp_zones = (
        RcpCeilingZonePolygon("rcp_z_office", rcp_lin, ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0))),
        RcpCeilingZonePolygon("rcp_z_prep", rcp_lin, ((110.0, 0.0), (220.0, 0.0), (220.0, 100.0), (110.0, 100.0))),
        RcpCeilingZonePolygon("rcp_z_cold", rcp_lin, ((230.0, 0.0), (320.0, 0.0), (320.0, 100.0), (230.0, 100.0))),
        RcpCeilingZonePolygon("rcp_z_entry", rcp_lin, ((0.0, 110.0), (120.0, 110.0), (120.0, 200.0), (0.0, 200.0))),
    )
    rcp_bubbles = (
        RcpMaterialHeightBubble("rb_1", rcp_lin, (50.0, 50.0), ("GRID", "CH 2700")),
        RcpMaterialHeightBubble("rb_2", rcp_lin, (165.0, 50.0), ("WFPB", "3000 AFFL")),
        RcpMaterialHeightBubble("rb_3", rcp_lin, (275.0, 50.0), ("FPB", "2400")),
        RcpMaterialHeightBubble("rb_4", rcp_lin, (60.0, 155.0), ("CL02", "RAKED 2700-3400")),
    )
    zone_labels = {
        "rcp_z_office": "BACK OFFICE",
        "rcp_z_prep": "PREP ZONE",
        "rcp_z_cold": "COLD STORAGE",
        "rcp_z_entry": "ENTRY FOYER",
    }

    pkt = assemble_room_finish_rcp_handoff_shadow(
        rooms=rooms,
        legend_rows=legend_rows,
        room_faces=room_faces,
        room_number_bubbles=room_bubbles,
        exclusion_room_candidates=excl_rooms,
        green_hatch_witnesses=(green_witness,),
        floor_finish_label_observations=finish_labels,
        finish_legend_definitions=finish_defs,
        rcp_zones=rcp_zones,
        rcp_bubbles=rcp_bubbles,
        rcp_zone_label_by_id=zone_labels,
    )
    by_room = {r.physical_room_id: r for r in pkt.records}

    assert by_room["room_01"].resolved_room_name == "BACK OFFICE"
    assert by_room["room_01"].room_name_source == "room_legend_bubble"
    assert by_room["room_01"].cross_view_ceiling_ready is True
    assert by_room["room_01"].rcp_material_code == "GRID"
    assert by_room["room_01"].rcp_ceiling_height_mm == 2700

    assert by_room["room_02"].cross_view_ceiling_ready is True
    assert by_room["room_02"].rcp_material_code == "WFPB"
    assert by_room["room_02"].rcp_ceiling_height_mm == 3000

    assert by_room["room_03_cold"].green_hatch_ordinary_excluded is True
    assert by_room["room_03_cold"].cross_view_ceiling_ready is False
    assert "ordinary_ceiling_quarantined_in_green_hatched_room" in by_room["room_03_cold"].blocking_reasons
    assert "EP1" in by_room["room_03_cold"].specialty_finish_codes

    assert by_room["room_04_raked"].cross_view_ceiling_ready is True
    assert by_room["room_04_raked"].rcp_raked_height_range_mm == (2700, 3400)

    assert pkt.distinct_ceiling_heights_preserved_mm == (2400, 2700, 3000)
    assert pkt.green_excluded_room_count == 1
    assert pkt.cross_view_ceiling_ready_count == 3
    assert pkt.commercial_authority_granted is False


def test_cross_revision_rcp_pairing_rejected() -> None:
    rcp_lin_other_rev = RcpLineageRef("doc_arch", "rev_02", _SHA, "page_09", "vp_rcp")
    rooms = (
        CrossViewRoomCeilingLinkInput("room_x", "doc_arch", "rev_01", _SHA, "page_07", "vp_plan", explicit_room_label="OFFICE", rcp_zone_id="z_rev2"),
    )
    rcp_zones = (RcpCeilingZonePolygon("z_rev2", rcp_lin_other_rev, ((0.0, 0.0), (50.0, 0.0), (50.0, 50.0), (0.0, 50.0))),)
    rcp_bubbles = (RcpMaterialHeightBubble("b1", rcp_lin_other_rev, (25.0, 25.0), ("GRID", "2700")),)
    pkt = assemble_room_finish_rcp_handoff_shadow(rooms=rooms, rcp_zones=rcp_zones, rcp_bubbles=rcp_bubbles)
    assert pkt.records[0].cross_view_ceiling_ready is False
    assert "cross_revision_rcp_ceiling_pairing_rejected" in pkt.records[0].blocking_reasons


def test_handoff_shared_source_audit_is_clean() -> None:
    p = Path(__file__).resolve().parent.parent / "pb_source_room_finish_rcp_handoff_shadow.py"
    assert audit_shared_source(p.read_text(encoding="utf-8"), filename=p.name) == ()
