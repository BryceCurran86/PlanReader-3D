from __future__ import annotations

import fitz

from pb_live_canonical_wall_composition import (
    LIVE_CANONICAL_WALL_BOUNDARY_CLEAN_PARTIAL,
    LIVE_CANONICAL_WALL_IDENTITY_CANDIDATE,
    LIVE_CANONICAL_WALL_PARTIAL,
    compose_live_canonical_walls,
)
from pb_live_wall_opening_authority_composition import (
    compose_live_wall_opening_authority,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    BOUNDARY_EVALUATION_EVALUATED,
    PhysicalWallCandidateSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from tests.test_live_canonical_room_composition import _source


def test_ambiguous_equivalence_preserves_candidate_wall_objects() -> None:
    source, wall_opening = _source(page_partitions=(True,))

    result = compose_live_canonical_walls(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )

    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.reason_codes[0] == LIVE_CANONICAL_WALL_PARTIAL
    assert LIVE_CANONICAL_WALL_IDENTITY_CANDIDATE in result.reason_codes
    assert result.source_pages == (1,)
    assert len(result.walls) == 5
    assert len(result.unresolved_wall_candidate_ids) == 5
    assert len(result.candidate_to_canonical_wall_id) == 5

    for wall in result.walls:
        assert wall.physical_wall_id is None
        assert wall.physical_identity_resolved is False
        assert wall.identity_status == "candidate_physical_equivalence_unresolved"
        assert wall.geometry_complete is True
        assert wall.metric_geometry_complete is False
        assert wall.quantity_complete is False
        assert len(wall.member_wall_candidate_ids) == 1
        assert len(wall.plan_members) == 1
        member_id = wall.member_wall_candidate_ids[0]
        assert result.candidate_to_canonical_wall_id[member_id] == wall.canonical_wall_id
        assert wall.plan_members[0].centerline_pts


def test_candidate_wall_payload_exposes_resolution_state() -> None:
    source, wall_opening = _source(page_partitions=(True,))
    result = compose_live_canonical_walls(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )

    payload = result.walls[0].to_dict()

    assert payload["identity_status"] == "candidate_physical_equivalence_unresolved"
    assert payload["physical_identity_resolved"] is False
    assert payload["geometry_complete"] is True
    assert payload["metric_geometry_complete"] is False
    assert payload["quantity_complete"] is False
    assert payload["plan_members"]

def _boundary_incomplete_source():
    doc = fitz.open()
    try:
        page = doc.new_page(width=520.0, height=400.0)

        # Positive floor-plan framing matches the already-frozen boundary
        # evaluation fixture. The frame is ownership evidence, not a wall.
        page.draw_rect(
            fitz.Rect(40.0, 30.0, 420.0, 330.0),
            color=(0, 0, 0),
            width=1.0,
        )
        page.insert_text(
            (80.0, 310.0),
            "GROUND FLOOR PLAN",
            fontsize=11.0,
        )

        # Two closed physical rooms wholly inside the framed plan.
        for first, second in (
            ((90.0, 80.0), (330.0, 80.0)),
            ((330.0, 80.0), (330.0, 230.0)),
            ((330.0, 230.0), (90.0, 230.0)),
            ((90.0, 230.0), (90.0, 80.0)),
            ((210.0, 80.0), (210.0, 230.0)),
        ):
            page.draw_line(
                fitz.Point(*first),
                fitz.Point(*second),
                color=(0, 0, 0),
                width=1.0,
            )

        # Reference-region line outside the authenticated plan frame. Its
        # free ends make the page-wide wall scope incomplete, while the plan
        # walls remain independently boundary-clean. This is the same generic
        # condition pinned by the merged #1300 boundary-evaluation tests.
        page.draw_line(
            fitz.Point(440.0, 60.0),
            fitz.Point(480.0, 60.0),
            color=(0, 0, 0),
            width=1.0,
        )
        payload = doc.tobytes()
    finally:
        doc.close()

    source = SourceVisibilityProducer(
        producer_method="boundary-clean-canonical-wall-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="boundary-clean-canonical-wall-doc",
        source_bytes=payload,
        source_locator="memory://boundary-clean-canonical-wall.pdf",
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    current = source.published_snapshot_for_revision(
        published.revision.revision_id
    )
    assert current is not None
    scope = wall_opening.physical_wall_candidate_authority.resolve_scope(
        PhysicalWallCandidateSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            page_id="1",
            decision_scope_id="wall-source:page-1",
        )
    )
    return source, wall_opening, scope


def test_incomplete_scope_preserves_only_boundary_clean_candidate_walls() -> None:
    source, wall_opening, scope = _boundary_incomplete_source()

    assert scope.status is EvidenceResolutionStatus.CORROBORATED
    assert scope.scope_complete is False
    assert scope.records
    evaluation = scope.boundary_evaluation
    assert evaluation is not None
    assert evaluation.status == BOUNDARY_EVALUATION_EVALUATED

    evaluated = set(evaluation.evaluated_wall_candidate_ids)
    tainted = set(evaluation.boundary_tainted_wall_candidate_ids)
    clean = evaluated - tainted
    assert clean
    assert tainted

    result = compose_live_canonical_walls(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )

    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert LIVE_CANONICAL_WALL_BOUNDARY_CLEAN_PARTIAL in result.reason_codes
    assert result.source_pages == (1,)

    emitted_member_ids = {
        member_id
        for wall in result.walls
        for member_id in wall.member_wall_candidate_ids
    }
    assert emitted_member_ids == clean
    assert emitted_member_ids.isdisjoint(tainted)
    assert set(result.candidate_to_canonical_wall_id) == clean

    # Candidate preservation is not a physical-identity or completeness
    # promotion. Every member of the incomplete scope remains unresolved.
    assert set(result.unresolved_wall_candidate_ids) == {
        record.wall_candidate_id for record in scope.records
    }
    assert all(wall.physical_identity_resolved is False for wall in result.walls)
    assert all(wall.physical_wall_id is None for wall in result.walls)
    assert all(
        wall.identity_status == "candidate_boundary_clean_scope_incomplete"
        for wall in result.walls
    )

