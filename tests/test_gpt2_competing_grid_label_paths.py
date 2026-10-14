"""GRID path reports are source-only and cannot cut walls or mint rooms."""
from types import SimpleNamespace as N

from tools.diag_gpt2_competing_grid_label_paths import (
    inspect_exact_grid_competing_label_paths as audit,
)

EDGE1 = ((0., 0.), (10., 0.))
EDGE2 = ((10., 0.), (20., 0.))


def room(name):
    return N(face_id=name, record_id="receipt_" + name)


def pair(a, b, wall, edge):
    return (b, wall, edge), (a, wall, edge)


def graph():
    a_to_b, b_to_a = pair("a", "b", "w4_a", EDGE1)
    b_to_c, c_to_b = pair("b", "c", "w4_b", EDGE2)
    return {"a": (a_to_b,), "b": (b_to_a, b_to_c), "c": (c_to_b,)}


def check(g=None, faces=None, competitors=None):
    return audit(
        graph() if g is None else g,
        source_face_records=tuple(room(v) for v in "abc") if faces is None else faces,
        seed_face_ids=("a",),
        competitor_receipts=(
            {"native_room_label": "OTHER ROOM", "competing_source_face_ids": ["c"]},
        ) if competitors is None else competitors,
    )


def test_original_w4_path_is_observational_only():
    result = check()
    assert result["status"] == "original_source_grid_competing_label_paths_observed"
    path = result["routes"][0]["observed_route"]
    assert [(e["original_w4_wall_id"], e["to_source_face_id"]) for e in path] == [
        ("w4_a", "b"), ("w4_b", "c"),
    ]
    assert all(e["physical_room_separator_role_proven"] is False for e in path)
    assert result["authenticated_physical_boundary_or_room_recovered"] is False
    assert result["original_source_room_face_universe_proven_complete"] is False


def test_wrong_w4_second_side_never_mints_path():
    bad = graph()
    bad["c"] = (("b", "different_w4", EDGE2),)
    result = check(bad)
    assert result["status"] == "source_grid_edge_not_two_sided"
    assert not result["routes"]


def test_duplicate_face_and_receipt_ids_fail_closed():
    assert check(faces=(room("a"), room("a"), room("c")))["status"] == (
        "source_face_identity_ambiguous"
    )
    assert check(faces=(room("a"), room("b"), N(face_id="c", record_id="receipt_a")))[
        "status"
    ] == "source_face_identity_ambiguous"


def test_missing_native_competitor_and_invalid_edges_fail_closed():
    invalid = (
        {"native_room_label": "OTHER", "competing_source_face_ids": ["absent"]},
    )
    assert check(competitors=invalid)["status"] == "competing_label_face_missing"
    bad = graph()
    bad["b"] += (("c", "w4_other", ((float("nan"), 0.), (2., 0.))),)
    assert check(bad)["status"] == "source_grid_adjacency_malformed"


def test_bounded_safeguards_and_no_fallback_from_label_text():
    too_many = tuple(
        {"native_room_label": f"ROOM{i}", "competing_source_face_ids": ["c"]}
        for i in range(9)
    )
    assert check(competitors=too_many)["status"] == "competitor_universe_truncated"
    assert check(g={"a": (("b", "w4_a", EDGE1),)})[
        "status"
    ] == "source_grid_edge_not_two_sided"


def test_no_exact_path_is_explicit_unavailable_not_negative_room():
    g = {"a": (), "b": (), "c": ()}
    r = check(g)
    assert r["routes"][0]["status"] == "no_exact_source_grid_path_observed"
    assert r["authenticated_physical_boundary_or_room_recovered"] is False
