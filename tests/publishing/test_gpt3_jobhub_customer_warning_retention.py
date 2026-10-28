"""Source-owned commercial and draft warnings reach actual JobHub customer rows.

Real SQLite recipient retention tests, not original PDF or frozen V2 source proof.
"""
import json
from copy import deepcopy

import pytest

from pb_jobhub_publishing_contract import (
    PublishingMode, PublishingWarningPayload, validate_publishing_gate,
)
from pb_jobhub_publishing_pipeline import execute_jobhub_publishing
from test_gpt3_jobhub_atomic_destination_identity import _approved_package
from test_publishing_pipeline_e2e import test_dbs  # noqa: F401


def _notes_and_lines(conn):
    row = conn.execute(
        "SELECT notes FROM painting_takeoff_packages"
    ).fetchone()
    count = conn.execute(
        "SELECT COUNT(*) FROM painting_takeoff_package_lines"
    ).fetchone()[0]
    return row[0] if row else None, count


def _warning_json(notes):
    return json.loads(notes.split(" | Gate warnings: ", 1)[1])


def test_info_source_warning_survives_real_commercial_destination(test_dbs):
    _, hub, bridge = test_dbs
    package = _approved_package()
    package.warnings.append(PublishingWarningPayload(
        code="CLIENT_MATERIAL_RATE_NOTE", severity="Info",
        message="Rate includes separately quoted trim allowance",
    ))
    package.payload_hash = package.compute_payload_hash()
    gate = validate_publishing_gate(package)
    assert gate.is_publishable
    assert gate.warnings
    before = deepcopy(package.to_dict())
    receipt = execute_jobhub_publishing(package, bridge, "Approved Publisher")
    notes, lines = _notes_and_lines(hub)
    assert receipt["status"] == "Published"
    assert lines == len(package.quantities)
    assert _warning_json(notes) == sorted(gate.warnings)
    assert receipt["warnings"] == sorted(gate.warnings)
    assert package.payload_hash in notes
    assert "Published by Approved Publisher" in notes
    assert "Package creator: Source Estimator" in notes
    assert package.to_dict() == before
    with pytest.raises(RuntimeError, match="Duplicate package"):
        execute_jobhub_publishing(package, bridge, "Approved Publisher")


def test_draft_retains_original_critical_and_provisional_review_notices(test_dbs):
    _, hub, bridge = test_dbs
    package = _approved_package()
    package.mode = PublishingMode.DRAFT.value
    package.warnings.append(PublishingWarningPayload(
        code="SOURCE_BOUNDARY_MISSING", severity="Critical",
        message="Original wall closure has not been authenticated",
    ))
    package.quantities[0].authority_status = "provisional"
    package.quantities[0].notes = "Await original scale verification"
    package.payload_hash = package.compute_payload_hash()
    gate = validate_publishing_gate(package)
    assert gate.is_publishable
    assert any("SOURCE_BOUNDARY_MISSING" in note for note in gate.warnings)
    assert any("Draft notice:" in note for note in gate.warnings)
    receipt = execute_jobhub_publishing(package, bridge, "Draft Publisher")
    notes, lines = _notes_and_lines(hub)
    assert receipt["status"] == "Draft"
    assert lines == len(package.quantities)
    assert _warning_json(notes) == sorted(gate.warnings)
    assert receipt["warnings"] == sorted(gate.warnings)


def test_clean_publish_preserves_legacy_notes_without_empty_warning_field(test_dbs):
    _, hub, bridge = test_dbs
    package = _approved_package()
    assert not validate_publishing_gate(package).warnings
    receipt = execute_jobhub_publishing(package, bridge, "Publisher")
    notes, _ = _notes_and_lines(hub)
    assert "Gate warnings:" not in notes
    assert receipt["warnings"] == []
    assert package.payload_hash in notes


def test_blocker_source_warning_rejects_before_any_customer_connection(test_dbs):
    _, hub, _ = test_dbs
    package = _approved_package()
    package.warnings.append(PublishingWarningPayload(
        code="NO_ORIGINAL_QUANTITY", severity="Blocker",
        message="Measured floor remains unauthenticated",
    ))
    package.payload_hash = package.compute_payload_hash()
    assert not validate_publishing_gate(package).is_publishable

    class NeverConnect:
        def connect(self):
            raise AssertionError("Blocked source reached customer database")

    with pytest.raises(RuntimeError, match="Unresolved commercial source issue"):
        execute_jobhub_publishing(package, NeverConnect(), "Publisher")
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 0


def test_warn_order_in_existing_seal_is_canonical_in_customer_notes(test_dbs):
    _, hub, bridge = test_dbs
    package = _approved_package()
    first = PublishingWarningPayload(
        code="Z_NOTE", severity="Info", message="The second note",
    )
    second = PublishingWarningPayload(
        code="A_NOTE", severity="Warning", message="The first note",
    )
    package.warnings.extend([first, second, first])
    original = deepcopy(package)
    package.payload_hash = package.compute_payload_hash()
    original.warnings = list(reversed(original.warnings))
    original.payload_hash = original.compute_payload_hash()
    # Existing #4077 full-evidence hash canonicalizes warning collection order.
    assert package.payload_hash == original.payload_hash
    expected = sorted(validate_publishing_gate(original).warnings)
    receipt = execute_jobhub_publishing(package, bridge, "Publisher")
    notes, _ = _notes_and_lines(hub)
    assert receipt["warnings"] == expected
    assert _warning_json(notes) == expected
    assert len(expected) == 3
