"""Source-neutral regression for scale changes in rotated support viewports.

No project, page, or benchmark fixtures are embedded here.
"""
from pb_source_cross_view_floor_correspondence_shadow import (
    build_lines,
    rank_registrations,
)


def _segments(points):
    return [
        {"x1": a[0], "y1": a[1], "x2": b[0], "y2": b[1]}
        for a, b in points
    ]


def test_rotated_viewport_can_have_independent_scale():
    # Asymmetric perpendicular walls avoid a square-grid false positive.
    source = _segments([
        ((0, 0), (40, 0)),
        ((0, 0), (0, 25)),
        ((40, 0), (40, 15)),
        ((0, 25), (17, 25)),
    ])
    # rot90, scale 2, translated +120,+90
    target = _segments([
        ((120, 90), (120, 170)),
        ((120, 90), (70, 90)),
        ((120, 170), (90, 170)),
        ((70, 90), (70, 124)),
    ])
    rows = rank_registrations(
        build_lines(source), build_lines(target),
        identity_scales=(1.0, 2.0), topn=12,
    )
    matching = [r for r in rows if r["orientation"] == "rot90" and r["scale"] == 2.0]
    assert matching, "Rotated support views must be evaluated at independent scales"
    assert matching[0]["min_support_pt"] > 0


def test_identity_only_diagnostic_retains_legacy_fixed_scale():
    source = build_lines(_segments([
        ((0, 0), (40, 0)), ((0, 0), (0, 25)),
    ]))
    rows = rank_registrations(source, source, identity_only=True)
    assert rows
    assert {r["orientation"] for r in rows} == {"identity"}
    assert {r["scale"] for r in rows} == {1.0}
