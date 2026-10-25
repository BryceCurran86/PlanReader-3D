"""Source-neutral opening commercial-output nondropping integrity checks.

Synthetic PDF fixture only; no original client PDF, frozen gold or benchmark inputs.
"""
from dataclasses import replace

import pytest

from pb_live_opening_customer_projection import project_live_opening_customer_rows
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from tests.test_live_opening_customer_projection import _opening_pdf


@pytest.fixture
def claim(tmp_path):
    pdf = tmp_path / "synthetic-positive-opening.pdf"
    pdf.write_bytes(_opening_pdf())
    result = collect_live_physical_net_wall_claim(pdf, pages=(0,))
    assert len(result.opening_quantity_evidence) == 1
    assert result.opening_quantity_evidence[0].blocking_reasons == ()
    assert result.opening_quantity_evidence[0].metadata["commercial_projection_allowed"] is True
    return result


def project(value):
    return project_live_opening_customer_rows(
        value, workspace_id=17, project_id="customer-workspace:17",
    )


@pytest.mark.parametrize("position", ["only", "before_good", "after_good"])
def test_publishable_positive_area_with_blocker_is_not_silently_omitted(claim, position):
    original = claim.opening_quantity_evidence[0]
    blocked = replace(
        original,
        quantity_id="source-positive-blocked-area",
        blocking_reasons=("stale_original_source_receipt",),
    )
    if position == "only":
        items = (blocked,)
    elif position == "before_good":
        items = (blocked, original)
    else:
        items = (original, blocked)
    mutated = replace(claim, opening_quantity_evidence=items)
    with pytest.raises(ValueError, match="positive source quantity retains blocking"):
        project(mutated)
    assert len(project(claim)) == 1
    assert original.blocking_reasons == ()


@pytest.mark.parametrize("position", ["only", "before_good", "after_good"])
def test_publishable_firm_count_with_blocker_is_not_silently_omitted(claim, position):
    original = claim.opening_quantity_evidence[0]
    count = replace(
        original,
        quantity_id="source-positive-blocked-count",
        family="opening_count",
        status="firm",
        unit="ea",
        value=1,
        blocking_reasons=("source_member_conflict",),
        metadata={
            **dict(original.metadata),
            "schedule_corroborated": True,
            "opening_mark": "W1",
            "commercial_projection_allowed": True,
        },
    )
    if position == "only":
        area = ()
        counts = (count,)
    elif position == "before_good":
        area = (original,)
        counts = (count,)
    else:
        area = (original,)
        counts = (count,)
    mutated = replace(
        claim,
        opening_quantity_evidence=area,
        opening_count_quantity_evidence=counts,
    )
    with pytest.raises(ValueError, match="positive source quantity retains blocking"):
        project(mutated)
    assert len(project(claim)) == 1


def test_legitimate_abstained_and_noncommercial_shadows_are_still_filtered(claim):
    original = claim.opening_quantity_evidence[0]
    abstained = replace(
        original, quantity_id="source-abstained-opening", abstained=True,
        value=None, blocking_reasons=("unknown_physical_host",),
    )
    shadow = replace(
        original, quantity_id="source-unpublished-opening",
        blocking_reasons=("unpublished_measurement_shadow",),
        metadata={**dict(original.metadata), "commercial_projection_allowed": False},
    )
    # Source-owned ABSTAIN never blocks a separate true positive, and
    # noncommercial shadows never become customer rows on their own.
    with_abstention = replace(claim, opening_quantity_evidence=(abstained, original))
    rows = project(with_abstention)
    assert len(rows) == 1
    assert rows[0]["origin"] == "AI"
    only_noncommercial = replace(
        claim, opening_quantity_evidence=(abstained, shadow),
    )
    assert project(only_noncommercial) == ()
    assert len(project(claim)) == 1
