"""Independent GPT-2 red-team for a shared whole-wall opening host frame.

TEST-ONLY / EXPECTED-RED / DO NOT MERGE.

Item 10 requires every opening on one physical wall to resolve in one producer-owned
whole-wall coordinate frame. An opening-scoped set of host-binding members cannot
establish that proposition because different openings legitimately bind different
local wall pieces.
"""
from __future__ import annotations

import dataclasses
from dataclasses import fields, is_dataclass
import importlib
import importlib.util
import inspect
import math

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
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, PhysicalOpeningAuthority
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


MODULE_NAME = "pb_opening_host_frame_authority"
HAS_FRAME_AUTHORITY = importlib.util.find_spec(MODULE_NAME) is not None
EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_FRAME_AUTHORITY,
    strict=True,
    reason="shared whole-wall host-frame production is not on this base",
)

_FORBIDDEN_PUBLIC = {
    "host_wall_id",
    "wall_candidate_id",
    "wall_candidates",
    "member_wall_candidate_ids",
    "origin",
    "origin_pt",
    "axis",
    "axis_unit",
    "normal",
    "normal_unit",
    "baseline",
    "baseline_start",
    "baseline_end",
    "u0",
    "u1",
    "u0_pt",
    "u1_pt",
    "jambs",
    "opening_span",
    "thickness",
    "scale",
    "px_per_m",
    "points_per_mm",
    "confidence",
    "nearest",
    "first",
    "radius",
    "complete",
    "claimed_complete",
}


def _opening_ranges(count: int) -> tuple[tuple[float, float], ...]:
    assert count in {1, 2, 3}
    return tuple((100.0 + 120.0 * index, 140.0 + 120.0 * index) for index in range(count))


def _transform_point(
    point: tuple[float, float],
    *,
    dx: float,
    dy: float,
    rotate90: bool,
) -> tuple[float, float]:
    x, y = point
    if rotate90:
        # Rigid +90 degree rotation about the origin, followed by a translation
        # that keeps all coordinates positive on a generous PDF page.
        return (500.0 - y + dx, x + dy)
    return (x + dx, y + dy)


def _wall_pdf(
    count: int,
    *,
    dx: float = 0.0,
    dy: float = 0.0,
    reverse_segments: bool = False,
    reverse_draw_order: bool = False,
    split_nonopening_piece: bool = False,
    rotate90: bool = False,
    remote_unproven_fragments: bool = False,
) -> bytes:
    openings = _opening_ranges(count)
    wall_start = 20.0
    wall_end = openings[-1][1] + 80.0

    intervals: list[tuple[float, float]] = []
    cursor = wall_start
    for start, end in openings:
        intervals.append((cursor, start))
        cursor = end
    intervals.append((cursor, wall_end))

    if split_nonopening_piece:
        first_start, first_end = intervals[0]
        mid = (first_start + first_end) / 2.0
        intervals = [(first_start, mid), (mid, first_end), *intervals[1:]]

    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for y in (80.0, 100.0):
        for start, end in intervals:
            segments.append(((start, y), (end, y)))
    for start, end in openings:
        segments.append(((start, 80.0), (start, 100.0)))
        segments.append(((end, 80.0), (end, 100.0)))

    if remote_unproven_fragments:
        remote_start = wall_end + 60.0
        remote_end = wall_end + 120.0
        segments.extend(
            [
                ((remote_start, 80.0), (remote_end, 80.0)),
                ((remote_start, 100.0), (remote_end, 100.0)),
            ]
        )

    if reverse_draw_order:
        segments.reverse()

    doc = fitz.open()
    try:
        page = doc.new_page(width=700.0, height=700.0)
        shape = page.new_shape()
        for start, end in segments:
            start = _transform_point(start, dx=dx, dy=dy, rotate90=rotate90)
            end = _transform_point(end, dx=dx, dy=dy, rotate90=rotate90)
            if reverse_segments:
                start, end = end, start
            shape.draw_line(fitz.Point(*start), fitz.Point(*end))
        shape.finish(width=1.0)
        shape.commit()
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


@dataclasses.dataclass(frozen=True)
class _BoundOpening:
    opening_selector: ObservationSelector
    opening_record: object
    binding_selector: OpeningHostBindingSelector
    binding_record: object
    source_scalar: float


@dataclasses.dataclass(frozen=True)
class _Fixture:
    physical: PhysicalOpeningAuthority
    wall_authority: object
    binding_producer: OpeningHostBindingProducer
    openings: tuple[_BoundOpening, ...]


