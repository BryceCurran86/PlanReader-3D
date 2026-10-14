"""Non-simple original face forensics never grant room or wall authority."""
from types import SimpleNamespace as N

from tools.diag_gpt2_grid_component_first_failure import (
    inspect_non_simple_original_face_ring as inspect,
)


def face(polygon, wall_edges):
    return N(
        face_id="original-face",
        record_id="source-record",
        polygon_pdf_pts=tuple(polygon),
        area_page_pts2=100.0,
        boundary_wall_edges=tuple(wall_edges),
    )


def test_original_bowtie_with_source_w4_receipts_remains_not_repaired():
    polygon=((0.,0.),(10.,10.),(0.,10.),(10.,0.))
    record=face(polygon,(
        ("w4-one", ((0.,0.),(10.,10.))),
        ("w4-two", ((0.,10.),(10.,0.))),
    ))
    row=inspect(record)
    assert row["original_ring_vertex_count"]==4
    assert row["exact_backtrack_cleanup_yields_simple_polygon"] is False
    assert row["source_w4_boundary_edge_receipt_count"]==2
    assert len(row["source_w4_boundary_edges_candidate_only"])==2
    assert all(
        receipt["physical_wall_role_or_equivalence_proven"] is False
        for receipt in row["source_w4_boundary_edges_candidate_only"]
    )
    assert row["authentic_physical_room_polygon_published"] is False


def test_exact_retrace_is_only_diagnostic_even_if_clean_ring_is_simple():
    record=face(
        ((0.,0.),(10.,0.),(10.,10.),(20.,10.),
         (10.,10.),(0.,10.)),
        (),
    )
    record.area_page_pts2=100.
    row=inspect(record)
    assert row["exact_backtrack_cleanup_changed_original_ring"] is True
    assert row["exact_backtrack_cleanup_yields_simple_polygon"] is True
    assert row["exact_backtrack_cleanup_preserves_original_area"] is True
    assert row["source_face_identity_or_wall_equivalence_rewritten"] is False


def test_nonfinite_source_rejected_without_geometry_repair():
    row=inspect(face(
        ((0.,0.),(10.,10.),(float("nan"),10.),(10.,0.)),
        (),
    ))
    assert row["original_ring_vertices_pdf_pts"] == []
    assert row["exact_backtrack_cleanup_changed_original_ring"] is None
    assert row["authentic_physical_room_polygon_published"] is False


def test_bounded_original_receipts_do_not_expand_into_new_walls():
    rect=((0.,0.),(10.,0.),(10.,10.),(0.,10.))
    rows=(("w4-auth", (rect[0],rect[1])),)*110
    row=inspect(face(rect,rows))
    assert row["source_w4_boundary_edge_receipt_count"]==110
    assert row["source_w4_boundary_receipts_truncated"] is True
    assert len(row["source_w4_boundary_edges_candidate_only"])==96
    assert row["authentic_physical_room_polygon_published"] is False
