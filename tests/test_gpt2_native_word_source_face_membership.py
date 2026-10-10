"""Fail-closed native room-word face-membership diagnostic regressions."""
from types import SimpleNamespace
from tools.diag_gpt2_native_word_source_face_membership import (
    inspect_native_word_face_membership as inspect,
)


def face(name, coords):
    return SimpleNamespace(record_id=name, polygon_pdf_pts=coords)


A = face("source-face-a", ((0, 0), (10, 0), (10, 10), (0, 10)))
B = face("source-face-b", ((20, 0), (30, 0), (30, 10), (20, 10)))


def test_unique_candidate_is_not_an_authenticated_room():
    r = inspect([(1, 1, 2, 2), (3, 3, 4, 4)], [A, B])
    assert r["first_gate"] == "unique_native_word_source_face_candidate_only"
    assert r["candidate_face_ids"] == ["source-face-a"]
    assert not r["source_label_authenticated"]
    assert not r["metric_area_authenticated"]


def test_words_on_different_faces_cannot_bind():
    r = inspect([(1, 1, 2, 2), (21, 1, 22, 2)], [A, B])
    assert r["first_gate"] == "native_words_split_across_source_faces"
    assert r["candidate_face_ids"] == []


def test_competing_overlapping_faces_cannot_bind():
    r = inspect([(1, 1, 2, 2)], [A, face("source-face-duplicate", A.polygon_pdf_pts)])
    assert r["first_gate"] == "native_word_competing_source_face_candidates"


def test_partial_face_universe_does_not_create_room():
    r = inspect([(1, 1, 2, 2), (40, 1, 42, 2)], [A])
    assert r["first_gate"] == "native_word_center_outside_source_face_universe"
    assert not r["source_label_authenticated"]


def test_unavailable_word_geometry_fail_closed():
    for words in ([], [None], [(0, 0, 0, 2)], [(float("nan"), 0, 1, 2)]):
        assert inspect(words, [A])["first_gate"] == "native_word_geometry_unavailable"


def test_boundary_contact_does_not_mint_identity():
    r = inspect([(0, 1, 2, 3)], [A])
    assert r["first_gate"] == "unique_native_word_source_face_candidate_only"
    assert r["source_label_authenticated"] is False
