"""End-to-end height source evidence to exact plan-face candidate handoff."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import pytest

from planreader_next.engine import NativePage, NativeWord, NativeSegment, SourceConflict, load_native_page
from planreader_next.height_face_scope import (
    section_height_to_plan_face_candidates,
    reviewed_rcp_height_to_plan_face_candidates,
    reconcile_face_height_sources,
)
from tests.test_planreader_next_section_scope import _fixtures
from tests.test_planreader_next_rcp_zone_scope import _rcp_fixture, _plan_fixture


def _fake_plan_and_enclosure():
    plan, section, regions = _fixtures()
    extra_words = (
        NativeWord("bed-word", "BED", (89, 168, 110, 178)),
        NativeWord("robe-word", "ROBE", (89, 305, 117, 314)),
    )
    extra_segments = (
        NativeSegment("bed-face", "line", 75, 120, 130, 120),
        NativeSegment("robe-face", "line", 80, 290, 110, 290),
    )
    plan = replace(plan, words=plan.words + extra_words, segments=plan.segments + extra_segments)
    faces = [
        {
            "item_id": f"room-face-{name}",
            "region_id": name,
            "face_segment_ref": f"{name}-face",
            "face_role_hypothesis": "interior_finished_face_candidate",
            "interrupted_by_opening_ids": [f"temporary-{name}"],
            "topology_only": True,
            "physical_wall_authenticated": False,
        }
        for name in ("bed", "robe")
    ]
    locators = [
        {
            "source_sha256": plan.source_sha256,
            "page_index": plan.page_index,
            "region_id": name,
            "room_label_word_refs": [f"{name}-word"],
            "room_label_texts": [name.upper()],
            "wall_face_item_ids": [f"room-face-{name}"],
            "topology_only": True,
        }
        for name in ("bed", "robe")
    ]
    enclosure = {
        "regions": regions,
        "source_wall_inventory": {
            "source_sha256": plan.source_sha256, "page_index": plan.page_index,
            "topology_only": True, "region_locators": locators, "faces": faces,
        },
    }
    return plan, section, enclosure


def test_section_height_scopes_only_source_attested_intersecting_regions_and_faces():
    plan, section, enclosure = _fake_plan_and_enclosure()
    out = section_height_to_plan_face_candidates(plan, section, enclosure)
    assert out["section_height_mm_source_candidate"] == "2700"
    assert out["section_region_crossings"] == 2
    assert len(out["face_height_scope_candidates"]) == 2
    assert {x["face_item_id"] for x in out["face_height_scope_candidates"]} == {
        "room-face-bed", "room-face-robe",
    }
    assert all(x["height_source_receipt"]["height_mm"] == "2700"
               for x in out["face_height_scope_candidates"])
    assert all(x["section_cut_crosses_region"] for x in out["face_height_scope_candidates"])
    assert all(x["wall_finish_area_eligible"] is False for x in out["face_height_scope_candidates"])
    assert all(x["hosted_opening_authenticated"] is False for x in out["face_height_scope_candidates"])
    assert all(not x["commercial_publishable"] for x in out["face_height_scope_candidates"])


def test_wrong_region_label_or_unowned_wall_cannot_receive_height():
    plan, section, enclosure = _fake_plan_and_enclosure()
    enclosure["source_wall_inventory"]["region_locators"][0]["room_label_word_refs"] = ["not-source"]
    result = section_height_to_plan_face_candidates(plan, section, enclosure)
    assert [x["face_item_id"] for x in result["face_height_scope_candidates"]] == ["room-face-robe"]
    assert {
        "region_id": "bed", "reason_code": "section_region_or_label_identity_not_unique"
    } in result["unresolved_regions"]


def test_wrong_page_or_source_inventory_cannot_borrow_height():
    plan, section, enclosure = _fake_plan_and_enclosure()
    with pytest.raises(SourceConflict, match="height_wall_inventory_source_mismatch"):
        section_height_to_plan_face_candidates(
            plan, section, dict(enclosure, source_wall_inventory={
                **enclosure["source_wall_inventory"], "source_sha256": "0"*64
            })
        )
    with pytest.raises(SourceConflict, match="section_cut_cross_page_source_mismatch"):
        section_height_to_plan_face_candidates(
            plan, replace(section, source_sha256="f"*64), enclosure,
        )


def _synthetic_rcp_enclosure():
    plan, rcp = _plan_fixture(), _rcp_fixture()
    enclosure = {
        "regions": [],
        "source_wall_inventory": {
            "source_sha256": plan.source_sha256, "page_index": plan.page_index,
            "topology_only": True,
            "region_locators": [{
                "source_sha256": plan.source_sha256, "page_index": plan.page_index,
                "region_id": "office-region",
                "room_label_word_refs": ["room-word"],
                "room_label_texts": ["OFFICE"],
                "wall_face_item_ids": ["office-face-id"],
            }],
            "faces": [{
                "item_id": "office-face-id", "region_id": "office-region",
                "face_segment_ref": "wall-face", "topology_only": True,
                "physical_wall_authenticated": False,
                "interrupted_by_opening_ids": ["virtual-door"],
            }],
        },
    }
    selection = {
        "region_id": "office-region",
        "face_item_id": "office-face-id",
        "room_label_word_ref": "room-word",
        "rcp_source_rectangle_ref": "zone:grid",
        "rcp_height_word_ref": "word:b1:l0:w0:i0",
        "cross_sheet_correspondence_reviewed": True,
    }
    return plan, rcp, enclosure, selection


def test_rcp_height_matches_exact_face_and_one_source_material_zone_only():
    plan, rcp, enclosure, selection = _synthetic_rcp_enclosure()
    result = reviewed_rcp_height_to_plan_face_candidates(plan, rcp, enclosure, [selection])
    assert not result["abstentions"]
    assert len(result["face_height_scope_candidates"]) == 1
    face = result["face_height_scope_candidates"][0]
    assert face["height_mm"] == "2400"
    assert face["ceiling_material_code_candidate"] == "GRID"
    assert face["region_id"] == "office-region"
    assert face["plan_face_segment_ref"] == "wall-face"
    assert face["interrupted_by_opening_ids_topology_only"] == ["virtual-door"]
    assert face["wall_finish_area_eligible"] is False
    assert result["physical_ceiling_zone_authenticated"] is False
    assert result["official_score"] is None


def test_rcp_review_flag_missing_wrong_room_or_competing_zone_abstains():
    plan, rcp, enclosure, selection = _synthetic_rcp_enclosure()
    without = reviewed_rcp_height_to_plan_face_candidates(
        plan, rcp, enclosure, [dict(selection, cross_sheet_correspondence_reviewed=False)],
    )
    assert not without["face_height_scope_candidates"]
    assert without["abstentions"][0]["reason_code"] == "cross_sheet_room_zone_correspondence_not_reviewed"

    wrong_label = reviewed_rcp_height_to_plan_face_candidates(
        plan, rcp, enclosure, [dict(selection, room_label_word_ref="other-room")],
    )
    assert not wrong_label["face_height_scope_candidates"]
    assert wrong_label["abstentions"][0]["reason_code"] == "rcp_height_label_not_owned_by_selected_region"

    duplicate = reviewed_rcp_height_to_plan_face_candidates(
        plan, rcp, enclosure,
        [selection, dict(selection, rcp_source_rectangle_ref="zone:fpb",
                         rcp_height_word_ref="word:b2:l0:w0:i2")],
    )
    assert not duplicate["face_height_scope_candidates"]
    assert duplicate["abstentions"][0]["reason_code"] == "competing_rcp_height_zone_claims"


def test_real_3laurel_native_wall_region_height_link_stays_noncommercial():
    import os
    original = os.environ.get("PLANREADER_3LAUREL_ORIGINAL_PDF")
    if not original or not Path(original).is_file():
        pytest.skip("ORIGINAL_SOURCE_NOT_RUN")
    from planreader_next.enclosure import propose_room_enclosures
    plan = load_native_page(Path(original), 2)
    section = load_native_page(Path(original), 6)
    assert plan.source_sha256 == "014e9f68b377bef4fb556de61b83a94388792dfa4bfb8ea981644f9c323e9e2e"
    enclosure = propose_room_enclosures(plan, Path(original))
    out = section_height_to_plan_face_candidates(plan, section, enclosure)
    print("REAL_SOURCE_SECTION_WALL_CANDIDATES", len(out["face_height_scope_candidates"]))
    print("REAL_SOURCE_HEIGHT_SCOPE_ABSTENTIONS", out["unresolved_regions"])
    assert out["section_region_crossings"] == 3
    assert out["section_height_mm_source_candidate"] == "2700"
    assert len(out["face_height_scope_candidates"]) == 7
    assert sum(x["section_cut_crosses_this_face"] for x in out["face_height_scope_candidates"]) == 1
    assert len(out["unresolved_regions"]) == 1
    assert out["unresolved_regions"][0]["reason_code"] == "source_region_not_in_wall_inventory"
    assert out["face_height_scope_candidates"]
    assert all(not row["wall_finish_area_eligible"] for row in out["face_height_scope_candidates"])
    assert out["official_score"] is None and out["commercial_publishable"] is False



def test_section_and_rcp_disagreement_refuses_wall_height_promotion():
    plan, section, enclosure = _fake_plan_and_enclosure()
    rcp = replace(_rcp_fixture(), source_sha256=plan.source_sha256)
    section_scope = section_height_to_plan_face_candidates(
        plan, section, enclosure,
    )
    rcp_scope = reviewed_rcp_height_to_plan_face_candidates(
        plan, rcp, enclosure, [{
            "region_id": "bed",
            "face_item_id": "room-face-bed",
            "room_label_word_ref": "bed-word",
            "rcp_source_rectangle_ref": "zone:grid",
            "rcp_height_word_ref": "word:b1:l0:w0:i0",
            "cross_sheet_correspondence_reviewed": True,
        }],
    )
    assert len(rcp_scope["face_height_scope_candidates"]) == 1
    mixed = reconcile_face_height_sources(section_scope, rcp_scope)
    assert len(mixed["unique_source_lane_face_candidates"]) == 1
    assert mixed["unique_source_lane_face_candidates"][0]["face_item_id"] == "room-face-robe"
    assert mixed["abstentions"] == [{
        "face_item_id": "room-face-bed",
        "reason_code": "multiple_height_sources_require_ceiling_zone_authority",
        "height_source_kinds": ["section", "rcp"],
        "printed_height_mm_candidates": ["2400", "2700"],
    }]
    assert not mixed["wall_finish_area_eligible"]
    assert not mixed["commercial_publishable"]


def test_owner_confirmed_standard_allows_reviewed_local_rcp_to_override():
    from tests.test_planreader_next_height_evidence import _section
    from planreader_next.project_height_policy import resolve_project_standard_height
    plan, section, enclosure = _fake_plan_and_enclosure()
    rcp = replace(_rcp_fixture(), source_sha256=plan.source_sha256)
    section_packet = section_height_to_plan_face_candidates(plan, section, enclosure)
    rcp_packet = reviewed_rcp_height_to_plan_face_candidates(
        plan, rcp, enclosure, [{
            "region_id": "bed", "face_item_id": "room-face-bed",
            "room_label_word_ref": "bed-word",
            "rcp_source_rectangle_ref": "zone:grid",
            "rcp_height_word_ref": "word:b1:l0:w0:i0",
            "cross_sheet_correspondence_reviewed": True,
        }],
    )
    section_source = _section()
    section_source = replace(section_source, source_sha256=plan.source_sha256)
    from planreader_next.height_evidence import section_ffl_fcl_heights
    receipt = section_ffl_fcl_heights(section_source)[0]
    policy = {
        "rule": "all_walls_and_ceilings_unless_otherwise_stated",
        "owner_authorized": True,
        "project_id": "3Laurel",
        "source_sha256": plan.source_sha256,
        "section_page_index": section_source.page_index,
        "source_height_receipt": receipt,
    }
    standard = resolve_project_standard_height(
        {section_source.page_index:section_source},
        "3Laurel",plan.source_sha256,policy,
    )
    merged = reconcile_face_height_sources(
        section_packet,rcp_packet,owner_authorized_project_standard=standard,
    )
    assert len(merged["unique_source_lane_face_candidates"])==2
    mapped={x["face_item_id"]:x for x in merged["unique_source_lane_face_candidates"]}
    assert mapped["room-face-bed"]["height_mm_source_candidate"]=="2400"
    assert mapped["room-face-bed"]["height_policy_basis"]=="LOCAL_RCP_OVERRIDES_OWNER_AUTHORIZED_STANDARD"
    assert mapped["room-face-robe"]["height_mm_source_candidate"]=="2700"
    assert not merged["abstentions"]
    assert not merged["wall_finish_area_eligible"]


def test_height_source_reconciliation_must_share_one_source_and_never_accept_promotion_claim():
    plan, section, enclosure = _fake_plan_and_enclosure()
    section_scope = section_height_to_plan_face_candidates(
        plan, section, enclosure,
    )
    rcp_packet = {
        "source_sha256": plan.source_sha256,
        "plan_page_index": plan.page_index,
        "face_height_scope_candidates": [],
    }
    match = reconcile_face_height_sources(section_scope, rcp_packet)
    assert len(match["unique_source_lane_face_candidates"]) == 2
    assert not match["commercial_publishable"]
    with pytest.raises(SourceConflict, match="height_sources_cross_document_or_plan_page_mismatch"):
        reconcile_face_height_sources(
            section_scope, dict(rcp_packet, source_sha256="0"*64),
        )
    forged = dict(section_scope)
    forged["face_height_scope_candidates"] = [
        dict(section_scope["face_height_scope_candidates"][0],
             wall_finish_area_eligible=True),
    ]
    with pytest.raises(SourceConflict, match="height_source_candidate_not_shadow_only"):
        reconcile_face_height_sources(forged, rcp_packet)
