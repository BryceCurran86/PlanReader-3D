"""Production + adversarial tests for pb_dpc_substructure_authority (Item 30 V2).

Covers the source-backed contract: an ordinary wall/perimeter length must
never stand in for a DPC/foundation/strip-footing quantity. Every positive
case here requires an explicit, witness-bound, family-labelled dimension
callout; every negative case proves the authority fails closed rather than
falling back to generic wall geometry.
"""
from __future__ import annotations

import fitz
import pytest

from pb_dpc_substructure_authority import (
    DPC_SUBSTRUCTURE_MISSING_SECTION_DETAIL,
    DPC_SUBSTRUCTURE_PAGE_UNAVAILABLE,
    DPC_SUBSTRUCTURE_RECORD_UNAVAILABLE,
    DPC_SUBSTRUCTURE_RESOLVED,
    DPC_SUBSTRUCTURE_RUN_ID_MISMATCH,
    DPC_SUBSTRUCTURE_SOURCE_UNAVAILABLE,
    DPC_SUBSTRUCTURE_UNRESOLVED,
    DPC_SUBSTRUCTURE_VIEWPORT_MISMATCH,
    DPCSubstructureAuthority,
    DPCSubstructureProducer,
    DPCSubstructureSelector,
    SubstructureFamily,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer

DOC = "doc-dpc-v2-test"


def _draw_witness_dim(
    page: fitz.Page,
    *,
    x: float,
    y0: float,
    y1: float,
    text: str,
    witness_main: bool = True,
    witness_outer: bool = True,
) -> None:
    page.draw_line((x, y0), (x, y1))
    if witness_main:
        page.draw_line((x - 18, y0), (x + 18, y0))
    if witness_outer:
        page.draw_line((x - 18, y1), (x + 18, y1))
    page.insert_text((x + 5, (y0 + y1) / 2.0), text, fontsize=10, rotate=90)


def _substructure_pdf(
    *,
    label: str = "DPC",
    length_text: str = "4250",
    include_dim: bool = True,
    witness_main: bool = True,
    witness_outer: bool = True,
    second_length_text: str | None = None,
    prose: bool = False,
    depth_label: str | None = None,
    depth_text: str | None = None,
    second_label: bool = False,
) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=640, height=460)
    fx0, fy0 = 30.0, 30.0
    fx1, fy1 = fx0 + 280.0, fy0 + 280.0
    width, height = fx1 - fx0, fy1 - fy0
    page.draw_rect(fitz.Rect(fx0, fy0, fx1, fy1))
    page.insert_text((fx0 + 0.10 * width, fy1 - 8.0), "GROUND FLOOR PLAN", fontsize=10)

    if prose:
        page.insert_text(
            (fx0 + 0.10 * width, fy0 + 0.50 * height),
            f"{label} shall be provided to all external walls in accordance with BS 8215",
            fontsize=10,
        )
        data = doc.tobytes()
        doc.close()
        return data

    label_x = fx0 + 0.30 * width
    label_y = fy0 + 0.40 * height
    page.insert_text((label_x, label_y), label, fontsize=10)
    label_cx = label_x + fitz.get_text_length(label, fontsize=10) / 2.0
    label_cy = label_y - 3.5

    if second_label:
        page.insert_text((fx0 + 0.30 * width, fy0 + 0.70 * height), label, fontsize=10)

    if include_dim:
        y1 = label_cy - 4.0
        y0 = y1 - 36.0
        _draw_witness_dim(
            page,
            x=label_cx,
            y0=y0,
            y1=y1,
            text=length_text,
            witness_main=witness_main,
            witness_outer=witness_outer,
        )
        if second_length_text is not None:
            _draw_witness_dim(page, x=label_cx + 22.0, y0=y0, y1=y1, text=second_length_text)

    if depth_label and depth_text:
        dlabel_x = fx0 + 0.30 * width
        dlabel_y = fy0 + 0.85 * height
        page.insert_text((dlabel_x, dlabel_y), depth_label, fontsize=10)
        dlabel_cx = dlabel_x + fitz.get_text_length(depth_label, fontsize=10) / 2.0
        dlabel_cy = dlabel_y - 3.5
        dy1 = dlabel_cy - 4.0
        dy0 = dy1 - 36.0
        _draw_witness_dim(page, x=dlabel_cx, y0=dy0, y1=dy1, text=depth_text)

    data = doc.tobytes()
    doc.close()
    return data


