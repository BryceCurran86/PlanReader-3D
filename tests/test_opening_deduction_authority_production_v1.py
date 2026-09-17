from __future__ import annotations

from dataclasses import fields
import inspect

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_deduction_authority import (
    OPENING_DEDUCTION_OPENING_UNRESOLVED,
    OpeningDeductionAuthority,
    OpeningDeductionProducer,
    OpeningDeductionSelector,
)


def _selector() -> OpeningDeductionSelector:
    return OpeningDeductionSelector(
        document_id="doc",
        revision_id="rev",
        source_sha256="a" * 64,
        snapshot_id="snap",
        page_id="page-1",
        decision_scope_id="scope-1",
        opening_identity_id="opening-1",
        target_scope_id="target-1",
    )


def test_selector_shape_is_address_only() -> None:
    assert {item.name for item in fields(OpeningDeductionSelector)} == {
        "document_id",
        "revision_id",
        "source_sha256",
        "snapshot_id",
        "page_id",
        "decision_scope_id",
        "opening_identity_id",
        "target_scope_id",
    }


def test_public_publish_is_selector_only() -> None:
    assert tuple(inspect.signature(OpeningDeductionProducer.publish).parameters) == (
        "self",
        "selector",
    )


def test_factory_requires_sealed_upstream_authorities() -> None:
    with pytest.raises(TypeError):
        OpeningDeductionProducer.from_authorities(
            physical_void_authority=object(),
            host_binding_authority=object(),
            opening_universe_authority=object(),
        )


def test_authority_is_producer_owned() -> None:
    with pytest.raises(TypeError):
        OpeningDeductionAuthority({})


def test_missing_record_is_unknown_not_zero() -> None:
    mod = __import__("pb_opening_deduction_authority")
    authority = OpeningDeductionAuthority({}, _seal=mod._AUTHORITY_SEAL)
    result = authority.resolve(_selector())
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert OPENING_DEDUCTION_OPENING_UNRESOLVED in result.reason_codes
