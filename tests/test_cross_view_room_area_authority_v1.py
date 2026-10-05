from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import fitz

import pb_cross_view_room_area_authority as cross_view
from pb_cross_view_room_area_authority import (
    CROSS_VIEW_ROOM_AREA_CONFLICT,
    CROSS_VIEW_ROOM_AREA_RESOLVED,
    CrossViewRoomAreaProducer,
    CrossViewRoomAreaRecord,
)
from pb_live_canonical_room_composition import (
    LIVE_CANONICAL_ROOM_RESOLVED,
    LiveCanonicalRoomComposition,
    LiveCanonicalRoomObject,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_portable_raster_ocr_authority import MockOCRBackend
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _payload(*, duplicate_dimension_box: bool = False) -> bytes:
    doc = fitz.open()
    try:
        plan = doc.new_page(width=400.0, height=300.0)
        plan.insert_text((80.0, 60.0), "GROUND FLOOR PLAN", fontsize=10.0)

        detail = doc.new_page(width=400.0, height=300.0)

        # 3.6m horizontal span: 150 source points.
        detail.draw_line((100.0, 80.0), (250.0, 80.0), color=(0, 0, 0), width=1.0)
        detail.draw_line((100.0, 68.0), (100.0, 92.0), color=(0, 0, 0), width=1.0)
        detail.draw_line((250.0, 68.0), (250.0, 92.0), color=(0, 0, 0), width=1.0)
        detail.insert_text((164.0, 77.0), "3600", fontsize=9.0)

        # 2.4m vertical span: 100 source points, same figured scale ratio.
        # Its top witness crosses the horizontal dimension's right witness,
        # proving one orthogonal source-dimension junction.
        detail.draw_line((280.0, 80.0), (280.0, 180.0), color=(0, 0, 0), width=1.0)
        detail.draw_line((250.0, 80.0), (292.0, 80.0), color=(0, 0, 0), width=1.0)
        detail.draw_line((268.0, 180.0), (292.0, 180.0), color=(0, 0, 0), width=1.0)
        detail.insert_text((277.0, 147.0), "2400", fontsize=9.0, rotate=90)

        if duplicate_dimension_box:
            # A second complete orthogonal box around the same trusted label
            # must create ambiguity rather than a confidence/ranking choice.
            detail.draw_line((90.0, 230.0), (260.0, 230.0), color=(0, 0, 0), width=1.0)
            detail.draw_line((90.0, 218.0), (90.0, 242.0), color=(0, 0, 0), width=1.0)
            detail.draw_line((260.0, 218.0), (260.0, 242.0), color=(0, 0, 0), width=1.0)
            detail.insert_text((164.0, 227.0), "4080", fontsize=9.0)

            # 2.88m vertical span: 120 source points, same figured ratio
            # as the second 4.08m horizontal span. Its bottom witness crosses
            # the second horizontal dimension's right witness.
            detail.draw_line((280.0, 120.0), (280.0, 240.0), color=(0, 0, 0), width=1.0)
            detail.draw_line((268.0, 120.0), (292.0, 120.0), color=(0, 0, 0), width=1.0)
            detail.draw_line((260.0, 240.0), (292.0, 240.0), color=(0, 0, 0), width=1.0)
            detail.insert_text((277.0, 197.0), "2880", fontsize=9.0, rotate=90)

        # Insert semantic label after figured dimensions so the dimension-token
        # classifier does not see a room-label context immediately before 3600.
        detail.insert_text((150.0, 150.0), "TEST ROOM", fontsize=10.0)

        return doc.tobytes()
    finally:
        doc.close()


def _source_and_room(
    *,
    duplicate_room_label: bool = False,
    duplicate_dimension_box: bool = False,
    page_ids: tuple[str, ...] | None = None,
    room_page_id: str = "1",
):
    source = SourceVisibilityProducer(
        producer_method="cross-view-room-area-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="cross-view-room-area-doc",
        source_bytes=_payload(duplicate_dimension_box=duplicate_dimension_box),
        source_locator="memory://cross-view-room-area.pdf",
        page_ids=page_ids,
    )

    def room(identity: str, face_record: str) -> LiveCanonicalRoomObject:
        return LiveCanonicalRoomObject(
            canonical_room_id=identity,
            physical_room_id=identity,
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id=room_page_id,
            viewport_id="plan-vp",
            decision_scope_id="wall-source:viewport:1:plan-vp",
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

    rooms = [room("physical-room-1", "source-face-record-1")]
    if duplicate_room_label:
        rooms.append(room("physical-room-2", "source-face-record-2"))

    return source, LiveCanonicalRoomComposition(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(LIVE_CANONICAL_ROOM_RESOLVED,),
        rooms=tuple(rooms),
        source_pages=(int(room_page_id),),
    )


def _force_dimension_words_to_raster_authority(
    monkeypatch,
    source: SourceVisibilityProducer,
    revision_id: str,
    *,
    raster_override: dict[str, str] | None = None,
) -> None:
    published = source.published_snapshot_for_revision(revision_id)
    assert published is not None
    authority = source.text_integrity_authority()
    authority_type = type(authority)
    original_resolve = authority_type.resolve_text

    dimension_words: dict[str, str] = {}
    for observation_id in published.text_observation_ids:
        result = original_resolve(
            authority,
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            ),
        )
        receipt = result.receipt
        if (
            receipt is not None
            and str(receipt.page_id) == "2"
            and str(receipt.raw_text).strip() in {"3600", "2400"}
        ):
            dimension_words[str(observation_id)] = str(receipt.raw_text).strip()
    assert set(dimension_words.values()) == {"3600", "2400"}

    def forced_resolve(self, selector):
        result = original_resolve(self, selector)
        if str(selector.observation_id) in dimension_words:
            return replace(
                result,
                status=EvidenceResolutionStatus.ABSTAINED,
                trusted_text=None,
                reason_codes=("text_glyph_mapping_unverified",),
            )
        return result

    monkeypatch.setattr(authority_type, "resolve_text", forced_resolve)

    readings = dict(dimension_words)
    if raster_override:
        readings.update(raster_override)

    class FakeRaster:
        def publish(self, selector):
            value = readings.get(str(selector.observation_id))
            if value is None:
                return SimpleNamespace(
                    status=EvidenceResolutionStatus.ABSTAINED,
                    record=None,
                    corroborated_text=None,
                )
            return SimpleNamespace(
                status=EvidenceResolutionStatus.CORROBORATED,
                record=object(),
                corroborated_text=value,
            )

    monkeypatch.setattr(
        cross_view.RasterTextCorroborationProducer,
        "from_source_visibility_producer",
        classmethod(lambda cls, source: FakeRaster()),
    )


def test_cross_view_dimension_text_accepts_independent_raster_corroboration(
    monkeypatch,
) -> None:
    source, rooms = _source_and_room()
    _force_dimension_words_to_raster_authority(
        monkeypatch,
        source,
        rooms.rooms[0].revision_id,
    )

    result = CrossViewRoomAreaProducer.from_source(
        source=source,
        rooms=rooms,
    ).publish()

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.records) == 1
    assert result.records[0].area_evidence.normalized_value == 8.64


