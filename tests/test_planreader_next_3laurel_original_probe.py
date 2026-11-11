"""Protected genuine 3Laurel page-3 smoke: verify failure, never mint quantities.

The user's original is provisioned out-of-tree using the same frozen source
resolver as the 3Laurel benchmark tests. No private PDF enters this branch.
"""
from __future__ import annotations

import math

from planreader_next.building import measure_building_components
from planreader_next.engine import load_native_page
from planreader_next.suggest import suggest_room_bindings
from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel


def test_real_3laurel_floor_page_has_source_lines_but_no_rectangle_rooms():
    page = load_native_page(require_original_3laurel(), 2)
    assert page.source_sha256 == ORIGINAL_SHA256
    assert len(page.words) > 1000
    assert len(page.segments) > 9000
    assert page.rectangles == ()
    tokens = {word.text.strip().upper() for word in page.words}
    assert {"VINYL", "TILES", "CONCRETE", "DOOR"} <= tokens

    proposed = suggest_room_bindings(page)
    assert proposed["rooms"] == []
    assert proposed["human_internal_finished_face_review_required"] is True
    assert any(a["reason_code"] == "native_segment_faces_require_boundary_review"
               for a in proposed["abstentions"])


def test_real_3laurel_unreviewed_multifamily_page_abstains_without_issued_rows():
    page = load_native_page(require_original_3laurel(), 2)
    source_line = next(
        segment for segment in page.segments
        if segment.kind == "line" and
        math.hypot(segment.x2 - segment.x1, segment.y2 - segment.y1) > 20
    )
    # All claims are deliberately unreviewed. Do not impersonate source
    # authentication by setting a "reviewed" flag in an automated test.
    request = {
        "project_id": "au_qld_3laurel",
        "revision_id": "Rev3_08.05.26",
        "source_sha256": page.source_sha256,
        "rooms": [{
            "room_id": "3laurel-unreviewed-floor", "page_index": 2,
            "rectangle_ref": "missing-original-rectangle",
            "boundary_basis": "REVIEW_REQUIRED",
        }],
        "ceilings": [{
            "ceiling_id": "3laurel-unreviewed-ceiling", "room_id": "unknown",
            "page_index": 2, "rectangle_ref": "missing-rcp-zone",
            "boundary_basis": "REVIEW_REQUIRED",
        }],
        "walls": [{
            "wall_id": "3laurel-unreviewed-wall", "page_index": 2,
            "face_segment_ref": source_line.ref,
            "face_basis": "REVIEW_REQUIRED",
            "height_source_page_index": 2, "deduct_door_ids": ["unknown-door"],
        }],
        "doors": [{
            "door_id": "unknown-door", "host_wall_id": "3laurel-unreviewed-wall",
            "plan_page_index": 2, "schedule_page_index": 2,
            "opening_segment_ref": source_line.ref, "opening_reviewed": False,
            "frame_reviewed": True,
        }],
    }
    result = measure_building_components({2: page}, request)
    assert result["quantities"] == []
    assert result["official_score"] is None
    assert result["commercial_publishable"] is False
    assert {a["family"] for a in result["abstentions"]} == {
        "floor_finish", "ceiling_finish", "wall_finish", "door", "door_frame"
    }
    assert all(q.get("benchmark_credit") is not True for q in result["quantities"])
