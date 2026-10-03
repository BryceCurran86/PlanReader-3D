from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType

import fitz

from pb_live_opening_area_quantity_publication import (
    LIVE_OPENING_JOINERY_FIGURED_AREA_QUANTITY_AUTHORITY,
    publish_live_opening_area_quantities,
)
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


def _complete_void_pdf(
    *,
    include_height: bool = True,
    tag: str = "W1",
    include_joinery_note: bool = False,
) -> bytes:
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
        page.insert_text(fitz.Point(112.0, 106.0), tag)
        if include_joinery_note:
            page.insert_text(
                fitz.Point(60.0, 350.0),
                "JOINERY HEIGHTS TO BE 2100 AFL U.N.O.",
            )

        headings = (
            "MARK",
            "ROWDTH-MM",
            "ROHT-MM",
            "ROUGH-OPENING-SILL-MM",
            "ROUGH-OPENING-HEAD-MM",
        )
        values = (tag, "900", "2100" if include_height else "", "900", "3000")
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

    assert len(composition.canonical_openings) == 1
    opening = composition.canonical_openings[0]
    assert opening.canonical_opening_id == trace.opening_identity_id
    assert opening.physical_opening_id == trace.opening_identity_id
    assert opening.page_id == trace.page_id
    assert opening.semantic_class == "opening"
    assert opening.structural_pattern
    assert opening.representative_observation_id == trace.representative_observation_id
    assert opening.source_observation_ids
    assert opening.source_lineage_root_ids
    assert opening.source_geometries
    assert opening.host_wall_id == replay.record.host_wall_id
    assert opening.wall_local_frame_id == replay.record.wall_local_frame_id
    assert opening.opening_void_record_id == replay.record.record_id
    assert opening.u0 == replay.record.u0
    assert opening.u1 == replay.record.u1
    assert opening.z0 == replay.record.z0
    assert opening.z1 == replay.record.z1
    assert opening.width_m == replay.record.u1 - replay.record.u0
    assert opening.height_m == replay.record.z1 - replay.record.z0
    assert opening.area_m2 == opening.width_m * opening.height_m
    assert opening.geometry_complete is True
    assert opening.host_binding_record_id == replay.record.host_binding_record_id
    assert opening.opening_kind == "window"
    assert opening.type_mark == "W1"
    assert opening.schedule_page_id == "1"
    assert opening.schedule_declared_width_mm == 900
    assert opening.schedule_declared_height_mm == 2100
    assert opening.schedule_declared_count is None
    assert opening.schedule_count_explicit is False
    assert opening.schedule_row_observation_ids
    assert opening.tag_observation_id
    assert opening.tag_observation_id in opening.evidence_ids
    assert set(opening.schedule_row_observation_ids).issubset(
        set(opening.evidence_ids)
    )
    assert replay.record.record_id in opening.evidence_ids


def test_schedule_bound_door_reuses_the_same_physical_opening_identity() -> None:
    source = SourceVisibilityProducer(
        producer_method="live-physical-opening-door-subtype-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="live-physical-opening-door-subtype",
        source_bytes=_complete_void_pdf(tag="D1"),
        source_locator="memory://live-physical-opening-door-subtype.pdf",
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

    assert len(composition.canonical_openings) == 1
    opening = composition.canonical_openings[0]
    assert opening.canonical_opening_id == opening.physical_opening_id
    assert opening.opening_kind == "door"
    assert opening.type_mark == "D1"
    assert opening.schedule_declared_width_mm == 900
    assert opening.schedule_declared_height_mm == 2100
    assert opening.geometry_complete is True


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

    # Physical identity persists even when later height/void geometry abstains.
    assert len(composition.canonical_openings) == 1
    opening = composition.canonical_openings[0]
    assert opening.canonical_opening_id == trace.opening_identity_id
    assert opening.source_observation_ids
    assert opening.width_m is not None
    assert opening.height_m is None
    assert opening.area_m2 is None
    assert opening.opening_void_record_id is None
    assert opening.geometry_complete is False


def test_single_figured_door_width_plus_joinery_note_publishes_area_without_void_height() -> None:
    source = SourceVisibilityProducer(
        producer_method="live-opening-joinery-figured-area-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="live-opening-joinery-figured-area",
        source_bytes=_complete_void_pdf(
            include_height=False,
            tag="D1",
            include_joinery_note=True,
        ),
        source_locator="memory://live-opening-joinery-figured-area.pdf",
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    composition = compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )

    assert len(composition.canonical_openings) == 1
    opening = composition.canonical_openings[0]
    assert opening.opening_kind == "door"
    assert opening.height_m is None
    assert opening.geometry_complete is False
    assert opening.area_m2 == 0.9 * 2.1
    assert opening.area_basis == "figured_opening_width_x_joinery_height"
    assert opening.figured_area_record_id
    assert opening.figured_area_record_id in opening.evidence_ids

    quantities = publish_live_opening_area_quantities(composition)
    assert len(quantities) == 1
    quantity = quantities[0]
    assert quantity.value == 0.9 * 2.1
    assert (
        quantity.authority
        == LIVE_OPENING_JOINERY_FIGURED_AREA_QUANTITY_AUTHORITY
    )
    assert quantity.input_entity_ids == (opening.canonical_opening_id,)


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
    assert composition.canonical_openings == ()
