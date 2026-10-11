"""Q07: no unverified opening source value reaches customer draft quantities."""
from __future__ import annotations

from copy import copy
from dataclasses import replace

import pytest

from pb_live_opening_customer_projection import (
    _eligible_area_quantities, _eligible_count_quantities,
)
from pb_live_opening_area_quantity_publication import _opening_quantity
from tests.test_live_opening_area_quantity_publication import _opening
from tests.test_live_floor_finish_area_source_closed_export import _claim


def _source_opening_area():
    source = _opening_quantity(_opening())
    assert source is not None
    return source


def _source_opening_count():
    return replace(
        _source_opening_area(),
        family="opening_count",
        quantity_id="source-count-1",
        value=1.0,
        unit="ea",
        status="firm",
        metadata={"schedule_corroborated": True, "opening_mark": "W1",
                  "commercial_projection_allowed": True},
    )


def _replay(source, **changes):
    changed = copy(source)
    for key, value in changes.items():
        object.__setattr__(changed, key, value)
    return changed


@pytest.mark.parametrize("bad", [True, False, "2.172", 10 ** 400,
                                  float("nan"), float("inf"), -1.0])
def test_untyped_or_nonpositive_source_area_cannot_reach_customer(bad):
    quantity = _replay(_source_opening_area(), value=bad)
    claim = replace(_claim(), opening_quantity_evidence=(quantity,))
    assert _eligible_area_quantities(claim) == ()


def test_customer_area_requires_exact_producer_corrob_status_and_square_metres():
    source = _source_opening_area()
    assert _eligible_area_quantities(
        replace(_claim(), opening_quantity_evidence=(source,))
    ) == (source,)
    for bad in (replace(source, status="provisional"),
                replace(source, unit="ea")):
        assert _eligible_area_quantities(
            replace(_claim(), opening_quantity_evidence=(bad,))
        ) == ()


@pytest.mark.parametrize("bad", [True, False, "1", 10 ** 400, 1.5,
                                  float("nan"), float("inf"), -1])
def test_untyped_or_fractional_source_count_cannot_reach_customer(bad):
    count = _replay(_source_opening_count(), value=bad)
    claim = replace(_claim(), opening_count_quantity_evidence=(count,))
    assert _eligible_count_quantities(claim) == ()


@pytest.mark.parametrize("permission", [None, False, "true", 1])
def test_customer_area_cannot_infer_commercial_permission_from_missing_or_replayed_flag(permission):
    authentic = _source_opening_area()
    tampered = replace(authentic, metadata={
        **dict(authentic.metadata), "commercial_projection_allowed": permission,
    })
    assert _eligible_area_quantities(
        replace(_claim(), opening_quantity_evidence=(tampered,))
    ) == ()


@pytest.mark.parametrize("permission", [None, False, "true", 1])
def test_customer_count_cannot_infer_commercial_permission_from_missing_or_replayed_flag(permission):
    authentic = _source_opening_count()
    tampered = replace(authentic, metadata={
        **dict(authentic.metadata), "commercial_projection_allowed": permission,
    })
    assert _eligible_count_quantities(
        replace(_claim(), opening_count_quantity_evidence=(tampered,))
    ) == ()


def test_count_customer_requires_source_schedule_corrob_and_firm_each():
    source = _source_opening_count()
    assert _eligible_count_quantities(
        replace(_claim(), opening_count_quantity_evidence=(source,))
    ) == (source,)
    for bad in (
        replace(source, status="provisional"),
        replace(source, unit="m2"),
        replace(source, metadata={"schedule_corroborated": False, "opening_mark": "W1"}),
    ):
        assert _eligible_count_quantities(
            replace(_claim(), opening_count_quantity_evidence=(bad,))
        ) == ()



def test_provisional_duplicate_must_not_disappear_before_source_customer_collision_gate():
    from pb_live_opening_customer_projection import project_live_opening_customer_rows

    authentic = _source_opening_area()
    replayed = replace(
        authentic,
        status="provisional",
        value=None,
        abstained=True,
        blocking_reasons=("missing_source_measurement",),
    )
    # The second claim cannot publish, but it still contests the same source
    # quantity ID. Filtering it away would hide a physically conflicting claim.
    claim = replace(
        _claim(),
        opening_quantity_evidence=(authentic, replayed),
    )
    with pytest.raises(ValueError, match="identities collide before commercial filtering"):
        project_live_opening_customer_rows(
            claim, workspace_id=1, project_id="customer-integrity-test",
        )


def test_cross_family_blocked_duplicate_cannot_mask_firm_source_area_claim():
    from pb_live_opening_customer_projection import project_live_opening_customer_rows

    area = _source_opening_area()
    count = replace(
        _source_opening_count(),
        quantity_id=area.quantity_id,
        status="blocked",
        value=None,
        abstained=True,
        blocking_reasons=("incomplete_opening_universe",),
    )
    claim = replace(
        _claim(),
        opening_quantity_evidence=(area,),
        opening_count_quantity_evidence=(count,),
    )
    with pytest.raises(ValueError, match="identities collide before commercial filtering"):
        project_live_opening_customer_rows(
            claim, workspace_id=1, project_id="customer-integrity-test",
        )


def _physical_original_opening_claim():
    opening = _opening()
    quantity = _opening_quantity(opening)
    assert quantity is not None
    return replace(
        _claim(),
        canonical_openings=(opening,),
        opening_quantity_evidence=(quantity,),
        opening_count_quantity_evidence=(),
    )


@pytest.mark.parametrize("changes", [
    {"value": 3.14},
    {"formula": "guessed_opening_area"},
    {"metadata": {"source_sha256": "f" * 64}},
])
def test_customer_source_area_replay_rejects_copied_original_quantity_id(changes):
    from pb_live_opening_customer_projection import project_live_opening_customer_rows
    claim = _physical_original_opening_claim()
    original = claim.opening_quantity_evidence[0]
    if "metadata" in changes:
        changes = {"metadata": {**dict(original.metadata), **changes["metadata"]}}
    forged = replace(original, **changes)
    assert forged.quantity_id == original.quantity_id
    assert forged.evidence_ids == original.evidence_ids
    with pytest.raises(ValueError, match="claim differs from physical source producer"):
        project_live_opening_customer_rows(
            replace(claim, opening_quantity_evidence=(forged,)),
            workspace_id=7, project_id="gpt1-source-replay",
        )


def test_customer_original_canonical_source_area_still_reaches_one_sealed_row():
    from pb_live_opening_customer_projection import project_live_opening_customer_rows
    rows = project_live_opening_customer_rows(
        _physical_original_opening_claim(),
        workspace_id=7, project_id="gpt1-source-replay",
    )
    assert len(rows) == 1
    assert rows[0]["quantity"] == 2.172


def test_customer_replayed_firm_status_does_not_get_customer_row():
    from pb_live_opening_customer_projection import project_live_opening_customer_rows
    claim = _physical_original_opening_claim()
    original = claim.opening_quantity_evidence[0]
    forged = replace(original, status="firm")
    assert project_live_opening_customer_rows(
        replace(claim, opening_quantity_evidence=(forged,)),
        workspace_id=7, project_id="gpt1-source-replay",
    ) == ()
