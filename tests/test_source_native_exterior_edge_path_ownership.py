"""Synthetic unique-or-abstain native owners for footprint-first exterior edges."""
from __future__ import annotations

import hashlib

import fitz
import pytest

from pb_external_footprint_first_trace import ExternalFootprintTrace
from pb_layered_wall_doorway_room_ring_shadow import build_layered_wall_doorway_room_rings
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_native_exterior_edge_path_ownership import (
    first_unsupported_open_to_exterior_span,
    own_exterior_contour_native_paths,
)
from tests.test_layered_wall_doorway_room_ring_shadow_v1 import SHA, _open_gap_room, strip


def _trace(points, *, sha="ab" * 32):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return ExternalFootprintTrace(
        source_sha256=sha,
        page_index=0,
        status="CANDIDATE",
        reason="test_morphological_contour",
        polygon_pdf_pts=tuple(points),
        bbox_pdf_pts=(min(xs), min(ys), max(xs), max(ys)),
        candidate_count=1,
        commercial_publishable=False,
        measurement_authorized=False,
    )


def _stroke(a, b, *, dashes="", width=0.5, layer="Enclosure_WallInternal"):
    return {
        "layer": layer,
        "fill": None,
        "color": (0.0, 0.0, 0.0),
        "width": width,
        "dashes": dashes,
        "items": [("l", fitz.Point(*a), fitz.Point(*b))],
    }


def test_unique_outer_native_stroke_owns_axis_aligned_contour_edge():
    drawings = [
        _stroke((200.0, 130.0), (200.0, 490.0)),
        _stroke((200.0, 130.0), (800.0, 130.0)),
        _stroke((800.0, 130.0), (800.0, 490.0)),
        _stroke((200.0, 490.0), (800.0, 490.0)),
    ]
    owned = own_exterior_contour_native_paths(
        drawings,
        _trace(((200.0, 130.0), (800.0, 130.0), (800.0, 490.0), (200.0, 490.0))),
    )
    assert len(owned) == 4
    assert all(edge.status is EvidenceResolutionStatus.CANDIDATE for edge in owned)
    assert all(edge.classification == "source_native_wall_ink_candidate" for edge in owned)
    assert all(edge.physical_wall_authenticated is False for edge in owned)
    assert all(edge.can_issue_area is False for edge in owned)
    assert {tuple(edge.native_path_indices) for edge in owned} == {(0,), (1,), (2,), (3,)}


def test_dashed_site_perimeter_is_not_an_exterior_wall_owner():
    drawings = [
        _stroke((50.0, 50.0), (50.0, 700.0), dashes="[3 2] 0"),
        _stroke((200.0, 130.0), (200.0, 490.0)),
    ]
    owned = own_exterior_contour_native_paths(
        drawings,
        _trace(((50.0, 50.0), (50.0, 700.0), (51.0, 700.0), (51.0, 50.0))),
    )
    left = owned[0]
    assert left.status is EvidenceResolutionStatus.ABSTAINED
    assert left.classification == "unmatched_contour_segment"
    assert left.native_path_indices == ()


def test_diagonal_furniture_and_dimension_leaders_are_geometric_bridges():
    drawings = [
        _stroke((210.0, 130.0), (800.0, 490.0), width=0.2),
        _stroke((300.0, 200.0), (420.0, 340.0), layer="Dimension"),
    ]
    owned = own_exterior_contour_native_paths(
        drawings,
        _trace(((210.0, 130.0), (800.0, 490.0), (800.0, 491.0), (210.0, 131.0))),
    )
    diagonal = owned[0]
    assert diagonal.diagonal is True
    assert diagonal.status is EvidenceResolutionStatus.ABSTAINED
    assert diagonal.classification == "incorrect_geometric_bridge"
    assert diagonal.native_path_indices == ()


