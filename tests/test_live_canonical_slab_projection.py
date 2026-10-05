from __future__ import annotations

from pb_live_canonical_slab_projection import (
    LIVE_CANONICAL_SLAB_BOUNDARY_MISMATCH,
    LIVE_CANONICAL_SLAB_LINEAGE_UNAVAILABLE,
    LIVE_CANONICAL_SLAB_RESOLVED,
    LIVE_CANONICAL_SLAB_UNAVAILABLE,
    project_resolved_slab_entity,
)
from pb_slab_classification_geometry import (
    CandidateBoundary,
    ResolvedSlabEntity,
    SlabReinforcement,
    SlabResolutionState,
)


def _lineage(**changes) -> dict[str, str]:
    base = {
        "document_id": "doc-slab",
        "revision_id": "rev-1",
        "source_sha256": "a" * 64,
        "snapshot_id": "snap-1",
    }
    base.update(changes)
    return base


def _boundary(
    *,
    boundary_id: str = "footprint_p1",
    polygon=None,
    area_m2: float = 48.0,
    source_page: int = 1,
) -> CandidateBoundary:
    return CandidateBoundary(
        boundary_id=boundary_id,
        polygon=polygon
        or [(0.0, 0.0), (8.0, 0.0), (8.0, 6.0), (0.0, 6.0)],
        area_m2=area_m2,
        source_page=source_page,
        units_authoritative=True,
    )


def _resolved_slab(
    *,
    slab_id: str = "slab_p1_0",
    polygon=None,
    area_m2: float = 48.0,
    slab_type: str = "reinforced_concrete",
    source_page: int = 1,
) -> ResolvedSlabEntity:
    return ResolvedSlabEntity(
        slab_id=slab_id,
        slab_type=slab_type,
        thickness_mm=150.0,
        reinforcement=[
            SlabReinforcement(
                reinforcement_type="T12@200-EW",
                specification="T12 @ 200 EW",
            )
        ],
        boundary_polygon=polygon
        or [
            (0.0, 0.0),
            (8.0, 0.0),
            (8.0, 6.0),
            (0.0, 6.0),
        ],
        area_m2=area_m2,
        resolution_state=SlabResolutionState.RESOLVED.value,
        provenance={
            "annotation_raw_text": "150mm RC SLAB",
            "annotation_source_page": source_page,
            "boundary_id": "footprint_p1",
        },
    )


def test_resolved_slab_projects_to_reusable_canonical_object() -> None:
    result = project_resolved_slab_entity(
        slab=_resolved_slab(),
        boundary=_boundary(),
        **_lineage(),
    )

    assert result.reason_codes == (LIVE_CANONICAL_SLAB_RESOLVED,)
    assert result.object is not None
    slab = result.object
    assert slab.canonical_slab_id == slab.physical_slab_id
    assert slab.canonical_slab_id != slab.slab_id
    assert slab.slab_id == "slab_p1_0"
    assert slab.document_id == "doc-slab"
    assert slab.revision_id == "rev-1"
    assert slab.source_sha256 == "a" * 64
    assert slab.snapshot_id == "snap-1"
    assert slab.source_page == 1
    assert slab.boundary_id == "footprint_p1"
    assert slab.area_m2 == 48.0
    assert slab.thickness_m == 0.15
    assert slab.polygon_m == (
        (0.0, 0.0),
        (8.0, 0.0),
        (8.0, 6.0),
        (0.0, 6.0),
    )
    assert slab.reinforcement[0]["reinforcement_type"] == "T12@200-EW"
    payload = slab.to_dict()
    assert payload["canonical_slab_id"] == slab.physical_slab_id
    assert payload["physical_slab_id"] == slab.physical_slab_id
    assert payload["geometry_complete"] is True
    assert payload["thickness_complete"] is True
    assert payload["coordinate_space"] == "metres"


def test_missing_source_lineage_fails_closed() -> None:
    result = project_resolved_slab_entity(
        slab=_resolved_slab(),
        boundary=_boundary(),
    )

    assert result.object is None
    assert result.reason_codes == (LIVE_CANONICAL_SLAB_LINEAGE_UNAVAILABLE,)


def test_physical_slab_identity_ignores_resolver_id_revision_sha_and_polygon_order() -> None:
    first = project_resolved_slab_entity(
        slab=_resolved_slab(),
        boundary=_boundary(),
        **_lineage(),
    )
    reordered = [
        (8.0, 6.0),
        (8.0, 0.0),
        (0.0, 0.0),
        (0.0, 6.0),
    ]
    second = project_resolved_slab_entity(
        slab=_resolved_slab(
            slab_id="slab_reindexed",
            polygon=reordered,
            slab_type="concrete",
        ),
        boundary=_boundary(polygon=reordered),
        **_lineage(
            revision_id="rev-2",
            source_sha256="b" * 64,
            snapshot_id="snap-2",
        ),
    )

    assert first.object is not None
    assert second.object is not None
    assert first.object.slab_id != second.object.slab_id
    assert first.object.slab_type != second.object.slab_type
    assert first.object.source_sha256 != second.object.source_sha256
    assert first.object.physical_slab_id == second.object.physical_slab_id
    assert first.object.canonical_slab_id == second.object.canonical_slab_id
    # Stored polygon ordering remains source-preserving even though identity is normalized.
    assert second.object.polygon_m == tuple(reordered)


def test_distinct_authoritative_polygon_gets_distinct_physical_slab_identity() -> None:
    first = project_resolved_slab_entity(
        slab=_resolved_slab(),
        boundary=_boundary(),
        **_lineage(),
    )
    larger = [(0.0, 0.0), (9.0, 0.0), (9.0, 6.0), (0.0, 6.0)]
    second = project_resolved_slab_entity(
        slab=_resolved_slab(polygon=larger, area_m2=54.0),
        boundary=_boundary(polygon=larger, area_m2=54.0),
        **_lineage(),
    )

    assert first.object is not None
    assert second.object is not None
    assert first.object.physical_slab_id != second.object.physical_slab_id


def test_identical_polygon_on_different_source_page_is_distinct_physical_slab() -> None:
    first = project_resolved_slab_entity(
        slab=_resolved_slab(source_page=1),
        boundary=_boundary(source_page=1),
        **_lineage(),
    )
    second = project_resolved_slab_entity(
        slab=_resolved_slab(slab_id="slab_p2_0", source_page=2),
        boundary=_boundary(source_page=2),
        **_lineage(),
    )

    assert first.object is not None
    assert second.object is not None
    assert first.object.polygon_m == second.object.polygon_m
    assert first.object.physical_slab_id != second.object.physical_slab_id


def test_unresolved_slab_does_not_become_canonical_object() -> None:
    slab = _resolved_slab()
    slab.resolution_state = SlabResolutionState.UNRESOLVED_THICKNESS.value
    slab.thickness_mm = None

    result = project_resolved_slab_entity(
        slab=slab,
        boundary=_boundary(),
        **_lineage(),
    )

    assert result.object is None
    assert result.reason_codes == (LIVE_CANONICAL_SLAB_UNAVAILABLE,)


def test_boundary_lineage_mismatch_fails_closed() -> None:
    result = project_resolved_slab_entity(
        slab=_resolved_slab(),
        boundary=_boundary(boundary_id="different-boundary"),
        **_lineage(),
    )

    assert result.object is None
    assert result.reason_codes == (LIVE_CANONICAL_SLAB_BOUNDARY_MISMATCH,)
