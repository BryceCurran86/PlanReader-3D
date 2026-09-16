from __future__ import annotations

import inspect

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_dimension_authority import OpeningDimensionAuthority
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, PhysicalOpeningAuthority
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _opening_pdf(*, text_color=(0.0, 0.0, 0.0), witnesses=True) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=700, height=500)
    for first, second in (
        ((20.0, 100.0), (100.0, 100.0)),
        ((140.0, 100.0), (220.0, 100.0)),
        ((20.0, 110.0), (100.0, 110.0)),
        ((140.0, 110.0), (220.0, 110.0)),
        ((100.0, 100.0), (100.0, 110.0)),
        ((140.0, 100.0), (140.0, 110.0)),
    ):
        page.draw_line(fitz.Point(*first), fitz.Point(*second), color=(0, 0, 0), width=1)
    page.draw_line(fitz.Point(100, 70), fitz.Point(140, 70), color=(0, 0, 0), width=0.5)
    if witnesses:
        page.draw_line(fitz.Point(100, 70), fitz.Point(100, 100), color=(0, 0, 0), width=0.5)
        page.draw_line(fitz.Point(140, 70), fitz.Point(140, 100), color=(0, 0, 0), width=0.5)
    page.insert_text(fitz.Point(112, 65), "900", color=text_color)
    payload = doc.tobytes()
    doc.close()
    return payload


def _schedule_only_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=400, height=250)
    page.insert_text((40, 40), "DOOR SCHEDULE")
    page.insert_text((40, 70), "D-01 900 x 2100")
    payload = doc.tobytes()
    doc.close()
    return payload


def _ingest(payload: bytes, document_id: str):
    producer = SourceVisibilityProducer(
        producer_method="odim-production-test", producer_version="1.0"
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator=f"memory://{document_id}.pdf",
    )
    return producer, published, producer.authority()


def _selector(published, observation_id: str, *, source_sha256: str | None = None):
    return ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=source_sha256 or published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=observation_id,
    )


def _positive_selector(published, visibility):
    physical = PhysicalOpeningAuthority(visibility)
    for observation_id in published.visible_observation_ids:
        selector = _selector(published, observation_id)
        if physical.prove_existence(selector).proposition == PHYSICAL_OPENING_EXISTS:
            return selector
    raise AssertionError("fixture must prove one opening")


def test_dimension_authority_is_producer_minted_and_selector_only() -> None:
    producer, _published, _visibility = _ingest(_opening_pdf(), "odim-api")
    authority = producer.opening_dimension_authority()
    assert isinstance(authority, OpeningDimensionAuthority)
    parameters = set(inspect.signature(authority.resolve_width).parameters)
    assert parameters == {"selector"}
    for writer in (
        "write",
        "publish_dimension",
        "ingest_native_pdf_bytes",
        "publish_derived_observation",
    ):
        assert not hasattr(authority, writer)
    with pytest.raises(TypeError):
        OpeningDimensionAuthority(
            producer.authority(), producer.text_integrity_authority()
        )


def test_explicit_witnessed_visible_width_resolves_without_inventing_height() -> None:
    producer, published, visibility = _ingest(_opening_pdf(), "odim-positive")
    selector = _positive_selector(published, visibility)
    authority = producer.opening_dimension_authority()
    width = authority.resolve_width(selector)
    height = authority.resolve_height(selector)
    assert width.status is EvidenceResolutionStatus.CORROBORATED
    assert width.value_mm == pytest.approx(900.0)
    assert height.status is not EvidenceResolutionStatus.CORROBORATED
    assert height.value_mm is None


def test_hidden_white_text_and_missing_witnesses_fail_closed() -> None:
    producer, published, visibility = _ingest(
        _opening_pdf(text_color=(1.0, 1.0, 1.0)), "odim-hidden"
    )
    hidden = producer.opening_dimension_authority().resolve_width(
        _positive_selector(published, visibility)
    )
    assert hidden.status is not EvidenceResolutionStatus.CORROBORATED
    assert hidden.value_mm is None

    producer2, published2, visibility2 = _ingest(
        _opening_pdf(witnesses=False), "odim-no-witness"
    )
    unwitnessed = producer2.opening_dimension_authority().resolve_width(
        _positive_selector(published2, visibility2)
    )
    assert unwitnessed.status is not EvidenceResolutionStatus.CORROBORATED
    assert unwitnessed.value_mm is None


def test_schedule_only_and_source_hash_laundering_cannot_resolve() -> None:
    producer, published, _visibility = _ingest(_schedule_only_pdf(), "odim-schedule")
    authority = producer.opening_dimension_authority()
    for observation_id in published.snapshot.observation_ids:
        result = authority.resolve_width(_selector(published, observation_id))
        assert result.status is not EvidenceResolutionStatus.CORROBORATED
        assert result.value_mm is None

    producer2, published2, visibility2 = _ingest(_opening_pdf(), "odim-forged")
    selector = _positive_selector(published2, visibility2)
    forged = ObservationSelector(
        document_id=selector.document_id,
        revision_id=selector.revision_id,
        source_sha256="0" * 64,
        snapshot_id=selector.snapshot_id,
        observation_id=selector.observation_id,
    )
    result = producer2.opening_dimension_authority().resolve_width(forged)
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert result.value_mm is None


def test_dimension_resolution_is_deterministic_and_downstream_firewall_stays_closed() -> None:
    producer, published, visibility = _ingest(_opening_pdf(), "odim-determinism")
    selector = _positive_selector(published, visibility)
    authority = producer.opening_dimension_authority()
    first = authority.resolve_width(selector)
    second = authority.resolve_width(selector)
    assert first == second
    assert first.status is EvidenceResolutionStatus.CORROBORATED
    caps = PhysicalOpeningAuthority.capabilities()
    assert caps["opening_dimensions"] is False
    assert caps["opening_universe_complete"] is False
    assert caps["host_binding"] is False
    assert caps["physical_void"] is False
    assert caps["net_wall_area"] is False
    for name in (
        "deduct_wall_area",
        "publish_firm_quantity",
        "publish_commercial",
        "publish_to_jobhub",
    ):
        assert not hasattr(authority, name)