def test_cross_view_dimension_raster_corroboration_must_match_figured_value(
    monkeypatch,
) -> None:
    source, rooms = _source_and_room()

    published = source.published_snapshot_for_revision(
        rooms.rooms[0].revision_id
    )
    assert published is not None
    authority = source.text_integrity_authority()
    wrong_observation_id = None
    for observation_id in published.text_observation_ids:
        result = authority.resolve_text(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        if (
            result.receipt is not None
            and str(result.receipt.page_id) == "2"
            and str(result.receipt.raw_text).strip() == "3600"
        ):
            wrong_observation_id = str(observation_id)
            break
    assert wrong_observation_id is not None

    _force_dimension_words_to_raster_authority(
        monkeypatch,
        source,
        rooms.rooms[0].revision_id,
        raster_override={wrong_observation_id: "3601"},
    )

    result = CrossViewRoomAreaProducer.from_source(
        source=source,
        rooms=rooms,
    ).publish()

    assert result.records == ()
    assert result.status in {
        EvidenceResolutionStatus.ABSTAINED,
        EvidenceResolutionStatus.CONFLICT,
    }


def test_cross_view_exact_label_and_witnessed_orthogonal_dimensions_mint_room_owned_area():
    source, rooms = _source_and_room()
    result = CrossViewRoomAreaProducer.from_source(
        source=source,
        rooms=rooms,
    ).publish()

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (CROSS_VIEW_ROOM_AREA_RESOLVED,)
    assert result.unresolved_physical_room_ids == ()
    assert len(result.records) == 1

    record = result.records[0]
    assert record.physical_room_id == "physical-room-1"
    assert record.source_room_face_record_id == "source-face-record-1"
    assert record.source_dimension_page_id == "2"
    assert record.source_label_observation_ids
    assert record.source_label_receipt_ids
    assert record.horizontal_dimension_id
    assert record.vertical_dimension_id

    evidence = record.area_evidence
    assert evidence.document_id == rooms.rooms[0].document_id
    # The area proposition is owned by the physical room plan scope, not by
    # the independent dimension sheet that supports the derived value.
    assert evidence.page_id == "1"
    assert evidence.viewport_id == "plan-vp"
    assert evidence.kind == "explicit_room_area"
    assert evidence.method == "authenticated_cross_view_figured_dimensions"
    assert evidence.status is EvidenceResolutionStatus.CORROBORATED
    assert evidence.normalized_value == 8.64
    assert evidence.unit == "m2"
    assert evidence.metadata["source_dimension_page_id"] == "2"
    assert evidence.metadata["horizontal_value_mm"] == 3600
    assert evidence.metadata["vertical_value_mm"] == 2400
    assert set(evidence.metadata["figured_dimension_ids"]) == {
        record.horizontal_dimension_id,
        record.vertical_dimension_id,
    }
    assert evidence.metadata["horizontal_witness_observation_ids"]
    assert evidence.metadata["vertical_witness_observation_ids"]


def test_scoped_ingest_preserves_one_based_measurement_page_identity():
    source, rooms = _source_and_room(page_ids=("2",))
    result = CrossViewRoomAreaProducer.from_source(
        source=source,
        rooms=rooms,
    ).publish()

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.records) == 1
    assert result.records[0].source_dimension_page_id == "2"
    assert result.records[0].area_evidence.metadata["source_dimension_page_id"] == "2"


