"""No source-linked job quote can carry forged or inferred client line money."""
from __future__ import annotations

from copy import deepcopy

import pytest

from pb_jobhub_publishing_contract import PublishingMode, validate_publishing_gate
from pb_jobhub_publishing_pipeline import build_publishing_package_from_workspace, execute_jobhub_publishing
from test_commercial_identity_default_safety import _minimal_commercial_package
from test_publishing_pipeline_e2e import test_dbs


def _approved():
    return _minimal_commercial_package(
        estimator="Estimator A", created_by="Estimator A",
        approved_by="Estimator A",
    )


@pytest.mark.parametrize(("quantity", "rate", "amount"), [
    (10.0, 5.0, 500.0),
    (13.270425, 150.0, 1990.57),
    (10.0, 5.0, 0.0),
    (10.0, 0.0, 15.0),
    (10.0, 1.001, 10.01),
    (10.0, 5.0, 50.001),
    (1e308, 1e308, 1e308),
])
def test_rehashed_quote_financial_mismatch_is_blocked_even_with_firm_geometry(
    quantity, rate, amount,
):
    pkg = _approved()
    line = pkg.quantities[0]
    line.quantity = quantity
    line.rate = rate
    line.total_price = amount
    pkg.payload_hash = pkg.compute_payload_hash()
    result = validate_publishing_gate(pkg)
    assert not result.is_publishable
    assert any("commercial line cost disagrees" in x for x in result.blocking_reasons)


def test_six_decimal_source_area_with_cent_rounded_customer_rate_is_valid():
    pkg = _approved()
    line = pkg.quantities[0]
    line.quantity = 13.270425
    line.rate = 150.0
    line.total_price = 1990.56
    pkg.payload_hash = pkg.compute_payload_hash()
    assert validate_publishing_gate(pkg).is_publishable


def test_exact_signed_count_and_rate_reproduce_customer_total():
    pkg = _approved()
    line = pkg.quantities[0]
    line.quantity = 3.0
    line.unit = "ea"
    line.rate = 210.0
    line.total_price = 630.0
    pkg.payload_hash = pkg.compute_payload_hash()
    assert validate_publishing_gate(pkg).is_publishable


def test_commercial_missing_client_price_is_not_computed_implicitly(test_dbs):
    local, hub, bridge = test_dbs
    local.execute("""
        INSERT INTO takeoff_rows (
            id,workspace_id,section,location,substrate,finish_tag,
            element,unit,quantity,rate,total_price,
            commercial_authority_status,commercial_authority_source,
            commercial_authority_reviewed_by
        ) VALUES (
            1,1,'Walls','Unit 1','PB','PB01','Wall','m2',10,12,NULL,
            'firm','documented_dimension','Estimator A'
        )
    """)
    with pytest.raises(ValueError, match="Missing client commercial line total"):
        build_publishing_package_from_workspace(
            local, 1, PublishingMode.COMMERCIAL, acting_user="Estimator A",
        )
    assert hub.execute("SELECT COUNT(*) FROM painting_takeoff_packages").fetchone()[0] == 0


def test_client_zero_price_remains_zero_and_cannot_be_automatically_repriced(test_dbs):
    local, hub, bridge = test_dbs
    local.execute("""
        INSERT INTO takeoff_rows (
            id,workspace_id,section,location,substrate,finish_tag,
            element,unit,quantity,rate,total_price,
            commercial_authority_status,commercial_authority_source,
            commercial_authority_reviewed_by
        ) VALUES (
            1,1,'Walls','Unit 1','PB','PB01','Wall','m2',10,12,0,
            'firm','documented_dimension','Estimator A'
        )
    """)
    pkg = build_publishing_package_from_workspace(
        local, 1, PublishingMode.COMMERCIAL, acting_user="Estimator A",
    )
    assert pkg.quantities[0].total_price == 0.0
    assert not validate_publishing_gate(pkg).is_publishable
    with pytest.raises(RuntimeError, match="Publishing blocked"):
        execute_jobhub_publishing(pkg, bridge, "Estimator A")
    assert hub.execute("SELECT COUNT(*) FROM painting_takeoff_packages").fetchone()[0] == 0


def test_provisional_draft_can_show_nonauthoritative_computed_estimate(test_dbs):
    local, hub, bridge = test_dbs
    local.execute("""
        INSERT INTO takeoff_rows (
            id,workspace_id,section,location,substrate,finish_tag,
            element,unit,quantity,rate,total_price,
            commercial_authority_status,commercial_authority_source
        ) VALUES (
            1,1,'Walls','Unit 1','PB','PB01','Wall','m2',10,12,NULL,
            'provisional','pdf_scaled'
        )
    """)
    pkg = build_publishing_package_from_workspace(
        local, 1, PublishingMode.DRAFT,
    )
    assert pkg.quantities[0].total_price == 120.0
    assert validate_publishing_gate(pkg).is_publishable
