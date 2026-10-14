"""Original W4 directed cycles preserve area, never infer physical rooms."""
from types import SimpleNamespace as N

from tools.diag_gpt2_exact_w4_directed_cycles import (
    inspect_exact_original_w4_directed_cycles as inspect,
)


def face(points, *, mismatch=False):
    vertices = tuple(points)
    edges = tuple(
        ("w4-original", (a, vertices[(i + 1) % len(vertices)]))
        for i, a in enumerate(vertices)
    )
    if mismatch:
        edges = edges[:-1] + (("w4-other", ((0., 0.), (1., 1.))),)
    signed = 0.5 * sum(
        a[0] * b[1] - b[0] * a[1]
        for a, b in zip(vertices, vertices[1:] + vertices[:1])
    )
    return N(face_id="source_original", area_page_pts2=abs(signed),
             polygon_pdf_pts=vertices, boundary_wall_edges=edges)


def test_nested_exact_source_loop_and_retrace_conserve_all_original_edges():
    # Outer 4x4 cell with a source-owned triangular nested excursion.
    ring = (
        (0., 0.), (4., 0.), (4., 2.), (3., 2.), (3., 3.),
        (2., 3.), (3., 2.), (4., 2.), (4., 4.), (0., 4.),
    )
    r = inspect(face(ring))
    assert r["status"] == "exact_original_w4_directed_cycles_observed_not_room"
    assert r["exact_source_wall_edges_owned"]
    assert r["directed_source_cycle_area_conserved"]
    assert sorted(
        index for item in r["source_cycles_observed_only"]
        for index in item["source_edge_indexes"]
    ) == list(range(len(ring)))
    assert r["source_nonzero_area_cycle_count"] >= 2
    assert r["new_authenticated_physical_room_or_metric_quantity"] is False
    assert r["original_room_label_ownership_changed"] is False
    assert all(not c["source_cycle_may_be_published_as_room"]
               for c in r["source_cycles_observed_only"])


def test_no_edge_can_gain_a_different_w4_wall_by_geometry_proximity():
    ring = ((0., 0.), (2., 0.), (2., 2.), (0., 2.))
    assert inspect(face(ring, mismatch=True))["status"] == (
        "original_w4_source_receipt_mismatch"
    )


def test_invalid_source_boundary_and_nonfinite_vertices_fail_closed():
    ring = ((0., 0.), (2., 0.), (2., 2.), (0., 2.))
    damaged = face(ring)
    damaged.boundary_wall_edges = damaged.boundary_wall_edges[:-1]
    assert inspect(damaged)["status"] == "original_boundary_receipt_count_or_safety_bound"
    assert inspect(face(((0., 0.), (2., 0.), (float("nan"), 2.))))[
        "status"
    ] == "original_source_vertex_invalid"


def test_no_area_substitution_and_no_benchmark_inference():
    ring = ((0., 0.), (3., 0.), (3., 2.), (0., 2.))
    source = face(ring)
    source.area_page_pts2 = 7.0
    r = inspect(source)
    assert r["status"] == "original_signed_source_area_unverified"
    assert not r["directed_source_cycle_area_conserved"]
    assert not r["new_authenticated_physical_room_or_metric_quantity"]