def test_open_connected_living_span_stays_unclosed_and_reports_native_ends():
    rows = _open_gap_room()
    receipt = first_unsupported_open_to_exterior_span(
        rows, source_sha256=SHA, page_index=0,
    )
    assert receipt is not None
    assert receipt.status is EvidenceResolutionStatus.ABSTAINED
    assert receipt.can_issue_area is False
    assert receipt.opening_authenticated is False
    assert receipt.missing_jamb_opening_evidence is True
    assert receipt.swing_or_slider_or_stroke_witness is False
    assert set(receipt.adjacent_wall_native_path_indices) == {3, 4}
    assert receipt.left_wall_native_path_indices == (3,)
    assert receipt.right_wall_native_path_indices == (4,)
    assert receipt.source_path_side_partition_proven is True
    assert receipt.layer_names == ("Enclosure_WallInternal", "Enclosure_WallInternal")
    width = receipt.gap_interval_pdf_pts[1] - receipt.gap_interval_pdf_pts[0]
    assert width == pytest.approx(24.0)
    rings = build_layered_wall_doorway_room_rings(
        rows, source_sha256=SHA, page_index=0,
    )
    assert rings.closures == ()


def test_wide_unwitnessed_span_is_not_closed_as_a_door():
    """A long collinear interruption without swing/slider/stroke stays open.

    Length is evidence of an unresolved span, never a close threshold.
    """
    rows = (
        strip(0, 0, 400, 2)
        + strip(0, 2, 2, 298)
        + strip(0, 298, 400, 300)
        + strip(398, 2, 400, 20)
        + strip(398, 242, 400, 298)
    )
    receipt = first_unsupported_open_to_exterior_span(
        rows, source_sha256=SHA, page_index=0,
    )
    assert receipt is not None
    span = receipt.gap_interval_pdf_pts[1] - receipt.gap_interval_pdf_pts[0]
    assert span == pytest.approx(222.0)
    assert receipt.missing_jamb_opening_evidence is True
    assert receipt.status is EvidenceResolutionStatus.ABSTAINED
    assert receipt.can_issue_area is False
    result = build_layered_wall_doorway_room_rings(
        rows, source_sha256=SHA, page_index=0,
    )
    assert result.closures == ()


def test_long_graze_does_not_own_a_short_morphological_jog():
    drawings = [_stroke((50.0, 450.0), (950.0, 450.0))]
    owned = own_exterior_contour_native_paths(
        drawings,
        _trace(((327.8, 448.9), (311.1, 450.0), (311.1, 451.0), (327.8, 449.9))),
    )
    assert owned[0].status is EvidenceResolutionStatus.ABSTAINED
    assert owned[0].native_path_indices == ()


def test_morphological_polygon_alone_is_not_a_wall_owner():
    owned = own_exterior_contour_native_paths(
        [],
        _trace(((200.0, 130.0), (800.0, 130.0), (800.0, 490.0), (200.0, 490.0))),
    )
    assert owned
    assert all(edge.status is EvidenceResolutionStatus.ABSTAINED for edge in owned)
    assert all(edge.classification == "unmatched_contour_segment" for edge in owned)
    assert all(edge.native_path_indices == () for edge in owned)


def test_foreign_sha_still_does_not_publish_area_from_ownership():
    sha = hashlib.sha256(b"foreign").hexdigest()
    drawings = [_stroke((200.0, 130.0), (200.0, 490.0))]
    owned = own_exterior_contour_native_paths(
        drawings,
        _trace(((200.0, 130.0), (200.0, 490.0), (201.0, 490.0), (201.0, 130.0)), sha=sha),
    )
    assert all(edge.commercial_publishable is False for edge in owned)
    assert all(edge.can_issue_area is False for edge in owned)


