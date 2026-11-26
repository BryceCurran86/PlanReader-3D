"""The tracer's piece cache (C08): a correction re-forms rooms from stored pieces; any other change is traced again.

Synthetic only. Every result is compared with a run that has no cache.
"""
from __future__ import annotations

import copy

import pytest

import pb_next_wall_ring_preview as tracer
from pb_next_wall_ring_preview import LayeredPieceCache
from pb_user_assisted_review_topology import BarrierRecorder, build_review_block, plan_review
from tests.test_user_assisted_review_topology_v1 import SHA, _bar, _mark, _missing_wall_room, _packet, _trace


def _second_room(dx=500):
    return [_bar(100 + dx, 100, 300 + dx, 106), _bar(100 + dx, 106, 106 + dx, 250), _bar(294 + dx, 106, 300 + dx, 250),
            _bar(106 + dx, 244, 294 + dx, 250)]


ROWS = _missing_wall_room() + _second_room()
MARKS = {
    "wall": _mark("a", "internal_wall", (160, 247), (190, 247)),
    "closure": _mark("b", "opening", (160, 247), (190, 247)),
    "reject": _mark("c", "reject_candidate", (790, 175), (810, 175)),
    "finish": _mark("d", "boundary", (600, 175), (800, 175)),
    "exclusion": _mark("e", "exclusion", (650, 130), (750, 130), (750, 220)),
    "outline": _mark("f", "room_outline", (606, 106), (794, 106), (794, 244), (606, 244)),
    "dimension": _mark("g", "dimension_witness", (100, 90), (300, 90)),
    "unsupported": _mark("h", "not_a_category", (0, 0), (1, 1)),
}
# Each step is a later packet of one session: marks are added, then undone.
SESSION = [("wall",), ("wall", "reject"), ("wall",), ("closure", "finish"), ("exclusion", "outline"),
           ("dimension", "unsupported"), ("reject",), ()]


