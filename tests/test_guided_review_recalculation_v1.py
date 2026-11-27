"""The review screen's recalculation call (C08): session cache, stale and mismatched packets refused, results never reused wrongly.

Synthetic PDFs only. The packet format is the review screen's; the real builder is used when it is present.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json

import fitz
import pytest

import pb_guided_review_recalculation as recalculation
import pb_new_source_trace_preview as canonical
import pb_next_wall_ring_preview as tracer
from pb_native_page_frame import native_page_frame
from pb_user_assisted_review_topology import ReviewPacketError
from tests.test_user_assisted_review_topology_v1 import (
    _correction, _missing_wall_room, _pdf, _raw_packet, _two_rooms_missing_partition,
)

CLOSE_GAP = _correction()


def _packet(path, *corrections, revision=1, **scope):
    data = path.read_bytes()
    with fitz.open(stream=data, filetype="pdf") as doc:
        frame = json.loads(json.dumps(asdict(native_page_frame(doc[0]))))
    sha = hashlib.sha256(data).hexdigest()
    packet = _raw_packet(list(corrections), sha=sha, frame=frame, review_revision=revision)
    if scope:
        packet["scope"].update(scope)
        body = {k: v for k, v in packet.items() if k != "packet_sha256"}
        packet["packet_sha256"] = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return packet


def _run(session, path, packet, **overrides):
    kwargs = dict(pdf_path=path, packet=packet, registered_sha=packet["scope"]["source_sha256"], workspace_id=1,
                  page_id=1, pdf_page=1)
    kwargs.update(overrides)
    return recalculation.recalculate_review(session, **kwargs)


def _counted(monkeypatch, module, name):
    calls = []
    real = getattr(module, name)
    monkeypatch.setattr(module, name, lambda *args, **kwargs: calls.append(1) or real(*args, **kwargs))
    return calls


@pytest.fixture
def path(tmp_path):
    return _pdf(tmp_path / "page.pdf", _missing_wall_room())


def test_the_result_is_the_preview_with_the_marks_and_is_kept_for_that_packet(path, monkeypatch):
    packet = _packet(path, CLOSE_GAP)
    expected = canonical.source_native_trace_preview(path, 0, review_packet=packet)
    session, traces = {}, _counted(monkeypatch, canonical, "source_native_trace_preview")
    first = _run(session, path, packet)
    assert (first["summary"], first["png"]) == expected
    assert first["summary"]["user_assisted_review"]["user_assisted_room_count"] == 1
    assert _run(session, path, packet) == first and len(traces) == 1
    assert recalculation.stored_review_result(session, packet=packet, registered_sha=packet["scope"]["source_sha256"]) == first


def test_a_newer_revision_replaces_it_and_undo_returns_the_automatic_rooms(path, monkeypatch):
    session, walls = {}, _counted(monkeypatch, tracer, "_collect_strips")
    added = _run(session, path, _packet(path, CLOSE_GAP, revision=1))["summary"]["user_assisted_review"]
    undone = _run(session, path, _packet(path, revision=2))["summary"]["user_assisted_review"]
    assert added["user_assisted_room_count"] == 1 and undone["user_assisted_room_count"] == 0
    assert undone["review_revision"] == 2 and len(walls) == 1  # one read for the whole session


def test_older_and_conflicting_packets_are_refused_and_change_nothing(path):
    session = {}
    current = _packet(path, CLOSE_GAP, revision=3)
    kept = _run(session, path, current)
    for stale, reason in ((_packet(path, revision=2), "older_than_the_applied_one"),
                          (_packet(path, revision=3), "conflicts_with_the_applied_revision")):
        with pytest.raises(recalculation.ReviewRecalculationError, match=reason):
            _run(session, path, stale)
    sha = current["scope"]["source_sha256"]
    assert recalculation.stored_review_result(session, packet=current, registered_sha=sha) == kept
    assert recalculation.stored_review_result(session, packet=_packet(path, revision=2), registered_sha=sha) is None


@pytest.mark.parametrize("overrides, reason", [
    ({"workspace_id": 2}, "another_workspace_or_page"), ({"page_id": 2}, "another_workspace_or_page"),
    ({"pdf_page": 2}, "another_workspace_or_page"), ({"registered_sha": "ab" * 32}, "another_source"),
    ({"registered_sha": None}, "another_source"),
])
def test_a_packet_for_another_screen_or_source_is_refused_before_tracing(path, monkeypatch, overrides, reason):
    traces = _counted(monkeypatch, canonical, "source_native_trace_preview")
    session = {}
    with pytest.raises(recalculation.ReviewRecalculationError, match=reason):
        _run(session, path, _packet(path, CLOSE_GAP), **overrides)
    assert not traces and not session.get(recalculation.SESSION_KEY, {}).get("results")


@pytest.mark.parametrize("packet", [None, {}, {"scope": {"workspace_id": 1}}, "packet"])
def test_something_that_is_not_a_packet_is_refused(path, packet):
    with pytest.raises(recalculation.ReviewRecalculationError):
        recalculation.recalculate_review({}, pdf_path=path, packet=packet, registered_sha="ab" * 32, workspace_id=1,
                                         page_id=1, pdf_page=1)


def test_a_changed_file_drops_the_old_pieces_and_results(path):
    session = {}
    packet = _packet(path, CLOSE_GAP)
    _run(session, path, packet)
    cache = recalculation.session_piece_cache(session)
    assert len(cache) == 1
    _pdf(path, _two_rooms_missing_partition())
    with pytest.raises(recalculation.ReviewRecalculationError, match="original_pdf_changed"):
        _run(session, path, packet)
    assert len(cache) == 0
    assert recalculation.stored_review_result(session, packet=packet, registered_sha=packet["scope"]["source_sha256"]) is None
    updated = _packet(path, revision=1)  # the new file's own first packet is not "older" than the old file's
    assert _run(session, path, updated)["summary"]["source_sha256"] == updated["scope"]["source_sha256"]


def test_the_consumers_own_refusal_stores_nothing(path):
    session = {}
    bad = _packet(path, CLOSE_GAP)
    bad["commercial_projection_allowed"] = True
    body = {k: v for k, v in bad.items() if k != "packet_sha256"}
    bad["packet_sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    with pytest.raises(ReviewPacketError):
        _run(session, path, bad)
    assert not session[recalculation.SESSION_KEY]["results"]


def test_sessions_do_not_share_and_a_returned_result_cannot_change_the_stored_one(path):
    one, two = {}, {}
    packet = _packet(path, CLOSE_GAP)
    result = _run(one, path, packet)
    assert recalculation.session_piece_cache(one) is not recalculation.session_piece_cache(two)
    assert recalculation.stored_review_result(two, packet=packet, registered_sha=packet["scope"]["source_sha256"]) is None
    result["summary"]["user_assisted_review"]["rooms"].clear()
    assert _run(one, path, packet)["summary"]["user_assisted_review"]["rooms"]


def test_a_session_keeps_only_the_latest_pages_results(path, monkeypatch):
    monkeypatch.setattr(recalculation, "MAX_RESULTS", 2)
    session = {}
    packets = [_packet(path, CLOSE_GAP, page_id=page) for page in (1, 2, 3)]
    for page, packet in zip((1, 2, 3), packets):
        _run(session, path, packet, page_id=page)
    sha = packets[0]["scope"]["source_sha256"]
    kept = [recalculation.stored_review_result(session, packet=p, registered_sha=sha) is not None for p in packets]
    assert kept == [False, True, True]


@pytest.mark.parametrize("key, value", [
    ("source_sha256", "ab" * 32), ("page_index", 3), ("user_assisted_review", {"packet_sha256": "cd" * 32}),
])
def test_a_result_that_does_not_match_its_packet_is_not_kept(path, monkeypatch, key, value):
    real = canonical.source_native_trace_preview

    def wrong(*args, **kwargs):
        summary, png = real(*args, **kwargs)
        return {**summary, key: value}, png

    monkeypatch.setattr(canonical, "source_native_trace_preview", wrong)
    session = {}
    with pytest.raises(recalculation.ReviewRecalculationError, match="does_not_match_the_packet"):
        _run(session, path, _packet(path, CLOSE_GAP))
    assert not session[recalculation.SESSION_KEY]["results"]


def test_the_review_screens_own_packet_is_accepted_when_present(path, tmp_path):
    native = pytest.importorskip("pb_guided_plan_review_native")
    review = pytest.importorskip("pb_guided_plan_review")
    _summary, png = canonical.source_native_trace_preview(path, 0)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    scope = review.ReviewScope(1, 1, 1, sha, hashlib.sha256(png).hexdigest())
    saved = {"revision": 1, "shapes": [], "answers": {}}
    packet = native.build_native_review_packet(scope=scope, pdf_path=path, image_bytes=png, saved=saved,
                                               canonical_report=_summary)
    assert _run({}, path, packet)["summary"]["user_assisted_review"]["status"] == "applied"
