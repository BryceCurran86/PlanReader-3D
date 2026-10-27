"""Source-safe skirting candidate tests; no original threshold authority is inferred.

These are synthetic diagnostics only. No FIRM, sealed or customer quantity is
issued by the figured wall surface shadow.
"""
from dataclasses import replace
import math

from pb_migration_contracts import EvidenceResolutionStatus
from pb_gpt1_figured_chain_metric_shadow import (
    FiguredPhysicalSide,
    FiguredPolygonMetricShadow,
)
from pb_gpt1_figured_wall_surface_shadow import (
    DocumentedWallHeight,
    DocumentedWallOpening,
    measure_figured_wall_lining_shadow,
)

SHA = "a" * 64
VERTICES = ((0, 0), (10, 0), (10, 5), (0, 5))
METRIC = ((0, 0), (10000, 0), (10000, 5000), (0, 5000))


def _source_inputs():
    ring = tuple(
        FiguredPhysicalSide(
            f"side-{i}", VERTICES[i], VERTICES[(i + 1) % 4],
            (f"ink-{i}",),
        )
        for i in range(4)
    )
    metric = FiguredPolygonMetricShadow(
        EvidenceResolutionStatus.CANDIDATE, ("synthetic",), 50.0,
        METRIC, ("figure-source",), (), SHA, "rev", "7", "room-one",
    )
    metric = replace(
        metric,
        source_side_ids=tuple(f"side-{i}" for i in range(4)),
        source_segment_ids=tuple(f"ink-{i}" for i in range(4)),
        source_vertices_pdf_pts=VERTICES,
    )
    heights = tuple(
        DocumentedWallHeight(
            f"side-{i}", 3000, (f"height-{i}",), SHA, "rev", "7",
        )
        for i in range(4)
    )
    return ring, metric, heights


def _opening(kind, host_side, width, height, start):
    # The opening kind appears only in the diagnostic ID; a word like "door"
    # or "window" cannot certify the finished-floor contact of a frame.
    return DocumentedWallOpening(
        f"{kind}-1", host_side, width, height, f"signed-{kind}",
        (f"host-{kind}",), (f"frame-{kind}",), SHA, "rev", "7",
        published_original_opening_area_m2=width * height / 1_000_000,
        host_axis_start_mm=start,
        host_axis_end_mm=start + width,
        original_host_axis_witness_ids=(
            f"axis-{kind}-left", f"axis-{kind}-right",
        ),
    )


def test_no_openings_preserves_full_skirting_perimeter_candidate():
    ring, metric, heights = _source_inputs()
    result = measure_figured_wall_lining_shadow(ring, metric, heights)
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.candidate_perimeter_m == 30.0
    assert result.candidate_skirting_m == 30.0
    assert result.candidate_net_lining_m2 == 90.0
    assert "source_figured_skirting_opening_floor_contact_unproven" not in result.reason_codes
    assert result.diagnostic_only is True


def test_window_signed_lining_void_does_not_subtract_unproven_skirting_width():
    ring, metric, heights = _source_inputs()
    window = _opening("window", "side-2", 1200, 1000, 1000)
    original_inputs = repr((ring, metric, heights, window))
    result = measure_figured_wall_lining_shadow(ring, metric, heights, (window,))
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.candidate_skirting_m is None
    assert result.reason_codes == (
        "source_figured_wall_surface_shadow_only",
        "source_figured_skirting_opening_floor_contact_unproven",
    )
    assert result.candidate_gross_lining_m2 == 90.0
    assert math.isclose(result.candidate_net_lining_m2, 88.8)
    assert result.candidate_opening_deductions_m2 == (("window-1", 1.2),)
    assert repr((ring, metric, heights, window)) == original_inputs
    assert measure_figured_wall_lining_shadow(ring, metric, heights, (window,)) == result


def test_door_label_and_multiple_source_hosted_openings_still_cannot_grant_skirting():
    ring, metric, heights = _source_inputs()
    door = _opening("door", "side-0", 1000, 2100, 0)
    window = _opening("window", "side-2", 1200, 1000, 1000)
    first = measure_figured_wall_lining_shadow(
        ring, metric, heights, (door, window),
    )
    reversed_input = measure_figured_wall_lining_shadow(
        ring, metric, heights, (window, door),
    )
    assert first == reversed_input
    assert first.status is EvidenceResolutionStatus.CANDIDATE
    assert first.candidate_skirting_m is None
    assert first.candidate_perimeter_m == 30.0
    assert math.isclose(first.candidate_net_lining_m2, 86.7)
    assert first.candidate_opening_deductions_m2 == (
        ("door-1", 2.1), ("window-1", 1.2),
    )
    assert first.diagnostic_only is True
