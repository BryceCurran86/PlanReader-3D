"""Tests for source-owned material schedule semantic authority."""
from __future__ import annotations

import fitz
import pytest
from dataclasses import replace
from types import SimpleNamespace

import pb_source_material_semantic_authority as semantic
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import (
    SegmentedViewport,
    ViewportBoundarySource,
    ViewportSegmentationStatus,
    _stamp_segment_page_viewports_product,
)


def _pdf(*pages: tuple[str, ...]) -> bytes:
    doc = fitz.open()
    for lines in pages:
        page = doc.new_page(width=300.0, height=220.0)
        y = 35.0
        for line in lines:
            page.insert_text((25.0, y), line, fontsize=10)
            y += 20.0
    data = doc.tobytes()
    doc.close()
    return data


def _source(source_bytes: bytes):
    producer = SourceVisibilityProducer(
        producer_method="source-material-semantic-test",
        producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="doc-material-semantic",
        source_bytes=source_bytes,
        source_locator="memory:material-semantic.pdf",
    )
    return producer, published


def _viewport(page_number: int, view_type: str, view_id: str) -> SegmentedViewport:
    return SegmentedViewport(
        view_id=view_id,
        page_number=page_number,
        view_type=view_type,
        label=view_type.upper(),
        title_bbox=(20.0, 10.0, 130.0, 25.0),
        bounding_box=(10.0, 10.0, 290.0, 210.0),
        status=ViewportSegmentationStatus.RESOLVED.value,
        boundary_source=ViewportBoundarySource.VECTOR_FRAME.value,
        confidence=1.0,
    )


def _patch_viewports(monkeypatch, page_types):
    def _segment(_page, *, page_number):
        view_type = page_types[page_number]
        return tuple(
            _stamp_segment_page_viewports_product(
                [_viewport(page_number, view_type, f"vp-{page_number}")]
            )
        )
    monkeypatch.setattr(semantic, "segment_page_viewports", _segment)


def _definition_selector(published, code: str):
    return semantic.SourceMaterialDefinitionSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        code=code,
    )


def _occurrence_selector(published, page_id: str, viewport_id: str):
    return semantic.SourceMaterialOccurrenceSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=page_id,
        viewport_id=viewport_id,
    )


def test_confirmed_schedule_semantic_and_drawing_occurrence_share_source_lineage(
    monkeypatch,
) -> None:
    source, published = _source(
        _pdf(
            (
                "FINISH SCHEDULE",
                "WT1 Porcelain wall tile",
                "PT1 Dulux low sheen paint",
            ),
            (
                "INTERNAL ELEVATION",
                "WALL FINISH WT1",
            ),
        )
    )
    _patch_viewports(monkeypatch, {1: "schedule", 2: "elevation"})

    authority = semantic.SourceMaterialSemanticProducer.from_source_visibility_producer(
        source
    ).publish(published.revision.revision_id)

    definition = authority.resolve_definition(_definition_selector(published, "WT1"))
    assert definition.status is EvidenceResolutionStatus.CORROBORATED
    assert definition.record is not None
    assert definition.record.semantic_finish == "tile"
    assert definition.record.source_page_ids == ("1",)
    assert definition.record.source_viewport_ids == ("vp-1",)

    scope = authority.resolve_occurrences(
        _occurrence_selector(published, "2", "vp-2")
    )
    assert scope.status is EvidenceResolutionStatus.CORROBORATED
    assert scope.scope_complete is True
    assert len(scope.records) == 1
    occurrence = scope.records[0]
    assert occurrence.code == "WT1"
    assert occurrence.semantic_finish == "tile"
    assert occurrence.definition_record_id == definition.record.record_id
    assert occurrence.page_id == "2"
    assert occurrence.viewport_id == "vp-2"
    assert occurrence.bbox_pdf_pts[2] > occurrence.bbox_pdf_pts[0]
    assert occurrence.bbox_pdf_pts[3] > occurrence.bbox_pdf_pts[1]
    assert occurrence.source_sha256 == published.revision.source_sha256


