"""JobHub's persisted line must retain the values sealed by PlanReader.

The source-neutral SQLite fixture does not establish original-PDF measurement,
FIRM provenance, customer-release approval or a frozen benchmark score.
"""
from decimal import Decimal, ROUND_HALF_UP

import pytest

from pb_jobhub_publishing_contract import PublishingMode, validate_publishing_gate
from pb_jobhub_publishing_pipeline import (
    build_publishing_package_from_workspace,
    execute_jobhub_publishing,
)
from test_publishing_pipeline_e2e import test_dbs  # noqa: F401


def _commercial_row(conn, quantity, rate, total_price):
    conn.execute(
        """
        INSERT INTO takeoff_rows (
            id, workspace_id, section, location, substrate, finish_tag,
            element, unit, quantity, rate, total_price,
            commercial_authority_status, commercial_authority_source,
            commercial_authority_reviewed_by
        ) VALUES (
            1, 1, 'Internal walls', 'Level 1', 'Plasterboard', 'PB01',
            'Measured wall', 'm2', ?, ?, ?, 'firm', 'documented_dimension',
            'Estimator A'
        )
        """,
        (quantity, rate, total_price),
    )
    conn.commit()


def _sealed_package(conn):
    return build_publishing_package_from_workspace(
        conn,
        1,
        PublishingMode.COMMERCIAL,
        preflight_fingerprint="source-neutral-seal-replay",
        acting_user="Estimator A",
    )


@pytest.mark.parametrize(
    "quantity,rate,total_price",
    [
        (100.0, 0.015, 1.50),       # Valid sub-cent unit rate, cent-exact total
        (0.123456789, 10.0, 1.23), # Source quantity must not lose digits at 4dp
        (2.5, 19.99, 49.98),       # Ordinary cent-rate, half-up payable total
    ],
)
def test_sealed_source_quantity_and_client_rate_survive_real_jobhub_insert(
    test_dbs, quantity, rate, total_price,
):
    planreader, jobhub, bridge = test_dbs
    _commercial_row(planreader, quantity, rate, total_price)
    package = _sealed_package(planreader)
    assert package.payload_hash == package.compute_payload_hash()
    assert validate_publishing_gate(package).is_publishable
    original_payload = package.to_dict()
    sealed_line = package.quantities[0]

    result = execute_jobhub_publishing(package, bridge, "Estimator A")
    assert result["status"] == "Published"
    assert result["total_cost"] == total_price
    stored = jobhub.execute(
        """
        SELECT quantity, rate, total_price
        FROM painting_takeoff_package_lines
        WHERE package_id=?
        """,
        (result["package_id"],),
    ).fetchone()
    assert stored is not None
    # SQLite REAL round-trips the same source float; the writer must not
    # invent a different measured area or customer rate after hashing.
    assert stored[0] == sealed_line.quantity == quantity
    assert stored[1] == sealed_line.rate == rate
    assert stored[2] == sealed_line.total_price == total_price
    assert (
        Decimal(str(stored[0])) * Decimal(str(stored[1]))
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) == Decimal(str(stored[2]))
    assert package.to_dict() == original_payload

    with pytest.raises(RuntimeError, match="Duplicate package"):
        execute_jobhub_publishing(package, bridge, "Estimator A")
    assert jobhub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 1
    assert jobhub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_package_lines"
    ).fetchone()[0] == 1


def test_post_seal_rate_change_cannot_write_any_jobhub_line(test_dbs):
    planreader, jobhub, bridge = test_dbs
    _commercial_row(planreader, 100.0, 0.015, 1.50)
    package = _sealed_package(planreader)
    assert validate_publishing_gate(package).is_publishable
    original_hash = package.payload_hash
    package.quantities[0].rate = 0.02
    assert package.compute_payload_hash() != original_hash

    with pytest.raises(RuntimeError, match="Publishing blocked"):
        execute_jobhub_publishing(package, bridge, "Estimator A")
    assert jobhub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 0
    assert jobhub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_package_lines"
    ).fetchone()[0] == 0
