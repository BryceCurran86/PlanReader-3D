"""Source workspace selection must use an exact SQLite-owned primary key.

Real SQLite source->sealed package->JobHub consumer tests. Synthetic source rows
are not evidence of original PDF measurements or frozen V2 score improvement.
"""
from __future__ import annotations

import sqlite3
import pytest

from pb_jobhub_publishing_contract import PublishingMode, validate_publishing_gate
from pb_jobhub_publishing_pipeline import (
    build_publishing_package_from_workspace, execute_jobhub_publishing,
)
from test_gpt3_workspace_target_id_ingest import _one_source_neutral_row
from test_publishing_pipeline_e2e import test_dbs  # noqa: F401


@pytest.mark.parametrize("bad_workspace", [
    None, True, False, 1.0, 1.9, 0.0, float("nan"),
    "1", "01", " 1 ", "", "-1", 0, -1, [], {}, [1],
    sqlite3.Binary(b"1"),
])
@pytest.mark.parametrize("mode", [
    PublishingMode.COMMERCIAL, PublishingMode.DRAFT,
])
def test_aliased_or_unproven_workspace_never_reads_source_or_writes_jobhub(
    test_dbs, bad_workspace, mode,
):
    pr, hub, _ = test_dbs
    _one_source_neutral_row(pr)
    statements = []
    pr.set_trace_callback(statements.append)
    try:
        with pytest.raises(ValueError, match="exact positive integer"):
            build_publishing_package_from_workspace(
                pr, bad_workspace, mode=mode, acting_user="Source Estimator",
            )
    finally:
        pr.set_trace_callback(None)
    assert not statements
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 0
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_package_lines"
    ).fetchone()[0] == 0


@pytest.mark.parametrize(("mode", "status"), [
    (PublishingMode.COMMERCIAL, "Published"),
    (PublishingMode.DRAFT, "Draft"),
])
def test_canonical_source_workspace_continues_through_real_consumer(
    test_dbs, mode, status,
):
    pr, hub, bridge = test_dbs
    _one_source_neutral_row(pr)
    pkg = build_publishing_package_from_workspace(
        pr, workspace_id=1, mode=mode, acting_user="Source Estimator",
    )
    assert type(pkg.workspace_id) is int and pkg.workspace_id == 1
    assert pkg.payload_hash == pkg.compute_payload_hash()
    assert validate_publishing_gate(pkg).is_publishable
    receipt = execute_jobhub_publishing(pkg, bridge, user_name="Source Estimator")
    assert receipt["status"] == status
    assert receipt["payload_hash"] == pkg.payload_hash
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 1
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_package_lines"
    ).fetchone()[0] == len(pkg.quantities)
