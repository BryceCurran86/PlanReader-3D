"""Production + adversarial tests for pb_roof_ceiling_authority (Item 31 V2).

Covers the source-backed contract: generic wall-candidate metadata must
never stand in for roof/ceiling area, and pitch must never be assumed.
"""
from __future__ import annotations

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_roof_ceiling_authority import (
    ROOF_CEILING_GEOMETRY_INVALID,
    ROOF_CEILING_PAGE_UNAVAILABLE,
    ROOF_CEILING_PITCH_EVIDENCE_UNAVAILABLE,
    ROOF_CEILING_RECORD_UNAVAILABLE,
    ROOF_CEILING_RESOLVED,
    ROOF_CEILING_SOURCE_UNAVAILABLE,
    ROOF_CEILING_UNRESOLVED,
    ROOF_CEILING_VIEWPORT_MISMATCH,
    RoofCeilingAuthority,
    RoofCeilingProducer,
    RoofCeilingSelector,
    RoofCeilingFamily,
)
from pb_source_visibility_authority import SourceVisibilityProducer

DOC = "doc-roof-v2-test"


def _draw_witness_dim(page: fitz.Page, *, x: float, y0: float, y1: float, text: str) -> None:
    page.draw_line((x, y0), (x, y1))
    page.draw_line((x - 18, y0), (x + 18, y0))
    page.draw_line((x - 18, y1), (x + 18, y1))
    page.insert_text((x + 5, (y0 + y1) / 2.0), text, fontsize=10, rotate=90)


def _roof_pdf(
    *,
    label: str = "ROOF",
    area_text: str | None = "24.50",
    area_unit: str | None = "SM",
    length_label: str | None = None,
    length_text: str | None = None,
    second_area_text: str | None = None,
    prose: bool = False,
    sheet_title: str = "GROUND FLOOR PLAN",
) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=640, height=460)
    fx0, fy0 = 30.0, 30.0
    fx1, fy1 = fx0 + 280.0, fy0 + 280.0
    width, height = fx1 - fx0, fy1 - fy0
    page.draw_rect(fitz.Rect(fx0, fy0, fx1, fy1))
    page.insert_text((fx0 + 0.10 * width, fy1 - 8.0), sheet_title, fontsize=10)

    if prose:
        page.insert_text(
            (fx0 + 0.10 * width, fy0 + 0.50 * height),
            f"{label} covering shall be 24.50 SM of GCI sheet in accordance with specification",
            fontsize=10,
        )
        data = doc.tobytes()
        doc.close()
        return data

    label_x = fx0 + 0.30 * width
    label_y = fy0 + 0.40 * height
    page.insert_text((label_x, label_y), label, fontsize=10)
    label_cx = label_x + fitz.get_text_length(label, fontsize=10) / 2.0

    if area_text is not None and area_unit is not None:
        page.insert_text((label_cx - 10.0, label_y - 16.0), area_text, fontsize=10)
        area_word_width = fitz.get_text_length(area_text, fontsize=10)
        page.insert_text((label_cx - 10.0 + area_word_width + 4.0, label_y - 16.0), area_unit, fontsize=10)
        if second_area_text is not None:
            page.insert_text((label_cx - 10.0, label_y + 16.0), second_area_text, fontsize=10)
            page.insert_text(
                (label_cx - 10.0 + fitz.get_text_length(second_area_text, fontsize=10) + 4.0, label_y + 16.0),
                area_unit,
                fontsize=10,
            )

    if length_label and length_text:
        llabel_x = fx0 + 0.30 * width
        llabel_y = fy0 + 0.85 * height
        page.insert_text((llabel_x, llabel_y), length_label, fontsize=10)
        llabel_cx = llabel_x + fitz.get_text_length(length_label, fontsize=10) / 2.0
        llabel_cy = llabel_y - 3.5
        y1 = llabel_cy - 4.0
        y0 = y1 - 36.0
        _draw_witness_dim(page, x=llabel_cx, y0=y0, y1=y1, text=length_text)

    data = doc.tobytes()
    doc.close()
    return data


def _ingest(pdf_bytes: bytes):
    source = SourceVisibilityProducer(producer_method="item31_v2_test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id=DOC, source_bytes=pdf_bytes, source_locator="memory:item31-v2-test.pdf",
    )
    return source, published


def _selector(
    published, *, family: RoofCeilingFamily, viewport_id=None, page_id: str = "1", target_id: str = "roof-1"
) -> RoofCeilingSelector:
    return RoofCeilingSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=page_id,
        viewport_id=viewport_id,
        target_id=target_id,
        family=family,
    )