def test_partial_source_closure_at_gap_midpoint_cannot_authorize_whole_span():
    """An actual 2pt frame inside a 20pt unresolved gap is not a 20pt door."""
    from types import SimpleNamespace

    from pb_source_native_exterior_edge_path_ownership import (
        _closure_covers_edge,
        enrich_open_to_exterior_span,
    )

    witness = {
        "horizontal": True,
        "band_pdf_pts": (100.0, 102.0),
        "gap_interval_pdf_pts": (10.0, 30.0),
        "adjacent_wall_native_path_indices": (),
        "left_wall_native_path_indices": (),
        "right_wall_native_path_indices": (),
        "source_path_side_partition_proven": True,
    }
    partial = SimpleNamespace(
        horizontal=True, band=(100.0, 102.0), gap_interval=(19.0, 21.0),
    )
    receipt = enrich_open_to_exterior_span((), witness, closures=(partial,))
    assert receipt.missing_jamb_opening_evidence is True
    assert receipt.swing_or_slider_or_stroke_witness is False
    assert receipt.can_issue_area is False
    assert not _closure_covers_edge((10.0, 101.0), (30.0, 101.0), (partial,))
    assert not _closure_covers_edge((30.0, 101.0), (10.0, 101.0), (partial,))


def test_full_source_closure_covers_gap_both_directions_without_minting_area():
    from types import SimpleNamespace

    from pb_source_native_exterior_edge_path_ownership import (
        _closure_covers_edge,
        enrich_open_to_exterior_span,
    )

    horizontal = SimpleNamespace(
        horizontal=True, band=(100.0, 102.0), gap_interval=(10.0, 30.0),
    )
    assert _closure_covers_edge((10.0, 101.0), (30.0, 101.0), (horizontal,))
    assert _closure_covers_edge((30.0, 101.0), (10.0, 101.0), (horizontal,))
    witness = {
        "horizontal": True,
        "band_pdf_pts": (100.0, 102.0),
        "gap_interval_pdf_pts": (10.0, 30.0),
        "adjacent_wall_native_path_indices": (),
        "left_wall_native_path_indices": (),
        "right_wall_native_path_indices": (),
    }
    receipt = enrich_open_to_exterior_span((), witness, closures=(horizontal,))
    assert receipt.swing_or_slider_or_stroke_witness is True
    assert receipt.missing_jamb_opening_evidence is False
    assert receipt.can_issue_area is False
    vertical = SimpleNamespace(
        horizontal=False, band=(40.0, 42.0), gap_interval=(10.0, 30.0),
    )
    assert _closure_covers_edge((41.0, 10.0), (41.0, 30.0), (vertical,))
    assert not _closure_covers_edge((41.0, 5.0), (41.0, 30.0), (vertical,))


def test_separate_partial_source_closures_do_not_union_into_opening_authority():
    from types import SimpleNamespace

    from pb_source_native_exterior_edge_path_ownership import _closure_covers_edge

    left = SimpleNamespace(horizontal=True, band=(100., 102.), gap_interval=(10., 20.))
    right = SimpleNamespace(horizontal=True, band=(100., 102.), gap_interval=(20., 30.))
    assert not _closure_covers_edge((10., 101.), (30., 101.), (left, right))