def test_same_page_dimensions_cannot_mint_cross_view_room_area():
    source, rooms = _source_and_room(
        page_ids=("2",),
        room_page_id="2",
    )
    result = CrossViewRoomAreaProducer.from_source(
        source=source,
        rooms=rooms,
    ).publish()

    assert result.records == ()
    assert result.unresolved_physical_room_ids == ("physical-room-1",)
    assert result.status in {
        EvidenceResolutionStatus.ABSTAINED,
        EvidenceResolutionStatus.CONFLICT,
    }


def test_duplicate_canonical_room_label_fails_closed_before_cross_view_binding():
    source, rooms = _source_and_room(duplicate_room_label=True)
    result = CrossViewRoomAreaProducer.from_source(
        source=source,
        rooms=rooms,
    ).publish()

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.reason_codes == (CROSS_VIEW_ROOM_AREA_CONFLICT,)
    assert result.records == ()
    assert set(result.unresolved_physical_room_ids) == {
        "physical-room-1",
        "physical-room-2",
    }


def test_multiple_orthogonal_dimension_pairs_around_same_label_fail_closed():
    source, rooms = _source_and_room(duplicate_dimension_box=True)
    result = CrossViewRoomAreaProducer.from_source(
        source=source,
        rooms=rooms,
    ).publish()

    assert result.status in {
        EvidenceResolutionStatus.CONFLICT,
        EvidenceResolutionStatus.ABSTAINED,
    }
    assert result.records == ()
    assert result.unresolved_physical_room_ids == ("physical-room-1",)


def test_record_constructor_rejects_caller_forgery():
    source, rooms = _source_and_room()
    result = CrossViewRoomAreaProducer.from_source(
        source=source,
        rooms=rooms,
    ).publish()
    assert result.records
    record = result.records[0]

    try:
        CrossViewRoomAreaRecord(
            physical_room_id=record.physical_room_id,
            source_room_face_record_id=record.source_room_face_record_id,
            room_label=record.room_label,
            source_dimension_page_id=record.source_dimension_page_id,
            source_label_observation_ids=record.source_label_observation_ids,
            source_label_receipt_ids=record.source_label_receipt_ids,
            horizontal_dimension_id=record.horizontal_dimension_id,
            vertical_dimension_id=record.vertical_dimension_id,
            area_evidence=record.area_evidence,
        )
    except TypeError:
        pass
    else:
        raise AssertionError("caller-forged cross-view room area record was accepted")
