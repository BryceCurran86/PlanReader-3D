"""An invalid or unproven signed takeoff must never become a JobHub commercial job."""
from __future__ import annotations

from copy import deepcopy

import pytest

from pb_geometry_takeoff_model import MeasurementAuthorityType, AuthorityStatus
from pb_jobhub_publishing_contract import (
    PublishingMode, validate_publishing_gate,
)
from pb_jobhub_publishing_pipeline import (
    build_publishing_package_from_workspace, execute_jobhub_publishing,
)
from test_publishing_pipeline_e2e import test_dbs
from test_commercial_identity_default_safety import _minimal_commercial_package


def _approved():
    return _minimal_commercial_package(
        estimator="Source Estimator",
        created_by="Source Estimator",
        approved_by="Source Estimator",
    )


def test_previous_override_argument_cannot_publish_even_valid_package_without_gate(test_dbs):
    _, hub, bridge = test_dbs
    package = _approved()
    package.project_identity.target_jobhub_job_id = 501
    with pytest.raises(RuntimeError, match="override is prohibited"):
        execute_jobhub_publishing(
            package, bridge, user_name="Source Estimator",
            override_preflight_check=True,
        )
    assert hub.execute("SELECT COUNT(*) FROM painting_takeoff_packages").fetchone()[0] == 0


def test_old_schema_missing_authority_cannot_become_firm(test_dbs):
    local, hub, bridge = test_dbs
    local.executescript("""
        DROP TABLE takeoff_rows;
        CREATE TABLE takeoff_rows (
            id INTEGER PRIMARY KEY, workspace_id INTEGER, section TEXT,
            location TEXT, substrate TEXT, element TEXT, unit TEXT,
            quantity REAL, rate REAL, total_price REAL
        );
        INSERT INTO takeoff_rows VALUES (
            1,1,'Walls','Unit 1','Plasterboard','Internal Wall',
            'm2',120,10,1200
        );
    """)
    package = build_publishing_package_from_workspace(
        local, 1, PublishingMode.COMMERCIAL,
        acting_user="Source Estimator",
    )
    assert package.quantities[0].authority_status == "provisional"
    assert package.quantities[0].authority_type == "provisional"
    assert validate_publishing_gate(package).is_publishable is False
    with pytest.raises(RuntimeError, match="Publishing blocked"):
        execute_jobhub_publishing(package, bridge, user_name="Source Estimator")
    assert hub.execute("SELECT COUNT(*) FROM painting_takeoff_packages").fetchone()[0] == 0


def test_present_but_null_source_authority_can_never_default_to_firm(test_dbs):
    local, hub, bridge = test_dbs
    local.execute("""
        INSERT INTO takeoff_rows (
            id,workspace_id,section,location,substrate,finish_tag,
            element,unit,quantity,rate,total_price,
            commercial_authority_status,commercial_authority_source
        ) VALUES (1,1,'Walls','Unit 1','PB','PB01','Wall','m2',10,12,120,NULL,NULL)
    """)
    package = build_publishing_package_from_workspace(
        local, 1, PublishingMode.COMMERCIAL, acting_user="Source Estimator",
    )
    assert package.quantities[0].authority_status == "provisional"
    assert package.quantities[0].authority_type == "provisional"
    assert not validate_publishing_gate(package).is_publishable
    with pytest.raises(RuntimeError, match="Publishing blocked"):
        execute_jobhub_publishing(package, bridge, "Source Estimator")
    assert hub.execute("SELECT COUNT(*) FROM painting_takeoff_packages").fetchone()[0] == 0


@pytest.mark.parametrize(("status", "source"), [
    ("blocked", "documented_dimension"),
    ("excluded", "documented_dimension"),
    ("reference_only", "documented_dimension"),
    ("invented", "documented_dimension"),
    ("firm", "unknown_source"),
    ("firm", "provisional"),
    ("firm", "excluded"),
    ("firm", "reference_only"),
    ("firm", "pdf_scaled"),
])
def test_claimed_firm_or_unrecognised_source_cannot_bypass_commercial_gate(
    status, source,
):
    package = _approved()
    row = package.quantities[0]
    row.authority_status = status
    row.authority_type = source
    if source == "pdf_scaled":
        row.approved_by = None
    package.payload_hash = package.compute_payload_hash()
    outcome = validate_publishing_gate(package)
    assert not outcome.is_publishable
    assert outcome.blocking_reasons


@pytest.mark.parametrize("qty", [0.0, -1.0])
def test_empty_or_negative_physical_quantity_cannot_enter_commercial_job(qty):
    package = _approved()
    package.quantities[0].quantity = qty
    package.payload_hash = package.compute_payload_hash()
    outcome = validate_publishing_gate(package)
    assert not outcome.is_publishable


def test_unknown_publishing_mode_never_inherits_draft_allowance():
    package = _approved()
    package.mode = "commercial_without_checks"
    package.payload_hash = package.compute_payload_hash()
    result = validate_publishing_gate(package)
    assert not result.is_publishable
    assert any("Unsupported publishing mode" in reason for reason in result.blocking_reasons)