def test_source_ring_axis_not_inferred_from_opposite_faces_of_thick_wall_band():
    """Source witness orientation survives a thicker-than-2pt wall band."""
    from types import SimpleNamespace

    from pb_source_native_exterior_edge_path_ownership import (
        _closure_covers_edge,
        enrich_open_to_exterior_span,
    )

    # Horizontal wall-band thickness is 4.5 PDF points. The prior helper
    # misclassified these opposite-face endpoints as a vertical edge.
    horizontal_witness = {
        "horizontal": True,
        "band_pdf_pts": (100.0, 104.5),
        "gap_interval_pdf_pts": (10.0, 30.0),
    }
    full_h = SimpleNamespace(
        horizontal=True, band=(100.0, 104.5), gap_interval=(10.0, 30.0),
    )
    partial_h = SimpleNamespace(
        horizontal=True, band=(100.0, 104.5), gap_interval=(19.0, 21.0),
    )
    wrong_axis_h = SimpleNamespace(
        horizontal=False, band=(100.0, 104.5), gap_interval=(10.0, 30.0),
    )
    assert _closure_covers_edge(
        (10.0, 100.0), (30.0, 104.5), (full_h,),
        horizontal_witness=True,
    )
    full_receipt = enrich_open_to_exterior_span(
        (), horizontal_witness, closures=(full_h,),
    )
    assert full_receipt.swing_or_slider_or_stroke_witness is True
    assert full_receipt.missing_jamb_opening_evidence is False
    assert full_receipt.status is EvidenceResolutionStatus.ABSTAINED
    assert full_receipt.can_issue_area is False

    for closure in (partial_h, wrong_axis_h):
        receipt = enrich_open_to_exterior_span(
            (), horizontal_witness, closures=(closure,),
        )
        assert receipt.missing_jamb_opening_evidence is True
        assert receipt.swing_or_slider_or_stroke_witness is False
        assert receipt.can_issue_area is False

    # A short vertical gap may span less Y than its wall is thick in X;
    # the source witness remains vertical even when the helper's old
    # endpoint-only axis inference would label it horizontal.
    vertical_witness = {
        "horizontal": False,
        "band_pdf_pts": (40.0, 44.5),
        "gap_interval_pdf_pts": (10.0, 11.5),
    }
    full_v = SimpleNamespace(
        horizontal=False, band=(40.0, 44.5), gap_interval=(10.0, 11.5),
    )
    wrong_axis_v = SimpleNamespace(
        horizontal=True, band=(40.0, 44.5), gap_interval=(10.0, 11.5),
    )
    vertical_receipt = enrich_open_to_exterior_span(
        (), vertical_witness, closures=(full_v,),
    )
    assert vertical_receipt.swing_or_slider_or_stroke_witness is True
    assert vertical_receipt.missing_jamb_opening_evidence is False
    assert vertical_receipt.status is EvidenceResolutionStatus.ABSTAINED
    assert vertical_receipt.can_issue_area is False
    wrong_receipt = enrich_open_to_exterior_span(
        (), vertical_witness, closures=(wrong_axis_v,),
    )
    assert wrong_receipt.missing_jamb_opening_evidence is True
    assert wrong_receipt.can_issue_area is False


def test_nearby_parallel_source_face_is_not_the_same_opening_band():
    """Acacia p2 source path 4000 and 4002 sit on different parallel ink lines."""
    from types import SimpleNamespace
    from pb_source_native_exterior_edge_path_ownership import _closure_covers_edge

    other_face = SimpleNamespace(
        horizontal=True, band=(100.0, 100.4), gap_interval=(10.0, 30.0),
    )
    # Only 1.5pt apart: old 2.5pt association radius incorrectly
    # counted a closure on a different wall face.
    assert not _closure_covers_edge((10.0, 102.0), (30.0, 102.0), (other_face,))
    exact_face = SimpleNamespace(
        horizontal=True, band=(101.98, 102.02), gap_interval=(10.0, 30.0),
    )
    assert _closure_covers_edge((10.0, 102.0), (30.0, 102.0), (exact_face,))
    vertical_other = SimpleNamespace(
        horizontal=False, band=(50.0, 50.4), gap_interval=(10.0, 30.0),
    )
    assert not _closure_covers_edge((52.0, 10.0), (52.0, 30.0), (vertical_other,))
    vertical_exact = SimpleNamespace(
        horizontal=False, band=(51.98, 52.02), gap_interval=(10.0, 30.0),
    )
    assert _closure_covers_edge((52.0, 10.0), (52.0, 30.0), (vertical_exact,))


def test_nonfinite_closure_bounds_never_authenticate_an_exterior_gap():
    from types import SimpleNamespace
    from pb_source_native_exterior_edge_path_ownership import _closure_covers_edge

    for bad in (float("nan"), float("inf"), -float("inf")):
        closure = SimpleNamespace(
            horizontal=True, band=(100.0, 102.0), gap_interval=(10.0, bad),
        )
        assert not _closure_covers_edge((10.0, 101.0), (30.0, 101.0), (closure,))