def test_conflicting_schedule_definition_blocks_semantic_occurrences(monkeypatch) -> None:
    source, published = _source(
        _pdf(
            ("FINISH SCHEDULE", "WT1 Porcelain wall tile"),
            ("MATERIAL SCHEDULE", "WT1 Dulux low sheen paint"),
            ("INTERNAL ELEVATION", "WALL FINISH WT1"),
        )
    )
    _patch_viewports(
        monkeypatch,
        {1: "schedule", 2: "schedule", 3: "elevation"},
    )
    authority = semantic.SourceMaterialSemanticProducer.from_source_visibility_producer(
        source
    ).publish(published.revision.revision_id)

    definition = authority.resolve_definition(_definition_selector(published, "WT1"))
    assert definition.status is EvidenceResolutionStatus.CONFLICT
    assert definition.record is None
    assert semantic.SOURCE_MATERIAL_DEFINITION_CONFLICT in definition.reason_codes

    scope = authority.resolve_occurrences(
        _occurrence_selector(published, "3", "vp-3")
    )
    assert scope.status is EvidenceResolutionStatus.CORROBORATED
    assert scope.scope_complete is True
    assert scope.records == ()


def test_schedule_text_never_mints_occurrence_on_schedule_view(monkeypatch) -> None:
    source, published = _source(
        _pdf(("FINISH SCHEDULE", "PT1 Dulux low sheen paint"))
    )
    _patch_viewports(monkeypatch, {1: "schedule"})
    authority = semantic.SourceMaterialSemanticProducer.from_source_visibility_producer(
        source
    ).publish(published.revision.revision_id)

    definition = authority.resolve_definition(_definition_selector(published, "PT1"))
    assert definition.status is EvidenceResolutionStatus.CORROBORATED
    assert definition.record is not None
    assert definition.record.semantic_finish == "paint"

    scope = authority.resolve_occurrences(
        _occurrence_selector(published, "1", "vp-1")
    )
    assert scope.status is EvidenceResolutionStatus.ABSTAINED
    assert scope.records == ()


def test_unstamped_viewport_output_cannot_publish_source_semantics(monkeypatch) -> None:
    source, published = _source(
        _pdf(("FINISH SCHEDULE", "WT1 Porcelain wall tile"))
    )
    monkeypatch.setattr(
        semantic,
        "segment_page_viewports",
        lambda _page, *, page_number: (
            _viewport(page_number, "schedule", f"vp-{page_number}"),
        ),
    )
    authority = semantic.SourceMaterialSemanticProducer.from_source_visibility_producer(
        source
    ).publish(published.revision.revision_id)

    result = authority.resolve_definition(_definition_selector(published, "WT1"))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None


def test_generic_schedule_code_is_source_owned_not_global_token_guess(monkeypatch) -> None:
    source, published = _source(
        _pdf(
            ("FINISH SCHEDULE", "WM1 Liquid waterproofing membrane"),
            (
                "INTERNAL ELEVATION",
                "WALL MEMBRANE WM1",
                "REFER DRAWING A110",
            ),
        )
    )
    _patch_viewports(monkeypatch, {1: "schedule", 2: "elevation"})
    authority = semantic.SourceMaterialSemanticProducer.from_source_visibility_producer(
        source
    ).publish(published.revision.revision_id)

    definition = authority.resolve_definition(_definition_selector(published, "WM1"))
    assert definition.status is EvidenceResolutionStatus.CORROBORATED
    assert definition.record is not None
    assert definition.record.semantic_finish == "membrane"

    scope = authority.resolve_occurrences(
        _occurrence_selector(published, "2", "vp-2")
    )
    assert [record.code for record in scope.records] == ["WM1"]