def test_customer_approved_quantity_must_identify_human_approver():
    package = _approved()
    package.quantities[0].authority_status = AuthorityStatus.USER_APPROVED.value
    package.quantities[0].approved_by = None
    package.payload_hash = package.compute_payload_hash()
    assert not validate_publishing_gate(package).is_publishable


def test_draft_stays_draft_and_records_provisional_rows(test_dbs):
    local, hub, bridge = test_dbs
    local.execute("""
        INSERT INTO takeoff_rows (
            id,workspace_id,section,location,substrate,finish_tag,
            element,unit,quantity,rate,total_price,
            commercial_authority_status,commercial_authority_source
        ) VALUES (1,1,'Walls','Unit 1','PB','PB01','Wall','m2',
                  10,12,120,'provisional','pdf_scaled')
    """)
    pkg = build_publishing_package_from_workspace(
        local, 1, PublishingMode.DRAFT,
    )
    receipt = execute_jobhub_publishing(pkg, bridge, user_name="Source Estimator")
    assert receipt["status"] == "Draft"
    assert hub.execute("SELECT status FROM painting_takeoff_packages").fetchone()[0] == "Draft"


def test_original_firm_documented_takeoff_still_publishes_without_override(test_dbs):
    local, hub, bridge = test_dbs
    local.execute("""
        INSERT INTO takeoff_rows (
            id,workspace_id,section,location,substrate,finish_tag,
            element,unit,quantity,rate,total_price,
            commercial_authority_status,commercial_authority_source,
            commercial_authority_reviewed_by
        ) VALUES (1,1,'Walls','Unit 1','PB','PB01','Wall','m2',
                  10,12,120,'firm','documented_dimension','Source Estimator')
    """)
    pkg = build_publishing_package_from_workspace(
        local, 1, PublishingMode.COMMERCIAL, acting_user="Source Estimator",
    )
    assert validate_publishing_gate(pkg).is_publishable
    receipt = execute_jobhub_publishing(pkg, bridge, "Source Estimator")
    assert receipt["status"] == "Published"
    assert receipt["total_cost"] == 120.0


def test_source_proven_jobhub_numeric_id_but_wrong_job_number_cannot_publish(test_dbs):
    local, hub, bridge = test_dbs
    local.execute("""
        INSERT INTO takeoff_rows (
            id,workspace_id,section,location,substrate,finish_tag,
            element,unit,quantity,rate,total_price,
            commercial_authority_status,commercial_authority_source,
            commercial_authority_reviewed_by
        ) VALUES (1,1,'Walls','Unit 1','PB','PB01','Wall','m2',
                  10,12,120,'firm','documented_dimension','Source Estimator')
    """)
    pkg = build_publishing_package_from_workspace(
        local, 1, PublishingMode.COMMERCIAL, acting_user="Source Estimator",
    )
    assert validate_publishing_gate(pkg).is_publishable
    hub.execute("UPDATE jobs SET job_no='DIFFERENT-JOB' WHERE id=501")
    with pytest.raises(RuntimeError, match="target job number conflicts"):
        execute_jobhub_publishing(pkg, bridge, "Source Estimator")
    assert hub.execute("SELECT COUNT(*) FROM painting_takeoff_packages").fetchone()[0] == 0


def test_provisional_jobhub_export_cannot_leak_to_different_project(test_dbs):
    local, hub, bridge = test_dbs
    local.execute("""
        INSERT INTO takeoff_rows (
            id,workspace_id,section,location,substrate,finish_tag,
            element,unit,quantity,rate,total_price,
            commercial_authority_status,commercial_authority_source
        ) VALUES (1,1,'Walls','Unit 1','PB','PB01','Wall','m2',
                  10,12,120,'provisional','pdf_scaled')
    """)
    pkg = build_publishing_package_from_workspace(
        local, 1, PublishingMode.DRAFT,
    )
    hub.execute("UPDATE jobs SET job_no='OTHER-SITE' WHERE id=501")
    with pytest.raises(RuntimeError, match="target job number conflicts"):
        execute_jobhub_publishing(pkg, bridge, "Source Estimator")
    assert hub.execute("SELECT COUNT(*) FROM painting_takeoff_packages").fetchone()[0] == 0


def test_job_number_missing_from_jobhub_target_cannot_be_accepted(test_dbs):
    local, hub, bridge = test_dbs
    local.execute("""
        INSERT INTO takeoff_rows (
            id,workspace_id,section,location,substrate,finish_tag,
            element,unit,quantity,rate,total_price,
            commercial_authority_status,commercial_authority_source,
            commercial_authority_reviewed_by
        ) VALUES (1,1,'Walls','Unit 1','PB','PB01','Wall','m2',
                  10,12,120,'firm','documented_dimension','Source Estimator')
    """)
    pkg = build_publishing_package_from_workspace(
        local, 1, PublishingMode.COMMERCIAL, acting_user="Source Estimator",
    )
    hub.execute("UPDATE jobs SET job_no=NULL WHERE id=501")
    with pytest.raises(RuntimeError, match="target job number conflicts"):
        execute_jobhub_publishing(pkg, bridge, "Source Estimator")
    assert hub.execute("SELECT COUNT(*) FROM painting_takeoff_packages").fetchone()[0] == 0