def _fixture(payload: bytes, *, expected_openings: int) -> _Fixture:
    source = SourceVisibilityProducer(
        producer_method="gpt2-shared-host-frame-redteam",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="gpt2-shared-host-frame",
        source_bytes=payload,
        source_locator="memory://gpt2-shared-host-frame.pdf",
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
            discovered.setdefault(
                result.existence_record.record_id,
                (selector, result.existence_record),
            )
    assert len(discovered) == expected_openings

    wall_authority = PhysicalWallCandidateProducer.from_source_visibility_producer(source).authority()
    first_record = next(iter(discovered.values()))[1]
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

    bound: list[_BoundOpening] = []
    for selector, opening in discovered.values():
        binding = binding_producer.publish(
            opening_left_selector=selector,
            opening_right_selector=selector,
            host_universe_selector=universe_selector,
        )
        assert binding.status is EvidenceResolutionStatus.CORROBORATED
        assert binding.record is not None
        geometry = host_geometry._opening_geometry(physical, opening)
        assert geometry is not None
        source_scalar = (
            float(geometry.origin[0]) * float(geometry.axis[0])
            + float(geometry.origin[1]) * float(geometry.axis[1])
        )
        bound.append(
            _BoundOpening(
                opening_selector=selector,
                opening_record=opening,
                binding_selector=OpeningHostBindingSelector(
                    document_id=binding.record.document_id,
                    revision_id=binding.record.revision_id,
                    source_sha256=binding.record.source_sha256,
                    snapshot_id=binding.record.snapshot_id,
                    page_id=binding.record.page_id,
                    decision_scope_id=binding.record.decision_scope_id,
                    opening_identity_id=binding.record.opening_identity_id,
                ),
                binding_record=binding.record,
                source_scalar=source_scalar,
            )
        )

    bound.sort(key=lambda item: item.source_scalar)
    assert len({item.binding_record.opening_identity_id for item in bound}) == expected_openings
    return _Fixture(
        physical=physical,
        wall_authority=wall_authority,
        binding_producer=binding_producer,
        openings=tuple(bound),
    )


def _frames(fixture: _Fixture):
    mod = importlib.import_module(MODULE_NAME)
    producer = mod.OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=fixture.physical,
        host_binding_authority=fixture.binding_producer.authority(),
        physical_wall_candidate_authority=fixture.wall_authority,
    )
    results = []
    for bound in fixture.openings:
        result = producer.publish(
            opening_selector=bound.opening_selector,
            host_binding_selector=bound.binding_selector,
        )
        assert result.status is EvidenceResolutionStatus.CORROBORATED
        assert result.evidence is not None
        results.append(result.evidence)
    return producer, tuple(results)


def _assert_shared_frame(
    frames: tuple[object, ...],
    *,
    expected_intervals: tuple[tuple[float, float], ...],
) -> None:
    assert len(frames) == len(expected_intervals)
    origins = {tuple(frame.origin_pt) for frame in frames}
    axes = {tuple(frame.axis_unit) for frame in frames}
    normals = {tuple(frame.normal_unit) for frame in frames}
    thicknesses = {round(float(frame.wall_thickness_pt), 6) for frame in frames}
    assert len(origins) == 1, "openings on one wall must share one whole-wall origin"
    assert len(axes) == 1
    assert len(normals) == 1
    assert thicknesses == {20.0}
    actual = tuple((round(float(frame.u0_pt), 6), round(float(frame.u1_pt), 6)) for frame in frames)
    assert actual == expected_intervals
    assert len(set(actual)) == len(actual), "same-size physical openings must remain distinct"


def test_merged_host_binding_prerequisite_supports_three_openings_on_one_wall() -> None:
    """Current GREEN prerequisite: #417 must survive an ordinary three-opening wall."""
    fixture = _fixture(_wall_pdf(3), expected_openings=3)
    assert len(fixture.openings) == 3
    assert all(bound.binding_record is not None for bound in fixture.openings)


@EXPECTED_RED
def test_shared_frame_public_surface_is_selector_only_and_not_caller_mintable() -> None:
    mod = importlib.import_module(MODULE_NAME)
    assert is_dataclass(mod.OpeningHostFrameSelector)
    selector_fields = {field.name for field in fields(mod.OpeningHostFrameSelector)}
    assert not (selector_fields & _FORBIDDEN_PUBLIC)
    for callable_obj in (
        mod.OpeningHostFrameProducer.from_authorities,
        mod.OpeningHostFrameProducer.publish,
        mod.OpeningHostFrameAuthority.resolve,
    ):
        params = set(inspect.signature(callable_obj).parameters)
        assert not (params & _FORBIDDEN_PUBLIC)


