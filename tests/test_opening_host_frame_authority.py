"""Production regressions for source-space opening whole-wall host-frame authority."""
from __future__ import annotations

import dataclasses
import inspect

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
import pb_opening_host_binding_authority as host_geometry
from pb_opening_host_binding_authority import (
    OpeningHostBindingProducer,
    OpeningHostBindingSelector,
    OpeningHostWallUniverseProducer,
    OpeningHostWallUniverseSelector,
)
from pb_opening_host_frame_authority import (
    OPENING_HOST_FRAME_WHOLE_WALL_UNPROVEN,
    OpeningHostFrameAuthority,
    OpeningHostFrameProducer,
)
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, PhysicalOpeningAuthority
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _single_pdf(*, dx: float = 0.0, dy: float = 0.0, reverse: bool = False) -> bytes:
    segments = [
        ((20.0 + dx, 80.0 + dy), (120.0 + dx, 80.0 + dy)),
        ((160.0 + dx, 80.0 + dy), (280.0 + dx, 80.0 + dy)),
        ((20.0 + dx, 100.0 + dy), (120.0 + dx, 100.0 + dy)),
        ((160.0 + dx, 100.0 + dy), (280.0 + dx, 100.0 + dy)),
        ((120.0 + dx, 80.0 + dy), (120.0 + dx, 100.0 + dy)),
        ((160.0 + dx, 80.0 + dy), (160.0 + dx, 100.0 + dy)),
    ]
    doc = fitz.open()
    try:
        page = doc.new_page(width=420.0, height=320.0)
        shape = page.new_shape()
        for start, end in segments:
            if reverse:
                start, end = end, start
            shape.draw_line(fitz.Point(*start), fitz.Point(*end))
        shape.finish(width=1.0)
        shape.commit()
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _two_opening_pdf(*, remote_unproven: bool = False) -> bytes:
    openings = ((100.0, 140.0), (220.0, 260.0))
    intervals = ((20.0, 100.0), (140.0, 220.0), (260.0, 340.0))
    doc = fitz.open()
    try:
        page = doc.new_page(width=620.0, height=360.0)
        shape = page.new_shape()
        for y in (80.0, 100.0):
            for start, end in intervals:
                shape.draw_line(fitz.Point(start, y), fitz.Point(end, y))
        for start, end in openings:
            shape.draw_line(fitz.Point(start, 80.0), fitz.Point(start, 100.0))
            shape.draw_line(fitz.Point(end, 80.0), fitz.Point(end, 100.0))
        if remote_unproven:
            for y in (80.0, 100.0):
                shape.draw_line(fitz.Point(420.0, y), fitz.Point(480.0, y))
        shape.finish(width=1.0)
        shape.commit()
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _fixture(payload: bytes, *, expected_openings: int):
    source = SourceVisibilityProducer(
        producer_method="opening-host-frame-production-test",
        producer_version="2.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="opening-host-frame-production",
        source_bytes=payload,
        source_locator="memory://opening-host-frame-production.pdf",
    )
    physical = PhysicalOpeningAuthority(source.authority())
    discovered: dict[str, tuple[ObservationSelector, object]] = {}
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
            discovered.setdefault(result.existence_record.record_id, (selector, result.existence_record))
    assert len(discovered) == expected_openings

    ordered = []
    for selector, opening in discovered.values():
        geometry = host_geometry._opening_geometry(physical, opening)
        assert geometry is not None
        scalar = float(geometry.origin[0]) * float(geometry.axis[0]) + float(geometry.origin[1]) * float(geometry.axis[1])
        ordered.append((scalar, selector, opening))
    ordered.sort(key=lambda item: item[0])

    wall_authority = PhysicalWallCandidateProducer.from_source_visibility_producer(source).authority()
    first = ordered[0][2]
    universe_authority = OpeningHostWallUniverseProducer.from_physical_wall_candidate_authority(
        wall_authority
    ).authority()
    universe_selector = OpeningHostWallUniverseSelector(
        document_id=first.document_id,
        revision_id=first.revision_id,
        source_sha256=first.source_sha256,
        snapshot_id=first.snapshot_id,
        page_id=first.page_id,
        decision_scope_id=f"wall-source:page-{first.page_id}",
    )
    binding_producer = OpeningHostBindingProducer.from_authorities(
        physical_opening_authority=physical,
        host_wall_universe_authority=universe_authority,
    )
    bound = []
    for _scalar, opening_selector, opening in ordered:
        binding = binding_producer.publish(
            opening_left_selector=opening_selector,
            opening_right_selector=opening_selector,
            host_universe_selector=universe_selector,
        )
        assert binding.status is EvidenceResolutionStatus.CORROBORATED
        assert binding.record is not None
        bound.append(
            (
                opening_selector,
                opening,
                OpeningHostBindingSelector(
                    document_id=binding.record.document_id,
                    revision_id=binding.record.revision_id,
                    source_sha256=binding.record.source_sha256,
                    snapshot_id=binding.record.snapshot_id,
                    page_id=binding.record.page_id,
                    decision_scope_id=binding.record.decision_scope_id,
                    opening_identity_id=binding.record.opening_identity_id,
                ),
                binding.record,
            )
        )

    frame_producer = OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=physical,
        host_binding_authority=binding_producer.authority(),
        physical_wall_candidate_authority=wall_authority,
    )
    return physical, wall_authority, binding_producer, frame_producer, tuple(bound)


