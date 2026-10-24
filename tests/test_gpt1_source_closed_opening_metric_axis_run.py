"""Measured opening width/height in real m with full original area lineage."""
from dataclasses import replace

import pytest

from pb_live_opening_area_quantity_publication import (
    publish_live_opening_area_quantities,
)
from pb_live_opening_metric_dimensions_source_closed_export import (
    seal_live_opening_dimension_run,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_gpt1_live_original_opening_metric_axes import (
    _figured_with_explicit_axes, _source_frame_schedule,
)
from tests.test_live_opening_area_quantity_publication import _composition, _opening


@pytest.mark.parametrize("opening,expected", [
    (_figured_with_explicit_axes(), {"opening_width": 1.2, "opening_height": 1.81}),
    (_source_frame_schedule(), {"opening_width": 1.2, "opening_height": 1.8}),
])
def test_measured_original_opening_axes_seal_while_preserving_signed_area(opening, expected):
    source = _composition(opening)
    area_before = publish_live_opening_area_quantities(source)
    assert len(area_before) == 1
    result = seal_live_opening_dimension_run(
        source, workspace_id=7, project_id="synthetic-lot16",
    )
    assert len(result.quantities) == 2
    assert {row.family: row.value for row in result.quantities} == expected
    assert all(row.unit == "lm" and row.lineage_ok and not row.abstained
               for row in result.quantities)
    assert all(row.source_sha256 == opening.source_sha256.lower()
               for row in result.quantities)
    assert all(row.source_page == opening.page_id for row in result.quantities)
    assert publish_live_opening_area_quantities(source) == area_before
    assert not any(row.family == "opening_count" for row in result.quantities)


def test_opening_area_only_source_does_not_guess_dimensions_from_m2():
    result = seal_live_opening_dimension_run(
        _composition(_opening()), workspace_id=7, project_id="synthetic-lot16",
    )
    assert result.quantities == ()


def test_original_axis_seal_deterministic_and_has_no_customer_projection_grant():
    source = _composition(_source_frame_schedule())
    first = seal_live_opening_dimension_run(
        source, workspace_id=7, project_id="synthetic-lot16",
    )
    second = seal_live_opening_dimension_run(
        source, workspace_id=7, project_id="synthetic-lot16",
    )
    assert first.fingerprint == second.fingerprint
    assert len(first.quantities) == 2


def test_invalid_original_area_member_cannot_launder_a_metric_axis():
    legitimate = _source_frame_schedule()
    foreign = replace(
        legitimate, area_m2=6.2,
    )
    source = _composition(foreign)
    assert seal_live_opening_dimension_run(
        source, workspace_id=7, project_id="synthetic-lot16",
    ).quantities == ()


def test_duplicate_original_opening_identity_prevents_source_run():
    original = _source_frame_schedule()
    with pytest.raises((SourceClosedRunConflictError, ValueError)):
        seal_live_opening_dimension_run(
            _composition(original, original),
            workspace_id=7, project_id="synthetic-lot16",
        )
