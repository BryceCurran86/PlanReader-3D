from __future__ import annotations

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import (
    ObservationSelector,
    SourceObservationProducer,
)
from pb_source_visibility_authority import (
    NATIVE_PDF_VISIBLE_SEGMENT,
    VISIBLE_SOURCE_OBSERVATION_EXISTS,
    VISIBILITY_ACTIVE_CLIP_UNRESOLVED,
    VISIBILITY_CLIP_ASSOCIATION_UNKNOWN,
    VISIBILITY_PROVEN_NO_ACTIVE_CLIP,
    VISIBILITY_RECEIPT_UNAVAILABLE,
    SourceVisibilityAuthority,
    SourceVisibilityProducer,
    classify_native_segment_visibility,
)


def _rectangle_pdf_bytes(*, clip_prefix: bytes | None = None) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=240, height=240)
    page.draw_line((100, 100), (140, 100), color=(0, 0, 0), width=1)
    page.draw_line((100, 110), (140, 110), color=(0, 0, 0), width=1)
    page.draw_line((100, 100), (100, 110), color=(0, 0, 0), width=1)
    page.draw_line((140, 100), (140, 110), color=(0, 0, 0), width=1)
    if clip_prefix is not None:
        contents = page.get_contents()
        assert contents
        original = b"\n".join(doc.xref_stream(xref) for xref in contents)
        doc.update_stream(contents[0], b"q\n" + clip_prefix + b"\n" + original + b"\nQ\n")
        for xref in contents[1:]:
            doc.update_stream(xref, b"")
    payload = doc.tobytes()
    doc.close()
    return payload


def _selector(published, observation_id: str) -> ObservationSelector:
    return ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=observation_id,
    )


def _visible_ingest(payload: bytes, *, document_id: str = "visible-doc"):
    producer = SourceVisibilityProducer(
        producer_method="source-visibility-test",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator=f"memory://{document_id}.pdf",
    )
    return producer, published, producer.authority()


def test_unclipped_native_segments_publish_producer_owned_visible_receipts() -> None:
    producer, published, authority = _visible_ingest(_rectangle_pdf_bytes())
    assert len(published.visible_observation_ids) == 4
    assert published.snapshot.snapshot_id != published.base_source_snapshot_id

    for observation_id in published.visible_observation_ids:
        result = authority.resolve_visible(_selector(published, observation_id))
        assert result.status == EvidenceResolutionStatus.CORROBORATED
        assert result.proposition == VISIBLE_SOURCE_OBSERVATION_EXISTS
        assert result.observation is not None
        assert result.observation.observation_kind == NATIVE_PDF_VISIBLE_SEGMENT
        assert result.observation.viewport_id is None
        assert len(result.observation.derivation_parent_ids) == 1

    # The generic writer remains encapsulated by the visibility producer.
    assert not hasattr(producer, "publish_derived_observation")


def test_real_rectangular_clip_does_not_publish_visible_segments_in_phase1() -> None:
    payload = _rectangle_pdf_bytes(clip_prefix=b"0 0 20 20 re W n")
    producer, published, authority = _visible_ingest(payload, document_id="fully-clipped")

    # Raw source observations remain in the base/final snapshot, but no
    # authority-visible segment is minted while an active clip is unresolved.
    assert published.visible_observation_ids == ()
    raw_segment_count = 0
    source = producer._producer.authority()  # test-only inspection of producer store
    for observation_id in published.snapshot.observation_ids:
        result = source.resolve(_selector(published, observation_id))
        if result.observation and result.observation.observation_kind == "native_pdf_segment":
            raw_segment_count += 1
    assert raw_segment_count == 4

    missing = authority.resolve_visible(
        ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id="not-visible",
        )
    )
    assert missing.status == EvidenceResolutionStatus.ABSTAINED
    assert VISIBILITY_RECEIPT_UNAVAILABLE in missing.reason_codes


def test_nonrectangular_clip_does_not_publish_visible_segments() -> None:
    payload = _rectangle_pdf_bytes(
        clip_prefix=b"90 120 m 150 120 l 120 170 l h W n"
    )
    _, published, _ = _visible_ingest(payload, document_id="triangle-clip")
    assert published.visible_observation_ids == ()


def test_unknown_clip_association_is_never_authority_visible() -> None:
    decision = classify_native_segment_visibility(
        {
            "x1": 1.0,
            "y1": 1.0,
            "x2": 20.0,
            "y2": 1.0,
            "clip_known": False,
            "clip_present": False,
            "clip": None,
        }
    )
    assert decision.visible is False
    assert decision.reason_codes == (VISIBILITY_CLIP_ASSOCIATION_UNKNOWN,)


