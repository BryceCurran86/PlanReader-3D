"""GPT3: JobHub exterior wall quantities cannot be silently sold as interior.

Source-neutral real SQLite publishing consumer checks. These tests do not
authenticate an original plan, signed customer rows or frozen V2 accuracy.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_jobhub_publishing_contract import PublishingMode, validate_publishing_gate
from pb_jobhub_publishing_pipeline import execute_jobhub_publishing
from test_gpt3_jobhub_atomic_destination_identity import _approved_package
from test_publishing_pipeline_e2e import test_dbs  # noqa: F401


@pytest.mark.parametrize(("section", "interior", "exterior"), [
    ("External Walls", 0.0, 10.0),
    ("Exterior Wall", 0.0, 10.0),
    ("Facade Wall", 0.0, 10.0),
    ("Façade Wall", 0.0, 10.0),
    ("Elevation Walls", 0.0, 10.0),
    ("External Soffit", 0.0, 10.0),
    ("Internal Walls", 10.0, 0.0),
    ("Interior Wall", 10.0, 0.0),
    ("Ceiling", 10.0, 0.0),
    ("Walls", 10.0, 0.0),  # preserve legacy unqualified wall bucket
    ("Internal / External Walls", 0.0, 0.0),  # conflicting scope abstains
    ("Internal Soffit", 0.0, 0.0),
    ("Unclassified Floor", 0.0, 0.0),
])
def test_actual_customer_jobhub_area_totals_do_not_misclassify_external_walls(
    test_dbs, section, interior, exterior,
):
    _, hub, bridge = test_dbs
    package = _approved_package()
    package.quantities[0].section = section
    package.payload_hash = package.compute_payload_hash()
    assert validate_publishing_gate(package).is_publishable
    receipt = execute_jobhub_publishing(
        package, bridge, user_name="Source Estimator"
    )
    assert receipt["interior_m2"] == interior
    assert receipt["exterior_m2"] == exterior
    persisted = hub.execute(
        "SELECT interior_m2, exterior_m2 FROM painting_takeoff_packages"
    ).fetchone()
    assert tuple(persisted) == (interior, exterior)
    assert hub.execute(
        "SELECT COUNT(*), SUM(quantity) FROM painting_takeoff_package_lines"
    ).fetchone() == (1, 10.0)


@pytest.mark.parametrize("reversed_order", [False, True])
@pytest.mark.parametrize("mode", [
    PublishingMode.COMMERCIAL.value,
    PublishingMode.DRAFT.value,
])
def test_mixed_internal_and_external_wall_package_preserves_each_bucket(
    test_dbs, reversed_order, mode,
):
    _, hub, bridge = test_dbs
    package = _approved_package()
    package.mode = mode
    interior = package.quantities[0]
    interior.section = "Internal Walls"
    external = replace(
        interior,
        row_id=2,
        section="External Walls",
        quantity=7.0,
        total_price=7.0,
    )
    package.quantities = [interior, external]
    if reversed_order:
        package.quantities.reverse()
    package.payload_hash = package.compute_payload_hash()
    assert validate_publishing_gate(package).is_publishable
    receipt = execute_jobhub_publishing(
        package, bridge, user_name="Source Estimator"
    )
    assert receipt["interior_m2"] == 10.0
    assert receipt["exterior_m2"] == 7.0
    assert receipt["total_lines"] == 2
    assert receipt["total_cost"] == 17.0
    assert hub.execute(
        "SELECT interior_m2, exterior_m2 FROM painting_takeoff_packages"
    ).fetchone() == (10.0, 7.0)
    assert hub.execute(
        "SELECT COUNT(*), SUM(quantity) FROM painting_takeoff_package_lines"
    ).fetchone() == (2, 17.0)
