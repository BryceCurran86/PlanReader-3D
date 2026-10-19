"""Fail-closed source-owner regression tests for repeated same-label rooms."""
from dataclasses import dataclass
from dataclasses import replace

import pytest

from pb_repeated_room_label_source_shadow import uniquely_owned_repeated_label_lines
from pb_same_view_room_area_authority import SameViewRoomAreaProducer
from tests.test_same_view_room_area_authority_v1 import _source_and_rooms


@dataclass(frozen=True)
class NativeLine:
    observation_ids: tuple[str, ...]
    receipt_ids: tuple[str, ...]


A = NativeLine(("native-1", "native-2"), ("label-receipt-1",))
B = NativeLine(("native-3", "native-4"), ("label-receipt-2",))


def test_positive_unique_owners_are_order_invariant():
    owners = {
        "room-1": ("native-1", "native-2", "authority-1"),
        "room-2": ("native-3", "native-4", "authority-2"),
    }
    assert uniquely_owned_repeated_label_lines(owners, (A, B)) == {
        "room-1": A, "room-2": B,
    }
    assert uniquely_owned_repeated_label_lines(owners, (B, A)) == {
        "room-1": A, "room-2": B,
    }


@pytest.mark.parametrize("lines", [
    (A,), (A, B, B), (A, A),
    (A, NativeLine(("native-3",), ())),
    (A, NativeLine(("native-3", "unknown-word"), ("receipt",))),
    (A, NativeLine(("native-3", "native-3"), ("receipt",))),
])
def test_incomplete_duplicate_or_unowned_source_lines_abstain(lines):
    owners = {"room-1": ("native-1", "native-2"),
              "room-2": ("native-3", "native-4")}
    assert uniquely_owned_repeated_label_lines(owners, lines) == {}


def test_cross_room_shared_observation_abstains():
    owners = {
        "room-1": ("native-1", "native-2"),
        "room-2": ("native-1", "native-4"),
    }
    assert uniquely_owned_repeated_label_lines(owners, (A, B)) == {}


def test_invalid_native_observations_not_coerced():
    assert uniquely_owned_repeated_label_lines(
        {"room-1": ("native-1",), "room-2": (17,)}, (A, B)
    ) == {}
    assert uniquely_owned_repeated_label_lines(
        {"room-1": ("native-1", "native-1"), "room-2": ("native-3",)}, (A, B)
    ) == {}


def test_does_not_mutate_source_claims():
    owners = {"room-1": ["native-1", "native-2"],
              "room-2": ["native-3", "native-4"]}
    lines = [A, B]
    assert uniquely_owned_repeated_label_lines(owners, lines)
    assert lines == [A, B]
    assert owners["room-1"] == ["native-1", "native-2"]


def test_repeated_label_shadow_also_abstains_without_two_distinct_native_lines():
    # Two independent claimed physical rooms but only ONE native label line:
    # the shadow flag cannot manufacture the missing original second label.
    source, rooms = _source_and_rooms(duplicate_label=True)
    producer = SameViewRoomAreaProducer.from_source(source=source, rooms=rooms)
    original = producer.publish()
    shadow = producer.publish(repeated_label_source_ownership_shadow=True)
    assert original.records == ()
    assert shadow.records == ()
    assert shadow.unresolved_first_failure_by_physical_room_id == {
        "physical-room-1": "same_view_repeated_label_source_observation_ambiguous",
        "physical-room-2": "same_view_repeated_label_source_observation_ambiguous",
    }
    assert producer.publish() == original


def test_shadow_must_be_opted_into_by_explicit_boolean():
    source, rooms = _source_and_rooms()
    producer = SameViewRoomAreaProducer.from_source(source=source, rooms=rooms)
    with pytest.raises(TypeError):
        producer.publish(repeated_label_source_ownership_shadow="true")
