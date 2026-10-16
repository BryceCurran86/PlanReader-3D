"""No-authority tests for surviving W2 graph lineage vs snapped W4 edges."""
from copy import deepcopy
import hashlib
import json
import math

import pytest

from tools.diag_gpt2_native_source_edge_span_census import (
    MULTIPLE, ONE, UNKNOWN, ZERO,
    inspect_competing_source_edge, inspect_source_room_report,
)


def _wall(wall_id, *fragments, native="native:wall"):
    return {
        "wall_id": wall_id,
        "source_primitive_ids": (native,),
        "source_edge_fragments": tuple({
            "edge_id": f"{wall_id}:{i}",
            "geometry": geometry,
            "source_primitive_ids": (native,),
        } for i, geometry in enumerate(fragments)),
        "source_snap_collapsed_fragment_count": 0,
        "structural_wall_role_proven_by_this_report": False,
    }


def _audit(left, right, *, edge=((0, 0), (10, 0))):
    return inspect_competing_source_edge({
        "face_id": "face-authored-test",
        "competing_planar_edge": edge,
        "candidate_walls": (left, right),
        "existing_local_source_interval_proof": False,
    })


def _support(audit):
    return {item["wall_id"]: item for item in audit["all_wall_contenders"]}


def test_two_real_native_span_owners_are_not_silently_elected():
    a = _audit(_wall("left", (0, 0, 10, 0)),
               _wall("right", (10, 0, 0, 0)))
    assert a["surviving_w2_span_support_status"] == MULTIPLE
    assert a["observed_supported_wall_ids"] == ("left", "right")
    assert not a["physical_room_publication_granted"]
    assert not a["original_source_wall_equivalence_granted"]
    assert not a["commercial_projection_allowed"]


def test_surviving_w2_endpoint_touch_is_not_snap_created_double_owner():
    # Two actual source intervals meet at 10, but only left covers 9..10.
    a = _audit(_wall("left", (9, 0, 10, 0)),
               _wall("right", (10, 0, 14, 0)),
               edge=((9.2, 0), (10, 0)))
    assert a["surviving_w2_span_support_status"] == ONE
    assert a["observed_supported_wall_ids"] == ("left",)
    assert _support(a)["right"]["full_surviving_w2_span_supported"] is False


def test_surviving_w2_gap_and_orthogonal_contender_remain_zero():
    # A drawing-space 0.48 gap must not be bridged by snapped graph endpoints.
    a = _audit(
        _wall("vertical", (4.0, 0, 4.0, 10)),
        _wall("horizontal", (0, 5, 4, 5), (4.48, 5, 10, 5)),
        edge=((4, 5), (4.3, 5)),
    )
    assert a["surviving_w2_span_support_status"] == ZERO
    assert a["observed_supported_wall_ids"] == ()
    assert not a["commercial_projection_allowed"]


def test_split_same_native_source_is_order_and_reversal_invariant():
    whole = _wall("left", (0, 0, 10, 0))
    split = _wall("left", (4, 0, 0, 0), (10, 0, 4, 0))
    other = _wall("right", (11, 0, 20, 0))
    one = _audit(whole, other)
    two = _audit(split, other)
    reverse = _audit(other, _wall("left", (10, 0, 4, 0), (0, 0, 4, 0)),
                     edge=((10, 0), (0, 0)))
    for result in (one, two, reverse):
        assert result["surviving_w2_span_support_status"] == ONE
        assert result["observed_supported_wall_ids"] == ("left",)
        assert _support(result)["left"]["witness_source_primitive_ids"] == ("native:wall",)


def test_genuine_gap_in_same_native_id_cannot_be_joined():
    a = _audit(_wall("left", (0, 0, 4, 0), (4.48, 0, 10, 0)),
               _wall("right", (0, 1, 10, 1)))
    assert a["surviving_w2_span_support_status"] == ZERO


def test_different_native_primitive_ids_do_not_fake_continuity():
    left = _wall("left", (0, 0, 4, 0), native="source-a")
    left["source_primitive_ids"] = ("source-a", "source-b")
    left["source_edge_fragments"] = left["source_edge_fragments"] + ({
        "edge_id": "fragment-b", "geometry": (4, 0, 10, 0),
        "source_primitive_ids": ("source-b",),
    },)
    result = _audit(left, _wall("right", (20, 0, 30, 0)))
    assert result["surviving_w2_span_support_status"] == ZERO