def test_any_active_clip_is_fail_closed_until_clip_shape_is_independently_proven() -> None:
    decision = classify_native_segment_visibility(
        {
            "x1": 1.0,
            "y1": 1.0,
            "x2": 20.0,
            "y2": 1.0,
            "clip_known": True,
            "clip_present": True,
            "clip": [0.0, 0.0, 100.0, 100.0],
        }
    )
    assert decision.visible is False
    assert decision.reason_codes == (VISIBILITY_ACTIVE_CLIP_UNRESOLVED,)


def test_proven_no_active_clip_is_the_only_phase1_positive_state() -> None:
    decision = classify_native_segment_visibility(
        {
            "x1": 1.0,
            "y1": 1.0,
            "x2": 20.0,
            "y2": 1.0,
            "clip_known": True,
            "clip_present": False,
            "clip": None,
        }
    )
    assert decision.visible is True
    assert decision.reason_codes == (VISIBILITY_PROVEN_NO_ACTIVE_CLIP,)


def test_visibility_authority_cannot_be_constructed_from_caller_receipts() -> None:
    generic = SourceObservationProducer(
        producer_method="generic-source-test",
        producer_version="1.0",
    )
    with pytest.raises(TypeError):
        SourceVisibilityAuthority(
            generic.authority(),
            {("forged-snapshot", "forged-visible"): "forged-parent"},
        )


def test_visible_kind_alone_cannot_self_certify_without_producer_receipt() -> None:
    payload = _rectangle_pdf_bytes()
    generic = SourceObservationProducer(
        producer_method="generic-source-test",
        producer_version="1.0",
    )
    base = generic.ingest_native_pdf_bytes(
        document_id="generic-visible-forgery",
        source_bytes=payload,
        source_locator="memory://generic-visible-forgery.pdf",
    )
    source = generic.authority()
    raw = []
    for observation_id in base.snapshot.observation_ids:
        result = source.resolve(
            ObservationSelector(
                document_id=base.revision.document_id,
                revision_id=base.revision.revision_id,
                source_sha256=base.revision.source_sha256,
                snapshot_id=base.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        if result.observation and result.observation.observation_kind == "native_pdf_segment":
            raw.append(result.observation)
    assert raw
    parent = raw[0]
    forged = generic.publish_derived_observation(
        document_id=base.revision.document_id,
        revision_id=base.revision.revision_id,
        base_snapshot_id=base.snapshot.snapshot_id,
        page_id=parent.page_id,
        source_partition_id=parent.source_partition_id,
        observation_kind=NATIVE_PDF_VISIBLE_SEGMENT,
        source_primitive_ref=f"visible:{parent.source_primitive_ref}",
        origin_kind="producer_visibility_no_active_clip",
        parent_observation_ids=(parent.observation_id,),
        geometry=parent.geometry,
        viewport_id=None,
        observation_id="forged-visible",
    )

    legitimate = SourceVisibilityProducer(
        producer_method="legitimate-visibility",
        producer_version="1.0",
    ).authority()
    result = legitimate.resolve_visible(
        ObservationSelector(
            document_id=base.revision.document_id,
            revision_id=base.revision.revision_id,
            source_sha256=base.revision.source_sha256,
            snapshot_id=forged.snapshot_id,
            observation_id="forged-visible",
        )
    )
    assert result.status == EvidenceResolutionStatus.ABSTAINED
    assert result.proposition is None
    assert result.reason_codes == (VISIBILITY_RECEIPT_UNAVAILABLE,)


def test_same_bytes_replay_returns_same_visibility_snapshot_and_ids() -> None:
    payload = _rectangle_pdf_bytes()
    producer = SourceVisibilityProducer(
        producer_method="source-visibility-replay",
        producer_version="1.0",
    )
    first = producer.ingest_native_pdf_bytes(
        document_id="replay-doc",
        source_bytes=payload,
        source_locator="memory://replay-doc.pdf",
    )
    second = producer.ingest_native_pdf_bytes(
        document_id="replay-doc",
        source_bytes=payload,
        source_locator="memory://replay-doc.pdf",
    )
    assert second.revision.revision_id == first.revision.revision_id
    assert second.snapshot.snapshot_id == first.snapshot.snapshot_id
    assert second.visible_observation_ids == first.visible_observation_ids