def test_pale_compound_source_fill_never_owns_contour_edge():
    # Acacia p2 has a pale sheet-sized compound fill with nested segments.
    # Its rectangle may align with a red raster contour, but not a wall.
    trace = _trace(((200, 130), (800, 130), (800, 490), (200, 490)))
    pale = {
        "type": "f", "fill": (0.98, 0.98, 0.98), "color": None,
        "layer": "", "items": [
            ("re", fitz.Rect(200, 130, 800, 490), 1),
            ("l", fitz.Point(200, 130), fitz.Point(800, 130)),
        ],
    }
    grey = {
        "type": "s", "fill": None, "color": (0.48, 0.48, 0.48),
        "layer": "", "items": [
            ("l", fitz.Point(200, 130), fitz.Point(800, 130)),
        ],
    }
    top = own_exterior_contour_native_paths((pale, grey), trace)[0]
    assert top.status is EvidenceResolutionStatus.ABSTAINED
    assert top.native_path_indices == ()
    assert top.classification == "unmatched_contour_segment"
    assert not top.physical_wall_authenticated
    assert not top.can_issue_area


def test_dark_source_wall_kept_even_with_pale_surrounding_fill():
    trace = _trace(((200, 130), (800, 130), (800, 490), (200, 490)))
    pale = {
        "type": "f", "fill": (0.98, 0.98, 0.98), "color": None,
        "items": [("l", fitz.Point(200, 130), fitz.Point(800, 130))],
    }
    ink = _stroke((200, 130), (800, 130))
    ink["type"] = "s"
    top = own_exterior_contour_native_paths((pale, ink), trace)[0]
    assert top.status is EvidenceResolutionStatus.CANDIDATE
    assert top.native_path_indices == (1,)
    assert not top.physical_wall_authenticated


def test_native_dark_ink_rejects_nonfinite_and_wrong_draw_modes():
    from pb_source_native_exterior_edge_path_ownership import (
        _dark_original_ink, _visible_native_dark_wall_ink,
    )
    assert not _dark_original_ink((float("nan"), 0, 0))
    assert not _dark_original_ink((float("inf"), 0, 0))
    assert not _dark_original_ink((True, False, 0))
    assert not _dark_original_ink((0, 0))
    assert not _dark_original_ink(None)
    assert not _dark_original_ink((0.48, 0.48, 0.48))
    assert _dark_original_ink((0.0, 0.0, 0.0))
    assert not _visible_native_dark_wall_ink(
        {"type": "f", "color": (0, 0, 0), "fill": (0.98, 0.98, 0.98)}
    )
    assert _visible_native_dark_wall_ink(
        {"type": "fs", "color": (0, 0, 0), "fill": (0.98, 0.98, 0.98)}
    )


def test_exact_multi_path_original_stroke_chain_never_mints_wall_area():
    trace = _trace(((200, 0), (800, 0), (800, 100), (200, 100)))
    strokes = [_stroke((200, i * 25), (200, (i + 1) * 25))
               for i in range(4)]
    edge = own_exterior_contour_native_paths(strokes, trace)[3]
    assert edge.status is EvidenceResolutionStatus.CANDIDATE
    assert edge.native_path_indices == (0, 1, 2, 3)
    assert edge.classification == "source_native_wall_ink_chain_candidate"
    assert edge.physical_wall_authenticated is False
    assert edge.can_issue_area is False
    assert edge.commercial_publishable is False


def test_segment_chain_fails_closed_on_real_middle_and_oversized_terminal_gaps():
    trace = _trace(((200, 0), (800, 0), (800, 100), (200, 100)))
    # Gaps beyond CAD dash merge (~4 pt) stay unwitnessed middle breaks.
    middle = [
        _stroke((200, 0), (200, 25)),
        _stroke((200, 29.5), (200, 50)),
        _stroke((200, 50), (200, 75)),
        _stroke((200, 75), (200, 100)),
    ]
    missing = own_exterior_contour_native_paths(middle, trace)[3]
    assert missing.status is EvidenceResolutionStatus.ABSTAINED
    assert missing.classification == "incomplete_source_native_wall_ink_chain"
    assert not missing.physical_wall_authenticated
    # Sub-association (~1 pt) terminal shortfall is witnessed; oversized is not.
    near_tip = [
        _stroke((200, 0.5), (200, 25)),
        _stroke((200, 25), (200, 50)),
        _stroke((200, 50), (200, 75)),
        _stroke((200, 75), (200, 100)),
    ]
    tip_ok = own_exterior_contour_native_paths(near_tip, trace)[3]
    assert tip_ok.status is EvidenceResolutionStatus.CANDIDATE
    assert tip_ok.classification == "source_native_wall_ink_chain_candidate"
    assert tip_ok.chain_start_shortfall_pt == 0.5
    assert tip_ok.contour_endpoint_association_pt == 4.0
    assert tip_ok.physical_wall_authenticated is False
    # Beyond CAD dash association (~4 pt) the terminal remains unwitnessed.
    far_tip = [
        _stroke((200, 5.0), (200, 25)),
        _stroke((200, 25), (200, 50)),
        _stroke((200, 50), (200, 75)),
        _stroke((200, 75), (200, 100)),
    ]
    tip_far = own_exterior_contour_native_paths(far_tip, trace)[3]
    assert tip_far.status is EvidenceResolutionStatus.ABSTAINED
    assert tip_far.reason == "native_source_chain_has_unwitnessed_contour_endpoint"
    assert tip_far.chain_start_shortfall_pt == 5.0


