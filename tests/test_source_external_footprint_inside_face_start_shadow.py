"""#4549-01..05: inside-face start, left-turn closure, ink bands, porch/garage."""
from __future__ import annotations

from pb_source_external_footprint_inside_face_start_shadow import (
    ExteriorWallSegment,
    build_external_footprint_inside_face_bundle,
    classify_wall_ink_band,
    resolve_external_footprint_inside_face_start,
    walk_clockwise_left_turn_contour,
)

_PAGE = (0.0, 0.0, 400.0, 300.0)


def _rect_shell(*, include_porch: bool = False) -> tuple[ExteriorWallSegment, ...]:
    # Clockwise page rectangle: unique-longest south wall (01 dominant).
    rows = [
        # South is the unique longest single native segment (220pt).
        # North is split so no equal-length rival exists.
        ExteriorWallSegment(1, (40, 40), (260, 40), gray=0.0, stroke_weight_pt=2.5),
        ExteriorWallSegment(2, (260, 40), (260, 160), gray=0.0, stroke_weight_pt=2.5),
        ExteriorWallSegment(3, (260, 160), (150, 160), gray=0.0, stroke_weight_pt=2.5),
        ExteriorWallSegment(4, (150, 160), (40, 160), gray=0.0, stroke_weight_pt=2.5),
        ExteriorWallSegment(5, (40, 160), (40, 40), gray=0.0, stroke_weight_pt=2.5),
    ]
    if include_porch:
        rows.extend(
            [
                ExteriorWallSegment(
                    9, (230, 40), (280, 40), gray=0.0, stroke_weight_pt=2.0, label="PORCH",
                ),
                ExteriorWallSegment(
                    10, (280, 40), (280, 80), gray=0.0, stroke_weight_pt=2.0, label="PORCH",
                ),
            ]
        )
    return tuple(rows)


def test_01_start_is_inside_face_of_dominant_dark_wall_not_page_frame():
    shell = _rect_shell()
    frame = ExteriorWallSegment(
        99, (1, 1), (399, 1), gray=0.0, stroke_weight_pt=3.0,
    )
    # Longer dark south wall remains dominant over frame.
    long_south = ExteriorWallSegment(
        1, (40, 40), (260, 40), gray=0.0, stroke_weight_pt=2.5,
    )
    segs = (long_south, shell[1], shell[2], shell[3], frame)
    start = resolve_external_footprint_inside_face_start(
        segs, page_bounds_pdf_pts=_PAGE,
    )
    assert start.status == "CANDIDATE"
    assert start.start_wall_id == 1
    assert start.start_pdf_pts is not None
    # Inside-face seed is south of the outer stroke midline (toward centroid).
    assert start.start_pdf_pts[1] > 40.0
    assert start.ink is not None and start.ink.role == "structural_wall"
    assert start.measurement_authorized is False


def test_01_page_frame_only_ink_abstains():
    frame = (
        ExteriorWallSegment(1, (2, 2), (398, 2), gray=0.0, stroke_weight_pt=2.0),
        ExteriorWallSegment(2, (398, 2), (398, 298), gray=0.0, stroke_weight_pt=2.0),
        ExteriorWallSegment(3, (398, 298), (2, 298), gray=0.0, stroke_weight_pt=2.0),
        ExteriorWallSegment(4, (2, 298), (2, 2), gray=0.0, stroke_weight_pt=2.0),
    )
    start = resolve_external_footprint_inside_face_start(
        frame, page_bounds_pdf_pts=_PAGE,
    )
    assert start.status == "ABSTAINED"
    assert start.reason == "no_dominant_dark_outer_wall_inside_page"


def test_02_clockwise_left_turn_closes_to_start():
    segs = _rect_shell()
    start = resolve_external_footprint_inside_face_start(
        segs, page_bounds_pdf_pts=_PAGE,
    )
    walk = walk_clockwise_left_turn_contour(segs, start=start)
    assert walk.status == "CANDIDATE"
    assert walk.closed_to_start is True
    assert walk.steps >= 4
    assert walk.left_turn_ranks
    assert all(ranks for ranks in walk.left_turn_ranks)


def test_03_ink_classifier_normalizes_gray_and_weight_bands():
    dark = classify_wall_ink_band(gray=0.05, stroke_weight_pt=2.0)
    pale = classify_wall_ink_band(gray=0.7, stroke_weight_pt=2.0)
    hair = classify_wall_ink_band(gray=0.05, stroke_weight_pt=0.2)
    frame = classify_wall_ink_band(
        gray=0.0, stroke_weight_pt=3.0, near_page_frame=True,
    )
    assert dark.role == "structural_wall" and dark.normalized_weight_band == "heavy"
    assert pale.role == "decoration"
    assert hair.role == "decoration"
    assert frame.role == "page_frame"


def test_04_porch_edges_excluded_from_enclosed_contour():
    segs = _rect_shell(include_porch=True)
    bundle = build_external_footprint_inside_face_bundle(
        segs, page_bounds_pdf_pts=_PAGE,
    )
    assert bundle.walk.status == "CANDIDATE"
    assert bundle.walk.porch_edges_excluded == 2
    assert bundle.walk.closed_to_start is True
    xs = [p[0] for p in bundle.walk.vertices_pdf_pts]
    assert max(xs) <= 265.0


def test_05_garage_panel_bridge_closes_gap_without_wall_authority():
    # Open south edge; unique-longest north wall seeds the walk.
    open_shell = (
        ExteriorWallSegment(1, (40, 40), (100, 40), gray=0.0, stroke_weight_pt=2.5),
        ExteriorWallSegment(2, (160, 40), (220, 40), gray=0.0, stroke_weight_pt=2.5),
        ExteriorWallSegment(3, (220, 40), (220, 160), gray=0.0, stroke_weight_pt=2.5),
        ExteriorWallSegment(4, (220, 160), (40, 160), gray=0.0, stroke_weight_pt=2.5),
        ExteriorWallSegment(5, (40, 160), (40, 40), gray=0.0, stroke_weight_pt=2.5),
    )
    bridge = (
        ExteriorWallSegment(
            50, (100, 40), (160, 40), gray=0.0, stroke_weight_pt=2.0, label="GARAGE",
        ),
    )
    bundle = build_external_footprint_inside_face_bundle(
        open_shell,
        page_bounds_pdf_pts=_PAGE,
        garage_bridge_segments=bridge,
    )
    assert bundle.walk.garage_topology_bridges == 1
    assert bundle.walk.status == "CANDIDATE"
    assert bundle.walk.closed_to_start is True
    assert bundle.walk.to_dict()["doorway_closure_is_not_physical_wall"] is True
    assert bundle.to_dict()["measurement_authorized"] is False


def test_ambiguous_equal_dominant_walls_abstain():
    segs = (
        ExteriorWallSegment(1, (40, 40), (140, 40), gray=0.0, stroke_weight_pt=2.5),
        ExteriorWallSegment(2, (40, 160), (140, 160), gray=0.0, stroke_weight_pt=2.5),
    )
    start = resolve_external_footprint_inside_face_start(
        segs, page_bounds_pdf_pts=_PAGE,
    )
    assert start.status == "ABSTAINED"
    assert start.reason == "ambiguous_dominant_outer_wall_lengths"
