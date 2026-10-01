from __future__ import annotations

from pb_live_canonical_slab_projection import (
    LIVE_CANONICAL_SLAB_BOUNDARY_MISMATCH,
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


def _boundary(*, boundary_id: str = "footprint_p1") -> CandidateBoundary:
    return CandidateBoundary(
        boundary_id=boundary_id,
        polygon=[(0.0, 0.0), (8.0, 0.0), (8.0, 6.0), (0.0, 6.0)],
        area_m2=48.0,
        source_page=1,
        units_authoritative=True,
    )


def _resolved_slab() -> ResolvedSlabEntity:
    return ResolvedSlabEntity(
        slab_id="slab_p1_0",
        slab_type="reinforced_concrete",
        thickness_mm=150.0,
        reinforcement=[
            SlabReinforcement(
                reinforcement_type="T12@200-EW",
                specification="T12 @ 200 EW",
            )
        ],
        boundary_polygon=[
            (0.0, 0.0),
            (8.0, 0.0),
            (8.0, 6.0),
            (0.0, 6.0),
        ],
        area_m2=48.0,
        resolution_state=SlabResolutionState.RESOLVED.value,
        provenance={
            "annotation_raw_text": "150mm RC SLAB",
            "annotation_source_page": 1,
            "boundary_id": "footprint_p1",
        },
    )


def test_resolved_slab_projects_to_reusable_canonical_object() -> None:
    result = project_resolved_slab_entity(
        slab=_resolved_slab(),
        boundary=_boundary(),
    )

    assert result.reason_codes == (LIVE_CANONICAL_SLAB_RESOLVED,)
    assert result.object is not None
    slab = result.object
    assert slab.canonical_slab_id == "slab_p1_0"
    assert slab.slab_id == "slab_p1_0"
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
    assert payload["canonical_slab_id"] == "slab_p1_0"
    assert payload["geometry_complete"] is True
    assert payload["thickness_complete"] is True
    assert payload["coordinate_space"] == "metres"


def test_unresolved_slab_does_not_become_canonical_object() -> None:
    slab = _resolved_slab()
    slab.resolution_state = SlabResolutionState.UNRESOLVED_THICKNESS.value
    slab.thickness_mm = None

    result = project_resolved_slab_entity(
        slab=slab,
        boundary=_boundary(),
    )

    assert result.object is None
    assert result.reason_codes == (LIVE_CANONICAL_SLAB_UNAVAILABLE,)


def test_boundary_lineage_mismatch_fails_closed() -> None:
    result = project_resolved_slab_entity(
        slab=_resolved_slab(),
        boundary=_boundary(boundary_id="different-boundary"),
    )

    assert result.object is None
    assert result.reason_codes == (LIVE_CANONICAL_SLAB_BOUNDARY_MISMATCH,)
