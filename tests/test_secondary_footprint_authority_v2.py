"""Production + adversarial tests for pb_secondary_footprint_authority (Item 29 V2).

Covers the source-backed contract required by
``tests/test_secondary_footprint_source_backed_redteam_v2.py`` (#492):
sealed constructors, selector validation, ordinary happy-path resolution
from real PDF bytes, and fail-closed behavior when the underlying F.23
evidence, viewport or dimension geometry is missing or ambiguous.
"""
from __future__ import annotations

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_secondary_footprint_authority import (
    FootprintCategory,
    SECONDARY_FOOTPRINT_PAGE_UNAVAILABLE,
    SECONDARY_FOOTPRINT_RECORD_UNAVAILABLE,
    SECONDARY_FOOTPRINT_RESOLVED,
    SECONDARY_FOOTPRINT_SOURCE_UNAVAILABLE,
    SECONDARY_FOOTPRINT_UNRESOLVED,
    SECONDARY_FOOTPRINT_VIEWPORT_MISMATCH,
    SecondaryFootprintAuthority,
    SecondaryFootprintProducer,
    SecondaryFootprintSelector,
)
from pb_secondary_footprint_evidence import resolve_secondary_footprint_width_m
from pb_source_visibility_authority import SourceVisibilityProducer

DOC = "doc-fp-v2-test"
SPACE = "verandah-1"


def _draw_vertical_depth(page: fitz.Page, *, x: float, y0: float, y1: float, text: str) -> None:
    page.draw_line((x, y0), (x, y1))
    page.draw_line((x - 18, y0), (x + 18, y0))
    page.draw_line((x - 18, y1), (x + 18, y1))
    page.insert_text((x + 5, (y0 + y1) / 2.0), text, fontsize=10, rotate=90)


def _verandah_pdf(*, depth_text: str = "1800", with_label: bool = True) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=640, height=460)
    fx0, fy0 = 30.0, 30.0
    fx1, fy1 = fx0 + 280.0, fy0 + 280.0
    width, height = fx1 - fx0, fy1 - fy0
    page.draw_rect(fitz.Rect(fx0, fy0, fx1, fy1))
    page.insert_text((fx0 + 0.10 * width, fy1 - 8.0), "GROUND FLOOR PLAN", fontsize=10)

    if with_label:
        label = "VERANDAH"
        label_width = fitz.get_text_length(label, fontsize=10)
        label_x = fx0 + 0.50 * width - label_width / 2.0
        label_y = fy0 + 0.92 * height
        page.insert_text((label_x, label_y), label, fontsize=10)
        label_cx = label_x + label_width / 2.0
        label_cy = label_y - 3.5
        y1 = label_cy - 4.0
        y0 = y1 - 36.0
        _draw_vertical_depth(page, x=label_cx, y0=y0, y1=y1, text=depth_text)

    data = doc.tobytes()
    doc.close()
    return data


def _ingest(pdf_bytes: bytes):
    source = SourceVisibilityProducer(producer_method="item29_v2_test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id=DOC,
        source_bytes=pdf_bytes,
        source_locator="memory:item29-v2-test.pdf",
    )
    return source, published


def _selector(published, *, viewport_id, page_id: str = "1", secondary_space_id: str = SPACE) -> SecondaryFootprintSelector:
    return SecondaryFootprintSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=page_id,
        viewport_id=viewport_id,
        secondary_space_id=secondary_space_id,
    )


# ── Constructor Seals ─────────────────────────────────────────────────────────

def test_authority_constructor_sealed() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        SecondaryFootprintAuthority({})


def test_producer_constructor_sealed() -> None:
    source = SourceVisibilityProducer(producer_method="m", producer_version="1")
    with pytest.raises(TypeError, match="from_source_visibility_producer"):
        SecondaryFootprintProducer(source)  # type: ignore[call-arg]


def test_producer_factory_rejects_non_producer_type() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        SecondaryFootprintProducer.from_source_visibility_producer(object())  # type: ignore[arg-type]


# ── Happy Path ────────────────────────────────────────────────────────────────

def test_verandah_footprint_resolved_from_real_pdf() -> None:
    pdf = _verandah_pdf()
    source, published = _ingest(pdf)
    doc = fitz.open(stream=pdf, filetype="pdf")
    evidence = resolve_secondary_footprint_width_m(doc[0], page_num=1)
    doc.close()
    assert evidence is not None

    producer = SecondaryFootprintProducer.from_source_visibility_producer(source)
    sel = _selector(published, viewport_id=evidence.view_id)
    res = producer.publish(sel)

    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.category is FootprintCategory.VERANDAH
    assert res.record.depth_m == pytest.approx(1.8)
    assert res.record.width_m > 0.0
    assert res.record.area_m2 > 0.0
    assert res.record.perimeter_m > 0.0
    assert SECONDARY_FOOTPRINT_RESOLVED in res.reason_codes


