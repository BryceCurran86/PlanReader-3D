from __future__ import annotations

import fitz
from dataclasses import replace

import pb_cross_view_room_area_authority as dimension_authority

from pb_live_canonical_room_composition import (
    LIVE_CANONICAL_ROOM_RESOLVED,
    LiveCanonicalRoomComposition,
    LiveCanonicalRoomObject,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_same_view_room_area_authority import (
    SAME_VIEW_ROOM_AREA_CONFLICT,
    SAME_VIEW_ROOM_AREA_RESOLVED,
    SameViewRoomAreaProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _payload(
    *,
    duplicate_dimension_box: bool = False,
    yearlike_vertical_dimension: bool = False,
    second_label: bool = False,
) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=400.0, height=300.0)

        page.draw_line((100.0, 80.0), (250.0, 80.0), color=(0, 0, 0), width=1.0)
        page.draw_line((100.0, 68.0), (100.0, 92.0), color=(0, 0, 0), width=1.0)
        page.draw_line((250.0, 68.0), (250.0, 92.0), color=(0, 0, 0), width=1.0)
        page.insert_text((164.0, 77.0), "3600", fontsize=9.0)

        vertical_end_y = 163.33333333333334 if yearlike_vertical_dimension else 180.0
        vertical_text = "2000" if yearlike_vertical_dimension else "2400"
        vertical_text_y = 138.0 if yearlike_vertical_dimension else 147.0
        page.draw_line((280.0, 80.0), (280.0, vertical_end_y), color=(0, 0, 0), width=1.0)
        page.draw_line((250.0, 80.0), (292.0, 80.0), color=(0, 0, 0), width=1.0)
        page.draw_line((268.0, vertical_end_y), (292.0, vertical_end_y), color=(0, 0, 0), width=1.0)
        page.insert_text((277.0, vertical_text_y), vertical_text, fontsize=9.0, rotate=90)

        if duplicate_dimension_box:
            page.draw_line((90.0, 230.0), (260.0, 230.0), color=(0, 0, 0), width=1.0)
            page.draw_line((90.0, 218.0), (90.0, 242.0), color=(0, 0, 0), width=1.0)
            page.draw_line((260.0, 218.0), (260.0, 242.0), color=(0, 0, 0), width=1.0)
            page.insert_text((164.0, 227.0), "4080", fontsize=9.0)

            page.draw_line((280.0, 120.0), (280.0, 240.0), color=(0, 0, 0), width=1.0)
            page.draw_line((268.0, 120.0), (292.0, 120.0), color=(0, 0, 0), width=1.0)
            page.draw_line((260.0, 240.0), (292.0, 240.0), color=(0, 0, 0), width=1.0)
            page.insert_text((277.0, 197.0), "2880", fontsize=9.0, rotate=90)

        page.insert_text((150.0, 150.0), "TEST ROOM", fontsize=10.0)
        if second_label:
            page.insert_text((24.0, 265.0), "SPARE ROOM", fontsize=10.0)
        return doc.tobytes()
    finally:
        doc.close()


def _source_and_rooms(
    *,
    duplicate_label: bool = False,
    duplicate_dimension_box: bool = False,
    yearlike_vertical_dimension: bool = False,
    second_label: bool = False,
):
    source = SourceVisibilityProducer(
        producer_method="same-view-room-area-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="same-view-room-area-doc",
        source_bytes=_payload(
            duplicate_dimension_box=duplicate_dimension_box,
            yearlike_vertical_dimension=yearlike_vertical_dimension,
            second_label=second_label,
        ),
        source_locator="memory://same-view-room-area.pdf",
        page_ids=("1",),
    )

    def room(identity: str, face_record: str) -> LiveCanonicalRoomObject:
        return LiveCanonicalRoomObject(
            canonical_room_id=identity,
            physical_room_id=identity,
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id="1",
            viewport_id=None,
            decision_scope_id="wall-source:page-1",
            polygon_pdf_pts=((100.0, 100.0), (250.0, 100.0), (250.0, 200.0), (100.0, 200.0)),
            bounding_wall_ids=("w1", "w2", "w3", "w4"),
            canonical_bounding_wall_ids=(),
            wall_relationships_complete=False,
            area_page_pts2=15000.0,
            source_room_face_record_id=face_record,
            evidence_ids=(face_record,),
            geometry_complete=True,
            metric_geometry_complete=False,
            room_label="TEST ROOM",
            room_label_binding_record_id=f"label-binding:{identity}",
            room_label_evidence_ids=(f"label-evidence:{identity}",),
            room_label_reason_codes=("source_room_label_resolved",),
        )

    rooms=[room("physical-room-1","source-face-record-1")]
    if duplicate_label:
        rooms.append(room("physical-room-2","source-face-record-2"))
    if second_label:
        rooms.append(replace(
            room("physical-room-3","source-face-record-3"),
            room_label="SPARE ROOM",
        ))
    return source, LiveCanonicalRoomComposition(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(LIVE_CANONICAL_ROOM_RESOLVED,),
        rooms=tuple(rooms),
        source_pages=(1,),
    )


def test_same_view_figured_dimensions_mint_room_owned_area_without_scale() -> None:
    source, rooms = _source_and_rooms()
    result = SameViewRoomAreaProducer.from_source(source=source, rooms=rooms).publish()

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (SAME_VIEW_ROOM_AREA_RESOLVED,)
    assert len(result.records) == 1
    record=result.records[0]
    assert record.source_dimension_page_id == "1"
    assert record.area_evidence.normalized_value == 8.64
    assert record.area_evidence.unit == "m2"
    assert record.area_evidence.method == "authenticated_same_view_figured_dimensions"
    assert record.area_evidence.metadata["figured_dimension_ids"]
    assert record.area_evidence.metadata["source_dimension_page_id"] == "1"


def test_yearlike_dimension_is_promoted_only_by_floor_plan_witness_geometry() -> None:
    source, rooms = _source_and_rooms(yearlike_vertical_dimension=True)
    result = SameViewRoomAreaProducer.from_source(source=source, rooms=rooms).publish()

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (SAME_VIEW_ROOM_AREA_RESOLVED,)
    assert len(result.records) == 1
    record = result.records[0]
    assert record.area_evidence.normalized_value == 7.2
    assert record.area_evidence.method == "authenticated_same_view_figured_dimensions"
    assert record.area_evidence.metadata["vertical_value_mm"] == 2000


def test_same_view_room_eligibility_does_not_compare_room_polygons(monkeypatch) -> None:
    source, rooms = _source_and_rooms(second_label=True)

    def forbidden_room_equality(self, other):
        raise AssertionError("same-view membership must use object identity")

    monkeypatch.setattr(LiveCanonicalRoomObject, "__eq__", forbidden_room_equality)
    result = SameViewRoomAreaProducer.from_source(source=source, rooms=rooms).publish()
    assert len(result.records) == 1
    assert result.records[0].room_label == "TEST ROOM"
    assert "physical-room-3" in result.unresolved_physical_room_ids


def test_duplicate_same_page_room_label_fails_closed() -> None:
    source, rooms = _source_and_rooms(duplicate_label=True)
    result = SameViewRoomAreaProducer.from_source(source=source, rooms=rooms).publish()

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.reason_codes == (SAME_VIEW_ROOM_AREA_CONFLICT,)
    assert result.records == ()


def test_multiple_same_page_dimension_pairs_fail_closed() -> None:
    source, rooms = _source_and_rooms(duplicate_dimension_box=True)
    result = SameViewRoomAreaProducer.from_source(source=source, rooms=rooms).publish()

    assert result.status in {
        EvidenceResolutionStatus.CONFLICT,
        EvidenceResolutionStatus.ABSTAINED,
    }
    assert result.records == ()


def test_same_source_page_dimension_bundle_extracted_once_for_distinct_labels(
    monkeypatch,
) -> None:
    """Geometry extraction is reused; individual room ownership still fails closed."""
    source, rooms = _source_and_rooms(second_label=True)
    original = dimension_authority.extract_dimension_evidence_bundle
    extractions = []

    def counted(page, *, page_num, view_type):
        extractions.append((page_num, view_type))
        return original(page, page_num=page_num, view_type=view_type)

    monkeypatch.setattr(
        dimension_authority,
        "extract_dimension_evidence_bundle",
        counted,
    )
    producer = SameViewRoomAreaProducer.from_source(source=source, rooms=rooms)
    published = producer.publish()
    assert len(extractions) == 1
    assert len(published.records) == 1
    assert published.records[0].room_label == "TEST ROOM"
    assert published.records[0].area_evidence.normalized_value == 8.64
    assert "physical-room-3" in published.unresolved_physical_room_ids

    # Reusing the exact immutable snapshot must not redo raw geometric
    # extraction or allow another room to borrow the first one's evidence.
    assert producer.publish() == published
    assert len(extractions) == 1


def test_dimension_bundle_cache_is_scoped_to_source_producer(monkeypatch) -> None:
    source_a, rooms_a = _source_and_rooms()
    source_b, rooms_b = _source_and_rooms()
    original = dimension_authority.extract_dimension_evidence_bundle
    calls = []

    def counted(page, *, page_num, view_type):
        calls.append((page_num, view_type))
        return original(page, page_num=page_num, view_type=view_type)

    monkeypatch.setattr(
        dimension_authority,
        "extract_dimension_evidence_bundle",
        counted,
    )
    result_a = SameViewRoomAreaProducer.from_source(
        source=source_a, rooms=rooms_a
    ).publish()
    result_b = SameViewRoomAreaProducer.from_source(
        source=source_b, rooms=rooms_b
    ).publish()
    assert len(calls) == 2
    assert len(result_a.records) == len(result_b.records) == 1
    assert result_a.records[0].area_evidence.normalized_value == 8.64
    assert result_b.records[0].area_evidence.normalized_value == 8.64
