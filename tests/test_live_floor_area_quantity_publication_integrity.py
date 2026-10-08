"""Fail-closed replay integrity at the canonical floor QuantityEvidence boundary."""
from __future__ import annotations

from dataclasses import replace

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_live_floor_area_quantity_publication import publish_live_floor_area_quantities
from pb_migration_contracts import QuantityEvidence
from tests.test_live_floor_finish_area_source_closed_export import _claim, _floor


def _source_area() -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id="room-area-1",
        family="room_area",
        semantic_key="room_area:source-room-1",
        value=8.64,
        unit="m2",
        input_entity_ids=("source-room-1",),
        formula="authenticated_documented_room_area",
        formula_version="1",
        evidence_ids=("ev-room", "ev-area"),
        authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        status=AuthorityStatus.FIRM.value,
        confidence=1.0,
        abstained=False,
        blocking_reasons=(),
        reason_codes=("authenticated_room_area",),
        metadata={
            "source_sha256": "a" * 64,
            "revision_id": "rev-1",
            "page_no": "1",
            "viewport_id": "vp-1",
        },
    )


def _claim_with(*quantities: QuantityEvidence):
    return replace(
        _claim(_floor()),
        room_area_quantity_evidence=tuple(quantities),
    )


def test_unique_firm_room_area_publishes_exactly_one_canonical_floor_quantity() -> None:
    published = publish_live_floor_area_quantities(_claim_with(_source_area()))

    assert len(published) == 1
    result = published[0]
    assert result.family == "floor_area"
    assert result.value == 8.64
    assert result.status == AuthorityStatus.FIRM.value
    assert result.input_entity_ids == ("floor-1",)
    assert result.metadata["upstream_room_area_quantity_id"] == "room-area-1"


def test_identical_source_room_area_replay_is_idempotent() -> None:
    source = _source_area()

    unique = publish_live_floor_area_quantities(_claim_with(source))
    replay = publish_live_floor_area_quantities(_claim_with(source, source))

    assert len(unique) == 1
    assert replay == unique


def test_conflicting_duplicate_id_never_publishes_floor_area() -> None:
    original = _source_area()
    changes = (
        replace(original, value=9.0),
        replace(original, evidence_ids=("ev-room",)),
        replace(
            original,
            metadata={**original.metadata, "viewport_id": "another-viewport"},
        ),
    )
    for conflicting in changes:
        for quantities in (
            (original, conflicting),
            (conflicting, original),
            (original, conflicting, original),
        ):
            assert publish_live_floor_area_quantities(_claim_with(*quantities)) == ()


def test_unrelated_non_firm_replay_does_not_poison_a_firm_source_id() -> None:
    source = _source_area()
    rejected = replace(
        source,
        status=AuthorityStatus.PROVISIONAL.value,
        value=None,
        abstained=True,
        blocking_reasons=("not_firm",),
    )

    published = publish_live_floor_area_quantities(
        _claim_with(source, rejected)
    )
    assert len(published) == 1


def test_unsupported_area_units_and_blocked_claims_do_not_publish_m2() -> None:
    source = _source_area()
    invalid_claims = (
        replace(source, unit="ft2"),
        replace(source, blocking_reasons=("unresolved_source_authority",)),
    )
    for invalid in invalid_claims:
        assert publish_live_floor_area_quantities(_claim_with(invalid)) == ()


def test_unsupported_firm_authority_cannot_publish_canonical_floor_quantity() -> None:
    source = _source_area()
    for authority in ("model_derived", "schedule_extracted", "ai_detected"):
        unsupported = replace(source, authority=authority)
        floor = replace(_floor(), metric_area_authority=authority)
        claim = replace(
            _claim_with(unsupported),
            canonical_floors=(floor,),
        )
        assert publish_live_floor_area_quantities(claim) == ()
