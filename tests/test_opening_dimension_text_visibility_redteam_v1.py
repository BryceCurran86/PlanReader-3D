"""Opening-dimension figured-text visibility / render-eligibility red-team.

Exact base: post-#331 main 507c57db16be515e2432c695341bdea1e71b3fd7.

A producer-owned raw native word proves extraction, not that the figured text
was visibly/renderably trustworthy. Future dimension authority must not promote
hidden/non-rendering text merely because its characters and bbox were decoded.
"""
from __future__ import annotations

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, PhysicalOpeningAuthority
from pb_source_observation_authority import ObservationSelector, SourceObservationProducer
from pb_source_visibility_authority import SourceVisibilityProducer


EXPECTED_RED = pytest.mark.xfail(
    strict=True,
    reason="Figured-text render eligibility is not yet producer-authoritative",
)


def _opening_with_dimension_text(*, text_color: tuple[float, float, float]) -> bytes:
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
        page.draw_line(
            fitz.Point(*first),
            fitz.Point(*second),
            color=(0, 0, 0),
            width=1,
        )

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
    page.insert_text(fitz.Point(112.0, 65.0), "900", color=text_color)

    payload = doc.tobytes()
    doc.close()
    return payload


def _raw_word_records(payload: bytes, *, document_id: str):
    producer = SourceObservationProducer(
        producer_method="dimension-text-visibility-redteam",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator=f"memory://{document_id}.pdf",
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
    return published, words


def _visibility_ingest(payload: bytes, *, document_id: str):
    producer = SourceVisibilityProducer(
        producer_method="dimension-text-visibility-redteam",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator=f"memory://{document_id}.pdf",
    )
    return producer, published, producer.authority()


def _selector(published, observation_id: str) -> ObservationSelector:
    return ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=observation_id,
    )


def _positive_opening_selector(published, visibility) -> ObservationSelector:
    physical = PhysicalOpeningAuthority(visibility)
    for observation_id in published.visible_observation_ids:
        selector = _selector(published, observation_id)
        if physical.prove_existence(selector).proposition == PHYSICAL_OPENING_EXISTS:
            return selector
    raise AssertionError("fixture must still prove one G17 physical opening")


# ---------------------------------------------------------------------------
# Current-main evidence of the gap — GREEN
# ---------------------------------------------------------------------------


def test_hidden_white_900_is_still_extractable_as_raw_native_word() -> None:
    _published, words = _raw_word_records(
        _opening_with_dimension_text(text_color=(1.0, 1.0, 1.0)),
        document_id="odim-hidden-word",
    )
    hidden_900 = [word for word in words if word.raw_text.strip() == "900"]
    assert hidden_900, "white-on-white 900 should demonstrate raw extraction != visibility"


def test_raw_word_record_has_no_render_visibility_authority_fields() -> None:
    _published, words = _raw_word_records(
        _opening_with_dimension_text(text_color=(1.0, 1.0, 1.0)),
        document_id="odim-hidden-word-fields",
    )
    word = next(word for word in words if word.raw_text.strip() == "900")
    assert not hasattr(word, "text_visible")
    assert not hasattr(word, "render_mode")
    assert not hasattr(word, "fill_color")
    assert not hasattr(word, "occlusion_state")
    assert not hasattr(word, "text_decode_valid")


def test_hidden_text_fixture_still_has_independent_g17_opening_geometry() -> None:
    producer, published, visibility = _visibility_ingest(
        _opening_with_dimension_text(text_color=(1.0, 1.0, 1.0)),
        document_id="odim-hidden-g17",
    )
    assert producer is not None
    selector = _positive_opening_selector(published, visibility)
    assert selector.observation_id in published.visible_observation_ids


# ---------------------------------------------------------------------------
# Future producer-bound text/render authority — EXPECTED RED
# ---------------------------------------------------------------------------


@EXPECTED_RED
def test_attack_hidden_white_900_cannot_resolve_opening_width() -> None:
    producer, published, visibility = _visibility_ingest(
        _opening_with_dimension_text(text_color=(1.0, 1.0, 1.0)),
        document_id="odim-hidden-a1",
    )
    selector = _positive_opening_selector(published, visibility)
    authority = producer.opening_dimension_authority()  # type: ignore[attr-defined]
    width = authority.resolve_width(selector)
    assert width.status is not EvidenceResolutionStatus.CORROBORATED
    assert getattr(width, "value_mm", None) is None


@EXPECTED_RED
def test_attack_visible_black_900_and_hidden_white_900_are_not_equivalent_authority() -> None:
    black_producer, black_published, black_visibility = _visibility_ingest(
        _opening_with_dimension_text(text_color=(0.0, 0.0, 0.0)),
        document_id="odim-render-black",
    )
    white_producer, white_published, white_visibility = _visibility_ingest(
        _opening_with_dimension_text(text_color=(1.0, 1.0, 1.0)),
        document_id="odim-render-white",
    )
    black_selector = _positive_opening_selector(black_published, black_visibility)
    white_selector = _positive_opening_selector(white_published, white_visibility)

    black = black_producer.opening_dimension_authority().resolve_width(black_selector)  # type: ignore[attr-defined]
    white = white_producer.opening_dimension_authority().resolve_width(white_selector)  # type: ignore[attr-defined]

    assert black.status is EvidenceResolutionStatus.CORROBORATED
    assert black.value_mm == pytest.approx(900.0)
    assert white.status is not EvidenceResolutionStatus.CORROBORATED
    assert getattr(white, "value_mm", None) is None
