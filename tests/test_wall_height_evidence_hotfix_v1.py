"""Production + adversarial tests for the Item 17 wall-height positive-path hotfix.

pb_wall_height_authority.WallHeightProducer.publish_scope() previously
constructed pb_pdf_text_integrity_authority.ObservationSelector with an
unsupported page_id keyword argument (that selector only accepts
document_id/revision_id/source_sha256/snapshot_id/observation_id), and then
read a res.atom attribute that PdfTextIntegrityResult does not have. Both
mistakes raised inside a bare `except Exception: pass`, so the positive
FIRM path was unconditionally dead -- publish_scope() always returned
BLOCKED/abstained regardless of real height evidence in the source PDF.

This file proves the corrected path: a genuine witness-bound HEIGHT/HT
dimension in an elevation or section viewport resolves FIRM, and the same
fail-closed rigor used elsewhere in this codebase (F.23-style witness
binding, physical-identity binding against relabeling) applies here too.
"""
from __future__ import annotations

import fitz
import pytest

from pb_geometry_takeoff_model import AuthorityStatus
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_height_authority import WallHeightProducer, WallHeightSelector

DOC = "doc-wall-height-hotfix-test"


def _draw_witness_dim(page: fitz.Page, *, x: float, y0: float, y1: float, text: str) -> None:
    page.draw_line((x, y0), (x, y1))
    page.draw_line((x - 18, y0), (x + 18, y0))
    page.draw_line((x - 18, y1), (x + 18, y1))
    page.insert_text((x + 5, (y0 + y1) / 2.0), text, fontsize=10, rotate=90)


def _elevation_pdf(
    *,
    label: str = "HEIGHT",
    height_text: str = "2700",
    include_dim: bool = True,
    second_height_text: str | None = None,
    sheet_title: str = "ELEVATION",
    prose: bool = False,
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
            f"{label} of wall shall be 2700 mm unless noted otherwise",
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

    if include_dim:
        y1 = label_cy - 4.0
        y0 = y1 - 36.0
        _draw_witness_dim(
            page, x=label_cx, y0=y0, y1=y1, text=height_text,
        )
        if second_height_text is not None:
            _draw_witness_dim(page, x=label_cx + 22.0, y0=y0, y1=y1, text=second_height_text)

    data = doc.tobytes()
    doc.close()
    return data


def _elevation_pdf_one_sided(*, height_text: str = "2700") -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=640, height=460)
    fx0, fy0 = 30.0, 30.0
    fx1, fy1 = fx0 + 280.0, fy0 + 280.0
    width, height = fx1 - fx0, fy1 - fy0
    page.draw_rect(fitz.Rect(fx0, fy0, fx1, fy1))
    page.insert_text((fx0 + 0.10 * width, fy1 - 8.0), "ELEVATION", fontsize=10)

    label_x = fx0 + 0.30 * width
    label_y = fy0 + 0.40 * height
    page.insert_text((label_x, label_y), "HEIGHT", fontsize=10)
    label_cx = label_x + fitz.get_text_length("HEIGHT", fontsize=10) / 2.0
    label_cy = label_y - 3.5
    y1 = label_cy - 4.0
    y0 = y1 - 36.0
    page.draw_line((label_cx, y0), (label_cx, y1))
    page.draw_line((label_cx - 18, y0), (label_cx + 18, y0))
    # No outer witness line -- one-sided.
    page.insert_text((label_cx + 5, (y0 + y1) / 2.0), height_text, fontsize=10, rotate=90)

    data = doc.tobytes()
    doc.close()
    return data


def _ingest(pdf_bytes: bytes):
    source = SourceVisibilityProducer(producer_method="item17_hotfix_test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id=DOC, source_bytes=pdf_bytes, source_locator="memory:item17-hotfix-test.pdf",
    )
    return source, published


def _selector(published, *, physical_wall_id: str = "wall-1", page_id: str = "1") -> WallHeightSelector:
    return WallHeightSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=page_id,
        decision_scope_id="scope-1",
        physical_wall_id=physical_wall_id,
    )


# ── Happy path: the positive path actually works now ───────────────────────────

def test_real_witness_bound_height_resolves_firm() -> None:
    pdf = _elevation_pdf()
    source, published = _ingest(pdf)
    producer = WallHeightProducer.from_authorities(source)
    qty = producer.publish_scope(_selector(published))
    assert qty.status == AuthorityStatus.FIRM.value
    assert qty.abstained is False
    assert qty.value == pytest.approx(2.7)
    assert qty.unit == "m"
    assert qty.metadata.get("target_entity_id") == "wall-1"


def test_publish_is_idempotent() -> None:
    pdf = _elevation_pdf()
    source, published = _ingest(pdf)
    producer = WallHeightProducer.from_authorities(source)
    sel = _selector(published)
    first = producer.publish_scope(sel)
    second = producer.publish_scope(sel)
    assert first.status == second.status == AuthorityStatus.FIRM.value
    assert first.value == second.value == pytest.approx(2.7)
    assert first.quantity_id == second.quantity_id


def test_authority_resolve_returns_published_firm_quantity() -> None:
    pdf = _elevation_pdf()
    source, published = _ingest(pdf)
    producer = WallHeightProducer.from_authorities(source)
    sel = _selector(published)
    producer.publish_scope(sel)
    result = producer.authority().resolve(sel)
    assert result is not None
    assert result.status == AuthorityStatus.FIRM.value
    assert result.value == pytest.approx(2.7)