@pytest.mark.parametrize("invalid", [
    None, (), ("nan", 0, 10, 0), (float("inf"), 0, 10, 0),
    (0, 0, 0, 0), (0, 0, 1),
])
def test_invalid_source_fragments_are_unavailable_not_proof_of_absence(invalid):
    bad = _wall("left", (0, 0, 10, 0))
    bad["source_edge_fragments"] = ({
        "edge_id": "broken", "geometry": invalid,
        "source_primitive_ids": ("native:wall",),
    },)
    result = _audit(bad, _wall("right", (20, 0, 30, 0)))
    assert result["surviving_w2_span_support_status"] == UNKNOWN
    assert _support(result)["left"]["full_surviving_w2_span_supported"] is None
    assert not result["commercial_projection_allowed"]


def test_missing_source_candidate_must_abstain_even_when_other_wall_positive():
    absent = {"wall_id": "missing", "w4_record_unavailable": True}
    result = _audit(absent, _wall("present", (0, 0, 10, 0)))
    assert result["surviving_w2_span_support_status"] == UNKNOWN
    assert result["observed_supported_wall_ids"] == ("present",)


@pytest.mark.parametrize("point_fn", [
    lambda x, y: (x + 80, y - 40),
    lambda x, y: (-y, x),
    lambda x, y: (3 * x, 3 * y),
])
def test_translation_rotation_scale_preserve_original_support(point_fn):
    def geom(coords):
        a, b, c, d = coords
        return (*point_fn(a, b), *point_fn(c, d))
    start, end = point_fn(0, 0), point_fn(10, 0)
    result = _audit(_wall("owner", geom((0, 0, 10, 0))),
                    _wall("other", geom((10, 0, 20, 0))),
                    edge=(start, end))
    assert result["surviving_w2_span_support_status"] == ONE
    assert result["observed_supported_wall_ids"] == ("owner",)


def test_duplicate_wall_identity_and_malformed_plan_edge_fail_closed():
    with pytest.raises(ValueError, match="duplicate_or_invalid"):
        _audit(_wall("x", (0, 0, 10, 0)), _wall("x", (0, 0, 10, 0)))
    with pytest.raises(ValueError, match="contested_edge_or_contenders_invalid"):
        _audit(_wall("a", (0, 0, 10, 0)),
               _wall("b", (0, 0, 10, 0)), edge=((0, 0), (0, 0)))


def _report():
    digest = hashlib.sha256(b"isolated synthetic PDF").hexdigest()
    return {
        "source_sha256": digest,
        "source_snapshot_preserved": True,
        "new_commercial_quantities": [],
        "scopes": [{
            "source_sha256": digest, "revision_id": "original-revision",
            "snapshot_id": "native-snapshot", "page_id": "11",
            "decision_scope_id": "source-view-proven",
            "w4_scope_complete": False, "source_room_face_record_count": 0,
            "competing_source_edges": [{
                "face_id": "unresolved", "competing_planar_edge": ((0, 0), (10, 0)),
                "candidate_walls": [_wall("first", (0, 0, 10, 0)),
                                    _wall("second", (10, 0, 20, 0))],
            }],
        }],
    }


def test_source_report_retains_abstention_and_never_mutates_inputs():
    src = _report()
    preserved = deepcopy(src)
    result = inspect_source_room_report(src)
    assert src == preserved
    assert result["source_sha256"] == src["source_sha256"]
    assert result["source_snapshot_preserved"] is True
    assert result["scopes"][0]["source_room_face_record_count_unchanged"] == 0
    assert result["scopes"][0]["contested_source_edges"][0]["surviving_w2_span_support_status"] == ONE
    assert result["new_commercial_quantities"] == []
    assert result["frozen_evaluation_run"] is False


@pytest.mark.parametrize("mutation", [
    lambda x: x.update(source_snapshot_preserved=False),
    lambda x: x.update(new_commercial_quantities=[{"forbidden": True}]),
    lambda x: x["scopes"][0].update(source_sha256="different-source"),
    lambda x: x["scopes"][0].pop("competing_source_edges"),
])
def test_forbidden_source_mutations_or_incomplete_universe_are_rejected(mutation):
    src = _report()
    mutation(src)
    with pytest.raises(ValueError):
        inspect_source_room_report(src)


def test_deterministic_json_under_concurrent_nontarget_details_and_candidate_order():
    source = _report()
    alternate = deepcopy(source)
    rows = alternate["scopes"][0]["competing_source_edges"][0]["candidate_walls"]
    rows.reverse()
    alternate["scopes"][0]["unrelated_safe_note"] = {"does_not_select": "room"}
    a = inspect_source_room_report(source)
    b = inspect_source_room_report(alternate)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
