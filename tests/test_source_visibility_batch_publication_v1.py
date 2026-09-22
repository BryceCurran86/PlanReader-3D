"""Native source visibility batching preserves authority without per-segment cloning."""
from __future__ import annotations

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    NATIVE_PDF_VISIBLE_SEGMENT,
    SourceVisibilityProducer,
)


def _dense_vector_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=500, height=500)
    for index in range(120):
        y = 20.0 + index * 3.0
        page.draw_line(
            fitz.Point(20.0, y),
            fitz.Point(460.0, y),
            color=(0, 0, 0),
            width=1,
        )
    payload = doc.tobytes()
    doc.close()
    return payload


def test_native_visibility_uses_batch_publication_and_preserves_all_receipts(monkeypatch) -> None:
    source = SourceVisibilityProducer(
        producer_method="native-visible-batch-test",
        producer_version="1.0",
    )

    def _forbid_single_publish(*_args, **_kwargs):
        raise AssertionError("native visible observations must use batch publication")

    monkeypatch.setattr(
        source._producer,
        "publish_derived_observation",
        _forbid_single_publish,
    )

    published = source.ingest_native_pdf_bytes(
        document_id="dense-vector",
        source_bytes=_dense_vector_pdf(),
        source_locator="memory://dense-vector.pdf",
    )

    assert len(published.visible_observation_ids) >= 100
    authority = source.authority()
    for observation_id in published.visible_observation_ids:
        result = authority.resolve_visible(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        assert result.status is EvidenceResolutionStatus.CORROBORATED
        assert result.observation is not None
        assert result.observation.observation_kind == NATIVE_PDF_VISIBLE_SEGMENT
