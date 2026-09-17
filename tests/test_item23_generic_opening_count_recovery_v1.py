"""Item 23 generic opening-count recovery regressions."""
from __future__ import annotations

from types import SimpleNamespace

from pb_generic_opening_count_recovery import GenericOpeningCountRecovery
from pb_migration_contracts import QuantityEvidence
from pb_shadow_opening_count_gate import OPENING_COUNT_AUTHORITY_STATE


class _FakeAdapter:
    def __init__(self, quantities):
        self._quantities = tuple(quantities)

    def extract(self, _context):
        return SimpleNamespace(quantities=self._quantities)


def _qty(
    key: str,
    value: float | None,
    *,
    qid: str,
    family: str = "window_count",
    abstained: bool = False,
    description: str = "",
) -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id=qid,
        family=family,
        semantic_key=key,
        value=value,
        unit="ea",
        input_entity_ids=(f"ent-{qid}",) if not abstained else (),
        formula="schedule_plan_corroborated" if not abstained else "abstain",
        formula_version="1",
        evidence_ids=(f"ev-{qid}",) if not abstained else (),
        authority="shadow_opening_count",
        status="firm" if not abstained else "abstained",
        confidence=0.9 if not abstained else 0.0,
        abstained=abstained,
        blocking_reasons=("conflict",) if abstained else (),
        metadata={"description": description},
    )


def test_recovers_explicit_generic_type_count_with_provenance_only() -> None:
    recovery = GenericOpeningCountRecovery(_FakeAdapter((_qty("W17", 4.0, qid="q1"),)))
    result = recovery.recover(object())
    assert len(result.recovered) == 1
    item = result.recovered[0]
    assert item.semantic_key == "W17"
    assert item.value == 4.0
    assert item.evidence_ids == ("ev-q1",)
    assert item.spatially_reconstructed is False
    assert item.publishable_as_authoritative is False
    assert result.type_counts_do_not_imply_instances is True
    assert result.authority_state == OPENING_COUNT_AUTHORITY_STATE == "new_shadow"


def test_family_total_is_not_laundered_into_an_explicit_opening_identity() -> None:
    recovery = GenericOpeningCountRecovery(
        _FakeAdapter((_qty("window_total", 9.0, qid="q-total"),))
    )
    result = recovery.recover(object())
    assert result.recovered == ()
    assert result.rejected_quantity_ids == ("q-total",)


def test_dimension_shaped_key_cannot_create_opening_identity() -> None:
    recovery = GenericOpeningCountRecovery(
        _FakeAdapter((_qty("3000x1200", 2.0, qid="q-dim"),))
    )
    result = recovery.recover(object())
    assert result.recovered == ()
    assert result.rejected_quantity_ids == ("q-dim",)


def test_dimension_chain_generated_w1_is_rejected_even_though_tag_looks_valid() -> None:
    recovery = GenericOpeningCountRecovery(
        _FakeAdapter(
            (
                _qty(
                    "W1",
                    4.0,
                    qid="q-chain-w",
                    description="W1 plan opening/pier chain (4 No, 2900 mm)",
                ),
            )
        )
    )
    result = recovery.recover(object())
    assert result.recovered == ()
    assert result.rejected_quantity_ids == ("q-chain-w",)


def test_dimension_chain_generated_d1_is_rejected_even_though_tag_looks_valid() -> None:
    recovery = GenericOpeningCountRecovery(
        _FakeAdapter(
            (
                _qty(
                    "D1",
                    3.0,
                    qid="q-chain-d",
                    family="door_count",
                    description="D1 repeated floor-plan bay doors (3 No)",
                ),
            )
        )
    )
    result = recovery.recover(object())
    assert result.recovered == ()
    assert result.rejected_quantity_ids == ("q-chain-d",)


def test_abstained_conflict_stays_rejected() -> None:
    recovery = GenericOpeningCountRecovery(
        _FakeAdapter((_qty("D12", None, qid="q-conflict", family="door_count", abstained=True),))
    )
    result = recovery.recover(object())
    assert result.recovered == ()
    assert result.rejected_quantity_ids == ("q-conflict",)


def test_duplicate_same_identity_fails_closed_instead_of_first_or_last_wins() -> None:
    recovery = GenericOpeningCountRecovery(
        _FakeAdapter(
            (
                _qty("W7", 2.0, qid="q-first"),
                _qty("W7", 3.0, qid="q-second"),
            )
        )
    )
    result = recovery.recover(object())
    assert result.recovered == ()
    assert "q-second" in result.rejected_quantity_ids


def test_arbitrary_explicit_door_and_window_numbers_are_supported() -> None:
    recovery = GenericOpeningCountRecovery(
        _FakeAdapter(
            (
                _qty("W83", 6.0, qid="q-w"),
                _qty("D42", 1.0, qid="q-d", family="door_count"),
            )
        )
    )
    result = recovery.recover(object())
    assert {item.semantic_key for item in result.recovered} == {"W83", "D42"}
