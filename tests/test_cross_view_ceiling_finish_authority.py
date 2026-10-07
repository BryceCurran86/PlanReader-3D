"""Focused regressions for cross-view ceiling-finish authority."""
from __future__ import annotations

import fitz

import pb_cross_view_ceiling_finish_authority as ceiling
from pb_live_canonical_room_composition import (
    LiveCanonicalRoomComposition,
    LiveCanonicalRoomObject,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_material_semantic_authority import (
    SourceMaterialDefinitionRecord,
    SourceMaterialDefinitionResult,
    SourceMaterialOccurrenceRecord,
    SourceMaterialOccurrenceScopeResult,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _pdf() -> bytes:
    doc = fitz.open()
    doc.new_page(width=300.0, height=220.0)
    doc.new_page(width=300.0, height=220.0)
    payload = doc.tobytes()
    doc.close()
    return payload


def _source():
    source = SourceVisibilityProducer(
        producer_method="cross-view-ceiling-finish-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="doc-ceiling-finish",
        source_bytes=_pdf(),
        source_locator="memory:ceiling-finish.pdf",
        page_ids=("1", "2"),
    )
    return source, published


def _room(
    published,
    *,
    room_id: str = "room-1",
    canonical_id: str = "canonical-room-1",
    label: str = "OFFICE",
) -> LiveCanonicalRoomObject:
    return LiveCanonicalRoomObject(
        canonical_room_id=canonical_id,
        physical_room_id=room_id,
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        viewport_id="floor-vp",
        decision_scope_id="scope-1",
        polygon_pdf_pts=(
            (10.0, 10.0),
            (110.0, 10.0),
            (110.0, 90.0),
            (10.0, 90.0),
        ),
        bounding_wall_ids=("wall-1", "wall-2", "wall-3", "wall-4"),
        canonical_bounding_wall_ids=(
            "cwall-1",
            "cwall-2",
            "cwall-3",
            "cwall-4",
        ),
        wall_relationships_complete=True,
        area_page_pts2=8000.0,
        source_room_face_record_id=f"face-{room_id}",
        evidence_ids=(f"room-evidence-{room_id}",),
        geometry_complete=True,
        metric_geometry_complete=False,
        room_label=label,
        room_label_binding_record_id=f"label-binding-{room_id}",
        room_label_evidence_ids=(f"label-evidence-{room_id}",),
    )


def _rooms(published, *rooms: LiveCanonicalRoomObject):
    return LiveCanonicalRoomComposition(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("test",),
        rooms=tuple(rooms),
        source_pages=(1,),
    )


def _definition(published) -> SourceMaterialDefinitionRecord:
    return SourceMaterialDefinitionRecord(
        record_id="def-grid",
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        code="GRID",
        description="Suspended ceiling grid system",
        substrate="",
        finish="",
        semantic_finish="ceiling_grid",
        source_definition_ids=("def-evidence",),
        source_page_ids=("1",),
        source_viewport_ids=("schedule-vp",),
    )


def _occurrence(published) -> SourceMaterialOccurrenceRecord:
    return SourceMaterialOccurrenceRecord(
        record_id="occ-grid",
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="2",
        viewport_id="rcp-vp",
        code="GRID",
        semantic_finish="ceiling_grid",
        definition_record_id="def-grid",
        bbox_pdf_pts=(100.0, 70.0, 125.0, 82.0),
        raw_text="GRID",
        source_evidence_id="occ-evidence",
    )


def _patch_material(monkeypatch, published):
    definition = _definition(published)
    occurrence = _occurrence(published)

    class _Authority:
        def resolve_definition(self, selector):
            assert selector.code == "GRID"
            return SourceMaterialDefinitionResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=("resolved",),
                record=definition,
            )

    class _Producer:
        @classmethod
        def from_source_visibility_producer(cls, source):
            return cls()

        def publish(self, revision_id):
            assert revision_id == published.revision.revision_id
            return _Authority()

        def published_occurrence_results(self):
            return (
                SourceMaterialOccurrenceScopeResult(
                    status=EvidenceResolutionStatus.CORROBORATED,
                    reason_codes=("resolved",),
                    scope_complete=True,
                    records=(occurrence,),
                ),
            )

    monkeypatch.setattr(ceiling, "SourceMaterialSemanticProducer", _Producer)
    monkeypatch.setattr(
        ceiling,
        "_rcp_viewports",
        lambda *_args, **_kwargs: {
            ("2", "rcp-vp"): (0.0, 0.0, 250.0, 200.0),
        },
    )
    return occurrence


def _line(
    *,
    text: str,
    block_no: int,
    line_no: int,
    bbox: tuple[float, float, float, float],
):
    return ceiling._TrustedLine(
        page_id="2",
        source_partition_id="partition-2",
        block_no=block_no,
        line_no=line_no,
        text=text,
        bbox=bbox,
        observation_ids=(f"obs-{block_no}-{line_no}",),
        receipt_ids=(f"receipt-{block_no}-{line_no}",),
    )


def test_exact_same_native_block_binds_one_ceiling_finish(monkeypatch) -> None:
    source, published = _source()
    rooms = _rooms(published, _room(published))
    _patch_material(monkeypatch, published)

    label = _line(
        text="OFFICE",
        block_no=7,
        line_no=0,
        bbox=(50.0, 50.0, 90.0, 62.0),
    )
    finish = _line(
        text="GRID",
        block_no=7,
        line_no=1,
        bbox=(100.0, 70.0, 125.0, 82.0),
    )
    monkeypatch.setattr(
        ceiling,
        "_trusted_lines_for_pages",
        lambda *_args, **_kwargs: {"2": (label, finish)},
    )

    result = ceiling.CrossViewCeilingFinishProducer.from_source(
        source=source,
        rooms=rooms,
    ).publish()

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.unresolved_physical_room_ids == ()
    assert len(result.records) == 1
    record = result.records[0]
    assert record.physical_room_id == "room-1"
    assert record.room_label == "OFFICE"
    assert record.finish_code == "GRID"
    assert record.semantic_finish == "ceiling_grid"
    assert record.support_page_id == "2"
    assert record.support_viewport_id == "rcp-vp"
    assert record.support_block_no == 7
    assert record.occurrence_evidence_id == "occ-evidence"
    assert record.definition_evidence_ids == ("def-evidence",)


def test_finish_in_different_native_block_does_not_bind(monkeypatch) -> None:
    source, published = _source()
    rooms = _rooms(published, _room(published))
    _patch_material(monkeypatch, published)

    label = _line(
        text="OFFICE",
        block_no=7,
        line_no=0,
        bbox=(50.0, 50.0, 90.0, 62.0),
    )
    finish = _line(
        text="GRID",
        block_no=8,
        line_no=0,
        bbox=(100.0, 70.0, 125.0, 82.0),
    )
    monkeypatch.setattr(
        ceiling,
        "_trusted_lines_for_pages",
        lambda *_args, **_kwargs: {"2": (label, finish)},
    )

    result = ceiling.CrossViewCeilingFinishProducer.from_source(
        source=source,
        rooms=rooms,
    ).publish()

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.records == ()
    assert result.unresolved_physical_room_ids == ("room-1",)
    assert (
        ceiling.CROSS_VIEW_CEILING_FINISH_NATIVE_BLOCK_UNAVAILABLE
        in result.reason_codes
    )


def test_duplicate_canonical_room_label_cannot_mint_cross_view_identity(
    monkeypatch,
) -> None:
    source, published = _source()
    rooms = _rooms(
        published,
        _room(
            published,
            room_id="room-1",
            canonical_id="canonical-room-1",
            label="OFFICE",
        ),
        _room(
            published,
            room_id="room-2",
            canonical_id="canonical-room-2",
            label="OFFICE",
        ),
    )
    _patch_material(monkeypatch, published)

    label = _line(
        text="OFFICE",
        block_no=7,
        line_no=0,
        bbox=(50.0, 50.0, 90.0, 62.0),
    )
    finish = _line(
        text="GRID",
        block_no=7,
        line_no=1,
        bbox=(100.0, 70.0, 125.0, 82.0),
    )
    monkeypatch.setattr(
        ceiling,
        "_trusted_lines_for_pages",
        lambda *_args, **_kwargs: {"2": (label, finish)},
    )

    result = ceiling.CrossViewCeilingFinishProducer.from_source(
        source=source,
        rooms=rooms,
    ).publish()

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.records == ()
    assert result.unresolved_physical_room_ids == ("room-1", "room-2")
    assert ceiling.CROSS_VIEW_CEILING_FINISH_CONFLICT in result.reason_codes


def test_non_ceiling_material_definition_cannot_bind(monkeypatch) -> None:
    source, published = _source()
    rooms = _rooms(published, _room(published))

    definition = SourceMaterialDefinitionRecord(
        record_id="def-grid",
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        code="GRID",
        description="Floor tile grid layout",
        substrate="",
        finish="",
        semantic_finish="tile",
        source_definition_ids=("def-evidence",),
        source_page_ids=("1",),
        source_viewport_ids=("schedule-vp",),
    )
    occurrence = _occurrence(published)
    occurrence = SourceMaterialOccurrenceRecord(
        **{
            **occurrence.__dict__,
            "semantic_finish": "tile",
        }
    )

    class _Authority:
        def resolve_definition(self, selector):
            return SourceMaterialDefinitionResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=("resolved",),
                record=definition,
            )

    class _Producer:
        @classmethod
        def from_source_visibility_producer(cls, source):
            return cls()

        def publish(self, revision_id):
            return _Authority()

        def published_occurrence_results(self):
            return (
                SourceMaterialOccurrenceScopeResult(
                    status=EvidenceResolutionStatus.CORROBORATED,
                    reason_codes=("resolved",),
                    scope_complete=True,
                    records=(occurrence,),
                ),
            )

    monkeypatch.setattr(ceiling, "SourceMaterialSemanticProducer", _Producer)
    monkeypatch.setattr(
        ceiling,
        "_rcp_viewports",
        lambda *_args, **_kwargs: {
            ("2", "rcp-vp"): (0.0, 0.0, 250.0, 200.0),
        },
    )
    label = _line(
        text="OFFICE",
        block_no=7,
        line_no=0,
        bbox=(50.0, 50.0, 90.0, 62.0),
    )
    finish = _line(
        text="GRID",
        block_no=7,
        line_no=1,
        bbox=(100.0, 70.0, 125.0, 82.0),
    )
    monkeypatch.setattr(
        ceiling,
        "_trusted_lines_for_pages",
        lambda *_args, **_kwargs: {"2": (label, finish)},
    )

    result = ceiling.CrossViewCeilingFinishProducer.from_source(
        source=source,
        rooms=rooms,
    ).publish()

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.records == ()
    assert result.unresolved_physical_room_ids == ("room-1",)
