"""Independent GPT-2 red-team for a reusable whole-wall opening host frame.

TEST-ONLY / EXPECTED-RED / DO NOT MERGE.

Integration base combines exact post-#417 main with the exact #411 production
files.  These tests do not change production code.  They prove the key Physical
Opening Void V2 prerequisite that two openings on one physical wall share one
producer-owned wall coordinate frame even when their authenticated opening-scoped
host bindings legitimately contain different local wall pieces.
"""
from __future__ import annotations

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_host_binding_authority import (
    OpeningHostBindingProducer,
    OpeningHostBindingSelector,
    OpeningHostWallUniverseProducer,
    OpeningHostWallUniverseSelector,
)
from pb_opening_host_frame_authority import OpeningHostFrameProducer
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, PhysicalOpeningAuthority
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _two_opening_pdf(
    *,
    dx: float = 0.0,
    dy: float = 0.0,
    reverse_segments: bool = False,
) -> bytes:
    """One straight two-face wall interrupted by two 40pt openings."""
    doc = fitz.open()
    try:
        page = doc.new_page(width=460.0, height=360.0)
        shape = page.new_shape()
        segments = [
            # top face: left / between openings / right
            ((20.0 + dx, 80.0 + dy), (100.0 + dx, 80.0 + dy)),
            ((140.0 + dx, 80.0 + dy), (220.0 + dx, 80.0 + dy)),
            ((260.0 + dx, 80.0 + dy), (340.0 + dx, 80.0 + dy)),
            # bottom face
            ((20.0 + dx, 100.0 + dy), (100.0 + dx, 100.0 + dy)),
            ((140.0 + dx, 100.0 + dy), (220.0 + dx, 100.0 + dy)),
            ((260.0 + dx, 100.0 + dy), (340.0 + dx, 100.0 + dy)),
            # opening jambs
            ((100.0 + dx, 80.0 + dy), (100.0 + dx, 100.0 + dy)),
            ((140.0 + dx, 80.0 + dy), (140.0 + dx, 100.0 + dy)),
            ((220.0 + dx, 80.0 + dy), (220.0 + dx, 100.0 + dy)),
            ((260.0 + dx, 80.0 + dy), (260.0 + dx, 100.0 + dy)),
        ]
        for start, end in segments:
            if reverse_segments:
                start, end = end, start
            shape.draw_line(fitz.Point(*start), fitz.Point(*end))
        shape.finish(width=1.0)
        shape.commit()
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _publish_frames(payload: bytes):
    source = SourceVisibilityProducer(
        producer_method="gpt2-shared-host-frame-redteam",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="gpt2-shared-host-frame-two-openings",
        source_bytes=payload,
        source_locator="memory://gpt2-shared-host-frame-two-openings.pdf",
    )
    physical = PhysicalOpeningAuthority(source.authority())

    openings: dict[str, tuple[ObservationSelector, object]] = {}
    for observation_id in published.visible_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = physical.prove_existence(selector)
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.proposition == PHYSICAL_OPENING_EXISTS
            and result.existence_record is not None
        ):
            openings.setdefault(result.existence_record.record_id, (selector, result.existence_record))

    assert len(openings) == 2

    wall_authority = PhysicalWallCandidateProducer.from_source_visibility_producer(source).authority()
    first_record = next(iter(openings.values()))[1]
    decision_scope_id = f"wall-source:page-{first_record.page_id}"
    universe_authority = OpeningHostWallUniverseProducer.from_physical_wall_candidate_authority(
        wall_authority
    ).authority()
    universe_selector = OpeningHostWallUniverseSelector(
        document_id=first_record.document_id,
        revision_id=first_record.revision_id,
        source_sha256=first_record.source_sha256,
        snapshot_id=first_record.snapshot_id,
        page_id=first_record.page_id,
        decision_scope_id=decision_scope_id,
    )
    universe = universe_authority.resolve_scope(universe_selector)
    assert universe.status is EvidenceResolutionStatus.CORROBORATED
    assert universe.scope_complete is True

    binding_producer = OpeningHostBindingProducer.from_authorities(
        physical_opening_authority=physical,
        host_wall_universe_authority=universe_authority,
    )
    frame_producer = OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=physical,
        host_binding_authority=binding_producer.authority(),
        physical_wall_candidate_authority=wall_authority,
    )

    bindings = []
    frames = []
    for opening_selector, _opening_record in openings.values():
        binding_result = binding_producer.publish(
            opening_left_selector=opening_selector,
            opening_right_selector=opening_selector,
            host_universe_selector=universe_selector,
        )
        assert binding_result.status is EvidenceResolutionStatus.CORROBORATED
        assert binding_result.record is not None
        binding = binding_result.record
        bindings.append(binding)

        binding_selector = OpeningHostBindingSelector(
            document_id=binding.document_id,
            revision_id=binding.revision_id,
            source_sha256=binding.source_sha256,
            snapshot_id=binding.snapshot_id,
            page_id=binding.page_id,
            decision_scope_id=binding.decision_scope_id,
            opening_identity_id=binding.opening_identity_id,
        )
        frame_result = frame_producer.publish(
            opening_selector=opening_selector,
            host_binding_selector=binding_selector,
        )
        assert frame_result.status is EvidenceResolutionStatus.CORROBORATED
        assert frame_result.evidence is not None
        frames.append(frame_result.evidence)

    wall_scope = wall_authority.resolve_scope(
        PhysicalWallCandidateSelector(
            document_id=first_record.document_id,
            revision_id=first_record.revision_id,
            source_sha256=first_record.source_sha256,
            snapshot_id=first_record.snapshot_id,
            page_id=first_record.page_id,
            decision_scope_id=decision_scope_id,
        )
    )
    assert wall_scope.status is EvidenceResolutionStatus.CORROBORATED
    assert wall_scope.scope_complete is True
    records_by_id = {record.wall_candidate_id: record for record in wall_scope.records}

    local_extents = []
    for binding in bindings:
        xs = [
            float(point[0])
            for member_id in binding.member_wall_candidate_ids
            for point in records_by_id[member_id].wall_candidate.centerline_pts
        ]
        local_extents.append((min(xs), max(xs)))

    # This must be true before the frame assertion has any value: the two host
    # proofs really are opening-local and select different split pieces.
    assert len(set(local_extents)) == 2
    return tuple(frames), tuple(local_extents)


