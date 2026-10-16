"""Source-native diagnostic tests. No commercial or benchmark authority."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from test_same_view_room_area_authority_v1 import _source_and_rooms
from pb_live_canonical_room_composition import LiveCanonicalRoomComposition
from pb_cross_view_room_area_authority import _trusted_lines_for_page
from pb_migration_contracts import EvidenceResolutionStatus
from pb_same_view_room_area_authority import SameViewRoomAreaProducer
from tools.diag_gpt1_same_view_witness_census import report_same_view_witness_census


def _report(source, rooms, ids=("source-face-record-1",)):
    return report_same_view_witness_census(
        source=source, rooms=rooms, target_source_face_ids=ids,
    )


def test_manually_composed_room_cannot_borrow_even_valid_native_HV():
    # The same native PDF *does* support a synthetic production same-view
    # measurement; that is not an original SourceRoomFace/label scope grant.
    source, rooms = _source_and_rooms()
    baseline = SameViewRoomAreaProducer.from_source(source=source, rooms=rooms).publish()
    assert baseline.status is EvidenceResolutionStatus.CORROBORATED
    report = _report(source, rooms)
    row = report["rows"][0]
    assert row["status"] == "ABSTAINED"
    assert row["reason"] == "original_room_face_authority_binding_unavailable"
    assert row["quantity_published"] is False
    assert "horizontal_dimensions" not in row
    assert "vertical_dimensions" not in row
    after = SameViewRoomAreaProducer.from_source(source=source, rooms=rooms).publish()
    assert after.records[0].area_evidence == baseline.records[0].area_evidence
    assert _report(source, rooms) == report


def _mock_room_face_binding(room):
    # Unit-test-only seam: a dummy metadata object, NEVER an authority
    # publication or a fabricated original-source witness.
    return SimpleNamespace(
        snapshot_id=room.snapshot_id,
        page_id=room.page_id,
        decision_scope_id=room.decision_scope_id,
        source_room_face_record_ids=(room.source_room_face_record_id,),
        viewport_id=room.viewport_id,
    )


def test_matching_original_word_observations_keep_diagnostic_pairs_only():
    source, rooms = _source_and_rooms()
    room = rooms.rooms[0]
    original_lines = _trusted_lines_for_page(
        source, revision_id=room.revision_id, page_id=room.page_id,
        candidate_labels=(room.room_label,),
    )
    assert len(original_lines) == 1
    # Synthetic test fixture normally has no producer-owned room label; inject
    # the *actual native observation identities* solely to exercise the
    # post-binding census. The original-source workflow exercises real seals.
    with_observations = replace(
        rooms, rooms=(replace(room, room_label_evidence_ids=original_lines[0].observation_ids),)
    )
    with patch.object(
        LiveCanonicalRoomComposition, "room_face_authority_binding_for",
        return_value=_mock_room_face_binding(with_observations.rooms[0]),
    ):
        report = _report(source, with_observations)
    row = report["rows"][0]
    assert row["status"] == "DIAGNOSTIC_ONLY"
    assert row["trusted_label_line_observation_ids"] == original_lines[0].observation_ids
    assert len(row["horizontal_dimensions"]) == 1
    assert len(row["vertical_dimensions"]) == 1
    assert row["local_eligible_pair_count_diagnostic_only"] == 1
    assert row["producer_area_authority_proven"] is False
    assert row["quantity_published"] is False


def test_same_text_wrong_original_word_observation_fails_closed():
    source, rooms = _source_and_rooms()
    with patch.object(
        LiveCanonicalRoomComposition, "room_face_authority_binding_for",
        return_value=_mock_room_face_binding(rooms.rooms[0]),
    ):
        report = _report(source, rooms)
    row = report["rows"][0]
    assert row["status"] == "ABSTAINED"
    assert row["reason"] == "original_room_label_observations_unowned"
    assert row["trusted_label_line_observation_ids"]
    assert "horizontal_dimensions" not in row


def test_foreign_or_wrong_viewport_room_binding_abstains():
    source, rooms = _source_and_rooms()
    room = rooms.rooms[0]
    for mutated in (
        SimpleNamespace(**{**vars(_mock_room_face_binding(room)), "decision_scope_id": "foreign"}),
        SimpleNamespace(**{**vars(_mock_room_face_binding(room)), "snapshot_id": "foreign"}),
        SimpleNamespace(**{**vars(_mock_room_face_binding(room)), "viewport_id": "other"}),
        SimpleNamespace(**{**vars(_mock_room_face_binding(room)), "source_room_face_record_ids": ("other",)}),
    ):
        with patch.object(
            LiveCanonicalRoomComposition, "room_face_authority_binding_for",
            return_value=mutated,
        ):
            row = _report(source, rooms)["rows"][0]
        assert row["status"] == "ABSTAINED"
        assert row["reason"] == "original_room_face_authority_binding_unavailable"


def test_conflicting_room_snapshot_abstains_before_trusted_source_extraction():
    source, rooms = _source_and_rooms()
    stale = replace(rooms, rooms=(replace(rooms.rooms[0], snapshot_id="foreign"),))
    result = _report(source, stale)
    assert result["status"] == "ABSTAINED"
    assert result["reason"] == "producer_source_lineage_mismatch"
    assert result["rows"] == []


def test_competing_original_room_face_owner_never_selects_first():
    source, rooms = _source_and_rooms(second_label=True)
    same_face = rooms.rooms[0].source_room_face_record_id
    conflict = replace(
        rooms,
        rooms=(rooms.rooms[0], replace(rooms.rooms[1], source_room_face_record_id=same_face)),
    )
    result = _report(source, conflict)
    assert result["rows"][0]["reason"] == "source_face_owner_not_unique"
    assert result["rows"][0]["owner_count"] == 2


def test_mixed_room_source_lineage_abstains_whole_universe():
    source, rooms = _source_and_rooms(second_label=True)
    mixed = replace(
        rooms,
        rooms=(rooms.rooms[0], replace(rooms.rooms[1], source_sha256="b" * 64)),
    )
    result = _report(source, mixed)
    assert result["status"] == "ABSTAINED"
    assert result["reason"] == "mixed_room_source_lineage"


def test_missing_source_face_and_duplicate_selectors_fail_closed():
    source, rooms = _source_and_rooms()
    missing = _report(source, rooms, ("not-produced-face",))
    assert missing["rows"][0]["reason"] == "source_face_owner_not_unique"
    assert missing["rows"][0]["owner_count"] == 0
    for ids in [(), ("x", "x"), (" x",), ("",)]:
        with pytest.raises(ValueError):
            _report(source, rooms, ids)


def test_missing_vertical_fixture_remains_untrusted_even_when_native():
    source, rooms = _source_and_rooms(duplicate_dimension_box=True)
    report = _report(source, rooms)
    row = report["rows"][0]
    assert row["status"] == "ABSTAINED"
    assert row["reason"] == "original_room_face_authority_binding_unavailable"
    assert row["quantity_published"] is False
    assert "pairs" not in row
    # Exact synthetic source also cannot turn the competing pair into
    # a FIRM production measurement; the diagnostic may not bypass room scope.
    production = SameViewRoomAreaProducer.from_source(source=source, rooms=rooms).publish()
    assert production.records == ()


def test_source_face_selector_permutation_cannot_change_receipts():
    source, rooms = _source_and_rooms(second_label=True)
    # Two independently produced face addresses are reporting selectors only.
    first, second = (
        rooms.rooms[0].source_room_face_record_id,
        rooms.rooms[1].source_room_face_record_id,
    )
    left = _report(source, rooms, (first, second))
    right = _report(source, rooms, (second, first))
    assert left == right
    assert [row["source_room_face_record_id"] for row in left["rows"]] == sorted((first, second))


@pytest.mark.parametrize(
    "kind",
    (
        "empty_observations",
        "foreign_observation",
        "repeated_observation",
        "blank_observation",
        "padded_observation",
        "nonstring_observation",
        "missing_receipt",
        "extra_receipt",
    ),
)
def test_hostile_trusted_native_label_receipts_never_enter_metric_pair_census(kind):
    # A malformed copy of a source line must not become original native
    # observation ownership just because its human-readable text matches.
    source, rooms = _source_and_rooms()
    room = rooms.rooms[0]
    native = _trusted_lines_for_page(
        source, revision_id=room.revision_id, page_id=room.page_id,
        candidate_labels=(room.room_label,),
    )
    assert len(native) == 1
    original = native[0]
    owned = replace(rooms, rooms=(replace(
        room, room_label_evidence_ids=original.observation_ids,
    ),))
    from tools import diag_gpt1_same_view_witness_census as census
    changed = {
        "empty_observations": lambda: replace(original, observation_ids=()),
        "foreign_observation": lambda: replace(original, observation_ids=("foreign-obs",)),
        "repeated_observation": lambda: replace(
            original, observation_ids=(*original.observation_ids, *original.observation_ids),
        ),
        "blank_observation": lambda: replace(original, observation_ids=("",)),
        "padded_observation": lambda: replace(original, observation_ids=(" " + original.observation_ids[0],)),
        "nonstring_observation": lambda: replace(original, observation_ids=(123,)),
        "missing_receipt": lambda: replace(original, receipt_ids=()),
        "extra_receipt": lambda: replace(original, receipt_ids=(*original.receipt_ids, "foreign-receipt")),
    }[kind]()
    with patch.object(
        LiveCanonicalRoomComposition, "room_face_authority_binding_for",
        return_value=_mock_room_face_binding(owned.rooms[0]),
    ), patch.object(census, "_trusted_lines_for_page", return_value=(changed,)), patch.object(
        census, "_trusted_native_dimensions_for_page",
        side_effect=AssertionError("unowned text must not reach figured dimensions"),
    ):
        row = _report(source, owned)["rows"][0]
    assert row["status"] == "ABSTAINED"
    assert row["reason"] == "original_room_label_observations_unowned"
    assert row["quantity_published"] is False
    assert "horizontal_dimensions" not in row
    assert "vertical_dimensions" not in row


def test_source_label_line_source_ambiguity_abstains_even_with_one_owned_line():
    source, rooms = _source_and_rooms()
    room = rooms.rooms[0]
    native = _trusted_lines_for_page(
        source, revision_id=room.revision_id, page_id=room.page_id,
        candidate_labels=(room.room_label,),
    )
    assert len(native) == 1
    owned = replace(rooms, rooms=(replace(
        room, room_label_evidence_ids=native[0].observation_ids,
    ),))
    from tools import diag_gpt1_same_view_witness_census as census
    with patch.object(
        LiveCanonicalRoomComposition, "room_face_authority_binding_for",
        return_value=_mock_room_face_binding(owned.rooms[0]),
    ), patch.object(census, "_trusted_lines_for_page", return_value=(native[0], native[0])), patch.object(
        census, "_trusted_native_dimensions_for_page",
        side_effect=AssertionError("ambiguous text cannot enter figured dimensions"),
    ):
        row = _report(source, owned)["rows"][0]
    assert row["reason"] == "original_trusted_label_line_not_unique"
    assert row["trusted_label_line_count"] == 2
    assert row["status"] == "ABSTAINED"


def test_room_source_binding_precedes_any_unauthorized_label_lookup():
    source, rooms = _source_and_rooms()
    from tools import diag_gpt1_same_view_witness_census as census
    with patch.object(census, "_trusted_lines_for_page",
                      side_effect=AssertionError("unsealed room must not read label text")):
        row = _report(source, rooms)["rows"][0]
    assert row["reason"] == "original_room_face_authority_binding_unavailable"
    assert row["status"] == "ABSTAINED"
