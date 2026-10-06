from __future__ import annotations

import cv2
import fitz
import numpy as np

from pb_live_wall_opening_authority_composition import (
    compose_live_wall_opening_authority,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_semantic_opening_enumeration_authority import (
    SEMANTIC_OPENING_RASTER_CANDIDATE_CLOSURE_UNPROVEN,
    SEMANTIC_OPENING_UNIVERSE_EXHAUSTIVENESS_UNPROVEN,
    SemanticOpeningEnumerationProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _png(gray: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", gray)
    assert ok
    return bytes(encoded)


def _raster_framed_opening_pdf() -> bytes:
    gray = np.full((360, 640), 255, np.uint8)
    cv2.rectangle(gray, (30, 150), (240, 164), 0, -1)
    cv2.rectangle(gray, (400, 150), (610, 164), 0, -1)
    cv2.line(gray, (240, 154), (400, 154), 0, 1)
    cv2.line(gray, (240, 160), (400, 160), 0, 1)

    doc = fitz.open()
    page = doc.new_page(width=320.0, height=180.0)
    page.insert_image(page.rect, stream=_png(gray), keep_proportion=False)
    payload = bytes(doc.tobytes(garbage=4, deflate=True))
    doc.close()
    return payload


def _source(document_id: str) -> tuple[SourceVisibilityProducer, object]:
    source = SourceVisibilityProducer(
        producer_method="raster-live-enumeration-contract",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=_raster_framed_opening_pdf(),
        source_locator=f"memory://{document_id}.pdf",
        page_ids=("1",),
    )
    return source, published


def test_semantic_enumeration_keeps_raster_positive_but_not_false_completeness() -> None:
    source, ingested = _source("raster-semantic-enumeration")
    published = source.augment_with_raster_opening_primitives(
        ingested.revision.revision_id,
        page_ids=("1",),
    )
    assert published.raster_opening_primitive_observation_ids

    producer = SemanticOpeningEnumerationProducer.from_source_visibility_producer(
        source
    )
    result = producer.publish_page_scope(
        revision_id=published.revision.revision_id,
        decision_scope_id="raster-semantic-enumeration:page-1",
        page_ids=("1",),
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    record = result.record
    assert len(record.physical_opening_record_ids) == 1
    assert len(record.representative_observation_ids) == 1

    representative = record.representative_observation_ids[0]
    raster_ids = set(published.raster_opening_primitive_observation_ids)
    assert representative in raster_ids
    assert representative not in set(record.visible_observation_ids)
    assert set(record.opening_support_observation_ids) & raster_ids

    # The registered raster candidate family is source-closed now, but this
    # synthetic fixture intentionally has no ordinary visible structural
    # universe. Raster closure therefore clears only the raster-specific veto;
    # it does not manufacture whole-scope physical-opening completeness.
    assert record.physical_opening_universe_complete is False
    assert (
        SEMANTIC_OPENING_RASTER_CANDIDATE_CLOSURE_UNPROVEN
        not in record.reason_codes
    )
    assert SEMANTIC_OPENING_UNIVERSE_EXHAUSTIVENESS_UNPROVEN in record.reason_codes


def test_live_composer_materializes_and_enumerates_raster_opening_before_wall_scope() -> None:
    source, ingested = _source("raster-live-composer")

    before = source.published_snapshot_for_revision(
        ingested.revision.revision_id
    )
    assert before is not None
    assert before.raster_opening_primitive_observation_ids == ()

    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=ingested.revision.revision_id,
        page_ids=("1",),
    )

    refreshed = source.published_snapshot_for_revision(
        ingested.revision.revision_id
    )
    assert refreshed is not None
    assert refreshed.raster_opening_primitive_observation_ids

    semantic = composition.semantic_enumeration_result
    assert semantic.record is not None
    assert len(semantic.record.physical_opening_record_ids) == 1
    representative = semantic.record.representative_observation_ids[0]
    assert representative in set(
        refreshed.raster_opening_primitive_observation_ids
    )

    # Wall materialization runs after the raster-opening augmentation and must
    # share the final producer snapshot with downstream opening selectors.
    assert semantic.record.snapshot_id == refreshed.snapshot.snapshot_id
    for trace in composition.wall_scopes:
        selector = (
            composition.physical_wall_candidate_authority
            .selector_for_decision_scope(
                document_id=refreshed.revision.document_id,
                revision_id=refreshed.revision.revision_id,
                source_sha256=refreshed.revision.source_sha256,
                snapshot_id=refreshed.snapshot.snapshot_id,
                page_id=trace.page_id,
                decision_scope_id=f"wall-source:page-{trace.page_id}",
            )
        )
        assert selector is not None

    opening_ids = set(semantic.record.physical_opening_record_ids)
    assert any(
        trace.opening_identity_id in opening_ids
        for trace in composition.opening_bindings
    )
