"""GPT3: a real JobHub write requires the complete sealed evidence fingerprint.

Source-neutral SQLite consumer regressions. These are not original PDF,
FIRM source authentication, signed customer or frozen V2 scoring proofs.
"""
from __future__ import annotations

import pytest

from pb_jobhub_publishing_contract import PublishingMode, validate_publishing_gate
from pb_jobhub_publishing_pipeline import execute_jobhub_publishing
from test_gpt3_jobhub_atomic_destination_identity import _approved_package
from test_publishing_pipeline_e2e import test_dbs  # noqa: F401


class _NoConnectBridge:
    """An invalid source seal must be rejected before ANY database access."""

    def connect(self):
        raise AssertionError("Unsealed JobHub package reached the database")


@pytest.mark.parametrize("mode", [
    PublishingMode.COMMERCIAL.value,
    PublishingMode.DRAFT.value,
])
@pytest.mark.parametrize("unsealed", [
    "",
    None,
    " ",
    "0" * 63,
    "0" * 64,
    "not-a-sha256",
])
def test_missing_or_forged_hash_never_reaches_jobhub(mode, unsealed, test_dbs):
    _, hub, _ = test_dbs
    package = _approved_package()
    package.mode = mode
    package.payload_hash = unsealed
    if not unsealed:
        # Reproduces the real defect: the diagnostic gate intentionally
        # allows an absent hash, but the database writer MUST NOT.
        assert validate_publishing_gate(package).is_publishable
    with pytest.raises(RuntimeError, match="sealed matching SHA-256|TOCTOU violation"):
        execute_jobhub_publishing(
            package, _NoConnectBridge(), user_name="Source Estimator"
        )
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 0
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_package_lines"
    ).fetchone()[0] == 0


@pytest.mark.parametrize("mode", [
    PublishingMode.COMMERCIAL.value,
    PublishingMode.DRAFT.value,
])
def test_valid_sealed_hash_persists_and_rejects_duplicate(mode, test_dbs):
    _, hub, bridge = test_dbs
    package = _approved_package()
    package.mode = mode
    package.payload_hash = package.compute_payload_hash()
    assert validate_publishing_gate(package).is_publishable
    receipt = execute_jobhub_publishing(
        package, bridge, user_name="Source Estimator"
    )
    assert receipt["success"] is True
    assert receipt["payload_hash"] == package.payload_hash
    assert receipt["takeoff_no"].endswith(package.payload_hash[:8])
    assert receipt["status"] == (
        "Published" if mode == PublishingMode.COMMERCIAL.value else "Draft"
    )
    stored = hub.execute(
        "SELECT notes FROM painting_takeoff_packages"
    ).fetchone()[0]
    assert "Payload: " + package.payload_hash in stored
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_package_lines"
    ).fetchone()[0] == len(package.quantities)
    with pytest.raises(RuntimeError, match="Duplicate package"):
        execute_jobhub_publishing(
            package, bridge, user_name="Source Estimator"
        )
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 1


def test_post_seal_quantity_mutation_cannot_reach_writer(test_dbs):
    _, hub, _ = test_dbs
    package = _approved_package()
    original = package.payload_hash
    package.quantities[0].quantity = 11.0
    package.quantities[0].total_price = 11.0
    assert package.compute_payload_hash() != original
    with pytest.raises(RuntimeError, match="TOCTOU violation"):
        execute_jobhub_publishing(
            package, _NoConnectBridge(), user_name="Source Estimator"
        )
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 0


def test_unsealed_replay_cannot_be_rescued_by_preflight_override():
    package = _approved_package()
    package.payload_hash = ""
    with pytest.raises(RuntimeError, match="override is prohibited"):
        execute_jobhub_publishing(
            package, _NoConnectBridge(), user_name="Source Estimator",
            override_preflight_check=True,
        )
