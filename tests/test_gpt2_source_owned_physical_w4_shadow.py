"""Opt-in original F.07 plan W4 shadow: source owns geometry and scope."""
from __future__ import annotations

import fitz
import pytest

from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import (
    is_authoritative_derived_viewport,
    segment_source_page_viewports,
)


def _source_sheet(*, role="FLOOR PLAN", frame=True, both_axes=True, hidden=False):
    """Draw native title and two-axis positive frame; never provide a bbox."""
    doc = fitz.open()
    page = doc.new_page(width=850, height=500)
    if frame:
        page.draw_rect(fitz.Rect(50, 50, 350, 350), width=0.3)
    page.insert_text((140, 170), "KITCHEN", fontsize=10)
    page.insert_text((235, 250), "BATH", fontsize=10)
    for vertical in ((False, True) if both_axes else (False,)):
        a, b = (
            ((90, 110), (90, 300))
            if vertical else ((110, 90), (300, 90))
        )
        page.draw_line(fitz.Point(*a), fitz.Point(*b), width=0.3)
        for x, y in (a, b):
            endpoint = (x + 12, y) if vertical else (x, y + 12)
            page.draw_line(fitz.Point(x, y), fitz.Point(*endpoint), width=0.3)
            for sign in (-1, 1):
                page.draw_line(
                    fitz.Point(x, y),
                    fitz.Point(x + 3 * sign, y + 3 * sign),
                    width=0.3,
                )
        page.insert_text(
            (97, 218) if vertical else (180, 87), "3210",
            rotate=90 if vertical else 0, fontsize=8,
        )
    page.insert_text((430, 410), "DRAWING TITLE", fontsize=7,
                     render_mode=3 if hidden else 0)
    page.insert_text((430, 425), role, fontsize=10,
                     render_mode=3 if hidden else 0)
    for x, label in ((560, "SCALE"), (620, "DATE"), (680, "DRAWING NO")):
        page.insert_text((x, 410), label, fontsize=7)
    data = doc.tobytes()
    doc.close()
    return data


def _source(data):
    producer = SourceVisibilityProducer(
        producer_method="gpt2-original-plan-wall-shadow-test",
        producer_version="1",
    )
    pub = producer.ingest_native_pdf_bytes(
        document_id="original-plan-shadow",
        source_bytes=data,
        source_locator="memory://source.pdf",
        page_ids=("1",),
    )
    return producer, pub


def _selectors(source, pub):
    wall = PhysicalWallCandidateProducer.from_source_owned_plan_view_shadow(
        source, page_ids=("1",)
    ).authority()
    snapshot = source.published_snapshot_for_revision(pub.revision.revision_id)
    return wall.selectors_for_authenticated_viewports(
        document_id=pub.revision.document_id,
        revision_id=pub.revision.revision_id,
        source_sha256=pub.revision.source_sha256,
        snapshot_id=snapshot.snapshot.snapshot_id,
        page_id="1",
        view_type="floor_plan",
    ), wall


def test_original_positive_plan_flows_to_sealed_source_w4_scope():
    source, pub = _source(_source_sheet())
    views = segment_source_page_viewports(
        source, revision_id=pub.revision.revision_id,
        page_id="1", physical_plan_view_shadow=True,
    )
    owners = [v for v in views if is_authoritative_derived_viewport(v)]
    assert len(owners) == 1
    selectors, authority = _selectors(source, pub)
    assert len(selectors) == 1
    result = authority.resolve_scope(selectors[0])
    assert result.scope_kind == "viewport"
    assert result.viewport_view_type == "floor_plan"
    assert result.source_sha256 == pub.revision.source_sha256
    assert result.page_id == "1"
    assert result.viewport_id == owners[0].view_id
    assert all(
        candidate.wall_candidate.length_m is None
        for candidate in result.records
    )


@pytest.mark.parametrize("changes", [
    {"frame": False},
    {"both_axes": False},
    {"role": "FRONT ELEVATION"},
    {"role": "PROJECT FLOOR PLAN"},
    {"hidden": True},
])
def test_unproved_plan_never_yields_shadow_wall_viewport(changes):
    source, pub = _source(_source_sheet(**changes))
    selectors, _authority = _selectors(source, pub)
    assert selectors == ()


def test_page_address_validation_and_no_fabricated_caller_viewport():
    source, _pub = _source(_source_sheet())
    for invalid in ((), ("0",), (1,), ("01",), (" 1",), ("2", 1), "1"):
        with pytest.raises(ValueError):
            PhysicalWallCandidateProducer.from_source_owned_plan_view_shadow(
                source, page_ids=invalid
            )
    with pytest.raises(TypeError):
        PhysicalWallCandidateProducer.from_source_owned_plan_view_shadow(
            object(), page_ids=("1",)
        )
    with pytest.raises(ValueError):
        PhysicalWallCandidateProducer.from_source_owned_plan_view_shadow(
            source, page_ids=("2",)
        )