def test_untrusted_schedule_word_cannot_create_material_definition(monkeypatch) -> None:
    source, published = _source(
        _pdf(
            ("FINISH SCHEDULE", "WT1 Porcelain wall tile"),
            ("INTERNAL ELEVATION", "WALL FINISH WT1"),
        )
    )
    _patch_viewports(monkeypatch, {1: "schedule", 2: "elevation"})
    real = source.text_integrity_authority()

    class _BlockScheduleCode:
        def resolve_text(self, selector):
            result = real.resolve_text(selector)
            if (
                result.receipt is not None
                and str(result.receipt.page_id) == "1"
                and result.trusted_text == "WT1"
            ):
                return SimpleNamespace(
                    status=EvidenceResolutionStatus.ABSTAINED,
                    trusted_text=None,
                    reason_codes=("forced_untrusted_schedule_word",),
                    receipt=result.receipt,
                )
            return result

    monkeypatch.setattr(
        source,
        "text_integrity_authority",
        lambda: _BlockScheduleCode(),
    )
    authority = semantic.SourceMaterialSemanticProducer.from_source_visibility_producer(
        source
    ).publish(published.revision.revision_id)

    definition = authority.resolve_definition(_definition_selector(published, "WT1"))
    assert definition.status is EvidenceResolutionStatus.ABSTAINED
    assert definition.record is None


def test_untrusted_schedule_view_blocks_otherwise_readable_schedule_definition(
    monkeypatch,
) -> None:
    source, published = _source(
        _pdf(
            ("FINISH SCHEDULE", "WT1 Porcelain wall tile"),
            ("FINISH SCHEDULE", "WT1 Dulux low sheen paint"),
            ("INTERNAL ELEVATION", "WALL FINISH WT1"),
        )
    )
    _patch_viewports(
        monkeypatch,
        {1: "schedule", 2: "schedule", 3: "elevation"},
    )
    real = source.text_integrity_authority()

    class _BlockSecondSchedule:
        def resolve_text(self, selector):
            result = real.resolve_text(selector)
            if (
                result.receipt is not None
                and str(result.receipt.page_id) == "2"
                and result.trusted_text == "WT1"
            ):
                return SimpleNamespace(
                    status=EvidenceResolutionStatus.ABSTAINED,
                    trusted_text=None,
                    reason_codes=("forced_untrusted_competing_schedule",),
                    receipt=result.receipt,
                )
            return result

    monkeypatch.setattr(
        source,
        "text_integrity_authority",
        lambda: _BlockSecondSchedule(),
    )
    authority = semantic.SourceMaterialSemanticProducer.from_source_visibility_producer(
        source
    ).publish(published.revision.revision_id)

    definition = authority.resolve_definition(_definition_selector(published, "WT1"))
    assert definition.status is EvidenceResolutionStatus.ABSTAINED
    assert definition.record is None
    assert semantic.SOURCE_MATERIAL_VIEWPORT_UNAUTHENTICATED in definition.reason_codes

    scope = authority.resolve_occurrences(
        _occurrence_selector(published, "3", "vp-3")
    )
    assert scope.status is EvidenceResolutionStatus.ABSTAINED
    assert scope.scope_complete is False
    assert scope.records == ()


def test_untrusted_drawing_word_blocks_occurrence_scope_instead_of_being_skipped(
    monkeypatch,
) -> None:
    source, published = _source(
        _pdf(
            ("FINISH SCHEDULE", "WT1 Porcelain wall tile"),
            ("INTERNAL ELEVATION", "WALL FINISH WT1"),
        )
    )
    _patch_viewports(monkeypatch, {1: "schedule", 2: "elevation"})
    real = source.text_integrity_authority()

    class _BlockDrawingCode:
        def resolve_text(self, selector):
            result = real.resolve_text(selector)
            if (
                result.receipt is not None
                and str(result.receipt.page_id) == "2"
                and result.trusted_text == "WT1"
            ):
                return SimpleNamespace(
                    status=EvidenceResolutionStatus.ABSTAINED,
                    trusted_text=None,
                    reason_codes=("forced_untrusted_drawing_word",),
                    receipt=result.receipt,
                )
            return result

    monkeypatch.setattr(
        source,
        "text_integrity_authority",
        lambda: _BlockDrawingCode(),
    )
    authority = semantic.SourceMaterialSemanticProducer.from_source_visibility_producer(
        source
    ).publish(published.revision.revision_id)

    definition = authority.resolve_definition(_definition_selector(published, "WT1"))
    assert definition.status is EvidenceResolutionStatus.CORROBORATED

    scope = authority.resolve_occurrences(
        _occurrence_selector(published, "2", "vp-2")
    )
    assert scope.status is EvidenceResolutionStatus.ABSTAINED
    assert scope.scope_complete is False
    assert scope.records == ()
    assert semantic.SOURCE_MATERIAL_VIEWPORT_UNAUTHENTICATED in scope.reason_codes
    assert "forced_untrusted_drawing_word" in scope.reason_codes


