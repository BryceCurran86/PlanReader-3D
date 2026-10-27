"""Source-neutral adversarial finish-zone coverage; never commercial authority."""
from dataclasses import replace

import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_gpt1_figured_chain_metric_shadow import FiguredPolygonMetricShadow
from pb_gpt1_figured_finish_zones_shadow import (
    OriginalFiguredFinishZone,
    measure_figured_finish_zones_shadow,
)

SHA = "a" * 64
PARENT = ((0, 0), (10, 0), (10, 5), (0, 5))


def _metric(area: float) -> FiguredPolygonMetricShadow:
    return FiguredPolygonMetricShadow(
        Status.CANDIDATE, ("synthetic_figured_axes",), area,
        ((0, 0), (10000, 0), (10000, 5000), (0, 5000)),
        ("source_dimension_axis_1", "source_dimension_axis_2"), (),
        SHA, "rev", "7", "one-original-room",
    )


def _zone(name: str, ring, *, area: float = 25.0) -> OriginalFiguredFinishZone:
    return OriginalFiguredFinishZone(
        name, tuple(ring), _metric(area),
        "FT2" if name == "left" else "FT3",
        "tile", "original_definition_" + name,
        "original_painted_occurrence_" + name,
        ("original_source_word_" + name,),
        "11", "exact_original_registration_" + name,
    )


@pytest.mark.parametrize("require_complete", (False, True))
@pytest.mark.parametrize("reverse", (False, True))
def test_figured_area_total_cannot_hide_an_uncovered_original_finish_gap(
    require_complete: bool, reverse: bool,
):
    # Source image retains a real 2pt-wide unfinished strip through the room;
    # caller metadata claims a fake 25+25=50m², exactly the whole floor.
    zones = (
        _zone("left", ((0, 0), (4, 0), (4, 5), (0, 5))),
        _zone("right", ((6, 0), (10, 0), (10, 5), (6, 5))),
    )
    result = measure_figured_finish_zones_shadow(
        _metric(50.0), PARENT, tuple(reversed(zones)) if reverse else zones,
        require_complete_finish_coverage=require_complete,
    )
    assert result.status is Status.ABSTAINED
    assert result.reason_codes == ("figured_finish_original_source_coverage_incomplete",)
    assert result.candidate_finish_areas_m2 == ()
    assert result.candidate_remaining_unassigned_m2 is None
    assert result.diagnostic_only


def test_original_full_partition_keeps_both_distinct_figured_finish_candidates():
    zones = (
        _zone("left", ((0, 0), (5, 0), (5, 5), (0, 5))),
        _zone("right", ((5, 0), (10, 0), (10, 5), (5, 5))),
    )
    for current in (zones, tuple(reversed(zones))):
        result = measure_figured_finish_zones_shadow(
            _metric(50.0), PARENT, current,
            require_complete_finish_coverage=True,
        )
        assert result.status is Status.CANDIDATE
        assert result.candidate_remaining_unassigned_m2 == 0.0
        assert result.candidate_finish_areas_m2 == (
            ("left", "FT2", 25.0),
            ("right", "FT3", 25.0),
        )
        assert result.diagnostic_only


def test_genuine_original_unassigned_zone_stays_explicitly_partial():
    # The original plan really has an unassigned strip. Its independently
    # figured metrics also leave 10m² unassigned; partial mode may retain it
    # but complete-coverage mode may not.
    zones = (
        _zone("left", ((0, 0), (4, 0), (4, 5), (0, 5)), area=20.0),
        _zone("right", ((6, 0), (10, 0), (10, 5), (6, 5)), area=20.0),
    )
    partial = measure_figured_finish_zones_shadow(
        _metric(50.0), PARENT, zones,
        require_complete_finish_coverage=False,
    )
    assert partial.status is Status.CANDIDATE
    assert partial.candidate_remaining_unassigned_m2 == 10.0
    complete = measure_figured_finish_zones_shadow(
        _metric(50.0), PARENT, zones,
        require_complete_finish_coverage=True,
    )
    assert complete.status is Status.ABSTAINED
    assert complete.reason_codes == ("figured_finish_physical_zone_coverage_incomplete",)
    assert complete.diagnostic_only
