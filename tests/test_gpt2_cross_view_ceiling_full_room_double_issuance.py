"""Full-room RCP area authority cannot be reissued by rekeying ceiling ID."""
from dataclasses import replace

import pytest

from tests.test_gpt2_malformed_ceiling_quantity_result_quarantine import _issued
from tests.test_gpt2_signed_ceiling_quantity_identity_uniqueness import _second


@pytest.mark.parametrize("reused_field", [
    "physical_room_id",
    "canonical_room_id",
    "source_room_face_record_id",
    "upstream_room_area_quantity_id",
])
def test_distinct_signed_quantities_with_reused_full_room_owner_are_quarantined(
    reused_field,
):
    issued = _issued()
    first = issued.records[0]
    second = _second(
        issued, quantity_id="independent-signed-ceiling-2",
        independent_physical_owner=True,
    )
    second = replace(second, **{reused_field: getattr(first, reused_field)})
    for rows in ((first, second), (second, first)):
        result = replace(issued, records=rows)
        assert result.records_by_ceiling_id == {}
        assert result.quantities == ()
        assert result.canonical_ceilings == ()


@pytest.mark.parametrize("malformed", ["", " ", None, [], {}])
def test_bad_physical_room_owner_fails_closed_without_crashing(malformed):
    issued = _issued()
    rival = replace(
        _second(
            issued, quantity_id="independent-signed-ceiling-2",
            independent_physical_owner=True,
        ),
        physical_room_id=malformed,
    )
    result = replace(issued, records=(issued.records[0], rival))
    assert result.records_by_ceiling_id == {}
    assert result.quantities == ()


def test_independent_full_room_and_figure_source_authority_is_unaffected():
    issued = _issued()
    rival = _second(
        issued, quantity_id="independent-signed-ceiling-2",
        independent_physical_owner=True,
    )
    result = replace(issued, records=(rival, issued.records[0]))
    assert len(result.records_by_ceiling_id) == 2
    assert len(result.quantities) == 2