def _ingest(pdf_bytes: bytes):
    source = SourceVisibilityProducer(producer_method="item30_v2_test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id=DOC,
        source_bytes=pdf_bytes,
        source_locator="memory:item30-v2-test.pdf",
    )
    return source, published


def _selector(
    published,
    *,
    family: SubstructureFamily,
    viewport_id=None,
    page_id: str = "1",
    physical_run_id: str = "run-1",
) -> DPCSubstructureSelector:
    return DPCSubstructureSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=page_id,
        viewport_id=viewport_id,
        physical_run_id=physical_run_id,
        family=family,
    )


# ── Constructor Seals ─────────────────────────────────────────────────────────

def test_authority_constructor_sealed() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        DPCSubstructureAuthority({})


def test_producer_constructor_sealed() -> None:
    source = SourceVisibilityProducer(producer_method="m", producer_version="1")
    with pytest.raises(TypeError, match="from_source_visibility_producer"):
        DPCSubstructureProducer(source)  # type: ignore[call-arg]


def test_producer_factory_rejects_non_producer_type() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        DPCSubstructureProducer.from_source_visibility_producer(object())  # type: ignore[arg-type]


def test_selector_rejects_non_enum_family() -> None:
    with pytest.raises(TypeError):
        DPCSubstructureSelector(
            document_id="d", revision_id="r", source_sha256="a" * 64,
            snapshot_id="s", page_id="1", viewport_id=None,
            physical_run_id="run-1", family="dpc_length",  # type: ignore[arg-type]
        )


# ── Happy Path: real witness-bound family labels ───────────────────────────────

@pytest.mark.parametrize(
    "family,label",
    [
        (SubstructureFamily.DPC_LENGTH, "DPC"),
        (SubstructureFamily.FOUNDATION_WALL_LENGTH, "FOUNDATION"),
        (SubstructureFamily.STRIP_FOOTING_LENGTH, "FOOTING"),
    ],
)
def test_run_length_resolved_from_real_witness_bound_dimension(family, label) -> None:
    pdf = _substructure_pdf(label=label, length_text="4250")
    source, published = _ingest(pdf)
    producer = DPCSubstructureProducer.from_source_visibility_producer(source)
    res = producer.publish(_selector(published, family=family))
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.value == pytest.approx(4.25)
    assert res.record.unit == "m"
    assert DPC_SUBSTRUCTURE_RESOLVED in res.reason_codes


def test_substructure_wall_area_requires_both_length_and_depth() -> None:
    pdf = _substructure_pdf(label="FOUNDATION", length_text="4250", depth_label="DEPTH", depth_text="600")
    source, published = _ingest(pdf)
    producer = DPCSubstructureProducer.from_source_visibility_producer(source)
    res = producer.publish(_selector(published, family=SubstructureFamily.SUBSTRUCTURE_WALL_AREA))
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record.value == pytest.approx(4.25 * 0.6)
    assert res.record.unit == "m2"
    assert res.record.depth_dimension_chain_id is not None



def test_arbitrary_physical_run_id_cannot_relabel_one_source_measurement() -> None:
    """The physical run id is source-derived, never first-caller-owned."""
    pdf = _substructure_pdf(label="DPC", length_text="12000")
    source, published = _ingest(pdf)
    producer = DPCSubstructureProducer.from_source_visibility_producer(source)

    first = producer.publish(_selector(published, family=SubstructureFamily.DPC_LENGTH, physical_run_id="run-A"))
    second = producer.publish(_selector(published, family=SubstructureFamily.DPC_LENGTH, physical_run_id="run-B"))

    assert first.status is EvidenceResolutionStatus.CORROBORATED
    assert second.status is EvidenceResolutionStatus.CORROBORATED
    assert first.record is not None and second.record is not None
    assert first.record.physical_run_id == second.record.physical_run_id
    assert first.record.record_id == second.record.record_id
    assert first.record.physical_run_id not in {"run-A", "run-B"}


