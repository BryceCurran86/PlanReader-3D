"""Room-ring candidates of two builder settings combined without choosing (#4764 7227402524, C06). Synthetic only."""
from __future__ import annotations

import copy
import hashlib
from types import SimpleNamespace

import fitz
import pytest

from pb_layered_wall_doorway_room_ring_shadow import build_layered_wall_doorway_room_rings
from pb_migration_contracts import EvidenceResolutionStatus
from pb_room_ring_candidate_union_shadow import (
    ALTERNATIVE_RUN, DEFAULT_RUN, REASON_AGREED, REASON_CONFLICT, REASON_NO_PROVENANCE, REASON_ONE_RUN,
    REASON_OWNERSHIP, union_room_ring_candidates,
)

CANDIDATE, ABSTAINED = EvidenceResolutionStatus.CANDIDATE, EvidenceResolutionStatus.ABSTAINED
SHA = "a" * 64


def _ring(x0, y0, x1, y1, *, status=CANDIDATE, closure=None, sha=SHA, page=0):
    owners = [("layered_wall_strip:0",)] * 4
    if closure:
        owners[1] = (f"layered_doorway_closure:{closure}",)
    return SimpleNamespace(record_id=f"r{x0}-{y0}-{x1}-{y1}", source_sha256=sha, page_index=page, status=status,
                           polygon_pdf_pts=((x0, y0), (x1, y0), (x1, y1), (x0, y1)), edge_owner_ids=tuple(owners))


def _result(*rings, closures=()):
    return SimpleNamespace(rings=tuple(rings),
                           closures=tuple(SimpleNamespace(closure_id=i, kind="source_stroke_closure",
                                                          native_path_indices=paths) for i, paths in closures))


def _by_box(entries):
    return {(entry["polygon_pdf_pts"][0], entry["polygon_pdf_pts"][2]): entry for entry in entries}


ROOM_A, ROOM_B = (0, 0, 100, 100), (100, 0, 200, 100)  # neighbours sharing an edge
OPEN_REGION = (300, 0, 500, 200)
ONLY_ALT = (600, 0, 700, 100)


def _case():
    default = _result(_ring(*ROOM_A), _ring(*ROOM_B), _ring(300, 0, 360, 60),  # a valid small room (like WSH/DRY)
                      _ring(*ONLY_ALT, status=ABSTAINED))
    alternative = _result(_ring(*ROOM_A), _ring(*ROOM_B), _ring(*OPEN_REGION, status=ABSTAINED),
                          _ring(*ONLY_ALT, closure="c1"), closures=[("c1", (4, 5))])
    return default, alternative


def test_agreed_one_run_only_and_a_room_the_other_run_only_has_open():
    entries = _by_box(union_room_ring_candidates(*_case()))
    assert {e["status"] for e in entries.values()} == {CANDIDATE}
    assert entries[((0, 0), (100, 100))]["reason"] == REASON_AGREED  # and the shared edge is no conflict
    assert entries[((100, 0), (200, 100))]["runs"] == (DEFAULT_RUN, ALTERNATIVE_RUN)
    assert entries[((300, 0), (360, 60))]["runs"] == (DEFAULT_RUN,)  # kept: the other run only has an open region
    gained = entries[((600, 0), (700, 100))]
    assert gained["reason"] == REASON_ONE_RUN and gained["runs"] == (ALTERNATIVE_RUN,)
    assert gained["closures"] == {ALTERNATIVE_RUN: (("c1", "source_stroke_closure", (4, 5)),)}


def test_overlapping_different_candidates_all_abstain_never_one_chosen():
    default = _result(_ring(0, 0, 100, 100), _ring(100, 0, 200, 100), _ring(300, 0, 400, 100))
    alternative = _result(_ring(0, 0, 200, 100), _ring(300, 0, 400, 100))  # one run merges the two rooms
    entries = _by_box(union_room_ring_candidates(default, alternative))
    for box in (((0, 0), (100, 100)), ((100, 0), (200, 100)), ((0, 0), (200, 100))):
        assert entries[box]["status"] is ABSTAINED and entries[box]["reason"] == REASON_CONFLICT
    assert entries[((300, 0), (400, 100))]["status"] is CANDIDATE


@pytest.mark.parametrize("overlap,status", [(0.01, CANDIDATE), (1.0, ABSTAINED)], ids=["rounding", "real"])
def test_only_a_real_overlap_is_a_conflict(overlap, status):
    entries = union_room_ring_candidates(_result(_ring(0, 0, 100, 100)), _result(_ring(100 - overlap, 0, 200, 100)))
    assert [e["status"] for e in entries] == [status, status]


def test_a_ring_slightly_different_in_the_other_run_conflicts():
    entries = union_room_ring_candidates(_result(_ring(0, 0, 100, 100)), _result(_ring(0, 0, 100, 94)))
    assert [e["status"] for e in entries] == [ABSTAINED, ABSTAINED]


def test_a_closure_without_source_paths_abstains_its_ring():
    for closures in ([("c1", ())], []):
        alternative = _result(_ring(0, 0, 100, 100, closure="c1"), closures=closures)
        (entry,) = union_room_ring_candidates(_result(), alternative)
        assert entry["status"] is ABSTAINED and entry["reason"] == REASON_NO_PROVENANCE


@pytest.mark.parametrize("kwargs", [dict(sha="b" * 64), dict(page=1)], ids=["other-source", "other-page"])
def test_runs_from_different_sources_or_pages_publish_nothing(kwargs):
    entries = union_room_ring_candidates(_result(_ring(0, 0, 100, 100)), _result(_ring(300, 0, 400, 100, **kwargs)))
    assert {(e["status"], e["reason"]) for e in entries} == {(ABSTAINED, REASON_OWNERSHIP)}


def test_order_translation_determinism_and_no_mutation():
    default, alternative = _case()
    before = copy.deepcopy((default, alternative))
    first = union_room_ring_candidates(default, alternative)
    shuffled = union_room_ring_candidates(
        SimpleNamespace(rings=default.rings[::-1], closures=default.closures),
        SimpleNamespace(rings=alternative.rings[::-1], closures=alternative.closures))
    assert first == shuffled == union_room_ring_candidates(default, alternative)
    assert (default, alternative) == before

    def moved(result):
        rings = []
        for ring in result.rings:
            clone = copy.copy(ring)
            clone.polygon_pdf_pts = tuple((x + 37.5, y + 11.25) for x, y in ring.polygon_pdf_pts)
            rings.append(clone)
        return SimpleNamespace(rings=tuple(rings), closures=result.closures)

    assert [(e["status"], e["reason"], e["runs"]) for e in union_room_ring_candidates(moved(default), moved(alternative))] == [
        (e["status"], e["reason"], e["runs"]) for e in first]


def test_real_builder_runs_without_segmented_swings_agree():
    document = fitz.open()
    page = document.new_page(width=600, height=400)
    for x0, y0, x1, y1 in ((44, 44, 290, 170), (50, 50, 164, 164), (170, 50, 284, 164)):
        for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            page.draw_line(a, b, color=(0, 0, 0), width=0.7)
    drawings = page.get_drawings()
    sha = hashlib.sha256(document.tobytes()).hexdigest()
    document.close()
    runs = [build_layered_wall_doorway_room_rings(drawings, source_sha256=sha, page_index=0,
                                                  dark_painted_wall_source=True, **extra)
            for extra in ({}, {"door_jamb_returns": True})]
    entries = union_room_ring_candidates(*runs)
    assert len(entries) == 2 and {e["reason"] for e in entries} == {REASON_AGREED}
