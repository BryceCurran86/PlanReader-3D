"""Ceiling quantity accessor must revalidate a reconstructed FIRM source receipt."""
from dataclasses import replace

import pytest

from tests.test_gpt2_malformed_ceiling_quantity_result_quarantine import _issued


@pytest.mark.parametrize("quantity_field,bad", [
    ("family", "floor_finish_area"),
    ("status", "provisional"),
    ("authority", "unverified"),
    ("unit", "lm"),
    ("formula", "untrusted_formula"),
    ("value", 987.0),
    ("abstained", True),
])
def test_reconstructed_non_firm_or_mismatched_area_is_not_a_signed_ceiling(
    quantity_field, bad,
):
    original = _issued()
    record = original.records[0]
    # QuantityEvidence can be reconstructed without being reissued by producer.
    mutated = replace(record.quantity, **{quantity_field: bad}) if quantity_field != "abstained" else None
    if quantity_field == "abstained":
        import copy
        mutated = copy.copy(record.quantity)
        object.__setattr__(mutated, "abstained", True)
    result = replace(original, records=(replace(record, quantity=mutated),))
    assert result.records_by_ceiling_id == {}
    assert result.quantities == ()


@pytest.mark.parametrize("owner_key", [
    "canonical_ceiling_id", "physical_room_id", "canonical_room_id",
    "source_room_face_record_id", "upstream_room_area_quantity_id",
    "finish_code", "support_page_id", "support_viewport_id",
    "document_id", "revision_id", "source_sha256", "snapshot_id",
])
def test_rekeyed_source_quantity_metadata_does_not_grant_room_ceiling(owner_key):
    original = _issued()
    record = original.records[0]
    quantity = replace(record.quantity, metadata={
        **record.quantity.metadata,
        owner_key: "foreign-original-source-owner",
    })
    result = replace(original, records=(replace(record, quantity=quantity),))
    assert result.quantities == ()


def test_canonical_room_owner_and_area_source_must_agree_with_signed_ceiling():
    original = _issued()
    record = original.records[0]
    mutated = replace(
        record.canonical_ceiling,
        room_area_quantity_id="another-upstream-room-area",
    )
    result = replace(original, records=(replace(record, canonical_ceiling=mutated),))
    assert result.quantities == ()


def test_unmodified_producer_issued_ceiling_quantity_is_preserved():
    original = _issued()
    assert len(original.quantities) == 1
    assert len(original.canonical_ceilings) == 1