@EXPECTED_RED
def test_two_openings_share_one_whole_wall_origin_and_distinct_u_intervals() -> None:
    fixture = _fixture(_wall_pdf(2), expected_openings=2)
    _producer, frames = _frames(fixture)
    _assert_shared_frame(frames, expected_intervals=((80.0, 120.0), (200.0, 240.0)))
    assert frames[0].origin_pt == (20.0, 90.0)


@EXPECTED_RED
def test_three_same_size_openings_share_one_whole_wall_frame() -> None:
    fixture = _fixture(_wall_pdf(3), expected_openings=3)
    _producer, frames = _frames(fixture)
    _assert_shared_frame(
        frames,
        expected_intervals=((80.0, 120.0), (200.0, 240.0), (320.0, 360.0)),
    )
    assert frames[0].origin_pt == (20.0, 90.0)


@EXPECTED_RED
def test_split_vs_unsplit_wall_representation_does_not_move_opening_coordinates() -> None:
    ordinary = _frames(_fixture(_wall_pdf(2), expected_openings=2))[1]
    split = _frames(
        _fixture(_wall_pdf(2, split_nonopening_piece=True), expected_openings=2)
    )[1]
    ordinary_uv = tuple((frame.u0_pt, frame.u1_pt) for frame in ordinary)
    split_uv = tuple((frame.u0_pt, frame.u1_pt) for frame in split)
    assert ordinary_uv == split_uv == ((80.0, 120.0), (200.0, 240.0))
    assert ordinary[0].origin_pt == split[0].origin_pt == (20.0, 90.0)


@EXPECTED_RED
def test_reversed_primitives_and_discovery_order_do_not_change_shared_frame() -> None:
    ordinary = _frames(_fixture(_wall_pdf(2), expected_openings=2))[1]
    perturbed = _frames(
        _fixture(
            _wall_pdf(2, reverse_segments=True, reverse_draw_order=True),
            expected_openings=2,
        )
    )[1]
    assert tuple((frame.u0_pt, frame.u1_pt) for frame in ordinary) == tuple(
        (frame.u0_pt, frame.u1_pt) for frame in perturbed
    ) == ((80.0, 120.0), (200.0, 240.0))
    assert ordinary[0].origin_pt == perturbed[0].origin_pt == (20.0, 90.0)
    assert ordinary[0].axis_unit == perturbed[0].axis_unit
    assert ordinary[0].normal_unit == perturbed[0].normal_unit


@EXPECTED_RED
def test_translation_preserves_wall_local_coordinates_for_all_openings() -> None:
    ordinary = _frames(_fixture(_wall_pdf(2), expected_openings=2))[1]
    translated = _frames(
        _fixture(_wall_pdf(2, dx=47.0, dy=31.0), expected_openings=2)
    )[1]
    assert tuple((frame.u0_pt, frame.u1_pt) for frame in ordinary) == tuple(
        (frame.u0_pt, frame.u1_pt) for frame in translated
    ) == ((80.0, 120.0), (200.0, 240.0))
    assert ordinary[0].origin_pt == (20.0, 90.0)
    assert translated[0].origin_pt == (67.0, 121.0)


@EXPECTED_RED
def test_rigid_rotation_preserves_shared_wall_local_coordinates() -> None:
    ordinary = _frames(_fixture(_wall_pdf(2), expected_openings=2))[1]
    rotated = _frames(
        _fixture(_wall_pdf(2, rotate90=True), expected_openings=2)
    )[1]
    assert tuple((frame.u0_pt, frame.u1_pt) for frame in ordinary) == tuple(
        (frame.u0_pt, frame.u1_pt) for frame in rotated
    ) == ((80.0, 120.0), (200.0, 240.0))
    assert ordinary[0].origin_pt == (20.0, 90.0)
    assert rotated[0].origin_pt == (410.0, 20.0)
    assert rotated[0].axis_unit == (0.0, 1.0)
    assert math.isclose(abs(rotated[0].normal_unit[0]), 1.0, abs_tol=1e-9)


@EXPECTED_RED
def test_unproven_remote_wall_fragments_block_whole_wall_frame_publication() -> None:
    """Host binding may be local-positive while whole-wall traversal is unproven."""
    fixture = _fixture(
        _wall_pdf(1, remote_unproven_fragments=True),
        expected_openings=1,
    )
    mod = importlib.import_module(MODULE_NAME)
    producer = mod.OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=fixture.physical,
        host_binding_authority=fixture.binding_producer.authority(),
        physical_wall_candidate_authority=fixture.wall_authority,
    )
    bound = fixture.openings[0]
    result = producer.publish(
        opening_selector=bound.opening_selector,
        host_binding_selector=bound.binding_selector,
    )
    assert result.status in {
        EvidenceResolutionStatus.ABSTAINED,
        EvidenceResolutionStatus.CONFLICT,
    }
    assert result.evidence is None
