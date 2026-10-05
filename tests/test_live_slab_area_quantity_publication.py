from __future__ import annotations

from dataclasses import replace

from pb_live_canonical_coverage_registry import collect_live_canonical_coverage
from pb_live_canonical_slab_projection import project_resolved_slab_entity
from pb_live_slab_area_quantity_publication import (
    LIVE_SLAB_AREA_QUANTITY_AUTHORITY,
    publish_live_slab_area_quantity,
)
from pb_takeoff_coverage_audit_adapter import build_runtime_coverage_publication
from tests.test_live_canonical_slab_projection import (
    _boundary,
    _lineage,
    _resolved_slab,
)


def test_resolved_canonical_slab_publishes_identity_bound_area_quantity():
    result = project_resolved_slab_entity(
        slab=_resolved_slab(),
        boundary=_boundary(),
        **_lineage(),
    )
    assert result.object is not None
    quantity = publish_live_slab_area_quantity(result.object)
    assert quantity is not None
    assert quantity.family == "slab_area"
    assert quantity.value == 48.0
    assert quantity.unit == "m2"
    assert quantity.input_entity_ids == (result.object.physical_slab_id,)
    assert quantity.authority == LIVE_SLAB_AREA_QUANTITY_AUTHORITY
    assert quantity.status == "corroborated"
    assert result.object.boundary_id in quantity.evidence_ids


def test_slab_area_quantity_advances_floor_slab_family_to_quantified_only():
    result = project_resolved_slab_entity(
        slab=_resolved_slab(),
        boundary=_boundary(),
        **_lineage(),
    )
    assert result.object is not None
    quantity = publish_live_slab_area_quantity(result.object)
    assert quantity is not None

    summaries, gaps = collect_live_canonical_coverage(
        objects=(result.object,),
        quantities=(quantity,),
        registry_run_scope="slab-area-live",
    )
    report = build_runtime_coverage_publication(
        summaries,
        family_gaps=gaps,
    )
    counts = report["family_reports"]["floor_slab"]["stage_counts"]
    assert counts == {
        "DETECTED": 1,
        "AUTHENTICATED": 1,
        "CANONICALIZED": 1,
        "QUANTIFIED": 1,
        "PUBLISHED": 0,
    }


def test_slab_area_publication_fails_closed_if_boundary_provenance_is_damaged():
    result = project_resolved_slab_entity(
        slab=_resolved_slab(),
        boundary=_boundary(),
        **_lineage(),
    )
    assert result.object is not None
    damaged = replace(
        result.object,
        provenance={
            **dict(result.object.provenance),
            "boundary_id": "different-boundary",
        },
    )
    assert publish_live_slab_area_quantity(damaged) is None
