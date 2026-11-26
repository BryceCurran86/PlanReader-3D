"""The preview hands one session cache to both room traces (C08): same output, no second wall read, nothing stale.

Synthetic PDFs only. Every cached output is compared with a run that has no cache.
"""
from __future__ import annotations

import copy

import pytest

import pb_new_source_trace_preview as canonical
import pb_next_wall_ring_preview as tracer
from pb_next_wall_ring_preview import LayeredPieceCache
from tests.test_preview_doorway_chord_closures_v1 import KEY, _chord
from tests.test_user_assisted_review_topology_v1 import (
    _correction, _missing_wall_room, _pdf, _preview_packet, _two_rooms_missing_partition,
)

CLOSE_GAP = _correction()
NOTE_ONLY = _correction("n", "boundary", ((200.0, 110.0), (200.0, 240.0)))
# One session: first the automatic trace, then packets that add, replace and undo marks.
SESSION = [None, [CLOSE_GAP], [CLOSE_GAP, NOTE_ONLY], [NOTE_ONLY], [], None]


def _counted(monkeypatch):
    """How often the room tracer reads walls from the drawings."""
    calls = []
    real = tracer._collect_strips
    monkeypatch.setattr(tracer, "_collect_strips", lambda *args, **kwargs: calls.append(1) or real(*args, **kwargs))
    return calls


def _preview(path, corrections, **kwargs):
    packet = None if corrections is None else _preview_packet(path, *corrections)
    return canonical.source_native_trace_preview(path, 0, review_packet=packet, **kwargs)


def test_a_session_with_a_cache_gives_the_same_outputs_and_reads_the_walls_once(tmp_path, monkeypatch):
    path = _pdf(tmp_path / "missing.pdf", _missing_wall_room())
    fresh = [_preview(path, corrections) for corrections in SESSION]
    assert fresh[1][0] != fresh[0][0]  # the wall mark changes the review block
    calls, cache = _counted(monkeypatch), LayeredPieceCache()
    for corrections, expected in zip(SESSION, fresh):
        assert _preview(path, corrections, piece_cache=cache) == expected, corrections
    assert len(calls) == 1 and len(cache) == 1


def test_a_replaced_file_is_traced_again(tmp_path, monkeypatch):
    path = _pdf(tmp_path / "page.pdf", _missing_wall_room())
    cache = LayeredPieceCache()
    _preview(path, [CLOSE_GAP], piece_cache=cache)
    _pdf(path, _two_rooms_missing_partition())
    expected = _preview(path, [CLOSE_GAP])
    calls = _counted(monkeypatch)
    assert _preview(path, [CLOSE_GAP], piece_cache=cache) == expected
    assert calls


def test_an_evicted_page_is_traced_again_with_the_same_output(tmp_path, monkeypatch):
    first = _pdf(tmp_path / "a.pdf", _missing_wall_room())
    second = _pdf(tmp_path / "b.pdf", _two_rooms_missing_partition())
    expected = _preview(first, [CLOSE_GAP])
    cache = LayeredPieceCache(max_entries=1)
    _preview(first, None, piece_cache=cache)
    _preview(second, None, piece_cache=cache)
    calls = _counted(monkeypatch)
    assert _preview(first, [CLOSE_GAP], piece_cache=cache) == expected
    assert len(calls) == 1 and len(cache) == 1


def test_applied_chord_notes_do_not_change_what_the_second_trace_is_keyed_on(tmp_path, monkeypatch):
    path = _pdf(tmp_path / "missing.pdf", _missing_wall_room())
    block = {"chords": [_chord()], "chord_count": 1}
    monkeypatch.setattr(canonical, "_source_owned_doorway_chord_shadow_block", lambda rows, **kw: copy.deepcopy(block))
    expected = _preview(path, [CLOSE_GAP], source_owned_doorway_chord_closures=True)
    assert KEY in expected[0]
    calls, cache = _counted(monkeypatch), LayeredPieceCache()
    for _ in range(2):
        assert _preview(path, [CLOSE_GAP], source_owned_doorway_chord_closures=True, piece_cache=cache) == expected
    assert len(calls) == 1 and len(cache) == 1


@pytest.mark.parametrize("bad", [{}, True, "cache"])
def test_anything_but_a_piece_cache_is_rejected(tmp_path, bad):
    path = _pdf(tmp_path / "missing.pdf", _missing_wall_room())
    with pytest.raises(ValueError, match="new_trace_piece_cache_must_be_a_layered_piece_cache"):
        canonical.source_native_trace_preview(path, 0, piece_cache=bad)
