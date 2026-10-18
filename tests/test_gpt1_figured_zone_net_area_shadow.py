"""Independently source-figured physical void area is subtracted exactly once."""
from dataclasses import replace

from pb_gpt1_figured_chain_metric_shadow import (
    FiguredPhysicalSide, measure_figured_room_edge_chain_shadow,
)
from pb_gpt1_figured_zone_net_area_shadow import (
    SourceFiguredAreaVoid, source_figured_net_zone_area_shadow,
)
from pb_migration_contracts import EvidenceResolutionStatus


def _measured_box(x0, y0, x1, y1, width, height, prefix):
    points = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    sides = []
    for i, (a, b) in enumerate(zip(points, points[1:] + points[:1])):
        given = {0: width, 1: height}.get(i)
        sides.append(FiguredPhysicalSide(
            f"{prefix}-side-{i}", a, b, (f"{prefix}-segment-{i}",),
            given, f"{prefix}-dimension-{i}" if given is not None else None,
            (f"{prefix}-witness-{i}-1", f"{prefix}-witness-{i}-2")
            if given is not None else (),
        ))
    result = measure_figured_room_edge_chain_shadow(
        tuple(sides), source_sha256="a" * 64,
        revision_id="r1", page_id="7", physical_room_id="room-1",
    )
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    return result, points


def test_fully_source_bound_hole_subtracts_metric_area_without_plan_scale():
    gross, perimeter = _measured_box(0, 0, 10, 10, 10000, 10000, "gross")
    child, ring = _measured_box(3, 3, 5, 5, 2000, 2000, "hole")
    void = SourceFiguredAreaVoid("physical-void-a", child, ring, ("ink-void-a",))
    net = source_figured_net_zone_area_shadow(gross, perimeter, (void,))
    assert net.status is EvidenceResolutionStatus.CANDIDATE
    assert net.gross_area_m2 == 100.0
    assert net.separately_measured_void_m2 == (("physical-void-a", 4.0),)
    assert net.candidate_net_area_m2 == 96.0
    assert net.diagnostic_only is True


def test_two_separate_original_source_voids_do_not_merge_or_disappear():
    gross, outer = _measured_box(0, 0, 20, 20, 20000, 20000, "gross")
    a, ring_a = _measured_box(3, 3, 5, 5, 2000, 2000, "hole-a")
    b, ring_b = _measured_box(8, 8, 11, 11, 3000, 3000, "hole-b")
    voids = (
        SourceFiguredAreaVoid("b", b, ring_b, ("b-source-ink",)),
        SourceFiguredAreaVoid("a", a, ring_a, ("a-source-ink",)),
    )
    result = source_figured_net_zone_area_shadow(gross, outer, voids)
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.candidate_net_area_m2 == 387.0
    assert result.separately_measured_void_m2 == (("a", 4.0), ("b", 9.0))


def test_void_without_authentic_original_containment_is_not_deducted():
    gross, outer = _measured_box(0, 0, 10, 10, 10000, 10000, "gross")
    hole, _ = _measured_box(20, 20, 22, 22, 2000, 2000, "hole")
    fake = SourceFiguredAreaVoid(
        "physical-void", hole,
        ((20, 20), (22, 20), (22, 22), (20, 22)),
        ("hole-source",),
    )
    result = source_figured_net_zone_area_shadow(gross, outer, (fake,))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.candidate_net_area_m2 is None


def test_overlapping_voids_cannot_double_deduct_source_area():
    gross, outer = _measured_box(0, 0, 20, 20, 20000, 20000, "gross")
    a, ring_a = _measured_box(3, 3, 7, 7, 4000, 4000, "a")
    b, ring_b = _measured_box(6, 6, 8, 8, 2000, 2000, "b")
    voids = (
        SourceFiguredAreaVoid("a", a, ring_a, ("a-source",)),
        SourceFiguredAreaVoid("b", b, ring_b, ("b-source",)),
    )
    result = source_figured_net_zone_area_shadow(gross, outer, voids)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == ("figured_source_voids_overlap",)


def test_foreign_original_source_void_is_not_deducted():
    gross, outer = _measured_box(0, 0, 10, 10, 10000, 10000, "gross")
    hole, ring = _measured_box(3, 3, 5, 5, 2000, 2000, "hole")
    other = replace(hole, source_sha256="b" * 64)
    out = source_figured_net_zone_area_shadow(
        gross, outer, (SourceFiguredAreaVoid("foreign", other, ring, ("foreign-source",)),)
    )
    assert out.status is EvidenceResolutionStatus.ABSTAINED
    assert out.reason_codes == ("figured_source_void_metric_lineage_conflict",)
