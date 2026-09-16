"""Item 4B — physical-wall equivalence prerequisite for host authority.

TEST-ONLY / EXPECTED-RED / DO NOT MERGE.

The proposition under test is upstream of opening-host binding. A complete
source-backed WallCandidate universe is not enough when every candidate is
individually addressable but the producer-owned physical equivalence resolver
still says its relationship to every other relevant representation is
AMBIGUOUS_PHYSICAL_EQUIVALENCE.

This validator deliberately does NOT define host binding, opening deductions,
physical void, net wall area, commercial publication or JobHub behavior.
"""
from __future__ import annotations

import fitz
import pytest

from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PHYSICAL_WALL_CANDIDATE_AUTHORITY_SCHEMA_VERSION,
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_physical_wall_identity import (
    PhysicalEquivalenceClass,
    PhysicalWallIdentity,
    classify_physical_wall_pair,
    resolve_physical_wall_equivalence,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_room_topology_contracts import JunctionType, WallCandidate


BASE_SHA = "76c7882b1c4b28764d1e6a6f467d72bb276c2e01"
EXPECTED_RED = pytest.mark.xfail(
    PHYSICAL_WALL_CANDIDATE_AUTHORITY_SCHEMA_VERSION == "1.0.0",
    strict=True,
    reason="Item 4B source-backed physical-wall equivalence prerequisite is absent",
)


def _wall(
    wall_id: str,
    points: tuple[tuple[float, float], tuple[float, float]],
    *,
    face_id: str,
    end_nodes: tuple[str, str],
) -> WallCandidate:
    return WallCandidate(
        candidate_id=wall_id,
        viewport_id="wall-source:page-1",
        representation="single_line",
        centerline_pts=points,
        face_a_segment_ids=(face_id,),
        face_b_segment_ids=None,
        is_curved=False,
        curve_control_pts=None,
        thickness_m=None,
        thickness_authority=MeasurementAuthorityType.PROVISIONAL,
        length_m=None,
        end_node_ids=end_nodes,
        junction_types=(JunctionType.ENDPOINT, JunctionType.ENDPOINT),
        interior_exterior="unresolved",
        level_id=None,
        confidence=0.5,
    )


def _identity(
    wall: WallCandidate,
    *,
    ancestry: tuple[str, ...],
    path: tuple[tuple[float, float], ...] | None = None,
) -> PhysicalWallIdentity:
    return PhysicalWallIdentity(
        wall_candidate_id=wall.candidate_id,
        viewport_id=wall.viewport_id,
        candidate_identity_id=f"candidate:{wall.candidate_id}",
        path_fingerprint=path or tuple(wall.centerline_pts),
        source_primitive_ids=ancestry,
        edge_ids=tuple(wall.face_a_segment_ids),
        status=EvidenceResolutionStatus.CORROBORATED,
    )


def _wall_band_pdf() -> bytes:
    """One native double-face wall band interrupted by an opening with jambs."""
    doc = fitz.open()
    try:
        page = doc.new_page(width=320.0, height=240.0)
        shape = page.new_shape()
        for start, end in (
            ((20.0, 80.0), (120.0, 80.0)),
            ((160.0, 80.0), (280.0, 80.0)),
            ((20.0, 100.0), (120.0, 100.0)),
            ((160.0, 100.0), (280.0, 100.0)),
            ((120.0, 80.0), (120.0, 100.0)),
            ((160.0, 80.0), (160.0, 100.0)),
        ):
            shape.draw_line(fitz.Point(*start), fitz.Point(*end))
        shape.finish(width=1.0)
        shape.commit()
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _real_scope():
    producer = SourceVisibilityProducer(
        producer_method="physical-wall-equivalence-host-prerequisite-v1",
        producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="doc-wall-equivalence-host-prerequisite-v1",
        source_bytes=_wall_band_pdf(),
        source_locator="memory://wall-equivalence-host-prerequisite-v1.pdf",
    )
    authority = PhysicalWallCandidateProducer.from_source_visibility_producer(producer).authority()
    selector = PhysicalWallCandidateSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        decision_scope_id="wall-source:page-1",
    )
    result = authority.resolve_scope(selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.scope_complete is True
    assert result.equivalence is not None
    return result


def _horizontal_ids(scope) -> tuple[str, ...]:
    result = []
    for record in scope.records:
        points = tuple(record.wall_candidate.centerline_pts)
        if len(points) < 2:
            continue
        if abs(float(points[0][1]) - float(points[-1][1])) <= 1e-6:
            result.append(record.wall_candidate_id)
    assert len(result) == 4
    return tuple(sorted(result))


def test_current_base_is_exact_item_4a_main() -> None:
    assert BASE_SHA == "76c7882b1c4b28764d1e6a6f467d72bb276c2e01"


def test_same_path_different_provenance_stays_ambiguous() -> None:
    left_wall = _wall("same-path-a", ((0.0, 0.0), (100.0, 0.0)), face_id="a", end_nodes=("n0", "n1"))
    right_wall = _wall("same-path-b", ((0.0, 0.0), (100.0, 0.0)), face_id="b", end_nodes=("n0", "n1"))
    left = _identity(left_wall, ancestry=("source:a",))
    right = _identity(right_wall, ancestry=("source:b",))
    assert classify_physical_wall_pair(left, right) is PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE


def test_reversed_duplicate_same_provenance_is_positive_same() -> None:
    a = _wall("reverse-a", ((0.0, 0.0), (100.0, 0.0)), face_id="a", end_nodes=("n0", "n1"))
    b = _wall("reverse-b", ((100.0, 0.0), (0.0, 0.0)), face_id="a", end_nodes=("n1", "n0"))
    canonical_path = ((0.0, 0.0), (100.0, 0.0))
    left = _identity(a, ancestry=("source:shared",), path=canonical_path)
    right = _identity(b, ancestry=("source:shared",), path=canonical_path)
    assert classify_physical_wall_pair(left, right) is PhysicalEquivalenceClass.SAME_PHYSICAL_WALL


def test_collinear_split_with_independent_provenance_is_not_silently_same() -> None:
    a = _wall("split-a", ((0.0, 0.0), (50.0, 0.0)), face_id="a", end_nodes=("n0", "n1"))
    b = _wall("split-b", ((50.0, 0.0), (100.0, 0.0)), face_id="b", end_nodes=("n1", "n2"))
    left = _identity(a, ancestry=("source:a",))
    right = _identity(b, ancestry=("source:b",))
    resolution = resolve_physical_wall_equivalence(
        (left, right), walls_by_id={a.candidate_id: a, b.candidate_id: b}
    )
    pair = resolution.pair_classifications[0]
    assert pair[2] != PhysicalEquivalenceClass.SAME_PHYSICAL_WALL.value


def test_candidate_identity_is_not_physical_equivalence_proof() -> None:
    wall = _wall("address-only", ((0.0, 0.0), (100.0, 0.0)), face_id="a", end_nodes=("n0", "n1"))
    identity = _identity(wall, ancestry=("source:a",))
    assert identity.usable is True
    assert identity.candidate_identity_id
    assert identity.physical_identity_id == identity.candidate_identity_id


@EXPECTED_RED
def test_real_source_wall_band_relevant_representations_are_not_ambiguous() -> None:
    """Positive prerequisite consumed by frozen host-binding V3.

    The source-backed producer must resolve the four horizontal wall-band
    representations sufficiently that none is globally blocked as ambiguous.
    The validator does not prescribe SAME versus DISTINCT; it only forbids the
    current state where every relevant representation is ambiguous.
    """
    scope = _real_scope()
    relevant = set(_horizontal_ids(scope))
    ambiguous = relevant & set(scope.equivalence.ambiguous_wall_ids)
    assert not ambiguous, (
        f"host-relevant wall representations remain ambiguous: {sorted(ambiguous)}; "
        f"equivalence={scope.equivalence!r}"
    )
    assert relevant <= set(scope.equivalence.representative_wall_ids) | set(scope.equivalence.same_wall_ids)


@EXPECTED_RED
def test_real_source_wall_band_has_no_ambiguous_pair_touching_relevant_representation() -> None:
    scope = _real_scope()
    relevant = set(_horizontal_ids(scope))
    ambiguous_pairs = [
        (left, right)
        for left, right, classification in scope.equivalence.pair_classifications
        if classification == PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE.value
        and (left in relevant or right in relevant)
    ]
    assert ambiguous_pairs == []


@EXPECTED_RED
def test_unrelated_source_candidate_cannot_poison_resolved_relevant_component() -> None:
    """Global pair enumeration must not turn every independent wall into one ambiguous component.

    This is a topology/equivalence requirement, not permission to ignore a
    genuinely competing duplicate. Same-path and unresolved split attacks above
    remain fail-closed.
    """
    scope = _real_scope()
    relevant = set(_horizontal_ids(scope))
    assert not (relevant & set(scope.equivalence.ambiguous_wall_ids))
    assert len(scope.equivalence.representative_wall_ids) >= 2
