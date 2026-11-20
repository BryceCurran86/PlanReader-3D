"""Fail closed on crossed footprint ink without inventing a replacement outline."""
import hashlib

from pb_external_footprint_first_trace import (
    _polygon_has_self_intersection,
    trace_external_footprint_first,
)


def test_simple_valid_rectangular_footprint_is_not_vetoed():
    assert not _polygon_has_self_intersection(((0, 0), (12, 0), (12, 9), (0, 9)))


def test_crossed_footprint_and_collinear_overlap_are_rejected():
    assert _polygon_has_self_intersection(((0, 0), (12, 9), (0, 9), (12, 0)))
    assert _polygon_has_self_intersection(((0, 0), (6, 0), (3, 0), (3, 4), (0, 4)))


def test_nonadjacent_touching_edges_are_rejected():
    assert _polygon_has_self_intersection(((0, 0), (8, 0), (8, 8), (4, 0), (0, 8)))


def test_authenticated_3laurel_page_3_does_not_publish_crossed_candidate():
    from tests.original_source_3laurel import require_original_3laurel

    pdf_bytes = require_original_3laurel().read_bytes()
    source_sha = hashlib.sha256(pdf_bytes).hexdigest()
    result, = trace_external_footprint_first(
        pdf_bytes, source_sha256=source_sha, page_indices=(2,),
    )
    assert result.status == "ABSTAINED"
    assert result.reason == "external_footprint_self_intersecting_candidate"
    assert not result.measurement_authorized
    assert not result.commercial_publishable
    assert not result.polygon_pdf_pts
