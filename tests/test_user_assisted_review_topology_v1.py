"""Guided-review marks reshape the canonical room topology as user-assisted evidence only.

Synthetic only; no private source. Marks reach the preview's room tracer through its ``barrier_view`` hook: wall and door marks
close rooms, rejections need exactly one target, finish lines split finish regions, exclusions flag, outlines compare. The
automatic result never changes and nothing is authenticated, measured or published.
"""
from __future__ import annotations

import copy
import hashlib
import json
import random
from dataclasses import asdict

import fitz
import pytest

import pb_new_source_trace_preview as canonical
import pb_next_wall_ring_preview as tracer
import pb_user_assisted_review_topology as consumer
from pb_native_page_frame import native_page_frame
from pb_user_assisted_review_topology import (
    BarrierRecorder,
    ReviewPacket,
    ReviewPacketError,
    UserMark,
    build_review_block,
    plan_review,
    read_review_packet,
)

SHA = "ab" * 32
BLACK = (0.0, 0.0, 0.0)
AUTHORITY_FALSE = ("physical_wall_authenticated", "measurement_authorized", "quantity_authorized", "commercial_publishable",
                   "frozen_benchmark_allowed")


def _bar(x0, y0, x1, y1):
    return {"layer": "", "fill": BLACK, "color": None, "width": 0.0, "items": [("re", fitz.Rect(x0, y0, x1, y1), 1)]}


def _line(a, b, width=0.5):
    return {"layer": "", "fill": None, "color": BLACK, "width": width, "items": [("l", fitz.Point(*a), fitz.Point(*b))]}


def _missing_wall_room():
    """A 200 x 150 room of 6 pt walls whose bottom wall is missing between x=160 and x=190."""
    return [_bar(100, 100, 300, 106), _bar(100, 106, 106, 250), _bar(294, 106, 300, 250),
            _bar(106, 244, 160, 250), _bar(190, 244, 294, 250)]


def _two_rooms_missing_partition():
    """A 300 x 150 outline with a doorway in the bottom wall and a partition that was never drawn."""
    return [_bar(100, 100, 400, 106), _bar(100, 106, 106, 250), _bar(394, 106, 400, 250),
            _bar(106, 244, 130, 250), _bar(160, 244, 394, 250), _bar(250, 106, 256, 130)]


def _mark(identity, category, *points):
    role = consumer.LINE_ROLES.get(category) or consumer.POLYGON_ROLES.get(category) or consumer.ROLE_UNSUPPORTED
    return UserMark(identity, category, role, tuple((float(x), float(y)) for x, y in points))


def _packet(*marks):
    return ReviewPacket(1, "c" * 64, tuple(sorted(marks, key=lambda m: m.correction_id)))


def _trace(rows, **kw):
    return tracer.build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0, stroke_pair_wall_faces=True, **kw)


def _assisted(rows, *marks, endpoint_reviews=()):
    packet, recorder = _packet(*marks), BarrierRecorder()
    automatic = _trace(rows, barrier_view=recorder)
    plan = plan_review(packet, recorder)
    user = _trace(rows, barrier_view=plan)
    block = build_review_block(packet, plan, source_sha256=SHA, page_index=0, automatic_rings=automatic.rings,
                               user_rings=user.rings, endpoint_reviews=endpoint_reviews)
    return automatic, user, block


def _rooms(result):
    return [r for r in result.rings if r.status.value == "candidate"]


def _outcome(block, identity):
    return next(m for m in block["marks"] if m["correction_id"] == identity)


def test_recording_the_pieces_changes_nothing():
    for rows in (_missing_wall_room(), _two_rooms_missing_partition()):
        plain, recorded = _trace(rows), _trace(rows, barrier_view=BarrierRecorder())
        assert [r.record_id for r in plain.rings] == [r.record_id for r in recorded.rings]
        assert [c.closure_id for c in plain.closures] == [c.closure_id for c in recorded.closures]
        assert plain.status is recorded.status and plain.reason_codes == recorded.reason_codes


