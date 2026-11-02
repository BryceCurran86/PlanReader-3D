"""Source measurement units must be preserved and validated at both JobHub gates.

These real SQLite-to-customer tests use only synthetic source-neutral rows.
They do not establish an original-PDF FIRM receipt or frozen V2 score gain.
"""
from __future__ import annotations

import sqlite3

import pytest

from pb_jobhub_publishing_contract import PublishingMode, validate_publishing_gate
from pb_jobhub_publishing_pipeline import (
    build_publishing_package_from_workspace,
    execute_jobhub_publishing,
)
from test_gpt3_jobhub_atomic_destination_identity import _approved_package
from test_gpt3_workspace_target_id_ingest import _one_source_neutral_row
from test_publishing_pipeline_e2e import test_dbs  # noqa: F401


@pytest.mark.parametrize("raw_unit", [
    None, "", " ", " \t ", sqlite3.Binary(b"m2"),
])
@pytest.mark.parametrize("mode", [
    PublishingMode.COMMERCIAL, PublishingMode.DRAFT,
])
def test_missing_source_unit_never_becomes_area_or_customer_row(
    test_dbs, raw_unit, mode,
):
    pr, hub, bridge = test_dbs
    _one_source_neutral_row(pr)
    pr.execute("UPDATE takeoff_rows SET unit=? WHERE id=1", (raw_unit,))
    pr.commit()

    package = build_publishing_package_from_workspace(
        pr, workspace_id=1, mode=mode, acting_user="Source Estimator",
    )
    assert len(package.quantities) == 1
    assert package.quantities[0].unit == ""  # No default square metres.
    assert package.payload_hash == package.compute_payload_hash()

    gate = validate_publishing_gate(package)
    assert not gate.is_publishable
    assert any("missing a source measurement unit" in reason
               for reason in gate.blocking_reasons)
    with pytest.raises(RuntimeError, match="missing a source measurement unit"):
        execute_jobhub_publishing(
            package, bridge, user_name="Source Estimator",
        )
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 0
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_package_lines"
    ).fetchone()[0] == 0


@pytest.mark.parametrize("invalid_unit", [
    None, False, True, 0, 1, [], {}, "", " ", "\t\n",
])
@pytest.mark.parametrize("mode", [
    PublishingMode.COMMERCIAL, PublishingMode.DRAFT,
])
def test_self_hashed_caller_cannot_bypass_final_unit_gate(
    test_dbs, invalid_unit, mode,
):
    _, hub, bridge = test_dbs
    package = _approved_package()
    package.mode = mode.value
    package.quantities[0].unit = invalid_unit
    package.payload_hash = package.compute_payload_hash()
    assert package.payload_hash == package.compute_payload_hash()

    gate = validate_publishing_gate(package)
    assert not gate.is_publishable
    assert any("missing a source measurement unit" in reason
               for reason in gate.blocking_reasons)
    with pytest.raises(RuntimeError, match="missing a source measurement unit"):
        execute_jobhub_publishing(
            package, bridge, user_name="Source Estimator",
        )
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 0
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_package_lines"
    ).fetchone()[0] == 0


@pytest.mark.parametrize("unit", [
    "m", "m²", "m2", "kg", "each",
])
@pytest.mark.parametrize(("mode", "expected_status"), [
    (PublishingMode.COMMERCIAL, "Published"),
    (PublishingMode.DRAFT, "Draft"),
])
def test_explicit_units_are_retained_through_real_customer_row(
    test_dbs, unit, mode, expected_status,
):
    pr, hub, bridge = test_dbs
    _one_source_neutral_row(pr)
    pr.execute("UPDATE takeoff_rows SET unit=? WHERE id=1", (unit,))
    pr.commit()
    package = build_publishing_package_from_workspace(
        pr, workspace_id=1, mode=mode, acting_user="Source Estimator",
    )
    assert package.quantities[0].unit == unit
    assert package.payload_hash == package.compute_payload_hash()
    assert validate_publishing_gate(package).is_publishable

    receipt = execute_jobhub_publishing(
        package, bridge, user_name="Source Estimator",
    )
    assert receipt["status"] == expected_status
    rows = hub.execute(
        "SELECT unit FROM painting_takeoff_package_lines"
    ).fetchall()
    assert rows == [(unit,)]


def test_explicit_excluded_scope_can_have_no_source_unit(test_dbs):
    pr, hub, bridge = test_dbs
    _one_source_neutral_row(pr)
    pr.execute(
        "UPDATE takeoff_rows SET unit=NULL, "
        "commercial_authority_status='excluded' WHERE id=1"
    )
    pr.commit()
    package = build_publishing_package_from_workspace(
        pr, workspace_id=1, mode=PublishingMode.DRAFT,
        acting_user="Source Estimator",
    )
    assert package.quantities == []
    assert len(package.excluded_items) == 1
    # Exclusion is not a measured/billable line; no default m² is invented.
    assert not validate_publishing_gate(package).is_publishable
    with pytest.raises(RuntimeError, match="Zero takeoff quantities"):
        execute_jobhub_publishing(
            package, bridge, user_name="Source Estimator",
        )
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 0