def test_cad_dash_terminal_shortfall_within_gap_is_complete_chain():
    """Acacia south-style ~3.9 pt dash shortfall completes under CAD association."""
    trace = _trace(((200, 0), (800, 0), (800, 100), (200, 100)))
    dashes = [
        _stroke((200, 0), (200, 24), dashes="[3 2] 0"),
        _stroke((200, 27.5), (200, 50), dashes="[3 2] 0"),
        _stroke((200, 53.5), (200, 75), dashes="[3 2] 0"),
        _stroke((200, 78.5), (200, 96.2), dashes="[3 2] 0"),
    ]
    west = own_exterior_contour_native_paths(dashes, trace)[3]
    assert west.status is EvidenceResolutionStatus.CANDIDATE
    assert west.classification == "source_native_wall_ink_chain_candidate"
    assert west.chain_end_shortfall_pt is not None
    assert 2.5 < west.chain_end_shortfall_pt <= 4.0
    assert west.physical_wall_authenticated is False


def test_cad_dash_gap_merges_into_complete_face_chain_candidate():
    """Acacia-style ~3.5 pt dash gaps on one face complete; never mint area."""
    trace = _trace(((200, 0), (800, 0), (800, 100), (200, 100)))
    dashes = [
        _stroke((200, 0), (200, 22), dashes="[3 2] 0"),
        _stroke((200, 25.5), (200, 47.5), dashes="[3 2] 0"),
        _stroke((200, 51), (200, 73), dashes="[3 2] 0"),
        _stroke((200, 76.5), (200, 100), dashes="[3 2] 0"),
    ]
    west = own_exterior_contour_native_paths(dashes, trace)[3]
    assert west.status is EvidenceResolutionStatus.CANDIDATE
    assert west.classification == "source_native_wall_ink_chain_candidate"
    assert west.native_path_indices == (0, 1, 2, 3)
    assert west.physical_wall_authenticated is False
    assert west.can_issue_area is False


def test_inner_parallel_face_does_not_compete_with_contour_face_chain():
    """Inner continuous face inside search window is not a nearest-tie rival."""
    trace = _trace(((200, 0), (800, 0), (800, 100), (200, 100)))
    strokes = [
        _stroke((200, 0), (200, 25), dashes="[3 2] 0"),
        _stroke((200, 28), (200, 50), dashes="[3 2] 0"),
        _stroke((200, 53), (200, 75), dashes="[3 2] 0"),
        _stroke((200, 78), (200, 100), dashes="[3 2] 0"),
        # Inner parallel continuous face ~0.7 pt inside search window.
        _stroke((200.7, 0), (200.7, 100)),
    ]
    west = own_exterior_contour_native_paths(strokes, trace)[3]
    assert west.classification == "source_native_wall_ink_chain_candidate"
    assert west.native_path_indices == (0, 1, 2, 3)
    assert 4 not in west.native_path_indices
    assert west.physical_wall_authenticated is False


