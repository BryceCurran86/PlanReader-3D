"""Tests for generic multi-wall open-plan room-face composition shadow (Item 2)."""
from __future__ import annotations

from pathlib import Path

from pb_source_multi_wall_open_room_face_shadow import (
    MarkedOpeningOrFinishThresholdInput,
    SourceWallSegmentInput,
    compose_multi_wall_open_room_face_shadow,
)
from tools.audit_no_job_specific_shared_rules import audit_shared_source

_SHA = "b" * 64


def _w(wid: str, p1, p2, *, sha=_SHA, page="1", vp="vp_1"):
    return SourceWallSegmentInput(
        segment_id=wid, p1_pts=p1, p2_pts=p2, stroke_width_pt=1.2,
        source_sha256=sha, page_id=page, viewport_id=vp,
    )


def _t(tid: str, kind: str, p1, p2, *, witness="wit_1", sha=_SHA, page="1", vp="vp_1"):
    return MarkedOpeningOrFinishThresholdInput(
        threshold_id=tid, kind=kind, p1_pts=p1, p2_pts=p2,
        witness_record_id=witness, source_sha256=sha, page_id=page, viewport_id=vp,
    )


def test_open_plan_l_shaped_room_composed_from_walls_and_witnessed_thresholds():
    # L-shaped living/dining zone: 5 walls + 1 doorway span + 1 finish transition line
    walls = (
        _w("w1", (0, 0), (100, 0)),
        _w("w2", (100, 0), (100, 40)),
        _w("w3", (100, 60), (100, 80)),      # 20pt opening gap between y=40..60
        _w("w4", (100, 80), (40, 80)),
        _w("w5", (0, 60), (0, 0)),
    )
    thresholds = (
        _t("t_door", "opening_span", (100, 40), (100, 60), witness="op_wit_1"),
        _t("t_fin1", "finish_transition", (40, 80), (40, 60), witness="fin_wit_1"),
        _t("t_fin2", "finish_transition", (40, 60), (0, 60), witness="fin_wit_2"),
    )
    res = compose_multi_wall_open_room_face_shadow(
        wall_segments=walls,
        thresholds=thresholds,
        room_label="OPEN_ZONE",
        room_label_anchor_pts=(50.0, 30.0),
        source_sha256=_SHA,
        page_id="1",
        viewport_id="vp_1",
        mm_per_pt_x=35.2778,
        mm_per_pt_y=35.2778,
    )
    assert res.resolved is True
    assert res.status == "CANDIDATE_MULTI_WALL_ROOM_FACE_COMPOSED"
    # Area = 100*80 - 40*20 = 7200 pts^2
    assert abs((res.area_pts2 or 0.0) - 7200.0) < 1e-2
    assert res.area_m2_non_commercial is not None and res.area_m2_non_commercial > 0
    assert res.commercial_projection_allowed is False
    assert res.shadow_only is True
    assert len(res.contributing_wall_segment_ids) == 5
    assert set(res.contributing_threshold_ids) == {"t_door", "t_fin1", "t_fin2"}


def test_unclosed_leak_without_threshold_abstains():
    walls = (
        _w("w1", (0, 0), (100, 0)),
        _w("w2", (100, 0), (100, 40)),
        _w("w3", (100, 60), (100, 80)),
        _w("w4", (100, 80), (0, 80)),
        _w("w5", (0, 80), (0, 0)),
    )
    res = compose_multi_wall_open_room_face_shadow(
        wall_segments=walls, thresholds=(),
        room_label="OPEN_ZONE", room_label_anchor_pts=(50.0, 40.0),
        source_sha256=_SHA, page_id="1", viewport_id="vp_1",
    )
    assert res.resolved is False
    assert "open_room_boundary_unclosed" in res.reason_codes


def test_unwitnessed_threshold_or_cross_revision_lineage_rejected():
    walls = (
        _w("w1", (0, 0), (100, 0)),
        _w("w2", (100, 0), (100, 80)),
        _w("w3", (100, 80), (0, 80)),
    )
    bad_t = (_t("t1", "finish_transition", (0, 80), (0, 0), witness=""),)
    r1 = compose_multi_wall_open_room_face_shadow(
        wall_segments=walls, thresholds=bad_t,
        room_label="R1", room_label_anchor_pts=(50.0, 40.0),
        source_sha256=_SHA, page_id="1", viewport_id="vp_1",
    )
    assert r1.resolved is False
    assert "unwitnessed_threshold_chord_rejected" in r1.reason_codes

    cross_sha = (_t("t1", "finish_transition", (0, 80), (0, 0), witness="ok", sha="c" * 64),)
    r2 = compose_multi_wall_open_room_face_shadow(
        wall_segments=walls, thresholds=cross_sha,
        room_label="R1", room_label_anchor_pts=(50.0, 40.0),
        source_sha256=_SHA, page_id="1", viewport_id="vp_1",
    )
    assert r2.resolved is False
    assert "lineage_mismatch_rejected" in r2.reason_codes


def test_threshold_only_box_without_sufficient_wall_support_rejected():
    walls = (_w("w1", (0, 0), (10, 0)),)
    thresholds = (
        _t("t1", "finish_transition", (10, 0), (100, 0)),
        _t("t2", "finish_transition", (100, 0), (100, 80)),
        _t("t3", "finish_transition", (100, 80), (0, 80)),
        _t("t4", "finish_transition", (0, 80), (0, 0)),
    )
    res = compose_multi_wall_open_room_face_shadow(
        wall_segments=walls, thresholds=thresholds,
        room_label="FAKE_BOX", room_label_anchor_pts=(50.0, 40.0),
        source_sha256=_SHA, page_id="1", viewport_id="vp_1",
    )
    assert res.resolved is False
    assert "wall_boundary_support_insufficient" in res.reason_codes


def test_zero_job_specific_shared_source_rules():
    path = Path(__file__).resolve().parents[1] / "pb_source_multi_wall_open_room_face_shadow.py"
    assert audit_shared_source(path.read_text(encoding="utf-8"), filename=path.name) == ()