# ── Adversarial: no floor/plan fallback, fail-closed ambiguity ─────────────────

def test_no_label_abstains() -> None:
    pdf = _elevation_pdf(label="UNRELATED")
    source, published = _ingest(pdf)
    producer = WallHeightProducer.from_authorities(source)
    qty = producer.publish_scope(_selector(published))
    assert qty.status == AuthorityStatus.BLOCKED.value
    assert qty.abstained is True
    assert qty.value is None


def test_regex_only_prose_does_not_mint_a_height() -> None:
    pdf = _elevation_pdf(prose=True)
    source, published = _ingest(pdf)
    producer = WallHeightProducer.from_authorities(source)
    qty = producer.publish_scope(_selector(published))
    assert qty.status == AuthorityStatus.BLOCKED.value
    assert qty.value is None


def test_one_sided_witness_fails_closed() -> None:
    pdf = _elevation_pdf_one_sided()
    source, published = _ingest(pdf)
    producer = WallHeightProducer.from_authorities(source)
    qty = producer.publish_scope(_selector(published))
    assert qty.status == AuthorityStatus.BLOCKED.value
    assert qty.value is None


def test_competing_height_values_fail_closed() -> None:
    pdf = _elevation_pdf(second_height_text="3000")
    source, published = _ingest(pdf)
    producer = WallHeightProducer.from_authorities(source)
    qty = producer.publish_scope(_selector(published))
    assert qty.status == AuthorityStatus.BLOCKED.value
    assert qty.value is None


def test_plan_view_type_is_not_eligible_for_wall_height() -> None:
    """A HEIGHT label with a witness-bound dimension on a floor PLAN (not
    an elevation/section) must not resolve -- wall height is only shown on
    elevations/sections in this resolver's scope."""
    pdf = _elevation_pdf(sheet_title="GROUND FLOOR PLAN")
    source, published = _ingest(pdf)
    producer = WallHeightProducer.from_authorities(source)
    qty = producer.publish_scope(_selector(published))
    assert qty.status == AuthorityStatus.BLOCKED.value
    assert qty.value is None


def test_out_of_range_page_abstains() -> None:
    pdf = _elevation_pdf()
    source, published = _ingest(pdf)
    producer = WallHeightProducer.from_authorities(source)
    qty = producer.publish_scope(_selector(published, page_id="99"))
    assert qty.status == AuthorityStatus.BLOCKED.value
    assert qty.value is None


def test_unpublished_revision_abstains() -> None:
    source = SourceVisibilityProducer(producer_method="m", producer_version="1")
    producer = WallHeightProducer.from_authorities(source)
    sel = WallHeightSelector(
        document_id="never-ingested", revision_id="R1", source_sha256="a" * 64,
        snapshot_id="snap-1", page_id="1", decision_scope_id="scope-1", physical_wall_id="wall-1",
    )
    qty = producer.publish_scope(sel)
    assert qty.status == AuthorityStatus.BLOCKED.value
    assert qty.abstained is True


def test_stale_source_sha_abstains() -> None:
    pdf = _elevation_pdf()
    source, published = _ingest(pdf)
    producer = WallHeightProducer.from_authorities(source)
    bad = WallHeightSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256="f" * 64,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1", decision_scope_id="scope-1", physical_wall_id="wall-1",
    )
    qty = producer.publish_scope(bad)
    assert qty.status == AuthorityStatus.BLOCKED.value
    assert qty.value is None


def test_stale_snapshot_abstains() -> None:
    pdf = _elevation_pdf()
    source, published = _ingest(pdf)
    producer = WallHeightProducer.from_authorities(source)
    bad = WallHeightSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id + "-stale",
        page_id="1", decision_scope_id="scope-1", physical_wall_id="wall-1",
    )
    qty = producer.publish_scope(bad)
    assert qty.status == AuthorityStatus.BLOCKED.value
    assert qty.value is None


# ── Adversarial: identity binding against relabeling ────────────────────────────

def test_arbitrary_physical_wall_id_cannot_relabel_one_source_measurement() -> None:
    pdf = _elevation_pdf()
    source, published = _ingest(pdf)
    producer = WallHeightProducer.from_authorities(source)

    a = producer.publish_scope(_selector(published, physical_wall_id="wall-A"))
    assert a.status == AuthorityStatus.FIRM.value
    assert a.value == pytest.approx(2.7)

    b = producer.publish_scope(_selector(published, physical_wall_id="wall-B"))
    assert b.status == AuthorityStatus.BLOCKED.value
    assert b.value is None
    assert "wall_height_physical_wall_id_mismatch" in b.blocking_reasons

    replay = producer.authority().resolve(_selector(published, physical_wall_id="wall-A"))
    assert replay.status == AuthorityStatus.FIRM.value


def test_same_physical_wall_id_republished_is_idempotent_not_a_conflict() -> None:
    pdf = _elevation_pdf()
    source, published = _ingest(pdf)
    producer = WallHeightProducer.from_authorities(source)
    sel = _selector(published, physical_wall_id="wall-A")
    first = producer.publish_scope(sel)
    second = producer.publish_scope(sel)
    assert first.status == second.status == AuthorityStatus.FIRM.value