def test_same_physical_run_id_republished_is_idempotent_not_a_conflict() -> None:
    pdf = _substructure_pdf(label="DPC", length_text="12000")
    source, published = _ingest(pdf)
    producer = DPCSubstructureProducer.from_source_visibility_producer(source)
    sel = _selector(published, family=SubstructureFamily.DPC_LENGTH, physical_run_id="caller-run")
    first = producer.publish(sel)
    second = producer.publish(sel)
    assert first.status is EvidenceResolutionStatus.CORROBORATED
    assert second.status is EvidenceResolutionStatus.CORROBORATED
    assert first.record == second.record
    assert first.record is not None
    assert first.record.physical_run_id != "caller-run"

def test_no_family_label_abstains_unresolved() -> None:
    pdf = _substructure_pdf(label="UNRELATED", length_text="4250")
    source, published = _ingest(pdf)
    producer = DPCSubstructureProducer.from_source_visibility_producer(source)
    res = producer.publish(_selector(published, family=SubstructureFamily.DPC_LENGTH))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert DPC_SUBSTRUCTURE_UNRESOLVED in res.reason_codes


def test_regex_only_prose_does_not_mint_a_quantity() -> None:
    pdf = _substructure_pdf(label="DPC", prose=True)
    source, published = _ingest(pdf)
    producer = DPCSubstructureProducer.from_source_visibility_producer(source)
    res = producer.publish(_selector(published, family=SubstructureFamily.DPC_LENGTH))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert DPC_SUBSTRUCTURE_UNRESOLVED in res.reason_codes


def test_one_sided_witness_fails_closed() -> None:
    pdf = _substructure_pdf(label="DPC", length_text="4250", witness_outer=False)
    source, published = _ingest(pdf)
    producer = DPCSubstructureProducer.from_source_visibility_producer(source)
    res = producer.publish(_selector(published, family=SubstructureFamily.DPC_LENGTH))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert DPC_SUBSTRUCTURE_UNRESOLVED in res.reason_codes


def test_competing_run_lengths_fail_closed() -> None:
    pdf = _substructure_pdf(label="DPC", length_text="4250", second_length_text="6000")
    source, published = _ingest(pdf)
    producer = DPCSubstructureProducer.from_source_visibility_producer(source)
    res = producer.publish(_selector(published, family=SubstructureFamily.DPC_LENGTH))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert DPC_SUBSTRUCTURE_UNRESOLVED in res.reason_codes


def test_conflicting_duplicate_labels_fail_closed() -> None:
    pdf = _substructure_pdf(label="DPC", length_text="4250", second_label=True)
    source, published = _ingest(pdf)
    producer = DPCSubstructureProducer.from_source_visibility_producer(source)
    res = producer.publish(_selector(published, family=SubstructureFamily.DPC_LENGTH))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert DPC_SUBSTRUCTURE_UNRESOLVED in res.reason_codes


def test_area_family_without_depth_evidence_abstains_missing_section_detail() -> None:
    pdf = _substructure_pdf(label="FOUNDATION", length_text="4250")  # no depth label
    source, published = _ingest(pdf)
    producer = DPCSubstructureProducer.from_source_visibility_producer(source)
    res = producer.publish(_selector(published, family=SubstructureFamily.SUBSTRUCTURE_WALL_AREA))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert DPC_SUBSTRUCTURE_MISSING_SECTION_DETAIL in res.reason_codes


def test_zero_or_unknown_value_is_not_confused_with_evidence() -> None:
    pdf = _substructure_pdf(label="DPC", length_text="0")
    source, published = _ingest(pdf)
    producer = DPCSubstructureProducer.from_source_visibility_producer(source)
    res = producer.publish(_selector(published, family=SubstructureFamily.DPC_LENGTH))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert res.record is None


def test_mismatched_viewport_id_abstains() -> None:
    pdf = _substructure_pdf(label="DPC", length_text="4250")
    source, published = _ingest(pdf)
    producer = DPCSubstructureProducer.from_source_visibility_producer(source)
    res = producer.publish(
        _selector(published, family=SubstructureFamily.DPC_LENGTH, viewport_id="not-the-real-viewport")
    )
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert DPC_SUBSTRUCTURE_VIEWPORT_MISMATCH in res.reason_codes


