from __future__ import annotations

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import (
    ObservationSelector,
    SourceObservationProducer,
)
from pb_vector_geometry_v130 import _normalize_axis_aligned_quad
from pb_source_visibility_authority import (
    NATIVE_PDF_VISIBLE_SEGMENT,
    VISIBLE_SOURCE_OBSERVATION_EXISTS,
    VISIBILITY_ACTIVE_CLIP_UNRESOLVED,
    VISIBILITY_CLIP_ASSOCIATION_UNKNOWN,
    VISIBILITY_CLIP_STATE_INCONSISTENT,
    VISIBILITY_PROVEN_NO_ACTIVE_CLIP,
    VISIBILITY_PROVEN_RECTANGULAR_CLIP,
    VISIBILITY_RECTANGULAR_CLIP_EXCLUDES_SEGMENT,
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


def test_native_visible_segments_publish_in_one_derived_snapshot() -> None:
    producer, published, authority = _visible_ingest(
        _rectangle_pdf_bytes(),
        document_id="batched-visible",
    )

    assert len(producer._producer._store.snapshots) == 2
    assert published.snapshot.parent_snapshot_id == published.base_source_snapshot_id
    assert len(published.visible_observation_ids) == 4

    for observation_id in published.visible_observation_ids:
        result = authority.resolve_visible(_selector(published, observation_id))
        assert result.status == EvidenceResolutionStatus.CORROBORATED
        assert result.observation is not None
        assert result.observation.snapshot_id == published.snapshot.snapshot_id
        assert len(result.observation.derivation_parent_ids) == 1


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


def test_rectangular_clip_containing_segments_publishes_visible_segments() -> None:
    payload = _rectangle_pdf_bytes(clip_prefix=b"0 0 240 240 re W n")
    _, published, authority = _visible_ingest(payload, document_id="contained-rect-clip")

    assert len(published.visible_observation_ids) == 4
    for observation_id in published.visible_observation_ids:
        result = authority.resolve_visible(_selector(published, observation_id))
        assert result.status == EvidenceResolutionStatus.CORROBORATED
        assert result.proposition == VISIBLE_SOURCE_OBSERVATION_EXISTS


def test_proven_rectangular_clip_requires_full_segment_containment() -> None:
    inside = classify_native_segment_visibility(
        {
            "x1": 10.0,
            "y1": 10.0,
            "x2": 20.0,
            "y2": 10.0,
            "clip_known": True,
            "clip_present": True,
            "clip": [0.0, 0.0, 100.0, 100.0],
            "clip_shape_known": True,
            "clip_exact_rect": [0.0, 0.0, 100.0, 100.0],
        }
    )
    assert inside.visible is True
    assert inside.reason_codes == (VISIBILITY_PROVEN_RECTANGULAR_CLIP,)

    crossing = classify_native_segment_visibility(
        {
            "x1": 90.0,
            "y1": 10.0,
            "x2": 110.0,
            "y2": 10.0,
            "clip_known": True,
            "clip_present": True,
            "clip": [0.0, 0.0, 100.0, 100.0],
            "clip_shape_known": True,
            "clip_exact_rect": [0.0, 0.0, 100.0, 100.0],
        }
    )
    assert crossing.visible is False
    assert crossing.reason_codes == (
        VISIBILITY_RECTANGULAR_CLIP_EXCLUDES_SEGMENT,
    )

    outside = classify_native_segment_visibility(
        {
            "x1": 110.0,
            "y1": 10.0,
            "x2": 120.0,
            "y2": 10.0,
            "clip_known": True,
            "clip_present": True,
            "clip": [0.0, 0.0, 100.0, 100.0],
            "clip_shape_known": True,
            "clip_exact_rect": [0.0, 0.0, 100.0, 100.0],
        }
    )
    assert outside.visible is False
    assert outside.reason_codes == (
        VISIBILITY_RECTANGULAR_CLIP_EXCLUDES_SEGMENT,
    )


@pytest.mark.parametrize(
    "exact_rect",
    [
        None,
        [0.0, 0.0, float("nan"), 100.0],
        [0.0, 0.0, float("inf"), 100.0],
        [100.0, 0.0, 0.0, 100.0],
        [0.0, 0.0, 0.0, 100.0],
        [0.0, 0.0, 100.0],
    ],
)
def test_claimed_rectangular_clip_with_invalid_exact_rect_fails_closed(
    exact_rect,
) -> None:
    decision = classify_native_segment_visibility(
        {
            "x1": 10.0,
            "y1": 10.0,
            "x2": 20.0,
            "y2": 10.0,
            "clip_known": True,
            "clip_present": True,
            "clip": [0.0, 0.0, 100.0, 100.0],
            "clip_shape_known": True,
            "clip_exact_rect": exact_rect,
        }
    )
    assert decision.visible is False
    assert decision.reason_codes == (VISIBILITY_CLIP_STATE_INCONSISTENT,)


def test_exact_clip_proof_rejects_conflicting_diagnostic_scissor() -> None:
    decision = classify_native_segment_visibility(
        {
            "x1": 10.0,
            "y1": 10.0,
            "x2": 20.0,
            "y2": 10.0,
            "clip_known": True,
            "clip_present": True,
            "clip": [50.0, 50.0, 60.0, 60.0],
            "clip_shape_known": True,
            "clip_exact_rect": [0.0, 0.0, 100.0, 100.0],
        }
    )
    assert decision.visible is False
    assert decision.reason_codes == (VISIBILITY_CLIP_STATE_INCONSISTENT,)


def test_axis_aligned_quad_is_exact_rectangular_clip_proof() -> None:
    class _Point:
        def __init__(self, x: float, y: float) -> None:
            self.x = x
            self.y = y

    class _Quad:
        ul = _Point(0.0, 0.0)
        ur = _Point(100.0, 0.0)
        ll = _Point(0.0, 50.0)
        lr = _Point(100.0, 50.0)

    class _Skewed:
        ul = _Point(0.0, 0.0)
        ur = _Point(100.0, 1.0)
        ll = _Point(0.0, 50.0)
        lr = _Point(100.0, 50.0)

    assert _normalize_axis_aligned_quad(_Quad()) == pytest.approx(
        (0.0, 0.0, 100.0, 50.0)
    )
    assert _normalize_axis_aligned_quad(_Skewed()) is None


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


def test_scissor_alone_cannot_unlock_active_clip_visibility() -> None:
    # Adversarial mutation: even a caller-supplied scissor and exact-rect-like
    # payload cannot unlock visibility without producer-owned shape proof.
    decision = classify_native_segment_visibility(
        {
            "x1": 1.0,
            "y1": 1.0,
            "x2": 20.0,
            "y2": 1.0,
            "clip_known": True,
            "clip_present": True,
            "clip": [0.0, 0.0, 100.0, 100.0],
            "clip_shape_known": False,
            "clip_exact_rect": [0.0, 0.0, 100.0, 100.0],
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

def _two_page_rectangle_pdf_bytes() -> bytes:
    doc = fitz.open()
    for index in range(2):
        page = doc.new_page(width=240, height=240)
        page.insert_text((20, 30), f"PAGE-{index + 1}")
        page.draw_line((100, 100), (140, 100), color=(0, 0, 0), width=1)
        page.draw_line((100, 110), (140, 110), color=(0, 0, 0), width=1)
        page.draw_line((100, 100), (100, 110), color=(0, 0, 0), width=1)
        page.draw_line((140, 100), (140, 110), color=(0, 0, 0), width=1)
    payload = doc.tobytes()
    doc.close()
    return payload


def test_visibility_scoped_ingestion_never_decodes_or_publishes_other_pages() -> None:
    payload = _two_page_rectangle_pdf_bytes()
    producer = SourceVisibilityProducer(
        producer_method="source-visibility-scoped-test",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="visible-scoped",
        source_bytes=payload,
        source_locator="memory://visible-scoped.pdf",
        page_ids=("2",),
    )

    assert published.coverage.total_pages == 2
    assert published.coverage.decoded_pages == (2,)
    assert published.coverage.state == "partial"
    assert len(published.visible_observation_ids) == 4

    source = producer._producer.authority()
    observed_pages = set()
    for observation_id in published.snapshot.observation_ids:
        result = source.resolve(_selector(published, observation_id))
        if result.observation is not None:
            observed_pages.add(result.observation.page_id)
    assert observed_pages == {"2"}

    assert producer.optional_content_state_for_scope(
        published.revision.revision_id,
        page_ids=("2",),
    ) == "known_visible"
    assert producer.optional_content_state_for_scope(
        published.revision.revision_id,
        page_ids=("1",),
    ) == "unresolved"
