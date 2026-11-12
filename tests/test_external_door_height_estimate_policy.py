"""Source-neutral regressions for Bryce's external-door 2100 estimate policy."""
from dataclasses import FrozenInstanceError
from dataclasses import replace
import pytest

from pb_external_door_height_estimate_policy import (
    OWNER_EXTERNAL_DOOR_ASSUMED_HEIGHT_MM,
    OWNER_EXTERNAL_DOOR_ASSUMPTION_BASIS,
    resolve_external_door_height_estimate,
)


def estimate(**kwargs):
    args = dict(
        opening_id="native-physical-external-door-1",
        external_door_authenticated=True,
        external_door_identity_evidence_id="native-external-door-kind-and-identity",
    )
    args.update(kwargs)
    return resolve_external_door_height_estimate(**args)


def assert_review_only(result, *, labelled_provisional_customer=False):
    assert result.commercial_review_required is True
    assert result.can_issue_firm_quantity is False
    assert result.can_seal_source_closed_customer is False
    assert result.benchmark_score_granted is False
    assert result.can_issue_labelled_provisional_customer is labelled_provisional_customer


def test_default_for_authentic_external_door_without_specific_height():
    result = estimate()
    assert result.height_mm == OWNER_EXTERNAL_DOOR_ASSUMED_HEIGHT_MM == 2100
    assert result.basis == OWNER_EXTERNAL_DOOR_ASSUMPTION_BASIS
    assert result.source_authenticated_height is False
    assert result.assumption_used is True
    assert result.verify_on_site is True
    assert_review_only(result, labelled_provisional_customer=True)


def test_proven_elevation_height_overrides_default():
    result = estimate(
        elevation_height_mm=2250, elevation_height_evidence_id="source-elevation-2250",
        elevation_owned_to_opening=True,
    )
    assert result.height_mm == 2250
    assert result.basis == "authenticated_door_elevation"
    assert result.source_authenticated_height is True
    assert result.assumption_used is False
    assert result.verify_on_site is False
    assert_review_only(result)


def test_proven_schedule_height_overrides_default():
    result = estimate(
        schedule_height_mm=2040, schedule_height_evidence_id="schedule-row-door-1",
        schedule_owned_to_opening=True,
    )
    assert result.height_mm == 2040
    assert result.basis == "authenticated_door_schedule"
    assert result.assumption_used is False
    assert_review_only(result)


def test_explicit_2100_elevation_is_not_an_assumption():
    result = estimate(
        elevation_height_mm=2100, elevation_height_evidence_id="owned-elevation-2100",
        elevation_owned_to_opening=True,
    )
    assert result.height_mm == 2100
    assert result.assumption_used is False
    assert result.source_evidence_ids == ("owned-elevation-2100",)
    assert_review_only(result)


def test_agreeing_schedule_and_elevation_retains_both_witnesses():
    result = estimate(
        schedule_height_mm=2250, schedule_height_evidence_id="sch", schedule_owned_to_opening=True,
        elevation_height_mm=2250, elevation_height_evidence_id="elev", elevation_owned_to_opening=True,
    )
    assert result.height_mm == 2250
    assert result.basis == "authenticated_door_schedule"
    assert result.source_evidence_ids == ("sch", "elev")
    assert_review_only(result)


@pytest.mark.parametrize("height", [2100, 2040, 2300])
def test_conflicting_explicit_height_blocks_default(height):
    result = estimate(
        schedule_height_mm=2100, schedule_height_evidence_id="sch", schedule_owned_to_opening=True,
        elevation_height_mm=height + 50, elevation_height_evidence_id="elev",
        elevation_owned_to_opening=True,
    )
    assert result.height_mm is None
    assert result.reason_code == "schedule_elevation_height_conflict"
    assert result.assumption_used is False
    assert_review_only(result)


@pytest.mark.parametrize("kwargs", [
    {"external_door_authenticated": False},
    {"external_door_identity_evidence_id": ""},
    {"external_door_identity_evidence_id": None},
])
def test_unproven_external_door_cannot_get_height(kwargs):
    result = estimate(**kwargs)
    assert result.height_mm is None
    assert result.reason_code == "external_door_identity_not_authenticated"
    assert_review_only(result)


@pytest.mark.parametrize("kwargs", [
    {"schedule_height_mm": 2200},
    {"schedule_height_mm": 2200, "schedule_height_evidence_id": "source"},
    {"schedule_height_mm": 2100, "schedule_owned_to_opening": True},
    {"schedule_height_evidence_id": "orphan"},
    {"schedule_owned_to_opening": True},
    {"schedule_height_mm": 0, "schedule_height_evidence_id": "row", "schedule_owned_to_opening": True},
    {"schedule_height_mm": float("inf"), "schedule_height_evidence_id": "row", "schedule_owned_to_opening": True},
    {"schedule_height_mm": True, "schedule_height_evidence_id": "row", "schedule_owned_to_opening": True},
])
def test_unverified_specific_schedule_does_not_fallback(kwargs):
    result = estimate(**kwargs)
    assert result.height_mm is None
    assert result.reason_code == "specific_schedule_height_unverified"
    assert_review_only(result)


@pytest.mark.parametrize("kwargs", [
    {"elevation_height_mm": 2100},
    {"elevation_height_mm": 2100, "elevation_height_evidence_id": "note"},
    {"elevation_height_mm": 2100, "elevation_owned_to_opening": True},
    {"elevation_height_evidence_id": "general-joinery-height"},
    {"elevation_owned_to_opening": True},
])
def test_unverified_elevation_or_general_joinery_note_blocks_fallback(kwargs):
    result = estimate(**kwargs)
    assert result.height_mm is None
    assert result.reason_code == "specific_elevation_height_unverified"
    assert_review_only(result)


def test_specific_exception_without_proven_height_needs_review():
    result = estimate(specific_exception_noted=True)
    assert result.height_mm is None
    assert result.reason_code == "specific_height_exception_unresolved"
    assert_review_only(result)


def test_specific_height_with_exception_remains_specific():
    result = estimate(
        specific_exception_noted=True,
        elevation_height_mm=2400,
        elevation_height_evidence_id="unique-door-witness",
        elevation_owned_to_opening=True,
    )
    assert result.height_mm == 2400
    assert result.assumption_used is False
    assert_review_only(result)


@pytest.mark.parametrize("field", [
    "external_door_authenticated", "schedule_owned_to_opening",
    "elevation_owned_to_opening", "specific_exception_noted",
])
@pytest.mark.parametrize("bad", [None, 0, 1, "yes"])
def test_boolean_controls_are_strict(field, bad):
    with pytest.raises(TypeError):
        estimate(**{field: bad})


def test_invalid_missing_identity_rejected():
    with pytest.raises(ValueError):
        estimate(opening_id=" ")


def test_read_only_and_stable_under_replay():
    a = estimate()
    b = estimate()
    assert a == b
    with pytest.raises(FrozenInstanceError):
        a.height_mm = 2040
    # The assumption may become a labelled provisional customer line, never FIRM.
    forged = replace(a, can_issue_firm_quantity=True)
    assert a.can_issue_firm_quantity is False
    assert a.can_issue_labelled_provisional_customer is True
    assert a.can_seal_source_closed_customer is False
    assert forged != a