def _rounded_span(frame) -> tuple[float, float]:
    return (round(float(frame.u0_pt), 6), round(float(frame.u1_pt), 6))


def test_two_openings_on_one_wall_share_one_whole_wall_frame() -> None:
    """Expected RED on current #411: binding-member min/max is not whole-wall extent."""
    frames, local_extents = _publish_frames(_two_opening_pdf())
    assert len(frames) == 2
    assert len(set(local_extents)) == 2

    # Both openings belong to the same physical wall coordinate system.  A
    # correct producer-owned traversal therefore anchors both at the whole-wall
    # centreline origin x=20,y=90 rather than each opening's local member min.
    assert {tuple(frame.origin_pt) for frame in frames} == {(20.0, 90.0)}
    assert {tuple(frame.axis_unit) for frame in frames} == {(1.0, 0.0)}
    assert {round(float(frame.wall_thickness_pt), 6) for frame in frames} == {20.0}

    # Whole-wall local coordinates distinguish the two openings.
    assert sorted(_rounded_span(frame) for frame in frames) == [
        (80.0, 120.0),
        (200.0, 240.0),
    ]


def test_shared_whole_wall_coordinates_are_translation_invariant() -> None:
    base_frames, _ = _publish_frames(_two_opening_pdf())
    shifted_frames, _ = _publish_frames(_two_opening_pdf(dx=50.0, dy=40.0))

    assert {tuple(frame.origin_pt) for frame in base_frames} == {(20.0, 90.0)}
    assert {tuple(frame.origin_pt) for frame in shifted_frames} == {(70.0, 130.0)}
    assert sorted(_rounded_span(frame) for frame in base_frames) == sorted(
        _rounded_span(frame) for frame in shifted_frames
    ) == [(80.0, 120.0), (200.0, 240.0)]


def test_shared_whole_wall_frame_ignores_source_segment_direction() -> None:
    forward_frames, _ = _publish_frames(_two_opening_pdf())
    reversed_frames, _ = _publish_frames(_two_opening_pdf(reverse_segments=True))

    assert {tuple(frame.origin_pt) for frame in forward_frames} == {
        tuple(frame.origin_pt) for frame in reversed_frames
    } == {(20.0, 90.0)}
    assert sorted(_rounded_span(frame) for frame in forward_frames) == sorted(
        _rounded_span(frame) for frame in reversed_frames
    ) == [(80.0, 120.0), (200.0, 240.0)]


# Baseline CI trigger: assertions above are the independent contract under test.
