"""Source-figured metric chains recover true polygon area without PDF scale."""
from dataclasses import replace
import math

from pb_gpt1_figured_chain_metric_shadow import (
    FiguredPhysicalSide,
    measure_figured_room_edge_chain_shadow,
)
from pb_migration_contracts import EvidenceResolutionStatus

SHA = "a" * 64


def _polygon(vertices, measured):
    edges = []
    for i, start in enumerate(vertices):
        end = vertices[(i + 1) % len(vertices)]
        value = measured.get(i)
        edges.append(FiguredPhysicalSide(
            source_side_id=f"source-side-{i}",
            start_pdf_pt=start,
            end_pdf_pt=end,
            source_segment_ids=(f"source-original-line-{i}",),
            length_mm=value,
            figured_dimension_id=(f"figured-dimension-{i}" if value is not None else None),
            witness_observation_ids=(
                (f"dimension-witness-{i}-a", f"dimension-witness-{i}-b")
                if value is not None else ()
            ),
        ))
    return tuple(edges)


def _run(sides):
    return measure_figured_room_edge_chain_shadow(
        sides, source_sha256=SHA, revision_id="r1", page_id="7",
        physical_room_id="original-room-1",
    )


def test_source_figured_rectangle_recovers_metric_area_with_no_page_scale():
    # Only two original orthogonal figured dimensions exist; closure uniquely
    # determines the other two opposing wall spans, never the PDF scale.
    ring = ((0, 0), (10, 0), (10, 5), (0, 5))
    result = _run(_polygon(ring, {0: 5000, 1: 2000}))
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.candidate_area_m2 == 10.0
    assert result.closure_inferred_side_ids == ("source-side-2", "source-side-3")
    assert result.diagnostic_only is True


def test_concave_source_figured_chain_calculates_true_l_area_not_bbox():
    ring = ((0, 0), (8, 0), (8, 3), (4, 3), (4, 6), (0, 6))
    result = _run(_polygon(ring, {0: 8000, 1: 3000, 2: 4000, 3: 3000}))
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.candidate_area_m2 == 36.0  # 8m x 3m plus 4m x 3m
    assert result.candidate_area_m2 != 48.0  # Bounding rectangle is wrong


def test_figured_area_is_independent_of_original_pdf_translation_rotation():
    ring = ((0, 0), (10, 0), (10, 5), (0, 5))
    original = _run(_polygon(ring, {0: 5000, 1: 2000}))
    moved = tuple((-y + 180, x - 73) for x, y in ring)
    translated_and_rotated = _run(_polygon(moved, {0: 5000, 1: 2000}))
    assert translated_and_rotated.candidate_area_m2 == original.candidate_area_m2
    assert translated_and_rotated.source_figure_ids == original.source_figure_ids


def test_cyclic_source_side_reordering_preserves_measured_area():
    sides = _polygon(((0, 0), (10, 0), (10, 5), (0, 5)), {0: 5000, 1: 2000})
    for i in range(len(sides)):
        result = _run(sides[i:] + sides[:i])
        assert result.candidate_area_m2 == 10.0


def test_figured_dimension_conflict_abstains_instead_of_calibrating_scale():
    ring = ((0, 0), (10, 0), (10, 5), (0, 5))
    mismatch = _polygon(ring, {0: 5000, 1: 2000, 2: 4000, 3: 2000})
    result = _run(mismatch)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.candidate_area_m2 is None
    assert result.reason_codes == ("figured_room_edge_chain_closure_conflict",)


def test_underconstrained_source_ring_stays_unmeasured():
    sides = _polygon(((0, 0), (10, 0), (10, 5), (0, 5)), {0: 5000})
    result = _run(sides)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == ("figured_room_edge_chain_underconstrained",)


def test_bowtie_source_ring_never_creates_a_metric_floor():
    ring = ((0, 0), (10, 10), (0, 10), (10, 0))
    result = _run(_polygon(ring, {0: 5000, 1: 2000}))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.candidate_area_m2 is None


def test_missing_original_witness_observation_is_not_a_metric_measurement():
    sides = list(_polygon(((0, 0), (10, 0), (10, 5), (0, 5)),
                          {0: 5000, 1: 2000}))
    sides[0] = replace(sides[0], witness_observation_ids=("only-one",))
    result = _run(tuple(sides))
    assert result.reason_codes == ("figured_source_dimension_receipt_incomplete",)


def test_same_original_figured_dimension_reissued_for_two_sides_abstains():
    sides = list(_polygon(((0, 0), (10, 0), (10, 5), (0, 5)),
                          {0: 5000, 1: 2000}))
    sides[1] = replace(sides[1], figured_dimension_id="figured-dimension-0")
    assert _run(tuple(sides)).status is EvidenceResolutionStatus.ABSTAINED


def test_only_a_candidate_m2_is_exposed_and_no_quantity_is_minted():
    sides = _polygon(((0, 0), (10, 0), (10, 5), (0, 5)), {0: 5000, 1: 2000})
    out = _run(sides)
    assert out.status is EvidenceResolutionStatus.CANDIDATE
    assert not hasattr(out, "quantity_id")
    assert out.diagnostic_only is True
    assert out.source_sha256 == SHA
