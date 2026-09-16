from __future__ import annotations

import math

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
    PhysicalOpeningAuthority,
)
from pb_source_observation_authority import ObservationSelector, SourceObservationProducer
from pb_source_visibility_authority import SourceVisibilityProducer


def _transform(point: tuple[float, float], *, angle_deg: float, scale: float, offset: tuple[float, float]):
    angle = math.radians(angle_deg)
    x, y = point
    xr = scale * (x * math.cos(angle) - y * math.sin(angle)) + offset[0]
    yr = scale * (x * math.sin(angle) + y * math.cos(angle)) + offset[1]
    return (xr, yr)


def _opening_pdf_bytes(*, angle_deg: float = 0.0, scale: float = 1.0, offset=(0.0, 0.0), rectangle_only: bool = False) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=700, height=700)
    if rectangle_only:
        segments = (
            ((100.0, 100.0), (140.0, 100.0)),
            ((100.0, 110.0), (140.0, 110.0)),
            ((100.0, 100.0), (100.0, 110.0)),
            ((140.0, 100.0), (140.0, 110.0)),
        )
    else:
        # Two wall faces each continue visibly on both sides of one common gap.
        # Two jambs connect the corresponding face endpoints at the gap bounds.
        segments = (
            ((20.0, 100.0), (100.0, 100.0)),
            ((140.0, 100.0), (220.0, 100.0)),
            ((20.0, 110.0), (100.0, 110.0)),
            ((140.0, 110.0), (220.0, 110.0)),
            ((100.0, 100.0), (100.0, 110.0)),
            ((140.0, 100.0), (140.0, 110.0)),
        )
    for first, second in segments:
        a = _transform(first, angle_deg=angle_deg, scale=scale, offset=offset)
        b = _transform(second, angle_deg=angle_deg, scale=scale, offset=offset)
        page.draw_line(fitz.Point(*a), fitz.Point(*b), color=(0, 0, 0), width=1)
    payload = doc.tobytes()
    doc.close()
    return payload


def _selector(published, observation_id: str) -> ObservationSelector:
    return ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=observation_id,
    )


def _visible_fixture(payload: bytes, *, document_id: str):
    producer = SourceVisibilityProducer(
        producer_method="g17-visible-opening-test",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator=f"memory://{document_id}.pdf",
    )
    visibility = producer.authority()
    physical = PhysicalOpeningAuthority(visibility)
    assert published.visible_observation_ids
    return producer, published, visibility, physical


@pytest.mark.parametrize(
    ("angle_deg", "scale", "offset"),
    (
        (0.0, 1.0, (0.0, 0.0)),
        (0.0, 2.0, (40.0, 30.0)),
        (90.0, 1.0, (350.0, 20.0)),
    ),
)
def test_visible_two_sided_wall_continuation_and_two_jambs_proves_local_existence(
    angle_deg: float,
    scale: float,
    offset: tuple[float, float],
) -> None:
    _, published, _, physical = _visible_fixture(
        _opening_pdf_bytes(angle_deg=angle_deg, scale=scale, offset=offset),
        document_id=f"visible-positive-{angle_deg}-{scale}",
    )
    results = [
        physical.prove_existence(_selector(published, observation_id))
        for observation_id in published.visible_observation_ids
    ]
    positives = [result for result in results if result.proposition == PHYSICAL_OPENING_EXISTS]
    assert len(positives) == 6
    for result in positives:
        assert result.status is EvidenceResolutionStatus.CORROBORATED
        assert result.existence_record is not None
        assert result.existence_record.viewport_id is None
        assert len(result.existence_record.source_observation_ids) == 6
        assert len(result.existence_record.source_lineage_root_ids) == 6


def test_closed_rectangle_without_wall_continuation_is_not_positive() -> None:
    _, published, _, physical = _visible_fixture(
        _opening_pdf_bytes(rectangle_only=True),
        document_id="visible-rectangle-only",
    )
    results = [
        physical.prove_existence(_selector(published, observation_id))
        for observation_id in published.visible_observation_ids
    ]
    assert all(result.proposition != PHYSICAL_OPENING_EXISTS for result in results)
    assert all(result.existence_record is None for result in results)


def test_raw_native_geometry_alone_cannot_publish_positive_existence() -> None:
    payload = _opening_pdf_bytes()
    producer = SourceObservationProducer(
        producer_method="g17-raw-negative",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="raw-negative",
        source_bytes=payload,
        source_locator="memory://raw-negative.pdf",
    )
    source = producer.authority()
    physical = PhysicalOpeningAuthority(source)
    results = [
        physical.prove_existence(_selector(published, observation_id))
        for observation_id in published.snapshot.observation_ids
    ]
    assert all(result.proposition != PHYSICAL_OPENING_EXISTS for result in results)
    assert all(result.existence_record is None for result in results)
    assert all(
        result.physical_opening_existence == PHYSICAL_OPENING_EXISTENCE_UNRESOLVED
        for result in results
    )


def test_visible_existence_does_not_unlock_downstream_capabilities() -> None:
    _, published, _, physical = _visible_fixture(
        _opening_pdf_bytes(),
        document_id="visible-firewall",
    )
    result = physical.prove_existence(
        _selector(published, published.visible_observation_ids[0])
    )
    assert result.proposition == PHYSICAL_OPENING_EXISTS
    assert physical.capabilities() == {
        "physical_opening_existence": True,
        "physical_opening_identity": True,
        "opening_universe_complete": False,
        "opening_dimensions": False,
        "host_identity": False,
        "host_binding": False,
        "physical_void": False,
        "net_wall_area": False,
    }
    for forbidden_method in (
        "deduct_wall_area",
        "publish_firm_quantity",
        "publish_commercial",
        "publish_to_jobhub",
        "jobhub_publish",
    ):
        assert not hasattr(physical, forbidden_method)
