from __future__ import annotations

from pb_gross_wall_geometry_authority import GROSS_WALL_GEOMETRY_HEIGHT_UNRESOLVED
from pb_live_gross_wall_geometry_composition import (
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
