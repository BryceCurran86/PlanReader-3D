"""Original room-area semantic/evidence authority at the real ceiling issuer.

These source-neutral adversarial controls use the existing producer-shaped
fixtures. They cannot substitute for SHA-verified original-page replay.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_cross_view_ceiling_quantity_authority import publish_cross_view_ceiling_quantities
from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_cross_view_ceiling_quantity_authority import _bridge, _finish, _rooms


def _publish(bridge):
    return publish_cross_view_ceiling_quantities(
        rooms=_rooms(), room_area_bridges=(bridge,), finishes=_finish()
    )


@pytest.mark.parametrize(
    "foreign_semantic",
    (
        "room_area:foreign-source-room",
        "floor_area:source-room-1",
        "ceiling_lining:source-room-1",
        "room_area:source-room-1 ",
        "",
    ),
)
def test_foreign_original_room_area_semantic_never_issues_ceiling(
    foreign_semantic: str,
) -> None:
    bridge = _bridge()
    forged = replace(
        bridge,
        quantities=(replace(bridge.quantities[0], semantic_key=foreign_semantic),),
    )
    assert _publish(forged).status is EvidenceResolutionStatus.ABSTAINED
    assert _publish(forged).records == ()
    assert _publish(forged).quantities == ()
    assert _publish(forged).canonical_ceilings == ()


@pytest.mark.parametrize(
    "foreign_evidence",
    (
        ("face-1", "foreign-figured-receipt"),
        ("foreign-figured-receipt",),
        ("face-1", "room-geometry-evidence", "room-geometry-evidence"),
    ),
)
def test_unowned_or_replayed_original_area_receipt_never_issues_ceiling(
    foreign_evidence: tuple[str, ...],
) -> None:
    bridge = _bridge()
    forged = replace(
        bridge,
        quantities=(replace(bridge.quantities[0], evidence_ids=foreign_evidence),),
    )
    result = _publish(forged)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.records == ()
    assert result.quantities == ()


@pytest.mark.parametrize(
    "invalid_entity_receipts",
    (
        (),
        ("face-1", "room-geometry-evidence", "room-geometry-evidence"),
        ("face-1", " room-geometry-evidence"),
        ("face-1", ""),
    ),
)
def test_malformed_source_room_receipt_inventory_cannot_authorize_ceiling(
    invalid_entity_receipts: tuple[str, ...],
) -> None:
    bridge = _bridge()
    forged = replace(
        bridge,
        entities=(replace(bridge.entities[0], evidence_ids=invalid_entity_receipts),),
    )
    result = _publish(forged)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.records == ()


def test_exact_source_owned_area_preserves_existing_firm_ceiling_and_is_immutable() -> None:
    bridge = _bridge()
    original_entity = bridge.entities[0]
    original_quantity = bridge.quantities[0]
    first = _publish(bridge)
    second = _publish(bridge)

    assert first.status is EvidenceResolutionStatus.CORROBORATED
    assert len(first.records) == 1
    assert len(first.quantities) == 1
    assert len(first.canonical_ceilings) == 1
    assert first.quantities[0].value == original_quantity.value
    assert first.quantities[0].status == "firm"
    assert first.records[0].quantity.quantity_id == second.records[0].quantity.quantity_id
    assert first.records[0].canonical_ceiling_id == second.records[0].canonical_ceiling_id
    assert bridge.entities[0] == original_entity
    assert bridge.quantities[0] == original_quantity


def test_foreign_receipt_cannot_be_rescued_by_valid_second_bridge() -> None:
    bridge = _bridge()
    forged = replace(
        bridge,
        quantities=(
            replace(bridge.quantities[0], evidence_ids=("face-1", "foreign-dimension")),
        ),
    )
    # Competing original receipts for the same room are never selected by
    # first/last order. The malformed sibling must not authorize a ceiling.
    for ordered in ((forged, bridge), (bridge, forged)):
        result = publish_cross_view_ceiling_quantities(
            rooms=_rooms(), room_area_bridges=ordered, finishes=_finish()
        )
        # The source-closed valid bridge may still be a legitimate sole
        # claimant, but no foreign receipt may appear in issued evidence.
        assert all(
            "foreign-dimension" not in quantity.evidence_ids
            for quantity in result.quantities
        )
