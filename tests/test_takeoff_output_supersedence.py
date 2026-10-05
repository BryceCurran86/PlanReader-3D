from __future__ import annotations

import json

from pb_migration_contracts import QuantityEvidence
from pb_takeoff_output_supersedence import (
    blocked_commercial_claim_key,
    prior_commercial_projection_key,
    select_prior_commercial_rows_to_preserve,
)


SHA_A = "a" * 64
SHA_B = "b" * 64


def blocked_quantity(**overrides) -> QuantityEvidence:
    data = {
        "quantity_id": "blocked-qty",
        "family": "room_area",
        "semantic_key": "room_area:room-1",
        "value": None,
        "unit": "m2",
        "input_entity_ids": ("room-1",),
        "formula": "figured",
        "formula_version": "1",
        "evidence_ids": ("ev-1",),
        "authority": "documented_dimension",
        "status": "blocked",
        "confidence": 0.0,
        "abstained": True,
        "blocking_reasons": ("temporary_measurement_conflict",),
        "reason_codes": ("temporary_measurement_conflict",),
    }
    data.update(overrides)
    return QuantityEvidence(**data)


def prior_row(*, sha: str = SHA_A, quantity_status: str = "To review"):
    provenance = {
        "adapter": "commercial_takeoff",
        "quantity": {
            "quantity_id": "firm-qty",
            "family": "room_area",
            "semantic_key": "room_area:room-1",
            "value": 13.27,
            "unit": "m2",
            "input_entity_ids": ["room-1"],
            "abstained": False,
        },
        "source_trace": {
            "source_sha256": sha,
            "canonical_entity_ids": ["room-1"],
        },
        "measurement_authority": {
            "method": "figured_dimension",
        },
    }
    return {
        "quantity_status": quantity_status,
        "quantity": 13.27,
        "unit": "m²",
        "notes": json.dumps(provenance, sort_keys=True),
        "source_reference": "PB Auto Geometry v1.2.19 · room_area_quantity:firm-qty",
    }


def test_preserves_prior_source_closed_draft_for_exact_current_abstention():
    key = blocked_commercial_claim_key(
        blocked_quantity(),
        source_sha256=SHA_A,
    )
    assert key is not None

    rows = select_prior_commercial_rows_to_preserve(
        [prior_row()],
        blocked_claim_keys=(key,),
    )

    assert len(rows) == 1
    assert prior_commercial_projection_key(rows[0]) == key


def test_source_change_does_not_preserve_stale_prior_output():
    key = blocked_commercial_claim_key(
        blocked_quantity(),
        source_sha256=SHA_B,
    )
    assert key is not None

    rows = select_prior_commercial_rows_to_preserve(
        [prior_row(sha=SHA_A)],
        blocked_claim_keys=(key,),
    )

    assert rows == ()


def test_disappeared_object_does_not_preserve_prior_output():
    rows = select_prior_commercial_rows_to_preserve(
        [prior_row()],
        blocked_claim_keys=(),
    )
    assert rows == ()


def test_reviewed_row_is_not_reinserted_as_unreviewed_auto_output():
    key = blocked_commercial_claim_key(
        blocked_quantity(),
        source_sha256=SHA_A,
    )
    assert key is not None

    rows = select_prior_commercial_rows_to_preserve(
        [prior_row(quantity_status="Measured")],
        blocked_claim_keys=(key,),
    )
    assert rows == ()


def test_unproven_or_identityless_blocker_cannot_preserve_prior_output():
    identityless = blocked_quantity(input_entity_ids=())
    key = blocked_commercial_claim_key(identityless, source_sha256=SHA_A)
    assert key is None


def test_current_replacement_wins_over_prior_row():
    key = blocked_commercial_claim_key(
        blocked_quantity(),
        source_sha256=SHA_A,
    )
    assert key is not None
    old = prior_row()
    replacement = prior_row()

    rows = select_prior_commercial_rows_to_preserve(
        [old],
        blocked_claim_keys=(key,),
        replacement_rows=(replacement,),
    )
    assert rows == ()