# ── Constructor Seals ─────────────────────────────────────────────────────────

def test_authority_constructor_sealed() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        RoofCeilingAuthority({})


def test_producer_constructor_sealed() -> None:
    source = SourceVisibilityProducer(producer_method="m", producer_version="1")
    with pytest.raises(TypeError, match="from_source_visibility_producer"):
        RoofCeilingProducer(source)  # type: ignore[call-arg]


def test_producer_factory_rejects_non_producer_type() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        RoofCeilingProducer.from_source_visibility_producer(object())  # type: ignore[arg-type]


def test_selector_rejects_non_enum_family() -> None:
    with pytest.raises(TypeError):
        RoofCeilingSelector(
            document_id="d", revision_id="r", source_sha256="a" * 64,
            snapshot_id="s", page_id="1", viewport_id=None,
            target_id="roof-1", family="roof_plan_area",  # type: ignore[arg-type]
        )


# ── Pitch and pitch-dependent families ALWAYS abstain ─────────────────────────

@pytest.mark.parametrize("family", [RoofCeilingFamily.ROOF_PITCH_DEG, RoofCeilingFamily.ROOF_SURFACE_AREA])
def test_pitch_dependent_families_always_abstain(family) -> None:
    pdf = _roof_pdf(label="ROOF")
    _source, published = _ingest(pdf)
    producer = RoofCeilingProducer.from_source_visibility_producer(_source)
    res = producer.publish(_selector(published, family=family))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert ROOF_CEILING_PITCH_EVIDENCE_UNAVAILABLE in res.reason_codes
    assert res.record is None


# ── Happy path: real printed area / witness-bound length ───────────────────────

@pytest.mark.parametrize(
    "family,label",
    [(RoofCeilingFamily.ROOF_PLAN_AREA, "ROOF"), (RoofCeilingFamily.CEILING_AREA, "CEILING")],
)
def test_area_family_resolved_from_real_printed_annotation(family, label) -> None:
    pdf = _roof_pdf(label=label, area_text="24.50", area_unit="SM")
    source, published = _ingest(pdf)
    producer = RoofCeilingProducer.from_source_visibility_producer(source)
    res = producer.publish(_selector(published, family=family))
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.value == pytest.approx(24.50)
    assert res.record.unit == "m2"
    assert ROOF_CEILING_RESOLVED in res.reason_codes


def test_eaves_overhang_resolved_from_real_witness_bound_dimension() -> None:
    pdf = _roof_pdf(
        label="ROOF", area_text=None, area_unit=None, length_label="EAVES", length_text="450",
        sheet_title="ROOF PLAN",
    )
    source, published = _ingest(pdf)
    producer = RoofCeilingProducer.from_source_visibility_producer(source)
    res = producer.publish(_selector(published, family=RoofCeilingFamily.EAVES_OVERHANG_LENGTH))
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record.value == pytest.approx(0.45)
    assert res.record.unit == "m"
    assert res.record.dimension_chain_id is not None


# ── Adversarial: no floor/footprint fallback, fail-closed ambiguity ────────────

def test_no_label_abstains_unresolved() -> None:
    pdf = _roof_pdf(label="UNRELATED")
    source, published = _ingest(pdf)
    producer = RoofCeilingProducer.from_source_visibility_producer(source)
    res = producer.publish(_selector(published, family=RoofCeilingFamily.ROOF_PLAN_AREA))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert ROOF_CEILING_UNRESOLVED in res.reason_codes


def test_regex_only_prose_does_not_mint_a_quantity() -> None:
    pdf = _roof_pdf(label="ROOF", prose=True)
    source, published = _ingest(pdf)
    producer = RoofCeilingProducer.from_source_visibility_producer(source)
    res = producer.publish(_selector(published, family=RoofCeilingFamily.ROOF_PLAN_AREA))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert ROOF_CEILING_UNRESOLVED in res.reason_codes


def test_competing_area_values_fail_closed() -> None:
    pdf = _roof_pdf(label="ROOF", area_text="24.50", area_unit="SM", second_area_text="30.00")
    source, published = _ingest(pdf)
    producer = RoofCeilingProducer.from_source_visibility_producer(source)
    res = producer.publish(_selector(published, family=RoofCeilingFamily.ROOF_PLAN_AREA))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert ROOF_CEILING_UNRESOLVED in res.reason_codes