def test_a_user_wall_closes_a_room_with_a_missing_wall_piece():
    automatic, user, block = _assisted(_missing_wall_room(), _mark("w1", "external_wall", (159, 247), (191, 247)))
    assert not _rooms(automatic)
    (room,) = _rooms(user)
    assert any(o.startswith("user_review_mark:w1") for owners in room.edge_owner_ids for o in owners)
    assert block["status"] == "applied" and block["user_assisted_room_count"] == 1 and block["automatic_room_count"] == 0
    assert block["rooms"][0]["user_mark_ids"] == ["w1"] and block["rooms"][0]["same_as_automatic"] is False
    assert _outcome(block, "w1")["outcome"] == "applied" and _outcome(block, "w1")["role"] == "user_wall"
    assert _outcome(block, "w1")["bounds_room_ids"] == [room.record_id]
    assert block["user_assisted"] is True and block["automatic_result_unchanged"] is True
    for flag in AUTHORITY_FALSE:
        assert block[flag] is False, flag


def test_a_partition_wall_and_a_temporary_door_closure_make_two_rooms():
    rows = _two_rooms_missing_partition()
    automatic, user, block = _assisted(
        rows,
        _mark("p", "internal_wall", (253, 130), (253, 245)),
        _mark("d", "swing_door", (129, 247), (161, 247)),
    )
    assert not _rooms(automatic) and len(_rooms(user)) == 2
    assert _outcome(block, "d")["role"] == "user_temporary_closure" and _outcome(block, "p")["role"] == "user_wall"
    assert all("p" in room["user_mark_ids"] for room in block["rooms"])
    assert sum("d" in room["user_mark_ids"] for room in block["rooms"]) == 1


@pytest.mark.parametrize("ends,joined,rooms", [
    ((161.0, 189.0), 2, 1),   # 1 pt short at both ends: within the 2.5 pt snap
    ((165.0, 189.0), 1, 0),   # 5 pt short at one end: left open and reported
    ((170.0, 180.0), 0, 0),
])
def test_a_line_joins_only_within_the_snap_and_open_ends_are_reported(ends, joined, rooms):
    _automatic, user, block = _assisted(_missing_wall_room(), _mark("w1", "external_wall", (ends[0], 247), (ends[1], 247)))
    assert len(_rooms(user)) == rooms
    outcome = _outcome(block, "w1")
    assert outcome["joined_end_count"] == joined
    assert len(outcome["open_end_points_pdf_pts"]) == 2 - joined
    assert sum(item["status"] == "user_mark_end_open" for item in block["residual_locations"]) == 2 - joined


def test_user_lines_may_join_each_other():
    # Two half walls that meet in the middle of the gap.
    _automatic, user, block = _assisted(
        _missing_wall_room(),
        _mark("a", "external_wall", (159, 247), (176, 247)),
        _mark("b", "external_wall", (175, 247), (191, 247)),
    )
    assert len(_rooms(user)) == 1 and _outcome(block, "a")["outcome"] == _outcome(block, "b")["outcome"] == "applied"


def _closed_by_threshold():
    return [*_missing_wall_room(), _line((160.0, 244.0), (190.0, 244.0))]


def test_a_reject_that_crosses_one_closure_removes_it():
    automatic, user, block = _assisted(_closed_by_threshold(), _mark("r", "reject_candidate", (175, 240), (175, 249)))
    assert len(_rooms(automatic)) == 1 and not _rooms(user)
    assert _outcome(block, "r") == {"correction_id": "r", "category": "reject_candidate", "role": "user_reject",
                                    "outcome": "applied", "removed_piece_count": 1}


@pytest.mark.parametrize("points,expected", [
    (((103, 90), (103, 260)), "unbound_ambiguous"),   # crosses the top and left walls
    (((200, 150), (220, 160)), "unbound_no_target"),
])
def test_a_reject_without_exactly_one_target_removes_nothing(points, expected):
    automatic, user, block = _assisted(_closed_by_threshold(), _mark("r", "reject_candidate", *points))
    assert _outcome(block, "r")["outcome"] == expected and _outcome(block, "r")["removed_piece_count"] == 0
    assert [r.record_id for r in user.rings] == [r.record_id for r in automatic.rings]


