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


def test_single_interpreter_source_capture_retains_all_ids_without_promotion(monkeypatch):
    data = {
        "source_sha256": "sha", "revision_id": "R", "snapshot_id": "S",
        "source_snapshot_unchanged": True, "scopes": [
            {"document_id": "doc", "revision_id": "R", "snapshot_id": "S",
             "source_sha256": "sha", "decision_scope_id": "scope",
             "walls": [{"wall_id": "w1", "original_w2_lineage": ["d0i0"]}],
             "shadow_faces": [{"face_id": "f1", "polygon": [[0,0],[1,0],[1,1]]}]}
        ],
    }
    old = deepcopy(data)
    monkeypatch.setattr(
        diagnostic, "capture_original_source",
        lambda source, *, page_no, preflight: data,
    )
    report = diagnostic.single_source_capture(b"fake", page_no=11)
    scope, = report["scopes"]
    assert scope["wall_count"] == 1 and scope["shadow_face_count"] == 1
    assert scope["wall_ids_and_digests"][0][0] == "w1"
    assert scope["face_ids_and_digests"][0][0] == "f1"
    assert len(scope["complete_scope_digest"]) == 64
    assert data == old
    assert report["new_commercial_quantities"] == []
    assert report["physical_room_or_material_granted"] is False


def test_per_interpreter_digests_detect_primitive_and_face_source_drift(monkeypatch):
    base = {
        "source_sha256": "sha", "revision_id": "R", "snapshot_id": "S",
        "source_snapshot_unchanged": True,
        "scopes": [{"document_id": "doc", "revision_id": "R",
            "snapshot_id": "S", "source_sha256": "sha",
            "decision_scope_id": "scope",
            "walls": [{"wall_id": "w1", "source_primitive_ids": ["d0i0"]}],
            "shadow_faces": [{"face_id": "f1", "polygon": [[0,0],[1,0],[1,1]]}],
        }],
    }
    monkeypatch.setattr(
        diagnostic, "capture_original_source",
        lambda source, *, page_no, preflight: deepcopy(base),
    )
    original = diagnostic.single_source_capture(b"sha", page_no=11)
    base["scopes"][0]["walls"][0]["source_primitive_ids"] = ["d1i0"]
    changed = diagnostic.single_source_capture(b"sha", page_no=11)
    assert original["scopes"][0]["wall_ids_and_digests"] != changed["scopes"][0]["wall_ids_and_digests"]
    assert original["scopes"][0]["complete_scope_digest"] != changed["scopes"][0]["complete_scope_digest"]
    assert original["scopes"][0]["face_ids_and_digests"] == changed["scopes"][0]["face_ids_and_digests"]


def test_original_f07_siblings_change_scope_fingerprint_without_w4_wall_change():
    from types import SimpleNamespace
    from pb_viewport_segmentation import (
        SegmentedViewport, _stamp_segment_page_viewports_product,
    )
    from pb_physical_wall_candidate_authority import _page_viewports_cache_key
    def pair(other_note):
        view = SegmentedViewport(
            view_id="same-view-id", page_number=11, view_type="floor_finish_plan",
            label="FLOOR FINISHES PLAN", title_bbox=(0., 0., 10., 10.),
            bounding_box=(0., 0., 100., 100.), status="resolved",
            boundary_source="vector_frame", confidence=1.0,
            provenance={"native_path": "d1i0"},
        )
        sibling = SegmentedViewport(
            view_id="same-sibling-id", page_number=11, view_type="schedule",
            label="FINISH SCHEDULE", title_bbox=(201., 0., 211., 10.),
            bounding_box=(200., 0., 300., 100.), status="resolved",
            boundary_source="vector_frame", confidence=1.0,
            notes=[other_note], provenance={"native_path": "d7i0"},
        )
        return tuple(_stamp_segment_page_viewports_product((view, sibling)))
    published = SimpleNamespace(
        revision=SimpleNamespace(
            document_id="source-original-doc", revision_id="R",
            source_sha256="a" * 64,
        ),
        snapshot=SimpleNamespace(snapshot_id="S"),
    )
    def snapshot(note):
        source=SimpleNamespace(_physical_wall_page_viewports_cache={
            _page_viewports_cache_key(published=published, page_id="11"):pair(note)
        })
        return diagnostic.audited_producer_f07_inventory(
            source=source, published=published, page_no=11,
        )
    first, second = snapshot("a"), snapshot("b")
    assert first["status"] == "original_producer_f07_sibling_inventory_captured"
    assert first["all_producer_view_count"] == 2
    assert all(v["producer_token_valid"] for v in first["all_source_owned_views"])
    assert first["all_source_owned_views"][0]["view_id"] == "same-sibling-id"
    # Same targeted plan view, DIFFERENT sibling source-note provenance:
    assert first["all_source_owned_views"][1]["producer_fingerprint"] == (
        second["all_source_owned_views"][1]["producer_fingerprint"]
    )
    assert first["sibling_set_fingerprint"] != second["sibling_set_fingerprint"]
    a = first["all_source_owned_views"][1]["expected_wall_scope_if_eligible"]
    b = second["all_source_owned_views"][1]["expected_wall_scope_if_eligible"]
    assert a != b and a.startswith("wall-source:viewport:11:")
    assert diagnostic.first_difference(first, second) is not None


def test_unavailable_or_mutated_f07_producer_cache_cannot_mint_scope_receipt():
    from types import SimpleNamespace
    from pb_physical_wall_candidate_authority import _page_viewports_cache_key
    from pb_viewport_segmentation import SegmentedViewport
    published = SimpleNamespace(
        revision=SimpleNamespace(
            document_id="d", revision_id="r", source_sha256="b"*64
        ), snapshot=SimpleNamespace(snapshot_id="s"),
    )
    missing = diagnostic.audited_producer_f07_inventory(
        source=SimpleNamespace(_physical_wall_page_viewports_cache={}),
        published=published, page_no=11,
    )
    assert missing["status"] == "producer_f07_cache_unavailable"
    spoof = SegmentedViewport(
        view_id="v", page_number=11, view_type="floor_finish_plan",
        label="PLAN", title_bbox=(0.,0.,10.,10.), bounding_box=(0.,0.,50.,50.),
        status="resolved",boundary_source="vector_frame",confidence=1.0,
    )
    bad = diagnostic.audited_producer_f07_inventory(
        source=SimpleNamespace(_physical_wall_page_viewports_cache={
            _page_viewports_cache_key(published=published,page_id="11"):(spoof,)
        }), published=published, page_no=11,
    )
    assert bad["status"] == "producer_f07_view_set_unavailable"
    assert bad["all_source_owned_views"] == []
