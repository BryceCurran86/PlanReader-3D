"""Final JobHub writer refuses noncanonical target IDs before opening SQL.

Source-neutral real SQLite consumer coverage. This does not authenticate plans,
measurement, estimator approval, sealed customer receipts or frozen V2 score.
"""
from __future__ import annotations

import pytest

from pb_jobhub_publishing_contract import PublishingMode, validate_publishing_gate
from pb_jobhub_publishing_pipeline import execute_jobhub_publishing
from test_gpt3_jobhub_atomic_destination_identity import _approved_package
from test_publishing_pipeline_e2e import test_dbs  # noqa: F401


def _same_job_number_on_other_job(hub):
    # A second JobHub job may legitimately share a human-facing project
    # number. The *exact* numeric destination ID is therefore authoritative.
    hub.execute(
        "INSERT INTO jobs (id, status, notes, job_no) "
        "VALUES (1, 'Active', 'Separate matching-number job', '26-017')"
    )
    hub.commit()


@pytest.mark.parametrize("bad_id", [
    True, 1.0, "1", "001", 501.0, "501", -1, -501, 1.5,
])
@pytest.mark.parametrize("mode", [
    PublishingMode.COMMERCIAL.value, PublishingMode.DRAFT.value,
])
def test_noncanonical_job_identity_never_opens_destination_or_publishes(
    test_dbs, bad_id, mode,
):
    _, hub, bridge = test_dbs
    _same_job_number_on_other_job(hub)
    package = _approved_package()
    package.mode = mode
    package.project_identity.target_jobhub_job_id = bad_id
    package.payload_hash = package.compute_payload_hash()

    # Existing evidence/amount gate is NOT a runtime target-ID validator.
    # The new assertion belongs immediately before any database write.
    assert validate_publishing_gate(package).is_publishable
    observed = []
    hub.set_trace_callback(observed.append)
    try:
        with pytest.raises(RuntimeError, match="exact positive integer"):
            execute_jobhub_publishing(
                package, bridge, user_name="Source Estimator"
            )
    finally:
        hub.set_trace_callback(None)

    assert not any("FROM jobs" in statement for statement in observed)
    assert not any("INSERT INTO painting_takeoff_" in statement for statement in observed)
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 0
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_package_lines"
    ).fetchone()[0] == 0


@pytest.mark.parametrize("bad_id", [None, False, 0, "", 0.0])
def test_missing_target_identity_preserves_existing_fail_closed_error(test_dbs, bad_id):
    _, hub, bridge = test_dbs
    package = _approved_package()
    package.project_identity.target_jobhub_job_id = bad_id
    package.payload_hash = package.compute_payload_hash()
    with pytest.raises(RuntimeError, match="Target JobHub job ID is required"):
        execute_jobhub_publishing(
            package, bridge, user_name="Source Estimator"
        )
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 0


@pytest.mark.parametrize(("valid_id", "mode", "expected"), [
    (501, PublishingMode.COMMERCIAL.value, "Published"),
    (501, PublishingMode.DRAFT.value, "Draft"),
    (1, PublishingMode.COMMERCIAL.value, "Published"),
])
def test_real_exact_positive_integer_target_still_publishes_to_selected_job(
    test_dbs, valid_id, mode, expected,
):
    _, hub, bridge = test_dbs
    _same_job_number_on_other_job(hub)
    package = _approved_package()
    package.mode = mode
    package.project_identity.target_jobhub_job_id = valid_id
    package.payload_hash = package.compute_payload_hash()
    receipt = execute_jobhub_publishing(
        package, bridge, user_name="Source Estimator"
    )
    assert receipt["status"] == expected
    assert type(receipt["job_id"]) is int
    assert receipt["job_id"] == valid_id
    persisted = hub.execute(
        "SELECT job_id, status FROM painting_takeoff_packages"
    ).fetchall()
    assert persisted == [(valid_id, expected)]
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_package_lines"
    ).fetchone()[0] == 1
