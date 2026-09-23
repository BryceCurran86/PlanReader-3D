from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType

import fitz

from pb_live_physical_opening_void_composition import (
    LIVE_PHYSICAL_OPENING_VOID_RESOLVED,
    LIVE_PHYSICAL_OPENING_VOID_UPSTREAM_INCOMPLETE,
    compose_live_physical_opening_voids,
)
from pb_live_wall_opening_authority_composition import (
    compose_live_wall_opening_authority,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer


def _complete_void_pdf(*, include_height: bool = True) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=760.0, height=650.0)
        for first, second in (
            ((20.0, 100.0), (100.0, 100.0)),
            ((145.0, 100.0), (220.0, 100.0)),
            ((20.0, 110.0), (100.0, 110.0)),
            ((145.0, 110.0), (220.0, 110.0)),
            ((100.0, 100.0), (100.0, 110.0)),
            ((145.0, 100.0), (145.0, 110.0)),
            ((100.0, 70.0), (145.0, 70.0)),
            ((100.0, 70.0), (100.0, 100.0)),
            ((145.0, 70.0), (145.0, 100.0)),
        ):
            page.draw_line(fitz.Point(*first), fitz.Point(*second), width=1.0)
        page.insert_text(fitz.Point(112.0, 65.0), "900")
        page.insert_text(fitz.Point(112.0, 106.0), "W1")

        headings = (
            "MARK",
            "ROWDTH-MM",
            "ROHT-MM",
            "ROUGH-OPENING-SILL-MM",
            "ROUGH-OPENING-HEAD-MM",
        )
        values = ("W1", "900", "2100" if include_height else "", "900", "3000")
        xs = (50.0, 150.0, 250.0, 350.0, 550.0)
        for text, x in zip(headings, xs):
            page.insert_text(fitz.Point(x, 500.0), text)
        for text, x in zip(values, xs):
            page.insert_text(fitz.Point(x, 530.0), text)

        # Independent native graphic scale: 50 source points == 1000 mm.
        bar_x0 = 300.0
        bar_x1 = 350.0
        bar_y = 250.0
        page.draw_line(fitz.Point(bar_x0, bar_y), fitz.Point(bar_x1, bar_y), width=1.0)
        page.draw_line(
            fitz.Point(bar_x0, bar_y - 8.0),
            fitz.Point(bar_x0, bar_y + 8.0),
            width=1.0,
        )
        page.draw_line(
            fitz.Point(bar_x1, bar_y - 8.0),
            fitz.Point(bar_x1, bar_y + 8.0),
            width=1.0,
        )
        page.insert_text(fitz.Point(bar_x0 - 2.0, bar_y + 24.0), "0")
        page.insert_text(fitz.Point(bar_x1 - 4.0, bar_y + 24.0), "1m")
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def test_live_composition_resolves_sealed_physical_opening_void() -> None:
    source = SourceVisibilityProducer(
        producer_method="live-physical-opening-void-composition-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="live-physical-opening-void",
        source_bytes=_complete_void_pdf(),
        source_locator="memory://live-physical-opening-void.pdf",
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    assert wall_opening.status is EvidenceResolutionStatus.CORROBORATED

    composition = compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )

    assert composition.status is EvidenceResolutionStatus.CORROBORATED
    assert composition.reason_codes == (LIVE_PHYSICAL_OPENING_VOID_RESOLVED,)
    assert len(composition.traces) == 1
    trace = composition.traces[0]
    assert trace.decision_scope_id == "wall-source:page-1"
    assert trace.width_status is EvidenceResolutionStatus.CORROBORATED
    assert trace.width_record_id
    assert trace.schedule_binding_status is EvidenceResolutionStatus.CORROBORATED
    assert trace.schedule_binding_record_id
    assert trace.height_status is EvidenceResolutionStatus.CORROBORATED
    assert trace.height_record_id
    assert trace.vertical_status is EvidenceResolutionStatus.CORROBORATED
    assert trace.vertical_record_id
    assert trace.scale_status is EvidenceResolutionStatus.CORROBORATED
    assert trace.scale_record_id
    assert trace.void_status is EvidenceResolutionStatus.CORROBORATED
    assert trace.void_record_id

    selector = composition.void_selectors[trace.opening_identity_id]
    authority = composition.physical_opening_void_authorities[trace.page_id]
    replay = authority.resolve(selector)
    assert replay.status is EvidenceResolutionStatus.CORROBORATED
    assert replay.record is not None
    assert replay.record.record_id == trace.void_record_id
    assert replay.record.coordinate_unit == "metre"


def test_live_void_composition_never_uses_default_height_when_source_height_is_missing() -> None:
    source = SourceVisibilityProducer(
        producer_method="live-physical-opening-void-no-default-height-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="live-physical-opening-void-no-height",
        source_bytes=_complete_void_pdf(include_height=False),
        source_locator="memory://live-physical-opening-void-no-height.pdf",
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    assert wall_opening.status is EvidenceResolutionStatus.CORROBORATED

    composition = compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )

    assert composition.status is not EvidenceResolutionStatus.CORROBORATED
    assert len(composition.traces) == 1
    trace = composition.traces[0]
    assert trace.height_status is not EvidenceResolutionStatus.CORROBORATED
    assert trace.height_record_id is None
    assert trace.void_status is not EvidenceResolutionStatus.CORROBORATED
    assert trace.void_record_id is None


def test_live_void_composition_cannot_resolve_a_narrowed_opening_subset() -> None:
    source = SourceVisibilityProducer(
        producer_method="live-physical-opening-void-subset-attack",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="live-physical-opening-void-subset",
        source_bytes=_complete_void_pdf(),
        source_locator="memory://live-physical-opening-void-subset.pdf",
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    assert wall_opening.status is EvidenceResolutionStatus.CORROBORATED
    assert wall_opening.semantic_enumeration_result.record is not None
    assert wall_opening.semantic_enumeration_result.record.physical_opening_record_ids

    # Adversarially narrow the downstream binding-selector view. The semantic
    # inventory remains complete and still names the opening, so a composer
    # must not certify a successful subset merely because there are no failed
    # traces for the omitted opening.
    narrowed = replace(
        wall_opening,
        binding_selectors=MappingProxyType({}),
    )
    composition = compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=narrowed,
    )

    assert composition.status is EvidenceResolutionStatus.ABSTAINED
    assert LIVE_PHYSICAL_OPENING_VOID_UPSTREAM_INCOMPLETE in composition.reason_codes
    assert composition.traces == ()
