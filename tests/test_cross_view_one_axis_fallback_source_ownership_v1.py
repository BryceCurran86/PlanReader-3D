"""A one-axis annotation is subordinate to an already bound source dimension.

These are fictional source IDs, not real building dimensions, page geometry,
frozen benchmark quantities, or production sources.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from pb_cross_view_room_area_authority import (
    _exclude_shadow_dimension_claims_using_strong_owners,
    _quarantine_reused_cross_view_dimensions,
)


def rec(room: str, h: str, v: str, page: str = "support-p2"):
    return SimpleNamespace(
        physical_room_id=room,
        source_dimension_page_id=page,
        horizontal_dimension_id=h,
        vertical_dimension_id=v,
    )


@pytest.mark.parametrize("orientation", ["horizontal", "vertical"])
@pytest.mark.parametrize("reverse", [False, True])
def test_weak_dimension_cannot_steal_authoritative_room(
    orientation: str, reverse: bool,
) -> None:
    strong = rec("old-room", "existing-h", "existing-v")
    weak = rec(
        "new-weak-room",
        "existing-h" if orientation == "horizontal" else "distinct-h",
        "existing-v" if orientation == "vertical" else "distinct-v",
    )
    records = [strong, weak]
    if reverse:
        records.reverse()

    retained, dropped = _exclude_shadow_dimension_claims_using_strong_owners(
        records, frozenset({"new-weak-room"}),
    )
    assert dropped == {"new-weak-room"}
    assert retained == [strong]
    verified, contested = _quarantine_reused_cross_view_dimensions(retained)
    assert verified == [strong]
    assert contested == set()


def test_conflicting_strong_claims_still_both_abstain() -> None:
    first = rec("first", "h", "v1")
    second = rec("second", "h", "v2")
    records, displaced = _exclude_shadow_dimension_claims_using_strong_owners(
        [first, second], frozenset(),
    )
    assert displaced == set()
    result, quarantined = _quarantine_reused_cross_view_dimensions(records)
    assert result == []
    assert quarantined == {"first", "second"}


def test_two_competing_weak_claims_still_both_abstain() -> None:
    first = rec("first", "h", "v1")
    second = rec("second", "h", "v2")
    records, displaced = _exclude_shadow_dimension_claims_using_strong_owners(
        [first, second], frozenset({"first", "second"}),
    )
    assert displaced == set()
    result, quarantined = _quarantine_reused_cross_view_dimensions(records)
    assert result == []
    assert quarantined == {"first", "second"}


def test_distinct_page_scopes_do_not_conflict_even_if_ids_repeat() -> None:
    strong = rec("first", "h", "v", "support-p2")
    weak = rec("second", "h", "v", "support-p3")
    records, displaced = _exclude_shadow_dimension_claims_using_strong_owners(
        [strong, weak], frozenset({"second"}),
    )
    assert displaced == set()
    accepted, disputed = _quarantine_reused_cross_view_dimensions(records)
    assert accepted == [strong, weak]
    assert disputed == set()


def test_weak_uses_no_strong_source_and_can_publish_independently() -> None:
    strong = rec("first", "h1", "v1")
    weak = rec("second", "h2", "v2")
    records, displaced = _exclude_shadow_dimension_claims_using_strong_owners(
        [strong, weak], frozenset({"second"}),
    )
    assert records == [strong, weak]
    assert displaced == set()
    accepted, disputed = _quarantine_reused_cross_view_dimensions(records)
    assert accepted == records
    assert disputed == set()


def test_strong_owners_remain_reserved_even_if_they_conflict_with_each_other() -> None:
    strong_one = rec("strong-one", "h", "v1")
    strong_two = rec("strong-two", "h", "v2")
    weak = rec("weak", "h", "v3")
    records, displaced = _exclude_shadow_dimension_claims_using_strong_owners(
        [strong_one, strong_two, weak], frozenset({"weak"}),
    )
    assert displaced == {"weak"}
    assert records == [strong_one, strong_two]
    accepted, disputed = _quarantine_reused_cross_view_dimensions(records)
    assert accepted == []
    assert disputed == {"strong-one", "strong-two"}