def test_no_eaves_label_abstains_no_overhang_default() -> None:
    pdf = _roof_pdf(label="ROOF", area_text=None, area_unit=None)
    source, published = _ingest(pdf)
    producer = RoofCeilingProducer.from_source_visibility_producer(source)
    res = producer.publish(_selector(published, family=RoofCeilingFamily.EAVES_OVERHANG_LENGTH))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert ROOF_CEILING_UNRESOLVED in res.reason_codes


def test_mismatched_viewport_id_abstains() -> None:
    pdf = _roof_pdf(label="ROOF")
    source, published = _ingest(pdf)
    producer = RoofCeilingProducer.from_source_visibility_producer(source)
    res = producer.publish(
        _selector(published, family=RoofCeilingFamily.ROOF_PLAN_AREA, viewport_id="not-the-real-viewport")
    )
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert ROOF_CEILING_VIEWPORT_MISMATCH in res.reason_codes


def test_out_of_range_page_abstains() -> None:
    pdf = _roof_pdf(label="ROOF")
    source, published = _ingest(pdf)
    producer = RoofCeilingProducer.from_source_visibility_producer(source)
    res = producer.publish(_selector(published, family=RoofCeilingFamily.ROOF_PLAN_AREA, page_id="99"))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert ROOF_CEILING_PAGE_UNAVAILABLE in res.reason_codes


def test_unpublished_revision_abstains_source_unavailable() -> None:
    source = SourceVisibilityProducer(producer_method="m", producer_version="1")
    producer = RoofCeilingProducer.from_source_visibility_producer(source)
    sel = RoofCeilingSelector(
        document_id="never-ingested", revision_id="R1", source_sha256="a" * 64,
        snapshot_id="snap-1", page_id="1", viewport_id=None,
        target_id="roof-1", family=RoofCeilingFamily.ROOF_PLAN_AREA,
    )
    res = producer.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert ROOF_CEILING_SOURCE_UNAVAILABLE in res.reason_codes


def test_stale_revision_source_or_snapshot_cannot_replay_record() -> None:
    pdf = _roof_pdf(label="ROOF")
    source, published = _ingest(pdf)
    producer = RoofCeilingProducer.from_source_visibility_producer(source)
    good = _selector(published, family=RoofCeilingFamily.ROOF_PLAN_AREA)
    producer.publish(good)
    authority = producer.authority()

    bad = RoofCeilingSelector(
        document_id=good.document_id,
        revision_id=good.revision_id + "-stale",
        source_sha256="f" * 64,
        snapshot_id=good.snapshot_id + "-stale",
        page_id=good.page_id,
        viewport_id=good.viewport_id,
        target_id=good.target_id,
        family=good.family,
    )
    res = authority.resolve(bad)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert res.record is None


# ── Authority Lookup ──────────────────────────────────────────────────────────

def test_authority_lookup_published_record() -> None:
    pdf = _roof_pdf(label="ROOF")
    source, published = _ingest(pdf)
    producer = RoofCeilingProducer.from_source_visibility_producer(source)
    sel = _selector(published, family=RoofCeilingFamily.ROOF_PLAN_AREA)
    producer.publish(sel)
    res = producer.authority().resolve(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record.target_id == "roof-1"


def test_authority_lookup_missing_abstains() -> None:
    pdf = _roof_pdf(label="ROOF")
    source, published = _ingest(pdf)
    producer = RoofCeilingProducer.from_source_visibility_producer(source)
    sel = _selector(published, family=RoofCeilingFamily.ROOF_PLAN_AREA)
    res = producer.authority().resolve(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert ROOF_CEILING_RECORD_UNAVAILABLE in res.reason_codes


def test_authority_lookup_wrong_selector_type_raises() -> None:
    source = SourceVisibilityProducer(producer_method="m", producer_version="1")
    producer = RoofCeilingProducer.from_source_visibility_producer(source)
    with pytest.raises(TypeError, match="RoofCeilingSelector"):
        producer.authority().resolve("not-a-selector")  # type: ignore[arg-type]


def test_publish_wrong_selector_type_raises() -> None:
    source = SourceVisibilityProducer(producer_method="m", producer_version="1")
    producer = RoofCeilingProducer.from_source_visibility_producer(source)
    with pytest.raises(TypeError, match="RoofCeilingSelector"):
        producer.publish("not-a-selector")  # type: ignore[arg-type]


def test_selector_empty_field_raises() -> None:
    with pytest.raises(ValueError):
        RoofCeilingSelector(
            document_id="", revision_id="r", source_sha256="a" * 64,
            snapshot_id="s", page_id="1", viewport_id=None,
            target_id="roof-1", family=RoofCeilingFamily.ROOF_PLAN_AREA,
        )
