from __future__ import annotations

from pb_live_gross_wall_geometry_composition import compose_live_gross_wall_geometry
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer
from tests.test_live_physical_opening_void_composition import _complete_void_pdf


def test_gross_wall_composition_addresses_the_shared_whole_wall_frame_not_opening_scoped_host_id() -> None:
    """Opening-scoped host IDs must never become downstream physical-wall identity.

    OpeningHostBindingRecord.host_wall_id is intentionally scoped to one exact
    opening/host proof. OpeningHostFrameEvidence.whole_wall_frame_id is the
    producer-owned shared wall identity that survives multiple openings on one
    physical wall. The live gross/net chain must therefore carry that shared
    identity forward before any Item21A publication can be enabled.
    """
    source = SourceVisibilityProducer(
        producer_method="net-wall-whole-wall-identity-validator",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="net-wall-whole-wall-identity",
        source_bytes=_complete_void_pdf(),
        source_locator="memory://net-wall-whole-wall-identity.pdf",
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
    assert len(physical_void.traces) == 1

    void_trace = physical_void.traces[0]
    void_selector = physical_void.void_selectors[void_trace.opening_identity_id]
    void_authority = physical_void.physical_opening_void_authorities[void_trace.page_id]
    void_result = void_authority.resolve(void_selector)
    assert void_result.status is EvidenceResolutionStatus.CORROBORATED
    assert void_result.record is not None
    void_record = void_result.record

    # These are deliberately different identity classes. The first is
    # opening-scoped lineage; the second is the producer-owned shared wall frame.
    assert void_record.host_wall_id
    assert void_record.wall_local_frame_id
    assert void_record.host_wall_id != void_record.wall_local_frame_id

    gross = compose_live_gross_wall_geometry(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
        physical_void_composition=physical_void,
    )

    assert len(gross.traces) == 1
    trace = gross.traces[0]

    # Future production must address gross/net wall truth by the shared whole-wall
    # identity, never by OpeningHostBindingRecord.host_wall_id.
    assert trace.physical_wall_id == void_record.wall_local_frame_id
    assert trace.physical_wall_id != void_record.host_wall_id
    assert void_record.wall_local_frame_id in gross.gross_selectors
    assert void_record.host_wall_id not in gross.gross_selectors
