from __future__ import annotations

import fitz

from pb_gross_wall_geometry_authority import GROSS_WALL_GEOMETRY_HEIGHT_UNRESOLVED
from pb_live_gross_wall_geometry_composition import (
    LIVE_GROSS_WALL_COVERAGE_INCOMPLETE,
    LIVE_GROSS_WALL_PARTIAL,
    compose_live_gross_wall_geometry,
)
from pb_live_physical_opening_void_composition import (
    compose_live_physical_opening_voids,
)
from pb_live_wall_opening_authority_composition import (
    compose_live_wall_opening_authority,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer
from tests.test_live_physical_opening_void_composition import _complete_void_pdf


def _one_page_chain():
    source = SourceVisibilityProducer(
        producer_method="live-gross-wall-geometry-composition-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="live-gross-wall-geometry",
        source_bytes=_complete_void_pdf(),
        source_locator="memory://live-gross-wall-geometry.pdf",
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    assert wall_opening.status is EvidenceResolutionStatus.CORROBORATED

    physical_void = compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )
    assert physical_void.status is EvidenceResolutionStatus.CORROBORATED
    return source, wall_opening, physical_void


def test_live_gross_wall_never_defaults_height_without_cross_sheet_identity() -> None:
    source, wall_opening, physical_void = _one_page_chain()

    composition = compose_live_gross_wall_geometry(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
        physical_void_composition=physical_void,
    )

    assert composition.status is EvidenceResolutionStatus.ABSTAINED
    assert LIVE_GROSS_WALL_PARTIAL in composition.reason_codes
    assert len(composition.traces) == 1

    trace = composition.traces[0]
    assert trace.registration_target_page_ids == ()
    assert trace.registration_record_ids == ()
    assert trace.height_m is None
    assert "no_cross_sheet_bound_wall_height_evidence" in trace.height_reason_codes
    assert trace.gross_status is EvidenceResolutionStatus.ABSTAINED
    assert trace.gross_record_id is None
    assert GROSS_WALL_GEOMETRY_HEIGHT_UNRESOLVED in trace.gross_reason_codes

    # The sealed replay remains unknown: lack of a source-bound wall height is
    # never converted to zero, gross=net, or a model/default height.
    selector = composition.gross_selectors[trace.physical_wall_id]
    assert composition.gross_wall_geometry_authority is not None
    replay = composition.gross_wall_geometry_authority.resolve(selector)
    assert replay.status is EvidenceResolutionStatus.ABSTAINED
    assert replay.record is None


def test_live_gross_wall_uses_shared_whole_wall_frame_identity() -> None:
    source, wall_opening, physical_void = _one_page_chain()

    void_trace = physical_void.traces[0]
    void_selector = physical_void.void_selectors[void_trace.opening_identity_id]
    void_authority = physical_void.physical_opening_void_authorities[
        void_trace.page_id
    ]
    void_result = void_authority.resolve(void_selector)
    assert void_result.status is EvidenceResolutionStatus.CORROBORATED
    assert void_result.record is not None
    void_record = void_result.record

    # The binding id is intentionally opening-scoped. Downstream gross/net wall
    # truth must instead use the producer-owned shared whole-wall frame.
    assert void_record.host_wall_id != void_record.wall_local_frame_id

    composition = compose_live_gross_wall_geometry(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
        physical_void_composition=physical_void,
    )

    assert len(composition.traces) == 1
    trace = composition.traces[0]
    assert trace.physical_wall_id == void_record.wall_local_frame_id
    assert trace.physical_wall_id != void_record.host_wall_id
    assert void_record.wall_local_frame_id in composition.gross_selectors
    assert void_record.host_wall_id not in composition.gross_selectors


def test_live_gross_wall_targets_proven_zero_opening_wall_without_weakening_global_coverage_firewall() -> None:
    doc = fitz.open(stream=_complete_void_pdf(), filetype="pdf")
    try:
        page = doc.new_page(width=760.0, height=650.0)
        # A separate source-owned wall on the second selected plan page. It has
        # no aperture, so it cannot appear in the opening-host frame inventory.
        # Use one centreline candidate: two unsupported parallel faces are
        # intentionally ambiguous until an independent relation proves they are
        # the same physical wall.
        page.draw_line(
            fitz.Point(80.0, 250.0),
            fitz.Point(300.0, 250.0),
            width=1.0,
        )
        payload = bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()

    source = SourceVisibilityProducer(
        producer_method="live-gross-wall-zero-opening-coverage-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="live-gross-wall-zero-opening-coverage",
        source_bytes=payload,
        source_locator="memory://live-gross-wall-zero-opening-coverage.pdf",
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1", "2"),
    )
    assert wall_opening.status is EvidenceResolutionStatus.CORROBORATED
    page_two = next(trace for trace in wall_opening.wall_scopes if trace.page_id == "2")
    assert page_two.scope_complete
    assert page_two.wall_candidate_ids

    physical_void = compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )
    assert physical_void.status is EvidenceResolutionStatus.CORROBORATED

    composition = compose_live_gross_wall_geometry(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
        physical_void_composition=physical_void,
    )

    # The unopened page-two wall is now positively framed from complete source
    # truth and enters the same gross-wall target set. The page-one opening
    # fixture intentionally leaves some face-level wall identities ambiguous,
    # so the composition must keep the global coverage firewall rather than
    # pretending that every physical wall on every selected page is resolved.
    page_two_traces = tuple(
        trace for trace in composition.traces if trace.page_id == "2"
    )
    assert page_two_traces
    assert LIVE_GROSS_WALL_COVERAGE_INCOMPLETE in composition.reason_codes
    assert any(
        trace.physical_wall_id in composition.gross_selectors
        for trace in page_two_traces
    )


def test_live_gross_wall_public_interface_has_no_height_or_area_truth_inputs() -> None:
    import inspect

    signature = inspect.signature(compose_live_gross_wall_geometry)
    forbidden = {
        "wall_id",
        "wall_ids",
        "height",
        "height_m",
        "gross_area",
        "gross_area_m2",
        "polygon",
        "target_page_id",
        "elevation_page_id",
        "scale",
    }
    assert not (forbidden & set(signature.parameters))


def test_live_gross_wall_reuses_upstream_wall_authority_for_exact_decode_scope(
    monkeypatch,
) -> None:
    source, wall_opening, physical_void = _one_page_chain()

    def _unexpected_rebuild(*args, **kwargs):
        raise AssertionError("exact upstream wall authority should be reused")

    monkeypatch.setattr(
        "pb_live_gross_wall_geometry_composition."
        "PhysicalWallCandidateProducer.from_source_visibility_producer",
        _unexpected_rebuild,
    )

    composition = compose_live_gross_wall_geometry(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
        physical_void_composition=physical_void,
    )

    assert (
        composition.physical_wall_candidate_authority
        is wall_opening.physical_wall_candidate_authority
    )
    assert composition.traces