def test_exclusion_outline_and_finish_marks_annotate_without_changing_rooms():
    rows = _closed_by_threshold()
    automatic, user, block = _assisted(
        rows,
        _mark("x", "exclusion", (110, 110), (190, 110), (190, 240), (110, 240)),
        _mark("o", "room_outline", (106, 106), (294, 106), (294, 244), (106, 244)),
        _mark("f", "boundary", (200, 105), (200, 245)),
        _mark("n", "dimension_witness", (106, 120), (294, 120)),
        _mark("u", "mystery_category", (0, 0), (1, 1)),
    )
    assert [r.record_id for r in user.rings] == [r.record_id for r in automatic.rings]
    (room,) = block["rooms"]
    assert room["exclusion"] == "partly_excluded" and 0.4 < room["excluded_area_share"] < 0.46
    assert _outcome(block, "x")["outcome"] == "flagged" and _outcome(block, "x")["room_ids"] == [room["room_id"]]
    assert _outcome(block, "o")["matches"][0]["room_id"] == room["room_id"]
    assert _outcome(block, "o")["matches"][0]["overlap_over_union"] > 0.99
    assert _outcome(block, "f")["outcome"] == "applied" and len(block["finish_regions"]) == 2
    assert sum(r["area_pt2"] for r in block["finish_regions"]) == pytest.approx(room["area_pt2"], rel=0.01)
    assert _outcome(block, "n")["outcome"] == "not_geometry"
    assert _outcome(block, "u")["outcome"] == "unsupported_category"


def test_a_finish_line_that_does_not_cross_a_room_splits_nothing():
    _automatic, _user, block = _assisted(_closed_by_threshold(), _mark("f", "boundary", (150, 150), (160, 150)))
    assert _outcome(block, "f") == {"correction_id": "f", "category": "boundary", "role": "user_finish_boundary",
                                    "outcome": "no_split", "room_ids": []}
    assert block["finish_regions"] == []


def test_residual_locations_keep_only_unexplained_places_not_covered_by_a_user_mark():
    reviews = [
        {"status": "unmatched_raw_wall_ink_terminal_needs_post_opening_review", "endpoint_pdf_pts": [175.0, 247.0]},
        {"status": "unmatched_raw_wall_ink_terminal_needs_post_opening_review", "endpoint_pdf_pts": [300.0, 180.0]},
        {"status": "hosted_aperture_terminal", "endpoint_pdf_pts": [50.0, 50.0]},
    ]
    _automatic, _user, block = _assisted(_missing_wall_room(), _mark("w1", "external_wall", (159, 247), (191, 247)),
                                         endpoint_reviews=reviews)
    assert [(i["status"], i["endpoint_pdf_pts"]) for i in block["residual_locations"]] == [
        ("unmatched_raw_wall_ink_terminal_needs_post_opening_review", [300.0, 180.0])]


@pytest.mark.parametrize("partial", [
    ((159.0, 247.0), (172.0, 247.0)),  # covers only the left part of the interruption
    ((178.0, 247.0), (191.0, 247.0)),  # covers only the right part
    ((175.0, 246.0), (175.0, 249.0)),  # a stub in the middle
])
def test_a_gap_the_user_did_not_close_still_vetoes_its_room(partial):
    # An alcove behind the missing piece closes the free space, but the interruption in the wall is still unexplained.
    rows = [*_missing_wall_room(), _bar(154, 250, 160, 286), _bar(190, 250, 196, 286), _bar(160, 280, 190, 286)]
    automatic, user, _block = _assisted(
        rows, _mark("w", "internal_wall", (200, 106), (200, 244)), _mark("s", "internal_wall", *partial),
    )
    assert not _rooms(automatic) and len(automatic.rings) == 1
    assert sorted(r.status.value for r in user.rings) == ["abstained", "candidate"]
    held = next(r for r in user.rings if r.status.value == "abstained")
    assert held.reason_codes == (tracer.REASON_OPEN_GAP,) and held.bbox_pdf_pts[0] < 200


def test_mark_order_does_not_matter_and_nothing_is_mutated():
    marks = [_mark("p", "internal_wall", (253, 130), (253, 245)), _mark("d", "swing_door", (129, 247), (161, 247)),
             _mark("r", "reject_candidate", (10, 10), (12, 12))]
    rows = _two_rooms_missing_partition()
    before = copy.deepcopy(rows)
    _a, _u, first = _assisted(rows, *marks)
    shuffled = marks[:]
    random.Random(3).shuffle(shuffled)
    _a, _u, second = _assisted(rows, *shuffled)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True) and rows == before


# ------------------------------------------------------------------------------------------------ the packet

