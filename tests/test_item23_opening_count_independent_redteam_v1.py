"""Independent Item 23 opening-count adversarial validator.

TEST ONLY / EXPECTED RED / NEVER MERGE.

Designed from merged authority contracts and the public production surface only.
No production test file was used as the basis of this suite.
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib
from types import SimpleNamespace

import pytest


SUT_MODULE = "pb_generic_opening_count_recovery"


def _sut():
    try:
        return importlib.import_module(SUT_MODULE)
    except ModuleNotFoundError as exc:
        pytest.fail("Item 23 opening-count production surface is absent on the frozen base")
        raise AssertionError from exc


@dataclass(frozen=True)
class _Context:
    document_id: str = "doc-A"
    source_sha256: str = "a" * 64
    current_revision_id: str = "rev-1"
    evidence_snapshot_id: str = "snap-1"
    page_id: str = "page-1"
    viewport_id: str = "view-1"


class _Result:
    def __init__(self, quantities, *, scope_complete=True):
        self.quantities = tuple(quantities)
        self.scope_complete = scope_complete


class _Adapter:
    def __init__(self, quantities, *, scope_complete=True):
        self._result = _Result(quantities, scope_complete=scope_complete)

    def extract(self, _context):
        return self._result


def _q(
    key: str,
    value: float,
    qid: str,
    *,
    evidence_ids=("ev-1",),
    metadata=None,
    formula="explicit source count",
    abstained=False,
):
    return SimpleNamespace(
        semantic_key=key,
        quantity_id=qid,
        family="window_count" if key.upper().startswith("W") else "door_count",
        abstained=abstained,
        value=value,
        unit="ea",
        evidence_ids=tuple(evidence_ids),
        status="FIRM",
        formula=formula,
        authority="documented_count",
        metadata=dict(metadata or {}),
    )


def _recover(*quantities, context=None, scope_complete=True):
    mod = _sut()
    recovery = mod.GenericOpeningCountRecovery(
        adapter=_Adapter(quantities, scope_complete=scope_complete)
    )
    return recovery.recover(context or _Context())


def _keys(result):
    return tuple(item.semantic_key for item in result.recovered)


# 01 — duplicate observations must not double count.
def test_attack01_duplicate_observations_fail_closed_not_double_counted() -> None:
    result = _recover(_q("W17", 4, "q-a"), _q("W17", 4, "q-b"))
    assert result.recovered == ()
    assert set(result.rejected_quantity_ids) == {"q-a", "q-b"}


# 02 — same mark is a type label, never proof of one physical opening instance.
def test_attack02_same_mark_does_not_create_physical_instance_identity() -> None:
    result = _recover(_q("W17", 4, "q-a"))
    assert len(result.recovered) == 1
    item = result.recovered[0]
    assert item.semantic_key == "W17"
    assert item.value == 4
    assert item.publishable_as_authoritative is False
    assert item.spatially_reconstructed is False
    assert not hasattr(item, "physical_opening_instance_id")
    assert result.type_counts_do_not_imply_instances is True


# 03 — equal counts/dimensions for distinct opening identities remain distinct.
def test_attack03_equal_size_or_equal_count_distinct_opening_types_remain_distinct() -> None:
    result = _recover(_q("W17", 2, "q-a"), _q("W18", 2, "q-b"))
    assert _keys(result) == ("W17", "W18")
    assert [item.value for item in result.recovered] == [2, 2]


# 04 — duplicated schedule rows for one mark are not first/last-wins.
def test_attack04_schedule_duplicate_same_mark_fails_closed() -> None:
    result = _recover(
        _q("D12", 3, "sched-row-a", evidence_ids=("sched-ev-a",)),
        _q("D12", 3, "sched-row-b", evidence_ids=("sched-ev-b",)),
    )
    assert result.recovered == ()
    assert set(result.rejected_quantity_ids) == {"sched-row-a", "sched-row-b"}


# 05 — plan/schedule disagreement is conflict, not silent precedence.
def test_attack05_plan_schedule_disagreement_fails_closed() -> None:
    result = _recover(
        _q("W21", 4, "plan-count", evidence_ids=("plan-ev",)),
        _q("W21", 5, "schedule-count", evidence_ids=("schedule-ev",)),
    )
    assert result.recovered == ()
    assert set(result.rejected_quantity_ids) == {"plan-count", "schedule-count"}


@pytest.mark.parametrize(
    "metadata",
    [
        {"document_id": "doc-A", "page_id": "page-2", "viewport_id": "view-1", "revision_id": "rev-1", "evidence_snapshot_id": "snap-1", "source_sha256": "a" * 64},
        {"document_id": "doc-A", "page_id": "page-1", "viewport_id": "view-2", "revision_id": "rev-1", "evidence_snapshot_id": "snap-1", "source_sha256": "a" * 64},
        {"document_id": "doc-A", "page_id": "page-1", "viewport_id": "view-1", "revision_id": "rev-0", "evidence_snapshot_id": "snap-1", "source_sha256": "a" * 64},
        {"document_id": "doc-A", "page_id": "page-1", "viewport_id": "view-1", "revision_id": "rev-1", "evidence_snapshot_id": "snap-old", "source_sha256": "a" * 64},
        {"document_id": "doc-A", "page_id": "page-1", "viewport_id": "view-1", "revision_id": "rev-1", "evidence_snapshot_id": "snap-1", "source_sha256": "b" * 64},
    ],
)
def test_attacks06_10_wrong_scope_or_stale_lineage_cannot_recover(metadata) -> None:
    result = _recover(_q("W31", 2, "q-stale", metadata=metadata))
    assert result.recovered == (), "wrong-page/viewport/revision/snapshot/source evidence was laundered"
    assert "q-stale" in result.rejected_quantity_ids


# 11 — caller-created instance identifiers in metadata never establish identity.
def test_attack11_forged_instance_ids_do_not_create_physical_openings() -> None:
    result = _recover(
        _q(
            "D42",
            2,
            "q-forged-instance",
            metadata={
                "physical_opening_instance_ids": ("caller-open-1", "caller-open-2"),
                "instance_identity_proven": True,
            },
        )
    )
    assert len(result.recovered) <= 1
    if result.recovered:
        item = result.recovered[0]
        assert item.publishable_as_authoritative is False
        assert item.spatially_reconstructed is False
        assert not hasattr(item, "physical_opening_instance_ids")


# 12 — caller supplied numeric counts may be diagnostic at most, never authority.
def test_attack12_caller_supplied_count_cannot_become_authoritative() -> None:
    result = _recover(_q("W83", 99, "caller-count"))
    assert len(result.recovered) == 1
    assert result.recovered[0].value == 99
    assert result.recovered[0].publishable_as_authoritative is False
    assert result.authority_state != "firm"


# 13 — incomplete universe cannot publish an answered count.
def test_attack13_incomplete_opening_universe_blocks_recovery() -> None:
    result = _recover(_q("W91", 3, "q-partial"), scope_complete=False)
    assert result.recovered == (), "a local/truncated quantity list was treated as a complete opening universe"


# 14 — ambiguity laundering with identical values still remains ambiguous.
def test_attack14_identical_duplicate_sources_do_not_launder_ambiguity() -> None:
    result = _recover(
        _q("D7", 2, "q-source-a", evidence_ids=("ev-a",)),
        _q("D7", 2, "q-source-b", evidence_ids=("ev-b",)),
    )
    assert result.recovered == ()


# 15 — ordering cannot decide which evidence wins.
def test_attack15_input_order_invariance() -> None:
    quantities = (
        _q("W17", 2, "q-w17"),
        _q("D12", 1, "q-d12"),
        _q("W18", 2, "q-w18"),
    )
    forward = _recover(*quantities)
    reverse = _recover(*reversed(quantities))
    assert forward.recovered == reverse.recovered
    assert forward.rejected_quantity_ids == reverse.rejected_quantity_ids