def test_acacia_east_style_chain_short_of_morphological_corners_is_complete_candidate():
    """Painted east ink ends ~1 pt inside collapsed NE/SE corners — association, not join."""
    trace = _trace(((328, 140), (328, 450), (904, 450), (904, 140)))
    strokes = [
        _stroke((903.1, 140.6), (903.1, 168.9)),
        _stroke((903.1, 168.9), (903.1, 244.6)),
        _stroke((903.1, 244.6), (903.1, 270.1)),
        _stroke((903.1, 270.1), (903.1, 308.2)),
        _stroke((903.1, 308.2), (903.1, 333.8)),
        _stroke((903.1, 333.8), (903.1, 348.2)),
        _stroke((903.1, 348.2), (903.1, 373.7)),
        _stroke((903.1, 373.7), (903.1, 441.8)),
        _stroke((903.1, 441.8), (903.1, 448.9)),
    ]
    # Also paint west/north/south unique owners so only east uses the chain path.
    strokes = [
        _stroke((328, 140), (328, 450)),
        _stroke((328, 450), (904, 450)),
        _stroke((904, 140), (328, 140)),
        *strokes,
    ]
    east = own_exterior_contour_native_paths(strokes, trace)[2]
    assert east.classification == "source_native_wall_ink_chain_candidate"
    assert east.status is EvidenceResolutionStatus.CANDIDATE
    assert east.chain_end_shortfall_pt is not None
    assert east.chain_end_shortfall_pt <= 2.5
    assert east.physical_wall_authenticated is False
    assert east.commercial_publishable is False


def test_complete_source_chain_preferred_over_partial_unique_owner():
    """Acacia south: two touching strokes beat a single long outer owner alone."""
    trace = _trace(((200, 0), (800, 0), (800, 100), (200, 100)))
    strokes = (
        _stroke((200, 0), (200, 100)),  # west unique
        _stroke((200, 100), (800, 100)),  # north unique
        _stroke((800, 100), (800, 0)),  # east unique
        _stroke((200, 0), (450, 0)),  # south left
        _stroke((450, 0), (800, 0)),  # south right (also unique-length alone)
    )
    south = own_exterior_contour_native_paths(strokes, trace)[0]
    assert south.classification == "source_native_wall_ink_chain_candidate"
    assert south.native_path_indices == (3, 4)
    assert south.physical_wall_authenticated is False


def test_unique_owner_reports_uncovered_tail_fraction():
    # Contour west edge is index 3: (200,100)->(200,0) in this winding.
    trace = _trace(((200, 0), (800, 0), (800, 200), (200, 200)))
    strokes = (
        _stroke((200, 0), (200, 90)),  # west covers only lower portion
        _stroke((200, 200), (800, 200)),
        _stroke((800, 200), (800, 0)),
        _stroke((800, 0), (200, 0)),
    )
    owned = own_exterior_contour_native_paths(strokes, trace)
    west = next(
        edge for edge in owned
        if abs(edge.start_pdf_pts[0] - 200) <= 1 and abs(edge.end_pdf_pts[0] - 200) <= 1
    )
    assert west.classification == "source_native_wall_ink_candidate"
    assert west.unique_owner_overlap_fraction is not None
    assert west.unique_owner_overlap_fraction < 0.6
    assert (
        (west.unique_owner_uncovered_start_pt or 0)
        + (west.unique_owner_uncovered_end_pt or 0)
    ) > 50.0
    assert west.physical_wall_authenticated is False


def test_parallel_source_chains_cannot_be_selected_as_one_wall():
    trace = _trace(((200, 0), (800, 0), (800, 100), (200, 100)))
    # Both faces sit inside contour-face coincidence; neither may win by nearest.
    strokes = (
        [_stroke((200, i * 25), (200, (i + 1) * 25))
         for i in range(4)]
        + [_stroke((200.3, i * 25), (200.3, (i + 1) * 25))
           for i in range(4)]
    )
    edge = own_exterior_contour_native_paths(strokes, trace)[3]
    assert edge.status is EvidenceResolutionStatus.ABSTAINED
    assert edge.reason == "ambiguous_competing_native_path_owners"
    assert set(edge.native_path_indices) == set(range(8))
    assert not edge.physical_wall_authenticated
