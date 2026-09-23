from __future__ import annotations

import fitz

from pb_live_wall_opening_authority_composition import (
    compose_live_wall_opening_authority,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_zero_opening_wall_frame_authority import (
    ZERO_OPENING_WALL_FRAME_HAS_OPENING,
    ZERO_OPENING_WALL_FRAME_RESOLVED,
    ZeroOpeningWallFrameProducer,
    ZeroOpeningWallFrameSelector,
)
from tests.test_live_physical_opening_void_composition import _complete_void_pdf


def _opening_plus_unopened_wall_pdf() -> bytes:
    doc = fitz.open(stream=_complete_void_pdf(), filetype="pdf")
    try:
        page = doc.new_page(width=760.0, height=650.0)
        page.draw_line(
            fitz.Point(80.0, 250.0),
            fitz.Point(300.0, 250.0),
            width=1.0,
        )
        page.draw_line(
            fitz.Point(80.0, 270.0),
            fitz.Point(300.0, 270.0),
            width=1.0,
        )
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _chain():
    source = SourceVisibilityProducer(
        producer_method="zero-opening-wall-frame-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="zero-opening-wall-frame",
        source_bytes=_opening_plus_unopened_wall_pdf(),
        source_locator="memory://zero-opening-wall-frame.pdf",
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1", "2"),
    )
    assert composition.status is EvidenceResolutionStatus.CORROBORATED
    return published, composition


def _scope(composition, published, page_id: str):
    return composition.physical_wall_candidate_authority.resolve_scope(
        PhysicalWallCandidateSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id=page_id,
            decision_scope_id=f"wall-source:page-{page_id}",
        )
    )


def _producer(composition, page_id: str) -> ZeroOpeningWallFrameProducer:
    return ZeroOpeningWallFrameProducer.from_authorities(
        physical_wall_candidate_authority=(
            composition.physical_wall_candidate_authority
        ),
        physical_opening_authority=composition.physical_opening_authority,
        opening_universe_completeness_authority=(
            composition.opening_universe_completeness_authorities[page_id]
        ),
        opening_host_frame_authority=composition.opening_host_frame_authority,
    )


def _selector(published, page_id: str, physical_wall_id: str):
    return ZeroOpeningWallFrameSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=page_id,
        decision_scope_id=f"wall-source:page-{page_id}",
        physical_wall_id=physical_wall_id,
    )


def test_zero_opening_wall_frame_publishes_from_complete_source_scope() -> None:
    published, composition = _chain()
    scope = _scope(composition, published, "2")
    assert scope.status is EvidenceResolutionStatus.CORROBORATED
    assert scope.scope_complete
    assert scope.equivalence is not None
    assert scope.equivalence.representative_wall_ids

    representative = scope.equivalence.representative_wall_ids[0]
    producer = _producer(composition, "2")
    result = producer.publish(_selector(published, "2", representative))

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (ZERO_OPENING_WALL_FRAME_RESOLVED,)
    assert result.record is not None
    assert result.record.physical_wall_id == representative
    assert result.record.member_wall_candidate_ids
    assert result.record.wall_local_frame_id
    assert result.record.viewport_id
    assert result.record.length_pt > 0.0
    assert result.record.u0_pt == 0.0
    assert result.record.u1_pt == result.record.length_pt


def test_zero_opening_wall_frame_refuses_wall_class_that_has_opening() -> None:
    published, composition = _chain()
    scope = _scope(composition, published, "1")
    assert scope.status is EvidenceResolutionStatus.CORROBORATED
    assert scope.equivalence is not None

    framed_members = {
        member
        for frame in composition.host_frames
        for member in frame.whole_wall_candidate_ids
        if frame.record_id is not None
    }
    assert framed_members

    groups = tuple(
        set(group) for group in scope.equivalence.equivalence_groups
    )
    target_representative = None
    for representative in scope.equivalence.representative_wall_ids:
        wall_class = next(
            (group for group in groups if representative in group),
            {representative},
        )
        if wall_class & framed_members:
            target_representative = representative
            break
    assert target_representative is not None

    producer = _producer(composition, "1")
    result = producer.publish(
        _selector(published, "1", target_representative)
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert ZERO_OPENING_WALL_FRAME_HAS_OPENING in result.reason_codes
    assert result.record is None


def test_zero_opening_wall_frame_public_writer_has_no_truth_shaped_inputs() -> None:
    import inspect

    signature = inspect.signature(ZeroOpeningWallFrameProducer.publish)
    assert tuple(signature.parameters) == ("self", "selector")
