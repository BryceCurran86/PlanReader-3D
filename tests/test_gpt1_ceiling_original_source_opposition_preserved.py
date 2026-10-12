"""Q02 original documented ceiling metric and source-polygon opposition cases.

Preserves independent tests from old #2280 without reverting newer canonical
ceiling and authenticated source exporters already on live main.
"""
from __future__ import annotations

from dataclasses import replace
from copy import copy
import pytest

import pb_live_ceiling_area_source_closed_export as ceiling_export
from pb_live_ceiling_area_quantity_publication import publish_live_ceiling_area_quantities
from tests.test_live_ceiling_area_quantity_publication import (
    _result, _ceiling, _shadow_quantity,
)

def test_sealed_ceiling_source_polygon_must_be_complete_finite_and_non_degenerate():
    from pb_source_closed_run_export import SourceClosedRunConflictError
    import pytest

    for bad_polygon in (
        (),
        ((1., 1.), (1., 2.), (1., 3.)),
        ((0., 0.), (float("nan"), 1.), (2., 2.)),
        ((0., 0.), (float("inf"), 1.), (2., 2.)),
    ):
        forged_ceiling = replace(_ceiling(), polygon_pdf_pts=bad_polygon)
        with pytest.raises(SourceClosedRunConflictError):
            ceiling_export.build_live_ceiling_area_source_traces(
                _result(ceiling=forged_ceiling),
                workspace_id=1, project_id="original-source",
            )
    assert len(ceiling_export.build_live_ceiling_area_source_traces(
        _result(), workspace_id=1, project_id="original-source",
    )) == 1


def test_sealed_ceiling_cannot_deduplicate_corrupted_source_receipts():
    from pb_source_closed_run_export import SourceClosedRunConflictError
    import pytest

    for evidence in (
        ("ev-dim-h", "ev-dim-h", "ev-dim-v", "ev-finish"),
        ("ev-dim-h", "ev-dim-v", "   ", "ev-finish"),
    ):
        forged = replace(_ceiling(), evidence_ids=evidence)
        # Invalid original receipts are already quarantined by Q02 quantity
        # publication, leaving no source-supported area to be sealed.
        assert ceiling_export.build_live_ceiling_area_source_traces(
            _result(ceiling=forged),
            workspace_id=1, project_id="original-source",
        ) == {}


def test_ceiling_area_rejects_missing_duplicate_or_blank_original_source_receipts():
    shadow = _shadow_quantity()
    ceiling = _ceiling()
    for bad_receipts in (
        ("ev-dim-h", "ev-dim-h", "ev-finish"),
        ("ev-dim-h", "   ", "ev-finish"),
        ("ev-dim-h", "", "ev-finish"),
        (),
    ):
        bad_source = copy(shadow)
        object.__setattr__(bad_source, "evidence_ids", bad_receipts)
        assert publish_live_ceiling_area_quantities(_result(shadow=bad_source)) == ()
        bad_ceiling = replace(ceiling, evidence_ids=bad_receipts)
        assert publish_live_ceiling_area_quantities(_result(ceiling=bad_ceiling)) == ()
    assert len(publish_live_ceiling_area_quantities(_result())) == 1


def test_ceiling_area_rejects_foreign_original_source_document_or_room_snapshot():
    shadow = _shadow_quantity()
    for key, value in (
        ("document_id", "foreign-document"),
        ("room_snapshot_id", "foreign-room-snapshot"),
    ):
        foreign = replace(
            shadow, metadata={**dict(shadow.metadata), key: value},
        )
        assert publish_live_ceiling_area_quantities(_result(shadow=foreign)) == ()

    same_source = replace(
        shadow,
        metadata={
            **dict(shadow.metadata),
            "document_id": _ceiling().document_id,
            "room_snapshot_id": _ceiling().snapshot_id,
        },
    )
    assert len(publish_live_ceiling_area_quantities(_result(shadow=same_source))) == 1


def test_ceiling_documented_metric_area_rejects_competing_dimension_systems():
    # A third independent figured line does not validate the other two:
    # original-source ownership of one orthogonal pair is required.
    for bad_ids in (
        ("dim-h", "dim-v", "unrelated-horizontal"),
        ("dim-h", "dim-v", "dim-h"),
        ("dim-h", "dim-v", ""),
        ("dim-h", "dim-v", "unrelated-horizontal", "other-vertical"),
        ("dim-h",),
        (),
    ):
        candidate = replace(_ceiling(), figured_dimension_ids=bad_ids)
        assert publish_live_ceiling_area_quantities(_result(ceiling=candidate)) == ()
    assert len(publish_live_ceiling_area_quantities(_result())) == 1


@pytest.mark.parametrize("bad_source", (
    ("value", True), ("value", False), ("value", "13.270425"),
    ("confidence", True), ("confidence", float("nan")),
    ("confidence", float("inf")), ("confidence", -0.01),
    ("confidence", 1.01),
))
def test_canonical_ceiling_rejects_forged_untyped_metric_or_confidence(bad_source):
    from copy import copy
    field, value = bad_source
    source = copy(_shadow_quantity())
    object.__setattr__(source, field, value)
    assert publish_live_ceiling_area_quantities(_result(shadow=source)) == ()


@pytest.mark.parametrize("bad_area", (True, False, "13.270425", None))
def test_canonical_ceiling_rejects_boolean_or_nonmetric_source_area(bad_area):
    assert publish_live_ceiling_area_quantities(
        _result(ceiling=replace(_ceiling(), area_m2=bad_area))
    ) == ()



@pytest.mark.parametrize("bad_ring", (
    ((0.0, 0.0), (1.0, 1.0), (2.0, 2.0)),
    ((0.0, 0.0), (2.0, 2.0), (0.0, 2.0), (2.0, 0.0)),
))
def test_source_closed_ceiling_refuses_zero_area_ring_even_with_nonzero_bbox(bad_ring):
    from pb_source_closed_run_export import SourceClosedRunConflictError

    altered = replace(_ceiling(), polygon_pdf_pts=bad_ring)
    # Canonical object carried a FIRM metric; its source polygon alone cannot
    # validate the geometry. Only the final source-closed exporter can reject
    # a valid-looking bounding box with no closed physical face.
    assert len(publish_live_ceiling_area_quantities(_result(ceiling=altered))) == 1
    with pytest.raises(SourceClosedRunConflictError, match="degenerate"):
        ceiling_export.build_live_ceiling_area_source_traces(
            _result(ceiling=altered), workspace_id=1, project_id="original-source",
        )


def test_source_closed_ceiling_keeps_original_non_degenerate_page_ring():
    traces = ceiling_export.build_live_ceiling_area_source_traces(
        _result(), workspace_id=1, project_id="original-source",
    )
    assert len(traces) == 1
    assert next(iter(traces.values())).source_bbox == (0.0, 0.0, 10.0, 10.0)