def test_publish_is_idempotent_and_deterministic() -> None:
    pdf = _verandah_pdf()
    source, published = _ingest(pdf)
    producer = SecondaryFootprintProducer.from_source_visibility_producer(source)
    sel = _selector(published, viewport_id=None)
    first = producer.publish(sel)
    second = producer.publish(sel)
    assert first.record is not None and second.record is not None
    assert first.record.record_id == second.record.record_id
    assert first.record.area_m2 == second.record.area_m2


# ── Adversarial: Missing / Unknown ─────────────────────────────────────────────

def test_no_label_abstains() -> None:
    pdf = _verandah_pdf(with_label=False)
    source, published = _ingest(pdf)
    producer = SecondaryFootprintProducer.from_source_visibility_producer(source)
    res = producer.publish(_selector(published, viewport_id=None))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert SECONDARY_FOOTPRINT_UNRESOLVED in res.reason_codes


def test_unpublished_revision_abstains_source_unavailable() -> None:
    source = SourceVisibilityProducer(producer_method="m", producer_version="1")
    producer = SecondaryFootprintProducer.from_source_visibility_producer(source)
    sel = SecondaryFootprintSelector(
        document_id="never-ingested",
        revision_id="R1",
        source_sha256="a" * 64,
        snapshot_id="snap-1",
        page_id="1",
        viewport_id=None,
        secondary_space_id=SPACE,
    )
    res = producer.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert SECONDARY_FOOTPRINT_SOURCE_UNAVAILABLE in res.reason_codes


def test_out_of_range_page_abstains() -> None:
    pdf = _verandah_pdf()
    source, published = _ingest(pdf)
    producer = SecondaryFootprintProducer.from_source_visibility_producer(source)
    sel = _selector(published, viewport_id=None, page_id="99")
    res = producer.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert SECONDARY_FOOTPRINT_PAGE_UNAVAILABLE in res.reason_codes


def test_mismatched_viewport_id_abstains() -> None:
    pdf = _verandah_pdf()
    source, published = _ingest(pdf)
    producer = SecondaryFootprintProducer.from_source_visibility_producer(source)
    sel = _selector(published, viewport_id="not-the-real-viewport")
    res = producer.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert SECONDARY_FOOTPRINT_VIEWPORT_MISMATCH in res.reason_codes


# ── Authority Lookup ──────────────────────────────────────────────────────────

def test_authority_lookup_published_record() -> None:
    pdf = _verandah_pdf()
    source, published = _ingest(pdf)
    producer = SecondaryFootprintProducer.from_source_visibility_producer(source)
    sel = _selector(published, viewport_id=None)
    producer.publish(sel)
    auth = producer.authority()
    res = auth.resolve(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record.secondary_space_id == SPACE


def test_authority_lookup_missing_abstains() -> None:
    pdf = _verandah_pdf()
    source, published = _ingest(pdf)
    producer = SecondaryFootprintProducer.from_source_visibility_producer(source)
    auth = producer.authority()
    sel = _selector(published, viewport_id=None)
    res = auth.resolve(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert SECONDARY_FOOTPRINT_RECORD_UNAVAILABLE in res.reason_codes


def test_authority_lookup_wrong_selector_type_raises() -> None:
    pdf = _verandah_pdf()
    source, _published = _ingest(pdf)
    producer = SecondaryFootprintProducer.from_source_visibility_producer(source)
    auth = producer.authority()
    with pytest.raises(TypeError, match="SecondaryFootprintSelector"):
        auth.resolve("not-a-selector")  # type: ignore[arg-type]


def test_publish_wrong_selector_type_raises() -> None:
    source = SourceVisibilityProducer(producer_method="m", producer_version="1")
    producer = SecondaryFootprintProducer.from_source_visibility_producer(source)
    with pytest.raises(TypeError, match="SecondaryFootprintSelector"):
        producer.publish("not-a-selector")  # type: ignore[arg-type]


def test_selector_empty_field_raises() -> None:
    with pytest.raises(ValueError):
        SecondaryFootprintSelector(
            document_id="",
            revision_id="R1",
            source_sha256="a" * 64,
            snapshot_id="snap-1",
            page_id="1",
            viewport_id=None,
            secondary_space_id=SPACE,
        )


def test_selector_blank_viewport_id_raises() -> None:
    with pytest.raises(ValueError):
        SecondaryFootprintSelector(
            document_id="doc",
            revision_id="R1",
            source_sha256="a" * 64,
            snapshot_id="snap-1",
            page_id="1",
            viewport_id="   ",
            secondary_space_id=SPACE,
        )
