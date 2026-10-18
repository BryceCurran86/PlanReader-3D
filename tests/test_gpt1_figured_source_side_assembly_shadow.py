"""Reconstruction of split source wall strokes before documented ring area."""
from dataclasses import replace

from pb_gpt1_figured_source_side_assembly_shadow import (
    FiguredSideSourceMembership,
    SourceWallFragment,
    assemble_original_figured_side_fragments,
    assemble_original_figured_room_ring,
)
from pb_gpt1_figured_chain_metric_shadow import (
    FiguredPhysicalSide, measure_figured_room_edge_chain_shadow,
)
from pb_migration_contracts import EvidenceResolutionStatus


def _two_fragments(tag, start, middle, end, metric=None):
    fragments = (
        SourceWallFragment(f"{tag}-left", start, middle),
        SourceWallFragment(f"{tag}-right", end, middle),
    )
    membership = FiguredSideSourceMembership(
        source_side_id=tag,
        segment_observation_ids=(f"{tag}-left", f"{tag}-right"),
        measured_length_mm=metric,
        figured_dimension_id=f"{tag}-figure" if metric is not None else None,
        figured_witness_ids=(f"{tag}-w1", f"{tag}-w2") if metric is not None else (),
    )
    return membership, fragments


def _shadow_area(sides):
    return measure_figured_room_edge_chain_shadow(
        sides, source_sha256="a" * 64, revision_id="r1",
        page_id="7", physical_room_id="room-1",
    )


def test_split_original_wall_segments_preserve_single_figured_source_owner():
    member, fragments = _two_fragments("wall-a", (0, 0), (5, 0), (10, 0), 5000)
    result = assemble_original_figured_side_fragments(member, fragments)
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.physical_side.source_segment_ids == ("wall-a-left", "wall-a-right")
    assert result.physical_side.length_mm == 5000
    assert result.physical_side.figured_dimension_id == "wall-a-figure"


def test_reversed_and_shuffled_native_fragements_are_split_invariant():
    member, fragments = _two_fragments("wall-a", (0, 0), (5, 0), (10, 0), 5000)
    original = assemble_original_figured_side_fragments(member, fragments)
    reversed_order = assemble_original_figured_side_fragments(
        member, tuple(reversed(fragments))
    )
    assert original.physical_side == reversed_order.physical_side


def test_split_walls_can_be_stitched_into_independently_figured_room_area():
    endpoints = ((0, 0), (10, 0), (10, 5), (0, 5))
    original_sides = []
    for n, (start, end) in enumerate(zip(endpoints, endpoints[1:] + endpoints[:1])):
        mid = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        member, segments = _two_fragments(
            f"physical-wall-{n}", start, mid, end,
            {0: 5000, 1: 2000}.get(n),
        )
        result = assemble_original_figured_side_fragments(member, segments)
        assert result.status is EvidenceResolutionStatus.CANDIDATE
        original_sides.append(result.physical_side)
    scrambled = (
        original_sides[2], original_sides[0],
        original_sides[3], original_sides[1],
    )
    ring = assemble_original_figured_room_ring(scrambled)
    assert ring.status is EvidenceResolutionStatus.CANDIDATE
    area = _shadow_area(ring.ordered_sides)
    assert area.status is EvidenceResolutionStatus.CANDIDATE
    assert area.candidate_area_m2 == 10.0


def test_missing_source_fragment_does_not_impute_a_wall():
    member, fragments = _two_fragments("side", (0, 0), (5, 0), (10, 0))
    result = assemble_original_figured_side_fragments(member, fragments[:1])
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.physical_side is None


def test_gapped_or_overlapping_original_segment_chain_does_not_make_a_side():
    member, fragments = _two_fragments("side", (0, 0), (5, 0), (10, 0))
    for broken in (
        replace(fragments[1], start_pdf_pt=(10, 0), end_pdf_pt=(6, 0)),
        replace(fragments[1], start_pdf_pt=(10, 0), end_pdf_pt=(4, 0)),
    ):
        out = assemble_original_figured_side_fragments(member, (fragments[0], broken))
        assert out.status is EvidenceResolutionStatus.ABSTAINED


def test_unrelated_or_reused_source_fragments_do_not_get_closest_owner():
    member, fragments = _two_fragments("side", (0, 0), (5, 0), (10, 0))
    modified = replace(fragments[1], source_segment_id="foreign-segment")
    result = assemble_original_figured_side_fragments(member, (fragments[0], modified))
    assert result.status is EvidenceResolutionStatus.ABSTAINED


def test_branched_room_perimeter_cannot_be_silently_normalized():
    valid = (
        FiguredPhysicalSide("a", (0, 0), (10, 0), ("1",)),
        FiguredPhysicalSide("b", (10, 0), (10, 5), ("2",)),
        FiguredPhysicalSide("c", (10, 5), (0, 5), ("3",)),
        FiguredPhysicalSide("d", (0, 5), (0, 0), ("4",)),
    )
    assert assemble_original_figured_room_ring(valid).status is EvidenceResolutionStatus.CANDIDATE
    altered = valid[:3] + (
        replace(valid[3], end_pdf_pt=(0, 2)),
    )
    assert assemble_original_figured_room_ring(altered).status is EvidenceResolutionStatus.ABSTAINED


def test_two_independent_closed_original_rooms_cannot_form_one_room_issuer():
    first = (
        FiguredPhysicalSide("a", (0, 0), (1, 0), ("a",)),
        FiguredPhysicalSide("b", (1, 0), (1, 1), ("b",)),
        FiguredPhysicalSide("c", (1, 1), (0, 1), ("c",)),
        FiguredPhysicalSide("d", (0, 1), (0, 0), ("d",)),
    )
    second = tuple(replace(
        side, source_side_id=side.source_side_id + "2",
        start_pdf_pt=(side.start_pdf_pt[0] + 10, side.start_pdf_pt[1]),
        end_pdf_pt=(side.end_pdf_pt[0] + 10, side.end_pdf_pt[1]),
    ) for side in first)
    assert assemble_original_figured_room_ring(first + second).status is EvidenceResolutionStatus.ABSTAINED
