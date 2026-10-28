"""Commercial rate is source-owned, not a defaulted zero on NULL SQL rows.

Real SQLite -> source-sealed SHA -> commercial gate -> JobHub customer.
Synthetic quantities only; no original PDF, FIRM or frozen V2 score claim.
"""
from __future__ import annotations

import pytest

from pb_jobhub_publishing_contract import PublishingMode, validate_publishing_gate
from pb_jobhub_publishing_pipeline import (
    build_publishing_package_from_workspace,
    execute_jobhub_publishing,
)
from test_gpt3_workspace_target_id_ingest import _one_source_neutral_row
from test_publishing_pipeline_e2e import test_dbs  # noqa: F401


@pytest.mark.parametrize("source_total", [None, 0.0, 200.0])
def test_null_rate_cannot_seal_commercial_source_quote(test_dbs, source_total):
    pr, hub, bridge = test_dbs
    _one_source_neutral_row(pr)
    pr.execute(
        "UPDATE takeoff_rows SET rate=NULL,total_price=? WHERE id=1",
        (source_total,),
    )
    pr.commit()
    with pytest.raises(ValueError, match="Missing client commercial unit rate"):
        build_publishing_package_from_workspace(
            pr, workspace_id=1, mode=PublishingMode.COMMERCIAL,
            acting_user="Source Estimator",
        )
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 0
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_package_lines"
    ).fetchone()[0] == 0


@pytest.mark.parametrize(("rate", "amount"), [
    (0.0, 0.0),
    (20.0, 200.0),
    (1.001, 10.01),
])
def test_explicit_price_rate_preserves_real_customer_publishing(
    test_dbs, rate, amount,
):
    pr, hub, bridge = test_dbs
    _one_source_neutral_row(pr)
    pr.execute(
        "UPDATE takeoff_rows SET rate=?,total_price=? WHERE id=1",
        (rate, amount),
    )
    pr.commit()
    package = build_publishing_package_from_workspace(
        pr, workspace_id=1, mode=PublishingMode.COMMERCIAL,
        acting_user="Source Estimator",
    )
    assert package.quantities[0].rate == rate
    assert package.quantities[0].total_price == amount
    assert package.payload_hash == package.compute_payload_hash()
    assert validate_publishing_gate(package).is_publishable
    receipt = execute_jobhub_publishing(
        package, bridge, user_name="Source Estimator",
    )
    assert receipt["status"] == "Published"
    assert tuple(hub.execute(
        "SELECT rate,total_price FROM painting_takeoff_package_lines"
    ).fetchone()) == (rate, amount)


def test_null_rate_remains_draft_provisional_without_commercial_authority(
    test_dbs,
):
    pr, hub, bridge = test_dbs
    _one_source_neutral_row(pr)
    pr.execute(
        "UPDATE takeoff_rows SET commercial_authority_status='provisional', "
        "commercial_authority_source='pdf_scaled',rate=NULL,total_price=NULL "
        "WHERE id=1"
    )
    pr.commit()
    package = build_publishing_package_from_workspace(
        pr, workspace_id=1, mode=PublishingMode.DRAFT,
        acting_user="Source Estimator",
    )
    assert package.quantities[0].rate == 0.0
    assert package.quantities[0].total_price == 0.0
    assert package.payload_hash == package.compute_payload_hash()
    receipt = execute_jobhub_publishing(
        package, bridge, user_name="Source Estimator",
    )
    assert receipt["status"] == "Draft"
    assert hub.execute(
        "SELECT status FROM painting_takeoff_packages"
    ).fetchone()[0] == "Draft"
