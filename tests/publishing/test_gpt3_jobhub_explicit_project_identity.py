"""Final V1 JobHub preflight requires explicit source/project match for sale.

These source-neutral rows test only the downstream commercial gate and payload
builder. They cannot authenticate private PDFs or change frozen V2 scores.
"""
from __future__ import annotations

import pytest

from pb_planreader_jobhub_publish_contract import (
    PlanReaderJobHubQuantityRow,
    PublishMode,
    build_jobhub_payload,
    run_jobhub_publish_preflight,
)


REVISION = {"revision_hash": "synthetic-source-revision-1"}


def _row():
    return PlanReaderJobHubQuantityRow(
        quantity_id="physical-wall-area-1",
        description="Synthetic documented wall area",
        value=1.25,
        unit="m²",
        trade="painting",
        source_type="documented_dimension",
        authority_status="firm",
        source_page=1,
        dimension_text_id="synthetic-figured-dimension",
        revision_hash=REVISION["revision_hash"],
        is_publishable=True,
    )


def _identity(**changes):
    result = {
        "project_id": "synthetic-project-1",
        "project_name": "Synthetic project",
        "identity_confirmed": True,
    }
    result.update(changes)
    return result


def _preflight(identity, *, mode=PublishMode.COMMERCIAL_PUBLISH):
    return run_jobhub_publish_preflight(
        rows=[_row()],
        project_identity=identity,
        drawing_revision=REVISION,
        mode=mode,
    )


@pytest.mark.parametrize("unverified", [None, "", 0, 1, "true", "false", [], {}])
def test_unverified_project_identity_never_becomes_commercial_ready(unverified):
    identity = _identity(identity_confirmed=unverified)
    preflight = _preflight(identity)
    assert not preflight.is_valid
    assert preflight.publishable_row_count == 1
    assert any(
        "explicitly confirmed project identity" in reason
        for reason in preflight.blocking_reasons
    )
    with pytest.raises(ValueError, match="Cannot build commercial payload"):
        build_jobhub_payload([_row()], identity, REVISION)


def test_missing_confirmation_field_is_not_a_source_match():
    identity = _identity()
    del identity["identity_confirmed"]
    preflight = _preflight(identity)
    assert not preflight.is_valid
    assert any("explicitly confirmed" in reason for reason in preflight.blocking_reasons)
    with pytest.raises(ValueError, match="Cannot build commercial payload"):
        build_jobhub_payload([_row()], identity, REVISION)


def test_explicit_mismatch_still_blocks_and_preserves_reason():
    identity = _identity(
        identity_confirmed=False,
        mismatch_reason="Original source belongs to another project",
    )
    preflight = _preflight(identity)
    assert not preflight.is_valid
    assert any(
        "Original source belongs to another project" in reason
        for reason in preflight.blocking_reasons
    )
    with pytest.raises(ValueError, match="Cannot build commercial payload"):
        build_jobhub_payload([_row()], identity, REVISION)


def test_explicit_true_match_preserves_customer_payload_and_row_identity():
    identity = _identity(identity_confirmed=True)
    preflight = _preflight(identity)
    assert preflight.is_valid
    assert preflight.publishable_row_count == 1
    package = build_jobhub_payload(
        [_row()], identity, REVISION, created_by="Estimator A",
    )
    assert package.is_commercial_ready is True
    assert package.project_identity["identity_confirmed"] is True
    assert len(package.quantities) == 1
    assert package.quantities[0].quantity_id == "physical-wall-area-1"
    assert package.quantities[0].value == 1.25
    assert package.payload_fingerprint == package.compute_payload_fingerprint()


@pytest.mark.parametrize("unverified", [None, "true", 1])
def test_unconfirmed_draft_remains_explicitly_noncommercial(unverified):
    identity = _identity(identity_confirmed=unverified)
    preflight = _preflight(identity, mode=PublishMode.DRAFT_PUBLISH)
    assert preflight.is_valid
    assert any("not explicitly confirmed" in note for note in preflight.warnings)
    draft = build_jobhub_payload(
        [_row()], identity, REVISION,
        created_by="Estimator A",
        publish_mode=PublishMode.DRAFT_PUBLISH,
    )
    assert draft.is_commercial_ready is False
    assert draft.publish_mode == PublishMode.DRAFT_PUBLISH.value
    assert any("not explicitly confirmed" in note for note in draft.warnings)


def test_explicit_wrong_project_still_blocks_even_draft_preflight():
    identity = _identity(identity_confirmed=False)
    result = _preflight(identity, mode=PublishMode.DRAFT_PUBLISH)
    assert not result.is_valid
    assert any("mismatch" in reason.lower() for reason in result.blocking_reasons)