def test_source_material_semantic_constructors_are_sealed() -> None:
    with pytest.raises(TypeError, match="from_source_visibility_producer"):
        semantic.SourceMaterialSemanticProducer(object())
    with pytest.raises(TypeError, match="producer-owned"):
        semantic.SourceMaterialSemanticAuthority({}, {})


def test_admissible_glyph_clip_failure_can_use_producer_owned_raster_corroboration(
    monkeypatch,
) -> None:
    source, published = _source(
        _pdf(
            ("FINISH SCHEDULE", "WT1 Porcelain wall tile"),
            ("INTERNAL ELEVATION", "WALL FINISH WT1"),
        )
    )
    _patch_viewports(monkeypatch, {1: "schedule", 2: "elevation"})
    real = source.text_integrity_authority()

    class _GlyphClipScheduleCode:
        def resolve_text(self, selector):
            result = real.resolve_text(selector)
            if (
                result.receipt is not None
                and str(result.receipt.page_id) == "1"
                and result.trusted_text == "WT1"
            ):
                reasons = (
                    semantic.TEXT_GLYPH_MAPPING_UNVERIFIED,
                    semantic.TEXT_CLIP_STATE_UNRESOLVED,
                )
                receipt = replace(
                    result.receipt,
                    trusted=False,
                    reason_codes=reasons,
                )
                return SimpleNamespace(
                    status=EvidenceResolutionStatus.ABSTAINED,
                    trusted_text=None,
                    reason_codes=reasons,
                    receipt=receipt,
                )
            return result

    class _FakeRasterProducer:
        @classmethod
        def from_source_visibility_producer(cls, _source):
            return cls()

        def publish(self, selector):
            source_result = source._producer.authority().resolve(
                ObservationSelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    observation_id=selector.observation_id,
                )
            )
            raw = source_result.observation.raw_text
            return SimpleNamespace(
                status=EvidenceResolutionStatus.CORROBORATED,
                record=SimpleNamespace(record_id="raster-proof"),
                corroborated_text=raw,
            )

    monkeypatch.setattr(
        source,
        "text_integrity_authority",
        lambda: _GlyphClipScheduleCode(),
    )
    monkeypatch.setattr(
        semantic,
        "RasterTextCorroborationProducer",
        _FakeRasterProducer,
    )

    authority = semantic.SourceMaterialSemanticProducer.from_source_visibility_producer(
        source
    ).publish(published.revision.revision_id)

    definition = authority.resolve_definition(_definition_selector(published, "WT1"))
    assert definition.status is EvidenceResolutionStatus.CORROBORATED
    assert definition.record is not None
    assert definition.record.semantic_finish == "tile"