FRAME = {"rotation": 0, "native_width": 400.0, "native_height": 300.0}


def _raw_packet(corrections, *, sha=SHA, page_index=0, frame=FRAME, **overrides):
    body = {
        "schema_version": 1,
        "scope": {"workspace_id": 1, "page_id": 1, "pdf_page": page_index + 1, "source_sha256": sha, "image_sha256": "c" * 64},
        "review_revision": 2, "coordinate_frame": dict(frame), "image_render_kind": "original_full_page", "raster_zoom": 1.0,
        "image_dimensions_px": [400, 300], "corrections": corrections, "unbound_review_answers": {},
        "affected_stage_candidates": [], "status": "USER_CORRECTIONS_PENDING_CONSUMER", "automatic_source_verified": False,
        "commercial_projection_allowed": False, "frozen_benchmark_allowed": False, "topology_recalculated": False,
    }
    body.update(overrides)
    body["packet_sha256"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    return body


def _correction(identity="w1", category="external_wall", points=((159.0, 247.0), (191.0, 247.0)), kind="line"):
    return {"correction_id": identity, "category": category, "kind": kind,
            "native_points_pdf_pts": [list(p) for p in points], "requires_candidate_binding": False,
            "authority": "user_selected_geometry"}


def _read(packet):
    return read_review_packet(packet, source_sha256=SHA, page_index=0, coordinate_frame=FRAME)


def test_a_good_packet_reads_its_marks_in_a_stable_order():
    packet = _read(_raw_packet([_correction("b"), _correction("a", "window")]))
    assert packet.review_revision == 2 and [m.correction_id for m in packet.marks] == ["a", "b"]
    assert [m.role for m in packet.marks] == ["user_temporary_closure", "user_wall"]


@pytest.mark.parametrize("mutate,reason", [
    (lambda p: p.update(review_revision=3), "review_packet_digest_mismatch"),
    (lambda p: p["corrections"][0].update(category="internal_wall"), "review_packet_digest_mismatch"),
])
def test_a_packet_edited_after_it_was_sealed_is_rejected(mutate, reason):
    packet = _raw_packet([_correction()])
    mutate(packet)
    with pytest.raises(ReviewPacketError, match=reason):
        _read(packet)


@pytest.mark.parametrize("overrides,reason", [
    ({"status": "APPLIED"}, "review_packet_schema_or_status_unsupported"),
    ({"schema_version": 2}, "review_packet_schema_or_status_unsupported"),
    ({"commercial_projection_allowed": True}, "review_packet_claims_authority"),
    ({"automatic_source_verified": True}, "review_packet_claims_authority"),
    ({"frozen_benchmark_allowed": True}, "review_packet_claims_authority"),
    ({"topology_recalculated": True}, "review_packet_claims_authority"),
    ({"scope": {"source_sha256": "0" * 64, "pdf_page": 1}}, "review_packet_source_or_page_mismatch"),
    ({"scope": {"source_sha256": SHA, "pdf_page": 2}}, "review_packet_source_or_page_mismatch"),
    ({"coordinate_frame": {"rotation": 90, "native_width": 400.0, "native_height": 300.0}}, "review_packet_page_frame_mismatch"),
    ({"review_revision": 0}, "review_packet_corrections_invalid"),
])
def test_a_foreign_or_authority_claiming_packet_is_rejected(overrides, reason):
    with pytest.raises(ReviewPacketError, match=reason):
        _read(_raw_packet([_correction()], **overrides))


@pytest.mark.parametrize("correction,reason", [
    ({**_correction(), "authority": "source_verified"}, "review_mark_not_user_geometry"),
    (_correction(points=((1.0, 1.0), (1.0, 1.0))), "review_mark_points_invalid"),
    (_correction(points=((1.0, 1.0), (2.0, float("inf")))), "review_packet_not_plain_json"),
    (_correction("z", "exclusion", ((0, 0), (10, 10), (10, 0), (0, 10)), "polygon"), "review_mark_outline_invalid"),
])
def test_malformed_marks_are_rejected(correction, reason):
    if reason == "review_packet_not_plain_json":
        packet = _raw_packet([_correction()])
        packet["corrections"] = [correction]
    else:
        packet = _raw_packet([correction])
    with pytest.raises(ReviewPacketError, match=reason):
        _read(packet)


def test_a_repeated_mark_identity_is_rejected():
    with pytest.raises(ReviewPacketError, match="review_mark_identity_invalid"):
        _read(_raw_packet([_correction(), _correction()]))


# ------------------------------------------------------------------------------------------------ the preview

def _pdf(path, rows):
    doc = fitz.open()
    page = doc.new_page(width=500.0, height=350.0)
    for row in rows:
        page.draw_rect(row["items"][0][1], color=None, fill=BLACK)
    doc.save(path)
    doc.close()
    return path


def _preview_packet(path, *corrections):
    data = path.read_bytes()
    with fitz.open(stream=data, filetype="pdf") as doc:
        frame = json.loads(json.dumps(asdict(native_page_frame(doc[0]))))
    return _raw_packet(list(corrections), sha=hashlib.sha256(data).hexdigest(), frame=frame)


def test_the_preview_adds_one_block_and_leaves_the_automatic_result_alone(tmp_path):
    path = _pdf(tmp_path / "missing.pdf", _missing_wall_room())
    off, off_png = canonical.source_native_trace_preview(path, 0)
    on, on_png = canonical.source_native_trace_preview(path, 0, review_packet=_preview_packet(path, _correction()))
    assert on_png == off_png
    assert {k: v for k, v in on.items() if k != "user_assisted_review"} == off
    block = on["user_assisted_review"]
    assert block["status"] == "applied" and block["automatic_room_count"] == off["candidate_enclosed_regions"]
    assert block["user_assisted_room_count"] == block["automatic_room_count"] + 1
    assert _outcome(block, "w1")["outcome"] == "applied"


def test_the_preview_rejects_a_packet_for_another_drawing_before_tracing(tmp_path, monkeypatch):
    path = _pdf(tmp_path / "missing.pdf", _missing_wall_room())
    packet = _preview_packet(path, _correction())
    other = _pdf(tmp_path / "other.pdf", _two_rooms_missing_partition())
    monkeypatch.setattr(canonical, "build_layered_wall_doorway_room_rings",
                        lambda *a, **k: pytest.fail("the tracer ran for a foreign packet"))
    with pytest.raises(ReviewPacketError, match="review_packet_source_or_page_mismatch"):
        canonical.source_native_trace_preview(other, 0, review_packet=packet)


def test_a_page_without_traced_walls_abstains_with_a_reason(tmp_path):
    path = _pdf(tmp_path / "blank.pdf", [])
    summary, _png = canonical.source_native_trace_preview(path, 0, review_packet=_preview_packet(path, _correction()))
    block = summary["user_assisted_review"]
    assert block["status"] == "abstained" and block["reason_codes"] == ["no_traced_walls_on_this_page"]
    assert _outcome(block, "w1")["outcome"] == "not_applied" and block["rooms"] == []


def test_the_editors_own_packet_builder_is_accepted_when_present(tmp_path):
    native = pytest.importorskip("pb_guided_plan_review_native")
    review = pytest.importorskip("pb_guided_plan_review")
    path = _pdf(tmp_path / "missing.pdf", _missing_wall_room())
    data = path.read_bytes()
    with fitz.open(stream=data, filetype="pdf") as doc:
        page = doc[0]
        zoom = min(1.2, 1800 / max(page.rect.width, page.rect.height))
        png = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False).tobytes("png")
        pixels = (page.rect * fitz.Matrix(zoom, zoom)).irect
    row = next(i for i, kind in enumerate(review.KINDS, 1) if kind[0] == "external_wall")
    pct = lambda x, y: (100 * x * zoom / pixels.width, 100 * y * zoom / pixels.height)
    (x1, y1), (x2, y2) = pct(159, 247), pct(191, 247)
    saved = {"revision": 1, "answers": {}, "shapes": review.normalise_editor_shapes(
        [{"id": "w1", "takeoff_row_id": row, "kind": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2}])}
    scope = review.ReviewScope(1, 1, 1, hashlib.sha256(data).hexdigest(), hashlib.sha256(png).hexdigest())
    packet = native.build_native_review_packet(scope=scope, pdf_path=path, image_bytes=png, saved=saved)
    summary, _png = canonical.source_native_trace_preview(path, 0, review_packet=packet)
    assert summary["user_assisted_review"]["user_assisted_room_count"] == 1