def test_out_of_range_page_abstains() -> None:
    pdf = _substructure_pdf(label="DPC", length_text="4250")
    source, published = _ingest(pdf)
    producer = DPCSubstructureProducer.from_source_visibility_producer(source)
    res = producer.publish(_selector(published, family=SubstructureFamily.DPC_LENGTH, page_id="99"))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert DPC_SUBSTRUCTURE_PAGE_UNAVAILABLE in res.reason_codes


def test_unpublished_revision_abstains_source_unavailable() -> None:
    source = SourceVisibilityProducer(producer_method="m", producer_version="1")
    producer = DPCSubstructureProducer.from_source_visibility_producer(source)
    sel = DPCSubstructureSelector(
        document_id="never-ingested", revision_id="R1", source_sha256="a" * 64,
        snapshot_id="snap-1", page_id="1", viewport_id=None,
        physical_run_id="run-1", family=SubstructureFamily.DPC_LENGTH,
    )
    res = producer.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert DPC_SUBSTRUCTURE_SOURCE_UNAVAILABLE in res.reason_codes


def test_stale_revision_source_or_snapshot_cannot_replay_record() -> None:
    pdf = _substructure_pdf(label="DPC", length_text="4250")
    source, published = _ingest(pdf)
    producer = DPCSubstructureProducer.from_source_visibility_producer(source)
    good = _selector(published, family=SubstructureFamily.DPC_LENGTH)
    producer.publish(good)
    authority = producer.authority()

    bad = DPCSubstructureSelector(
        document_id=good.document_id,
        revision_id=good.revision_id + "-stale",
        source_sha256="f" * 64,
        snapshot_id=good.snapshot_id + "-stale",
        page_id=good.page_id,
        viewport_id=good.viewport_id,
        physical_run_id=good.physical_run_id,
        family=good.family,
    )
    res = authority.resolve(bad)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert res.record is None


# ── Authority Lookup ──────────────────────────────────────────────────────────

def test_authority_lookup_published_record() -> None:
    pdf = _substructure_pdf(label="DPC", length_text="4250")
    source, published = _ingest(pdf)
    producer = DPCSubstructureProducer.from_source_visibility_producer(source)
    sel = _selector(published, family=SubstructureFamily.DPC_LENGTH)
    producer.publish(sel)
    res = producer.authority().resolve(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record.physical_run_id == "run-1"


def test_authority_lookup_missing_abstains() -> None:
    pdf = _substructure_pdf(label="DPC", length_text="4250")
    source, published = _ingest(pdf)
    producer = DPCSubstructureProducer.from_source_visibility_producer(source)
    sel = _selector(published, family=SubstructureFamily.DPC_LENGTH)
    res = producer.authority().resolve(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert DPC_SUBSTRUCTURE_RECORD_UNAVAILABLE in res.reason_codes


def test_authority_lookup_wrong_selector_type_raises() -> None:
    source = SourceVisibilityProducer(producer_method="m", producer_version="1")
    producer = DPCSubstructureProducer.from_source_visibility_producer(source)
    with pytest.raises(TypeError, match="DPCSubstructureSelector"):
        producer.authority().resolve("not-a-selector")  # type: ignore[arg-type]


def test_publish_wrong_selector_type_raises() -> None:
    source = SourceVisibilityProducer(producer_method="m", producer_version="1")
    producer = DPCSubstructureProducer.from_source_visibility_producer(source)
    with pytest.raises(TypeError, match="DPCSubstructureSelector"):
        producer.publish("not-a-selector")  # type: ignore[arg-type]


def test_selector_empty_field_raises() -> None:
    with pytest.raises(ValueError):
        DPCSubstructureSelector(
            document_id="", revision_id="r", source_sha256="a" * 64,
            snapshot_id="s", page_id="1", viewport_id=None,
            physical_run_id="run-1", family=SubstructureFamily.DPC_LENGTH,
        )
