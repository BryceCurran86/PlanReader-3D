"""Original-source blocking warnings must not disappear in JobHub commercial output."""
from __future__ import annotations

import pytest

from pb_jobhub_publishing_contract import (
    PublishingMode, PublishingWarningPayload, validate_publishing_gate,
)
from test_commercial_identity_default_safety import _minimal_commercial_package


def _package(mode=PublishingMode.COMMERCIAL):
    p = _minimal_commercial_package(
        estimator="Source Estimator", created_by="Source Estimator",
        approved_by="Source Estimator",
    )
    p.mode = mode.value
    p.drawing_revision.source_files_hash = "a" * 64
    return p


@pytest.mark.parametrize("severity", [
    "Blocker", "Critical", "Review", "UNKNOWN", "", "critical",
])
def test_firm_label_does_not_override_unresolved_source_warning(severity):
    p = _package()
    p.warnings.append(PublishingWarningPayload(
        code="ORIGINAL_SOURCE_UNPROVEN", severity=severity,
        message="This floor has no closed physical source boundary",
    ))
    p.payload_hash = p.compute_payload_hash()
    result = validate_publishing_gate(p)
    assert not result.is_publishable
    assert any("Unresolved commercial source issue" in reason
               for reason in result.blocking_reasons)


def test_draft_keeps_original_critical_warning_visible_without_publishing_firm():
    p = _package(PublishingMode.DRAFT)
    p.warnings.append(PublishingWarningPayload(
        code="MISSING_ROOM_CLOSURE", severity="Critical",
        message="Original wall faces do not close the source polygon",
    ))
    p.payload_hash = p.compute_payload_hash()
    result = validate_publishing_gate(p)
    assert result.is_publishable
    assert result.mode == "draft"
    assert any("MISSING_ROOM_CLOSURE" in w for w in result.warnings)


def test_information_warning_remains_publishable_and_visible_to_customer():
    p = _package()
    p.warnings.append(PublishingWarningPayload(
        code="EXTERNAL_CLIENT_NOTE", severity="Info",
        message="Customer supplied a new materials rate schedule",
    ))
    p.payload_hash = p.compute_payload_hash()
    result = validate_publishing_gate(p)
    assert result.is_publishable
    assert any("EXTERNAL_CLIENT_NOTE" in w for w in result.warnings)


def test_clean_original_documented_quantity_remains_publishable():
    p = _package()
    p.payload_hash = p.compute_payload_hash()
    result = validate_publishing_gate(p)
    assert result.is_publishable
    assert not result.blocking_reasons
