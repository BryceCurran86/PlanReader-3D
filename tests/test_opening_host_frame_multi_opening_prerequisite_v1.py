"""Diagnostic prerequisite check for a shared host-wall frame.

TEST-ONLY / SELF-AUTHORED / NOT FROZEN / DO NOT MERGE.

A wall with two physical openings is the minimum case that distinguishes a true
whole-wall coordinate frame from an opening-local frame. This test intentionally
uses only the already-merged opening, wall-candidate and host-binding authorities.
It does not manufacture a whole-wall identity or baseline.
"""
from __future__ import annotations

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_host_binding_authority import (
    OpeningHostBindingProducer,
    OpeningHostWallUniverseProducer,
    OpeningHostWallUniverseSelector,
)
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, PhysicalOpeningAuthority
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _two_opening_pdf() -> bytes:
    """One straight two-face wall with two 40pt openings."""
    doc = fitz.open()
    try:
        page = doc.new_page(width=420.0, height=320.0)
        shape = page.new_shape()
        segments = [
            # top face: left / between openings / right
            ((20.0, 80.0), (100.0, 80.0)),
            ((140.0, 80.0), (220.0, 80.0)),
            ((260.0, 80.0), (340.0, 80.0)),
            # bottom face
            ((20.0, 100.0), (100.0, 100.0)),
            ((140.0, 100.0), (220.0, 100.0)),
            ((260.0, 100.0), (340.0, 100.0)),
            # opening jambs
            ((100.0, 80.0), (100.0, 100.0)),
            ((140.0, 80.0), (140.0, 100.0)),
            ((220.0, 80.0), (220.0, 100.0)),
            ((260.0, 80.0), (260.0, 100.0)),
        ]
        for start, end in segments:
            shape.draw_line(fitz.Point(*start), fitz.Point(*end))
        shape.finish(width=1.0)
        shape.commit()
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def test_two_openings_expose_need_for_one_whole_wall_baseline() -> None:
    source = SourceVisibilityProducer(
        producer_method="opening-host-frame-multi-opening-diagnostic",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="opening-host-frame-two-openings",
        source_bytes=_two_opening_pdf(),
        source_locator="memory://opening-host-frame-two-openings.pdf",
    )
    physical = PhysicalOpeningAuthority(source.authority())

    openings: dict[str, tuple[ObservationSelector, object]] = {}
    for observation_id in published.visible_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = physical.prove_existence(selector)
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.proposition == PHYSICAL_OPENING_EXISTS
            and result.existence_record is not None
        ):
            openings.setdefault(result.existence_record.record_id, (selector, result.existence_record))

    # A reusable host-frame prerequisite must first survive the ordinary case of
    # two physical openings interrupting one wall.
    assert len(openings) == 2

    wall_authority = PhysicalWallCandidateProducer.from_source_visibility_producer(source).authority()
    first_record = next(iter(openings.values()))[1]
    page_id = first_record.page_id
    decision_scope_id = f"wall-source:page-{page_id}"
    universe_authority = OpeningHostWallUniverseProducer.from_physical_wall_candidate_authority(
        wall_authority
    ).authority()
    universe_selector = OpeningHostWallUniverseSelector(
        document_id=first_record.document_id,
        revision_id=first_record.revision_id,
        source_sha256=first_record.source_sha256,
        snapshot_id=first_record.snapshot_id,
        page_id=page_id,
        decision_scope_id=decision_scope_id,
    )
    universe = universe_authority.resolve_scope(universe_selector)
    assert universe.status is EvidenceResolutionStatus.CORROBORATED
    assert universe.scope_complete is True

    binding_producer = OpeningHostBindingProducer.from_authorities(
        physical_opening_authority=physical,
        host_wall_universe_authority=universe_authority,
    )
    bindings = []
    for selector, _record in openings.values():
        result = binding_producer.publish(
            opening_left_selector=selector,
            opening_right_selector=selector,
            host_universe_selector=universe_selector,
        )
        assert result.status is EvidenceResolutionStatus.CORROBORATED
        assert result.record is not None
        bindings.append(result.record)
    assert len(bindings) == 2

    wall_scope = wall_authority.resolve_scope(
        PhysicalWallCandidateSelector(
            document_id=first_record.document_id,
            revision_id=first_record.revision_id,
            source_sha256=first_record.source_sha256,
            snapshot_id=first_record.snapshot_id,
            page_id=page_id,
            decision_scope_id=decision_scope_id,
        )
    )
    assert wall_scope.status is EvidenceResolutionStatus.CORROBORATED
    assert wall_scope.scope_complete is True
    records_by_id = {record.wall_candidate_id: record for record in wall_scope.records}

    local_extents = []
    for binding in bindings:
        xs = [
            float(point[0])
            for member_id in binding.member_wall_candidate_ids
            for point in records_by_id[member_id].wall_candidate.centerline_pts
        ]
        local_extents.append((min(xs), max(xs)))

    # The two opening-scoped host bindings legitimately select different local
    # pieces. Therefore min/max(binding members) cannot itself be the common
    # whole-wall frame anchor required by Physical Opening Void V2.
    assert len(set(local_extents)) == 2
