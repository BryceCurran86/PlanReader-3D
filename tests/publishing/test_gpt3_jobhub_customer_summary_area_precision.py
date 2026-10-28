"""Real SQLite consumer regression for full-precision sealed customer area totals.

The synthetic source-neutral rows do NOT prove original-PDF FIRM authority,
customer release, original eight/nine replay or a frozen V2 score.
"""
import math

import pytest

from pb_jobhub_publishing_contract import PublishingMode, validate_publishing_gate
from pb_jobhub_publishing_pipeline import (
    build_publishing_package_from_workspace,
    execute_jobhub_publishing,
)
from test_publishing_pipeline_e2e import test_dbs  # noqa: F401


def _insert_rows(conn, rows, *, firm=True):
    for row_id, section, unit, quantity, rate, total_price in rows:
        conn.execute(
            """
            INSERT INTO takeoff_rows (
                id, workspace_id, section, location, substrate, finish_tag,
                element, unit, quantity, rate, total_price,
                commercial_authority_status, commercial_authority_source,
                commercial_authority_reviewed_by
            ) VALUES (?, 1, ?, 'Level 1', 'Plasterboard', 'PB01',
                      'Measured area', ?, ?, ?, ?, ?, ?, 'Estimator A')
            """,
            (
                row_id, section, unit, quantity, rate, total_price,
                "firm" if firm else "provisional",
                "documented_dimension" if firm else "pdf_scaled",
            ),
        )
    conn.commit()


def _package(conn, *, mode=PublishingMode.COMMERCIAL):
    return build_publishing_package_from_workspace(
        conn,
        1,
        mode,
        preflight_fingerprint="source-neutral-customer-area-replay",
        acting_user="Estimator A",
    )


def _stored_customer_areas(jobhub, package_id):
    return jobhub.execute(
        """
        SELECT interior_m2, exterior_m2
        FROM painting_takeoff_packages WHERE id=?
        """,
        (package_id,),
    ).fetchone()


def test_subcent_source_area_is_not_erased_from_customer_header(test_dbs):
    planreader, jobhub, bridge = test_dbs
    _insert_rows(planreader, [(1, "Internal walls", "m2", 0.004, 250.0, 1.00)])
    package = _package(planreader)
    assert validate_publishing_gate(package).is_publishable
    assert package.quantities[0].quantity == 0.004

    result = execute_jobhub_publishing(package, bridge, "Estimator A")
    assert result["status"] == "Published"
    assert result["interior_m2"] == 0.004
    assert result["exterior_m2"] == 0.0
    assert tuple(_stored_customer_areas(jobhub, result["package_id"])) == (0.004, 0.0)
    stored_line = jobhub.execute(
        "SELECT quantity, total_price FROM painting_takeoff_package_lines WHERE package_id=?",
        (result["package_id"],),
    ).fetchone()
    assert stored_line == (0.004, 1.0)
    assert result["total_cost"] == 1.0

    with pytest.raises(RuntimeError, match="Duplicate package"):
        execute_jobhub_publishing(package, bridge, "Estimator A")
    assert jobhub.execute("SELECT COUNT(*) FROM painting_takeoff_packages").fetchone()[0] == 1


@pytest.mark.parametrize("reverse_input", [False, True])
def test_mixed_sealed_areas_reconcile_to_jobhub_lines_without_rounding(
    test_dbs, reverse_input,
):
    planreader, jobhub, bridge = test_dbs
    rows = [
        (1, "Internal walls", "m2", 0.123456789, 10.0, 1.23),
        (2, "Interior ceilings", "m²", 0.004, 250.0, 1.00),
        (3, "External facade", "sqm", 0.987654321, 10.0, 9.88),
        (4, "Internal External walls", "m2", 2.0, 10.0, 20.00),
        (5, "Internal walls", "m", 5.0, 10.0, 50.00),
        (6, "Wall panels", "m2", 0.001, 1000.0, 1.00),
    ]
    _insert_rows(planreader, list(reversed(rows)) if reverse_input else rows)
    package = _package(planreader)
    assert validate_publishing_gate(package).is_publishable
    original_seal = package.payload_hash
    if reverse_input:
        package.quantities.reverse()
    # Quantity insertion order is not source/customer authority: hash sorts by row_id.
    assert package.compute_payload_hash() == original_seal
    before = package.to_dict()

    result = execute_jobhub_publishing(package, bridge, "Estimator A")
    expected_internal = math.fsum([0.123456789, 0.004, 0.001])
    expected_external = 0.987654321
    assert result["interior_m2"] == expected_internal
    assert result["exterior_m2"] == expected_external
    assert tuple(_stored_customer_areas(jobhub, result["package_id"])) == (
        expected_internal, expected_external,
    )
    assert package.to_dict() == before
    line_values = jobhub.execute(
        "SELECT quantity FROM painting_takeoff_package_lines WHERE package_id=?",
        (result["package_id"],),
    ).fetchall()
    assert sorted(x[0] for x in line_values) == sorted(row[3] for row in rows)
    assert result["total_cost"] == 83.11
    # The ambiguous interior+exterior line and the non-area unit remain
    # visible as full customer lines, but do not gain a summary bucket.
    assert expected_internal != math.fsum(row[3] for row in rows if row[2] in ("m2", "m²", "sqm"))


def test_postseal_area_mutation_blocks_all_customer_writes(test_dbs):
    planreader, jobhub, bridge = test_dbs
    _insert_rows(planreader, [(1, "Internal walls", "m2", 0.004, 250.0, 1.00)])
    package = _package(planreader)
    original_hash = package.payload_hash
    package.quantities[0].quantity = 0.005
    assert package.compute_payload_hash() != original_hash

    with pytest.raises(RuntimeError, match="Publishing blocked"):
        execute_jobhub_publishing(package, bridge, "Estimator A")
    assert jobhub.execute("SELECT COUNT(*) FROM painting_takeoff_packages").fetchone()[0] == 0
    assert jobhub.execute("SELECT COUNT(*) FROM painting_takeoff_package_lines").fetchone()[0] == 0


def test_draft_area_summary_retains_precision_without_minting_firm(test_dbs):
    planreader, jobhub, bridge = test_dbs
    _insert_rows(
        planreader, [(1, "Internal walls", "m2", 0.004, 250.0, 1.00)],
        firm=False,
    )
    package = _package(planreader, mode=PublishingMode.DRAFT)
    assert package.quantities[0].authority_status == "provisional"
    gate = validate_publishing_gate(package)
    assert gate.is_publishable
    assert gate.warnings

    result = execute_jobhub_publishing(package, bridge, "Estimator A")
    assert result["status"] == "Draft"
    assert result["interior_m2"] == 0.004
    assert tuple(_stored_customer_areas(jobhub, result["package_id"])) == (0.004, 0.0)
