"""Real-source integration check for #381 equivalence remediation.

The real positive host fixture contains four different structural roles around
one opening (left/right pieces on two wall faces). Upstream physical-wall
pairwise equivalence may remain ambiguous between different roles; host binding
must never reinterpret that ambiguity as SAME or DISTINCT. The authority-relevant
check is that no role contains competing representations that would require an
unproven choice. If a duplicate/split representation appears within one role,
production must consume upstream SAME/DISTINCT/AMBIGUOUS there.
"""
from __future__ import annotations

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
import pb_opening_host_binding_authority as host
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, PhysicalOpeningAuthority
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _pdf_bytes() -> bytes:
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


def test_real_host_fixture_has_no_unresolved_choice_within_one_host_role() -> None:
    source = SourceVisibilityProducer(
        producer_method="host-equivalence-source-integration-v3",
        producer_version="2",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="doc-host-equivalence-source-v3",
        source_bytes=_pdf_bytes(),
        source_locator="memory://host-equivalence-source-v3.pdf",
    )
    visibility = source.authority()
    physical = PhysicalOpeningAuthority(visibility)

    opening = None
    for observation_id in published.visible_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = physical.prove_existence(selector)
        if result.proposition == PHYSICAL_OPENING_EXISTS and result.existence_record is not None:
            opening = result.existence_record
            break
    assert opening is not None

    wall_authority = PhysicalWallCandidateProducer.from_source_visibility_producer(source).authority()
    wall_scope = wall_authority.resolve_scope(
        PhysicalWallCandidateSelector(
            document_id=opening.document_id,
            revision_id=opening.revision_id,
            source_sha256=opening.source_sha256,
            snapshot_id=opening.snapshot_id,
            page_id=opening.page_id,
            decision_scope_id=f"wall-source:page-{opening.page_id}",
        )
    )
    assert wall_scope.status is EvidenceResolutionStatus.CORROBORATED
    assert wall_scope.scope_complete is True
    assert wall_scope.equivalence is not None

    geometry = host._opening_geometry(physical, opening)
    assert geometry is not None
    edge_tol = max(0.5, min(2.0, geometry.length * 0.02))
    axis_tol = max(0.5, geometry.thickness * 0.05)
    left_raw = []
    right_raw = []
    for record in wall_scope.records:
        data = host._candidate_axis_data(record, geometry)
        if data is None:
            continue
        along_min, along_max, offset = data
        if along_min < -edge_tol and abs(along_max) <= edge_tol:
            left_raw.append((offset, record))
        if along_max > geometry.length + edge_tol and abs(along_min - geometry.length) <= edge_tol:
            right_raw.append((offset, record))

    left_clusters = host._clusters_by_offset(left_raw, axis_tol)
    right_clusters = host._clusters_by_offset(right_raw, axis_tol)
    assert left_clusters and right_clusters

    # The reviewed positive fixture has exactly one representation for each
    # host role. Therefore host binding makes no SAME/DISTINCT choice for the
    # globally ambiguous relationships between different structural roles.
    assert all(len(cluster) == 1 for cluster in left_clusters)
    assert all(len(cluster) == 1 for cluster in right_clusters)

    resolution = host._resolve_host_bands(
        wall_scope.records,
        geometry,
        wall_scope.equivalence,
    )
    assert resolution.status is EvidenceResolutionStatus.CORROBORATED
    assert resolution.reason_codes == ()
    assert len(resolution.bands) == 1