def _publish_all(frame_producer, bound):
    results = []
    for opening_selector, _opening, binding_selector, _binding in bound:
        results.append(
            frame_producer.publish(
                opening_selector=opening_selector,
                host_binding_selector=binding_selector,
            )
        )
    return tuple(results)


def test_authority_and_producer_are_sealed_and_no_raw_geometry_surface() -> None:
    physical, wall_authority, binding_producer, _frame_producer, _bound = _fixture(
        _single_pdf(), expected_openings=1
    )
    with pytest.raises(TypeError):
        OpeningHostFrameProducer(physical, binding_producer.authority(), wall_authority)
    with pytest.raises(ValueError):
        OpeningHostFrameAuthority({}, _seal=object())
    forbidden = {
        "host_wall_id", "origin", "axis", "normal", "baseline", "u0", "u1",
        "jambs", "thickness", "scale", "px_per_m", "confidence", "nearest",
        "first", "radius", "member_wall_candidate_ids", "complete", "claimed_complete",
    }
    params = set(inspect.signature(OpeningHostFrameProducer.publish).parameters)
    assert not (params & forbidden)


def test_single_opening_real_source_frame_resolves_and_replays() -> None:
    _physical, _walls, _bindings, producer, bound = _fixture(
        _single_pdf(), expected_openings=1
    )
    result = _publish_all(producer, bound)[0]
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.evidence is not None
    evidence = result.evidence
    assert evidence.origin_pt == (20.0, 90.0)
    assert evidence.axis_unit == (1.0, 0.0)
    assert evidence.u0_pt == 100.0
    assert abs(evidence.u1_pt - 140.0) <= 1e-6
    assert abs(evidence.wall_thickness_pt - 20.0) <= 1e-6
    assert producer.authority().resolve(evidence.selector) == result


def test_translation_and_reversed_primitives_preserve_local_geometry() -> None:
    _p1, _w1, _b1, producer1, bound1 = _fixture(_single_pdf(), expected_openings=1)
    first = _publish_all(producer1, bound1)[0].evidence
    _p2, _w2, _b2, producer2, bound2 = _fixture(
        _single_pdf(dx=50.0, dy=40.0, reverse=True), expected_openings=1
    )
    moved = _publish_all(producer2, bound2)[0].evidence
    assert first is not None and moved is not None
    assert first.origin_pt == (20.0, 90.0)
    assert moved.origin_pt == (70.0, 130.0)
    assert first.axis_unit == moved.axis_unit
    assert first.u0_pt == moved.u0_pt == 100.0
    assert abs(first.u1_pt - moved.u1_pt) <= 1e-6
    assert abs(first.wall_thickness_pt - moved.wall_thickness_pt) <= 1e-6


def test_cross_wired_binding_and_wrong_observation_fail_closed() -> None:
    _physical, _walls, _bindings, producer, bound = _fixture(_single_pdf(), expected_openings=1)
    opening_selector, _opening, binding_selector, _binding = bound[0]
    wrong_binding = dataclasses.replace(binding_selector, opening_identity_id="wrong-opening")
    result = producer.publish(
        opening_selector=opening_selector,
        host_binding_selector=wrong_binding,
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.evidence is None

    wrong_opening = dataclasses.replace(opening_selector, observation_id="not-a-real-observation")
    result = producer.publish(
        opening_selector=wrong_opening,
        host_binding_selector=binding_selector,
    )
    assert result.status in {
        EvidenceResolutionStatus.ABSTAINED,
        EvidenceResolutionStatus.CONFLICT,
    }
    assert result.evidence is None


def test_two_openings_share_one_whole_wall_origin_and_distinct_intervals() -> None:
    _physical, _walls, _bindings, producer, bound = _fixture(
        _two_opening_pdf(), expected_openings=2
    )
    results = _publish_all(producer, bound)
    assert all(result.status is EvidenceResolutionStatus.CORROBORATED for result in results)
    frames = tuple(result.evidence for result in results)
    assert all(frame is not None for frame in frames)
    assert {frame.origin_pt for frame in frames if frame is not None} == {(20.0, 90.0)}
    assert len({frame.whole_wall_frame_id for frame in frames if frame is not None}) == 1
    assert tuple(
        (frame.u0_pt, frame.u1_pt) for frame in frames if frame is not None
    ) == ((80.0, 120.0), (200.0, 240.0))


def test_unproven_aligned_remote_fragments_block_whole_wall_publication() -> None:
    _physical, _walls, _bindings, producer, bound = _fixture(
        _two_opening_pdf(remote_unproven=True), expected_openings=2
    )
    opening_selector, _opening, binding_selector, _binding = bound[0]
    result = producer.publish(
        opening_selector=opening_selector,
        host_binding_selector=binding_selector,
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.evidence is None
    assert OPENING_HOST_FRAME_WHOLE_WALL_UNPROVEN in result.reason_codes
