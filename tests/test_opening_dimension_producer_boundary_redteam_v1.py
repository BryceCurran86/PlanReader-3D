"""Opening-dimension producer/query boundary red-team.

Exact base: post-#331 main 507c57db16be515e2432c695341bdea1e71b3fd7.

This suite is test-first only. It prevents a future dimension implementation
from obtaining figured text by reaching through SourceVisibilityAuthority's
private producer state or by trusting caller-authored record bodies/values.
"""
from __future__ import annotations

import inspect

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PhysicalOpeningAuthority,
)
from pb_source_observation_authority import (
    ObservationSelector,
    SourceObservationProducer,
)
from pb_source_visibility_authority import (
    VISIBILITY_RECEIPT_UNAVAILABLE,
    SourceVisibilityProducer,
)


BASE_SHA = "507c57db16be515e2432c695341bdea1e71b3fd7"

EXPECTED_RED = pytest.mark.xfail(
    strict=True,
    reason="Producer-bound opening-dimension authority is not implemented",
)


def _witnessed_opening_pdf_bytes() -> bytes:
    """One G17 opening plus an explicit 900 width dimension and witnesses."""

    doc = fitz.open()
    page = doc.new_page(width=700, height=500)

    # Two interrupted parallel wall faces + two jambs: the accepted G17 shape.
    for first, second in (
        ((20.0, 100.0), (100.0, 100.0)),
        ((140.0, 100.0), (220.0, 100.0)),
        ((20.0, 110.0), (100.0, 110.0)),
        ((140.0, 110.0), (220.0, 110.0)),
        ((100.0, 100.0), (100.0, 110.0)),
        ((140.0, 100.0), (140.0, 110.0)),
    ):
        page.draw_line(
            fitz.Point(*first),
            fitz.Point(*second),
            color=(0, 0, 0),
            width=1,
        )

    # Figured-width line and witness lines terminate exactly at the jamb axis.
    page.draw_line(
        fitz.Point(100.0, 70.0),
        fitz.Point(140.0, 70.0),
        color=(0, 0, 0),
        width=0.5,
    )
    page.draw_line(
        fitz.Point(100.0, 70.0),
        fitz.Point(100.0, 100.0),
        color=(0, 0, 0),
        width=0.5,
    )
    page.draw_line(
        fitz.Point(140.0, 70.0),
        fitz.Point(140.0, 100.0),
        color=(0, 0, 0),
        width=0.5,
    )
    page.insert_text(fitz.Point(112.0, 65.0), "900")

    payload = doc.tobytes()
    doc.close()
    return payload


def _schedule_only_pdf_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=400, height=250)
    page.insert_text((40, 40), "DOOR SCHEDULE")
    page.insert_text((40, 70), "D-01 900 x 2100")
    payload = doc.tobytes()
    doc.close()
    return payload


