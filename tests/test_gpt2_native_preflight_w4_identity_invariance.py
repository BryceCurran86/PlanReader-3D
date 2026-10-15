"""Exact source identity read-order audit contract and fail-closed comparisons."""
from copy import deepcopy
import hashlib
import json

import pytest

import tools.diag_gpt2_native_preflight_w4_identity_invariance as diagnostic


def test_first_difference_exact_deep_equal_and_no_mutation():
    original = {"scopes": [{"id": "S", "walls": ["a", "b"]}], "sha": "same"}
    old = deepcopy(original)
    assert diagnostic.first_difference(original, deepcopy(original)) is None
    assert original == old


@pytest.mark.parametrize("a,b,expected_path", [
    ({"x": 2}, {"x": 2.000001}, "$.x"),
    ({"x": [1, 2]}, {"x": [1]}, "$.x"),
    ({"x": {"a": 1}}, {"x": {"b": 1}}, "$.x.a"),
    ({"x": [1]}, {"x": ["1"]}, "$.x[0]"),
    ({"scope": {"id": "s1"}}, {"scope": {"id": "s2"}}, "$.scope.id"),
])
def test_metamorphic_and_source_scope_difference_do_not_get_tolerated(a,b,expected_path):
    out = diagnostic.first_difference(a, b)
    assert out is not None
    assert out["path"] == expected_path


def test_digest_is_sort_order_stable_but_source_lineage_change_is_detected():
    original = {"source": "rev", "scope": {"a": [1.2, 2.3], "b": ["x"]}}
    rearranged = {"scope": {"b": ["x"], "a": [1.2, 2.3]}, "source": "rev"}
    assert diagnostic._digest(original) == diagnostic._digest(rearranged)
    changed = deepcopy(original)
    changed["scope"]["b"][0] = "different-original-primitive"
    assert diagnostic._digest(original) != diagnostic._digest(changed)


def test_comparison_uses_three_actual_capture_results_and_no_optimistic_publication(monkeypatch):
    calls = []
    fake_original = b"%PDF-local-source"
    sha = hashlib.sha256(fake_original).hexdigest()

    def capture(source, *, page_no, preflight):
        assert source == fake_original
        assert page_no == 1
        calls.append(preflight)
        return {
            "source_sha256": sha,
            "revision_id": "R1", "snapshot_id": "S1",
            "scopes": [{"decision_scope_id": "view-1", "walls": [
                {"wall_id": "wall-1", "original_source_ids": ["d1i0"]}
            ], "shadow_faces": [{"face_id": "f-1"}]}],
            "preflight_drawing_receipt": {"drawing_path_count": 1} if preflight else None,
            "source_snapshot_unchanged": True,
        }

    monkeypatch.setattr(diagnostic, "capture_original_source", capture)
    first = diagnostic.compare_source_read_order(fake_original, page_no=1)
    assert calls == [False, True, False]
    assert first["source_authority_stable_after_diagnostic_read"] is True
    assert first["physical_room_or_material_granted"] is False
    assert first["new_commercial_quantities"] == []
    assert first["frozen_benchmark_scored"] is False


def test_one_source_read_order_difference_is_reported_not_renamed(monkeypatch):
    calls = []
    def fake(source, *, page_no, preflight):
        calls.append(preflight)
        return {
            "source_sha256": "sha", "revision_id": "R", "snapshot_id": "S",
            "scopes": [{"decision_scope_id": "B" if preflight else "A",
                        "walls": [], "shadow_faces": []}],
            "preflight_drawing_receipt": {},
            "source_snapshot_unchanged": True,
        }

    monkeypatch.setattr(diagnostic, "capture_original_source", fake)
    report = diagnostic.compare_source_read_order(b"original", page_no=1)
    assert calls == [False, True, False]
    assert report["source_authority_stable_after_diagnostic_read"] is False
    assert report["preflight_vs_baseline_first_exact_difference"]["path"] == "$.scopes[0].decision_scope_id"
    assert report["repeat_baseline_first_exact_difference"] is None


def test_repeated_without_preflight_detects_nondeterminism_without_blame(monkeypatch):
    state = {"counter": 0}
    def fake(source, *, page_no, preflight):
        state["counter"] += 1
        return {
            "source_sha256": "sha", "revision_id": "R", "snapshot_id": "S",
            "scopes": [{"decision_scope_id": str(state["counter"]),
                        "walls": [], "shadow_faces": []}],
            "preflight_drawing_receipt": None,
            "source_snapshot_unchanged": True,
        }
    monkeypatch.setattr(diagnostic, "capture_original_source", fake)
    report = diagnostic.compare_source_read_order(b"original", page_no=1)
    assert report["preflight_vs_baseline_first_exact_difference"] is not None
    assert report["repeat_baseline_first_exact_difference"] is not None
    assert not report["source_authority_stable_after_diagnostic_read"]


def test_bad_pdf_type_and_invalid_original_page_address_are_rejected():
    with pytest.raises(ValueError, match="original_source_required"):
        diagnostic.capture_original_source("not bytes", page_no=1, preflight=False)
    with pytest.raises(ValueError, match="original_source_required"):
        diagnostic.capture_original_source(b"source", page_no=0, preflight=False)
    with pytest.raises(ValueError, match="original_source_required"):
        diagnostic.capture_original_source(b"source", page_no=True, preflight=True)


def test_digest_exact_lineage_and_no_source_mutation():
    original = {"walls": [("W2", ["d1i0", "d2i0"])], "sha": "abc"}
    old = deepcopy(original)
    result = diagnostic._digest(original)
    assert len(result) == 64 and result == diagnostic._digest(original)
    assert original == old
    assert json.loads(json.dumps(original))["sha"] == "abc"