def test_admissible_line_fallback_requires_exact_two_render_agreement(monkeypatch) -> None:
    source, published = _source(
        _pdf(
            ("FINISH SCHEDULE", "WT1 Porcelain wall tile"),
            ("INTERNAL ELEVATION", "WALL FINISH WT1"),
        )
    )
    _patch_viewports(monkeypatch, {1: "schedule", 2: "elevation"})
    real = source.text_integrity_authority()

    class _GlyphClipScheduleCode:
        def resolve_text(self, selector):
            result = real.resolve_text(selector)
            if (
                result.receipt is not None
                and str(result.receipt.page_id) == "1"
                and result.trusted_text == "WT1"
            ):
                reasons = (
                    semantic.TEXT_GLYPH_MAPPING_UNVERIFIED,
                    semantic.TEXT_CLIP_STATE_UNRESOLVED,
                )
                return SimpleNamespace(
                    status=EvidenceResolutionStatus.ABSTAINED,
                    trusted_text=None,
                    reason_codes=reasons,
                    receipt=replace(
                        result.receipt,
                        trusted=False,
                        reason_codes=reasons,
                    ),
                )
            return result

    class _Backend:
        def is_available(self):
            return True

    class _NoWordRaster:
        def __init__(self):
            self._backend = _Backend()

        @classmethod
        def from_source_visibility_producer(cls, _source):
            return cls()

        def publish(self, _selector):
            return SimpleNamespace(
                status=EvidenceResolutionStatus.ABSTAINED,
                record=None,
                corroborated_text=None,
            )

    monkeypatch.setattr(source, "text_integrity_authority", lambda: _GlyphClipScheduleCode())
    monkeypatch.setattr(semantic, "RasterTextCorroborationProducer", _NoWordRaster)
    monkeypatch.setattr(
        semantic,
        "_producer_owned_ocr_target",
        lambda _producer, **kwargs: (tuple(kwargs["word_bbox"]), 0),
    )
    monkeypatch.setattr(
        semantic,
        "_single_isolated_material_line_reading",
        lambda _backend, _image, *, dpi: "WT1 Porcelain wall tile",
    )

    authority = semantic.SourceMaterialSemanticProducer.from_source_visibility_producer(
        source
    ).publish(published.revision.revision_id)

    definition = authority.resolve_definition(_definition_selector(published, "WT1"))
    assert definition.status is EvidenceResolutionStatus.CORROBORATED
    assert definition.record is not None
    assert definition.record.semantic_finish == "tile"


def test_admissible_line_fallback_mismatched_second_render_remains_blocked(monkeypatch) -> None:
    source, published = _source(
        _pdf(
            ("FINISH SCHEDULE", "WT1 Porcelain wall tile"),
            ("INTERNAL ELEVATION", "WALL FINISH WT1"),
        )
    )
    _patch_viewports(monkeypatch, {1: "schedule", 2: "elevation"})
    real = source.text_integrity_authority()

    class _GlyphClipScheduleCode:
        def resolve_text(self, selector):
            result = real.resolve_text(selector)
            if (
                result.receipt is not None
                and str(result.receipt.page_id) == "1"
                and result.trusted_text == "WT1"
            ):
                reasons = (
                    semantic.TEXT_GLYPH_MAPPING_UNVERIFIED,
                    semantic.TEXT_CLIP_STATE_UNRESOLVED,
                )
                return SimpleNamespace(
                    status=EvidenceResolutionStatus.ABSTAINED,
                    trusted_text=None,
                    reason_codes=reasons,
                    receipt=replace(
                        result.receipt,
                        trusted=False,
                        reason_codes=reasons,
                    ),
                )
            return result

    class _Backend:
        def is_available(self):
            return True

    class _NoWordRaster:
        def __init__(self):
            self._backend = _Backend()

        @classmethod
        def from_source_visibility_producer(cls, _source):
            return cls()

        def publish(self, _selector):
            return SimpleNamespace(
                status=EvidenceResolutionStatus.ABSTAINED,
                record=None,
                corroborated_text=None,
            )

    readings = iter(("WT1 Porcelain wall tile", "WRONG MATERIAL LINE"))
    monkeypatch.setattr(source, "text_integrity_authority", lambda: _GlyphClipScheduleCode())
    monkeypatch.setattr(semantic, "RasterTextCorroborationProducer", _NoWordRaster)
    monkeypatch.setattr(
        semantic,
        "_producer_owned_ocr_target",
        lambda _producer, **kwargs: (tuple(kwargs["word_bbox"]), 0),
    )
    monkeypatch.setattr(
        semantic,
        "_single_isolated_material_line_reading",
        lambda _backend, _image, *, dpi: next(readings),
    )

    authority = semantic.SourceMaterialSemanticProducer.from_source_visibility_producer(
        source
    ).publish(published.revision.revision_id)

    definition = authority.resolve_definition(_definition_selector(published, "WT1"))
    assert definition.status is EvidenceResolutionStatus.ABSTAINED
    assert definition.record is None
    assert semantic.SOURCE_MATERIAL_VIEWPORT_UNAUTHENTICATED in definition.reason_codes