def _ingest_visibility(payload: bytes, *, document_id: str):
    producer = SourceVisibilityProducer(
        producer_method="opening-dimension-boundary-redteam",
        producer_version="1.0",
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


def _positive_opening_selector(published, visibility) -> ObservationSelector:
    physical = PhysicalOpeningAuthority(visibility)
    for observation_id in published.visible_observation_ids:
        selector = _selector(published, observation_id)
        result = physical.prove_existence(selector)
        if result.proposition == PHYSICAL_OPENING_EXISTS:
            return selector
    raise AssertionError("witnessed fixture must prove one G17 physical opening")


def _status_is_positive(result: object) -> bool:
    return getattr(result, "status", None) is EvidenceResolutionStatus.CORROBORATED


# ---------------------------------------------------------------------------
# Current-main boundary locks — GREEN now
# ---------------------------------------------------------------------------


def test_exact_post_identity_base_is_frozen() -> None:
    assert BASE_SHA == "507c57db16be515e2432c695341bdea1e71b3fd7"


def test_visibility_authority_has_no_public_raw_observation_query() -> None:
    producer, _published, visibility = _ingest_visibility(
        _witnessed_opening_pdf_bytes(),
        document_id="odim-boundary-public-api",
    )
    assert producer is not None
    public_callables = {
        name
        for name in dir(visibility)
        if not name.startswith("_") and callable(getattr(visibility, name))
    }
    assert "resolve_visible" in public_callables
    assert "resolve_source_observation" not in public_callables
    assert "resolve_raw" not in public_callables
    assert "source_authority" not in public_callables


def test_visibility_rejects_non_receipted_snapshot_members() -> None:
    _producer, published, visibility = _ingest_visibility(
        _witnessed_opening_pdf_bytes(),
        document_id="odim-boundary-nonvisible",
    )
    non_visible_ids = sorted(
        set(published.snapshot.observation_ids) - set(published.visible_observation_ids)
    )
    assert non_visible_ids, "fixture must contain raw page/word/segment observations"

    results = [
        visibility.resolve_visible(_selector(published, observation_id))
        for observation_id in non_visible_ids
    ]
    assert all(VISIBILITY_RECEIPT_UNAVAILABLE in result.reason_codes for result in results)


def test_raw_native_word_exists_in_source_observation_substrate() -> None:
    payload = _witnessed_opening_pdf_bytes()
    producer = SourceObservationProducer(
        producer_method="dimension-boundary-raw-source",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="odim-boundary-raw-word",
        source_bytes=payload,
        source_locator="memory://odim-boundary-raw-word.pdf",
    )
    authority = producer.authority()
    words = []
    for observation_id in published.snapshot.observation_ids:
        result = authority.resolve(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        observation = result.observation
        if observation is not None and observation.observation_kind == "native_pdf_word":
            words.append(observation)

    assert words
    assert any(word.raw_text.strip() == "900" for word in words)


def test_equal_source_hash_and_revision_do_not_prove_one_producer_binding() -> None:
    payload = _witnessed_opening_pdf_bytes()
    raw_producer = SourceObservationProducer(
        producer_method="independent-raw-producer",
        producer_version="1.0",
    )
    visibility_producer = SourceVisibilityProducer(
        producer_method="independent-visibility-producer",
        producer_version="2.0",
    )
    raw = raw_producer.ingest_native_pdf_bytes(
        document_id="odim-boundary-same-bytes",
        source_bytes=payload,
        source_locator="memory://raw.pdf",
    )
    visible = visibility_producer.ingest_native_pdf_bytes(
        document_id="odim-boundary-same-bytes",
        source_bytes=payload,
        source_locator="memory://visible.pdf",
    )

    # Revision identity intentionally binds document + bytes, not producer identity.
    assert raw.revision.source_sha256 == visible.revision.source_sha256
    assert raw.revision.revision_id == visible.revision.revision_id
    assert raw.revision.producer_method != visible.revision.producer_method
    assert raw.revision.producer_version != visible.revision.producer_version


def test_witnessed_fixture_still_proves_g17_opening() -> None:
    _producer, published, visibility = _ingest_visibility(
        _witnessed_opening_pdf_bytes(),
        document_id="odim-boundary-g17-positive",
    )
    selector = _positive_opening_selector(published, visibility)
    assert selector.observation_id in published.visible_observation_ids


def test_current_capabilities_keep_dimensions_and_downstream_closed() -> None:
    caps = PhysicalOpeningAuthority.capabilities()
    assert caps["physical_opening_existence"] is True
    assert caps["physical_opening_identity"] is True
    assert caps["opening_dimensions"] is False
    assert caps["opening_universe_complete"] is False
    assert caps["host_binding"] is False
    assert caps["physical_void"] is False
    assert caps["net_wall_area"] is False


# ---------------------------------------------------------------------------
# Future producer-bound dimension authority — EXPECTED RED now
# ---------------------------------------------------------------------------


@EXPECTED_RED
def test_attack01_trusted_producer_mints_read_only_dimension_authority() -> None:
    producer, _published, _visibility = _ingest_visibility(
        _witnessed_opening_pdf_bytes(),
        document_id="odim-boundary-a1",
    )
    factory = getattr(producer, "opening_dimension_authority", None)
    assert callable(factory)
    authority = factory()
    assert callable(getattr(authority, "resolve_width", None))
    assert callable(getattr(authority, "resolve_height", None))
    for writer_name in (
        "ingest_native_pdf_bytes",
        "publish_derived_observation",
        "publish_dimension",
        "write",
    ):
        assert not hasattr(authority, writer_name)


@EXPECTED_RED
def test_attack02_witnessed_900_resolves_via_producer_bound_selector_query() -> None:
    producer, published, visibility = _ingest_visibility(
        _witnessed_opening_pdf_bytes(),
        document_id="odim-boundary-a2",
    )
    selector = _positive_opening_selector(published, visibility)
    authority = producer.opening_dimension_authority()  # type: ignore[attr-defined]
    width = authority.resolve_width(selector)
    assert width.status is EvidenceResolutionStatus.CORROBORATED
    assert width.value_mm == pytest.approx(900.0)


@EXPECTED_RED
def test_attack03_public_width_query_accepts_selector_not_authority_bodies() -> None:
    producer, _published, _visibility = _ingest_visibility(
        _witnessed_opening_pdf_bytes(),
        document_id="odim-boundary-a3",
    )
    authority = producer.opening_dimension_authority()  # type: ignore[attr-defined]
    parameters = set(inspect.signature(authority.resolve_width).parameters)
    assert "selector" in parameters
    forbidden = {
        "width_mm",
        "height_mm",
        "figured_text",
        "existence_record",
        "source_observation",
        "source_record",
        "evidence_records",
        "observations",
    }
    assert parameters.isdisjoint(forbidden)


@EXPECTED_RED
def test_attack04_schedule_only_source_cannot_mint_instance_dimensions() -> None:
    producer, published, _visibility = _ingest_visibility(
        _schedule_only_pdf_bytes(),
        document_id="odim-boundary-a4-schedule",
    )
    authority = producer.opening_dimension_authority()  # type: ignore[attr-defined]

    results = [
        authority.resolve_width(_selector(published, observation_id))
        for observation_id in published.snapshot.observation_ids
    ]
    assert results
    assert all(not _status_is_positive(result) for result in results)
    assert all(getattr(result, "value_mm", None) is None for result in results)


@EXPECTED_RED
def test_attack05_plan_width_does_not_invent_height() -> None:
    producer, published, visibility = _ingest_visibility(
        _witnessed_opening_pdf_bytes(),
        document_id="odim-boundary-a5-height",
    )
    selector = _positive_opening_selector(published, visibility)
    authority = producer.opening_dimension_authority()  # type: ignore[attr-defined]
    width = authority.resolve_width(selector)
    height = authority.resolve_height(selector)
    assert width.status is EvidenceResolutionStatus.CORROBORATED
    assert width.value_mm == pytest.approx(900.0)
    assert (
        height.status is not EvidenceResolutionStatus.CORROBORATED
        or getattr(height, "value_mm", None) is None
    )


@EXPECTED_RED
def test_attack06_source_hash_laundering_fails_closed() -> None:
    producer, published, visibility = _ingest_visibility(
        _witnessed_opening_pdf_bytes(),
        document_id="odim-boundary-a6-hash",
    )
    selector = _positive_opening_selector(published, visibility)
    forged = ObservationSelector(
        document_id=selector.document_id,
        revision_id=selector.revision_id,
        source_sha256="0" * 64,
        snapshot_id=selector.snapshot_id,
        observation_id=selector.observation_id,
    )
    authority = producer.opening_dimension_authority()  # type: ignore[attr-defined]
    result = authority.resolve_width(forged)
    assert not _status_is_positive(result)
    assert getattr(result, "value_mm", None) is None


@EXPECTED_RED
def test_attack07_dimension_query_is_deterministic_for_same_selector() -> None:
    producer, published, visibility = _ingest_visibility(
        _witnessed_opening_pdf_bytes(),
        document_id="odim-boundary-a7-determinism",
    )
    selector = _positive_opening_selector(published, visibility)
    authority = producer.opening_dimension_authority()  # type: ignore[attr-defined]
    first = authority.resolve_width(selector)
    second = authority.resolve_width(selector)
    assert first == second
    assert first.status is EvidenceResolutionStatus.CORROBORATED
    assert first.value_mm == pytest.approx(900.0)


@EXPECTED_RED
def test_attack08_width_resolution_does_not_unlock_downstream_authority() -> None:
    producer, published, visibility = _ingest_visibility(
        _witnessed_opening_pdf_bytes(),
        document_id="odim-boundary-a8-firewall",
    )
    selector = _positive_opening_selector(published, visibility)
    authority = producer.opening_dimension_authority()  # type: ignore[attr-defined]
    width = authority.resolve_width(selector)
    assert width.status is EvidenceResolutionStatus.CORROBORATED

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
