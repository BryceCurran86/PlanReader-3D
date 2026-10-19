"""Only existing original producer widths/heights enter a measured-metre run."""
from dataclasses import replace
import pytest

from pb_live_opening_area_quantity_publication import publish_live_opening_area_quantities
from pb_live_opening_metric_dimensions_source_closed_export import (
    seal_live_opening_dimension_run, seal_live_opening_dimension_claim_run,
)
from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_opening_area_quantity_publication import _composition, _opening
from tests.test_gpt1_live_original_opening_metric_axes import (
    _source_frame_schedule, _figured_with_explicit_axes,
)


def _claim(composition):
    return LivePhysicalNetWallClaim(
        status=Status.ABSTAINED, reason_codes=(), quantity_m2=None,
        source_pages=(), canonical_walls=(),
        canonical_wall_status=Status.ABSTAINED,
        canonical_wall_reason_codes=(), canonical_wall_source_pages=(),
        unresolved_wall_candidate_ids=(),
        canonical_openings=composition.canonical_openings,
        canonical_rooms=(), canonical_floors=(),
        canonical_floor_status=Status.ABSTAINED,
        canonical_floor_reason_codes=(), canonical_floor_source_pages=(),
        canonical_room_status=Status.ABSTAINED,
        canonical_room_reason_codes=(), canonical_room_source_pages=(),
        external_wall_ids=(), evidence_ids=(), quantity_id=None,
        confidence=0.0, publication=None,
        opening_quantity_evidence=publish_live_opening_area_quantities(composition),
        opening_dimension_quantity_evidence=composition.physical_opening_dimension_quantities,
    )


@pytest.mark.parametrize("opening", [_source_frame_schedule(), _figured_with_explicit_axes()])
def test_live_claim_seals_the_exact_same_original_axis_quantities_as_composition(opening):
    composition = _composition(opening)
    claim = _claim(composition)
    actual = seal_live_opening_dimension_claim_run(
        claim, workspace_id=7, project_id="synthetic-lot16",
    )
    expected = seal_live_opening_dimension_run(
        composition, workspace_id=7, project_id="synthetic-lot16",
    )
    assert actual.fingerprint == expected.fingerprint
    assert len(actual.quantities) == 2
    assert all(q.lineage_ok and not q.abstained for q in actual.quantities)
    assert {q.unit for q in actual.quantities} == {"lm"}
    assert {q.family for q in actual.quantities} == {"opening_width", "opening_height"}


def test_area_only_source_claim_still_issues_no_guessed_lengths():
    claim = _claim(_composition(_opening()))
    result = seal_live_opening_dimension_claim_run(
        claim, workspace_id=7, project_id="synthetic-lot16",
    )
    assert result.quantities == ()


@pytest.mark.parametrize("mutation", [
    lambda q: replace(q, value=q.value + .03),
    lambda q: replace(q, unit="m2"),
    lambda q: replace(q, quantity_id="copied-foreign-source"),
    lambda q: replace(q, metadata={**q.metadata, "source_area_quantity_id": "other-area"}),
    lambda q: replace(q, metadata={**q.metadata, "commercial_projection_allowed": True}),
    lambda q: replace(q, evidence_ids=("invented-dimension-receipt",)),
])
def test_claim_axis_source_tamper_cannot_make_a_signed_measurement(mutation):
    claim = _claim(_composition(_source_frame_schedule()))
    first = claim.opening_dimension_quantity_evidence[0]
    with pytest.raises(SourceClosedRunConflictError):
        seal_live_opening_dimension_claim_run(
            replace(claim, opening_dimension_quantity_evidence=(
                mutation(first), *claim.opening_dimension_quantity_evidence[1:],
            )),
            workspace_id=7, project_id="synthetic-lot16",
        )


def test_partial_axis_pair_must_not_become_complete_quantity_universe():
    claim = _claim(_composition(_figured_with_explicit_axes()))
    with pytest.raises(SourceClosedRunConflictError, match="incomplete"):
        seal_live_opening_dimension_claim_run(
            replace(claim, opening_dimension_quantity_evidence=(
                claim.opening_dimension_quantity_evidence[0],
            )),
            workspace_id=7, project_id="synthetic-lot16",
        )