def _counted(monkeypatch):
    """How often walls are read from the drawings."""
    calls = []
    real = tracer._collect_strips

    def counted(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(tracer, "_collect_strips", counted)
    return calls


def _correct(rows, names, **kw):
    """What the preview does for one packet: the automatic trace, the plan, the user-assisted trace, the block."""
    packet, recorder = _packet(*(MARKS[name] for name in names)), BarrierRecorder()
    automatic = _trace(rows, barrier_view=recorder, **kw)
    plan = plan_review(packet, recorder)
    assisted = _trace(rows, barrier_view=plan, **kw)
    block = build_review_block(packet, plan, source_sha256=SHA, page_index=0, automatic_rings=automatic.rings,
                               user_rings=assisted.rings)
    return automatic, plan, assisted, block


def test_a_run_that_fills_the_cache_equals_a_run_without_one():
    assert _trace(ROWS, piece_cache=LayeredPieceCache()) == _trace(ROWS)


def test_a_second_run_reads_no_walls_and_gives_the_same_result(monkeypatch):
    calls, cache = _counted(monkeypatch), LayeredPieceCache()
    first = _trace(ROWS, piece_cache=cache)
    assert len(calls) == 1 and len(cache) == 1 and cache.stored_bytes > 0
    assert _trace(ROWS, piece_cache=cache) == first == _trace(ROWS)
    assert len(calls) == 2  # only the run without a cache read them again


def test_every_mark_kind_and_undo_matches_a_run_without_the_cache(monkeypatch):
    fresh = [_correct(ROWS, names) for names in SESSION]
    calls, cache = _counted(monkeypatch), LayeredPieceCache()
    for names, expected in zip(SESSION, fresh):
        assert _correct(ROWS, names, piece_cache=cache) == expected, names
    assert len(calls) == 1


def test_changed_barriers_are_never_served_from_stored_rooms():
    cache = LayeredPieceCache()
    recorder = BarrierRecorder()
    automatic = _trace(ROWS, barrier_view=recorder, piece_cache=cache)
    assert _trace(ROWS, piece_cache=cache) is automatic  # unchanged barriers: the stored rooms
    for name in ("wall", "closure", "reject"):
        plan = plan_review(_packet(MARKS[name]), recorder)
        changed = _trace(ROWS, barrier_view=plan, piece_cache=cache)
        assert changed is not automatic and changed.rings != automatic.rings, name
        assert changed == _trace(ROWS, barrier_view=plan), name
    assert _trace(ROWS, barrier_view=recorder, piece_cache=cache) is automatic


def test_a_cache_filled_by_a_changed_run_still_gives_the_automatic_rooms():
    recorder = BarrierRecorder()
    automatic = _trace(ROWS, barrier_view=recorder)
    cache = LayeredPieceCache()
    _trace(ROWS, barrier_view=plan_review(_packet(MARKS["wall"]), recorder), piece_cache=cache)
    assert _trace(ROWS, piece_cache=cache) == automatic


def _doorway_chord():
    return {"candidate_topology_doorway_closure": True, "source_physical_door_host_authenticated": False,
            "metric_area_issued": False, "commercial_publishable": False, "horizontal": True,
            "wall_band_pdf_pts": (244.0, 250.0), "door_interval_pdf_pts": (160.0, 190.0)}


def _nudged(rows):
    changed = list(rows)
    changed[0] = _bar(100, 100, 300.001, 106)
    return changed


@pytest.mark.parametrize("change", [
    {"rows": _nudged(ROWS)},
    {"rows": ROWS[::-1]},
    {"source_sha256": "cd" * 32},
    {"page_index": 1},
    {"stroke_pair_wall_faces": False},
    {"wall_end_stroke_closures": True},
    {"sliding_leaf_frame_closure": True},
    {"panel_lift_label_closure": True},
    {"source_words": ({"text": "CS", "bbox_pdf_pts": (1.0, 1.0, 2.0, 2.0), "source_ref": "w"},)},
    {"source_pair_baseline_drawings": ROWS},
    {"viewport_pdf_pts": (0.0, 0.0, 400.0, 400.0)},
    {"source_owned_doorway_chords": (_doorway_chord(),)},
], ids=lambda change: next(iter(change)))
def test_any_change_to_what_the_pieces_are_made_from_is_traced_again(monkeypatch, change):
    base = dict(rows=ROWS, source_sha256=SHA, page_index=0, stroke_pair_wall_faces=True)
    other = {**base, **change}

    def trace(options, **kw):
        options = dict(options)
        rows = options.pop("rows")
        return tracer.build_layered_wall_doorway_room_rings(rows, **options, **kw)

    expected = trace(other)
    cache = LayeredPieceCache()
    trace(base, piece_cache=cache)
    calls = _counted(monkeypatch)
    assert trace(other, piece_cache=cache) == expected
    assert calls, "the changed run must read the walls again"


@pytest.mark.parametrize("name, value", [("_PRIMITIVE_CAP", 19999), ("_code_revision", lambda: "changed")])
def test_a_changed_cap_or_changed_code_is_traced_again(monkeypatch, name, value):
    cache = LayeredPieceCache()
    _trace(ROWS, piece_cache=cache)
    calls = _counted(monkeypatch)
    monkeypatch.setattr(tracer, name, value)
    assert _trace(ROWS, piece_cache=cache) == _trace(ROWS)
    assert len(calls) == 2


VIEWPORTS = ((0.0, 0.0, 450.0, 400.0), (450.0, 0.0, 900.0, 400.0))


def test_a_page_traced_in_tiles_matches_with_and_without_the_cache(monkeypatch):
    monkeypatch.setattr(tracer, "_PRIMITIVE_CAP", 6)  # 9 wall paths on the page, at most 5 in either tile
    fresh = [_correct(ROWS, names, viewport_pdf_pts=VIEWPORTS) for names in SESSION]
    assert fresh[-1][0].rings  # the second room is closed
    calls, cache = _counted(monkeypatch), LayeredPieceCache()
    for names, expected in zip(SESSION, fresh):
        assert _correct(ROWS, names, viewport_pdf_pts=VIEWPORTS, piece_cache=cache) == expected, names
    assert len(calls) == 2 and len(cache) == 1  # one read per tile, once


def test_a_page_over_the_cap_abstains_the_same_way(monkeypatch):
    monkeypatch.setattr(tracer, "_PRIMITIVE_CAP", 3)
    expected = _trace(ROWS)
    assert expected.reason_codes == (tracer.REASON_PRIMITIVE_CAP,)
    cache = LayeredPieceCache()
    assert _trace(ROWS, piece_cache=cache) == expected
    assert _trace(ROWS, piece_cache=cache, barrier_view=BarrierRecorder()) == expected


def test_a_page_with_no_wall_ink_abstains_the_same_way():
    cache = LayeredPieceCache()
    expected = _trace([])
    assert _trace([], piece_cache=cache) == expected
    assert _trace([], piece_cache=cache) == expected


def _page(cache, page, rows=ROWS, sha=SHA):
    result = tracer.build_layered_wall_doorway_room_rings(rows, source_sha256=sha, page_index=page,
                                                          stroke_pair_wall_faces=True, piece_cache=cache)
    assert result.wall_strip_count  # real pieces are stored, not an early abstention
    return result


def test_the_cache_drops_the_least_recently_used_trace_past_its_entry_bound(monkeypatch):
    calls, cache = _counted(monkeypatch), LayeredPieceCache(max_entries=2)
    _page(cache, 0)
    _page(cache, 1)
    _page(cache, 0)  # used again, so page 1 is now the oldest
    _page(cache, 2)
    assert len(cache) == 2 and len(calls) == 3
    _page(cache, 0)  # kept
    assert len(calls) == 3
    _page(cache, 1)  # dropped
    assert len(calls) == 4


def test_the_cache_keeps_to_its_byte_bound():
    small = LayeredPieceCache(max_bytes=64)
    assert _trace(ROWS, piece_cache=small) == _trace(ROWS)
    assert len(small) == 0 and small.stored_bytes == 0

    probe = LayeredPieceCache()
    _page(probe, 0)
    one = probe.stored_bytes
    tight = LayeredPieceCache(max_bytes=int(one * 1.5))
    _page(tight, 0)
    _page(tight, 1)
    assert len(tight) == 1 and tight.stored_bytes <= int(one * 1.5)
    many = ROWS + [row for dx in range(1000, 4000, 500) for row in _second_room(dx)]
    _page(tight, 2, rows=many)  # too big to keep: it must not push out the trace already there
    assert len(tight) == 1 and tight.stored_bytes == one


def test_a_source_can_be_dropped_and_the_cache_cleared():
    cache = LayeredPieceCache()
    for sha in (SHA, "cd" * 32):
        _page(cache, 0, sha=sha)
    cache.drop_source(SHA)
    assert len(cache) == 1
    cache.clear()
    assert len(cache) == 0 and cache.stored_bytes == 0


def test_inputs_that_cannot_be_fingerprinted_are_traced_and_not_stored():
    rows = [dict(row, untrusted_extra=lambda: None) for row in ROWS]
    cache = LayeredPieceCache()
    assert _trace(rows, piece_cache=cache) == _trace(rows)
    assert len(cache) == 0


def test_the_cache_changes_neither_the_inputs_nor_later_results():
    rows = copy.deepcopy(ROWS)
    before = repr(rows)
    cache = LayeredPieceCache()
    results = [_correct(rows, ("wall", "reject"), piece_cache=cache) for _ in range(3)]
    assert results[0] == results[1] == results[2] and repr(rows) == before


def test_a_bad_cache_or_bound_is_rejected():
    with pytest.raises(ValueError):
        _trace(ROWS, piece_cache={})
    for kwargs in ({"max_entries": 0}, {"max_bytes": -1}, {"max_entries": 1.5}):
        with pytest.raises(ValueError):
            LayeredPieceCache(**kwargs)
