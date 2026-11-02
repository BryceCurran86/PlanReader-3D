"""Real SQLite JobHub recipient tests for separated sealed creator/delivery actor.
Source-neutral synthetic rows are NOT original source or frozen V2 score proof.
"""
import pytest

from pb_jobhub_publishing_contract import PublishingMode, validate_publishing_gate
from pb_jobhub_publishing_pipeline import execute_jobhub_publishing
from test_gpt3_jobhub_atomic_destination_identity import _approved_package
from test_publishing_pipeline_e2e import test_dbs  # noqa: F401


class _NeverConnect:
    """Invalid actor or changed source seal must fail before destination access."""

    def connect(self):
        raise AssertionError("Invalid publisher reached JobHub database")


def _stored_actor_and_notes(hub):
    return hub.execute(
        "SELECT created_by, notes FROM painting_takeoff_packages"
    ).fetchone()


def test_distinct_delegated_publisher_retains_source_creator_and_full_seal(test_dbs):
    _, hub, bridge = test_dbs
    package = _approved_package()
    assert package.created_by == "Source Estimator"
    assert validate_publishing_gate(package).is_publishable
    old_hash = package.payload_hash
    before = package.to_dict()

    result = execute_jobhub_publishing(package, bridge, "Release Approver")
    actor, notes = _stored_actor_and_notes(hub)
    assert actor == "Release Approver"
    assert "Published by Release Approver" in notes
    assert "Package creator: Source Estimator" in notes
    assert "Payload: " + old_hash in notes
    assert result["payload_hash"] == old_hash
    assert package.to_dict() == before
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_package_lines"
    ).fetchone()[0] == len(package.quantities)

    # Another delivery actor does not mint a new physical source package.
    with pytest.raises(RuntimeError, match="Duplicate package"):
        execute_jobhub_publishing(package, bridge, "Other Approver")
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 1


@pytest.mark.parametrize("actor", [None, "", "   ", "\t\n", 0, True])
@pytest.mark.parametrize("mode", [
    PublishingMode.COMMERCIAL.value, PublishingMode.DRAFT.value,
])
def test_missing_delivery_actor_blocks_before_any_customer_database_access(
    test_dbs, actor, mode,
):
    _, hub, _ = test_dbs
    package = _approved_package()
    package.mode = mode
    package.payload_hash = package.compute_payload_hash()
    assert validate_publishing_gate(package).is_publishable
    with pytest.raises(RuntimeError, match="named delivery actor"):
        execute_jobhub_publishing(package, _NeverConnect(), actor)
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 0


def test_publisher_outer_whitespace_is_not_persisted_as_another_identity(test_dbs):
    _, hub, bridge = test_dbs
    package = _approved_package()
    expected_hash = package.payload_hash
    execute_jobhub_publishing(package, bridge, "  Release Approver  ")
    actor, notes = _stored_actor_and_notes(hub)
    assert actor == "Release Approver"
    assert "Published by Release Approver" in notes
    assert "Package creator: Source Estimator" in notes
    assert package.payload_hash == expected_hash


def test_draft_without_sealed_creator_never_fabricates_source_attribution(test_dbs):
    _, hub, bridge = test_dbs
    package = _approved_package()
    package.mode = PublishingMode.DRAFT.value
    package.created_by = None
    package.payload_hash = package.compute_payload_hash()
    assert validate_publishing_gate(package).is_publishable

    result = execute_jobhub_publishing(package, bridge, "Draft Publisher")
    actor, notes = _stored_actor_and_notes(hub)
    assert result["status"] == "Draft"
    assert actor == "Draft Publisher"
    assert "Published by Draft Publisher" in notes
    assert "Package creator:" not in notes
    assert "Source Estimator" not in notes


def test_changed_sealed_creator_remains_a_toctou_veto_before_jobhub(test_dbs):
    _, hub, _ = test_dbs
    package = _approved_package()
    original = package.payload_hash
    package.created_by = "Different Creator"
    assert package.compute_payload_hash() != original
    with pytest.raises(RuntimeError, match="TOCTOU violation"):
        execute_jobhub_publishing(package, _NeverConnect(), "Release Approver")
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 0
