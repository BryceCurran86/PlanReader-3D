"""Source-native diagnostic tests. No commercial or benchmark authority."""
from __future__ import annotations

from dataclasses import replace

import pytest

from test_same_view_room_area_authority_v1 import _source_and_rooms
from pb_migration_contracts import EvidenceResolutionStatus
from pb_same_view_room_area_authority import SameViewRoomAreaProducer
from tools.diag_gpt1_same_view_witness_census import report_same_view_witness_census


def _report(source, rooms, ids=("source-face-record-1",)):
    return report_same_view_witness_census(
        source=source, rooms=rooms, target_source_face_ids=ids,
    )


def test_original_native_synthetic_HV_source_receipts_are_diagnostic_only():
    source, rooms = _source_and_rooms()
    baseline = SameViewRoomAreaProducer.from_source(source=source, rooms=rooms).publish()
    assert baseline.status is EvidenceResolutionStatus.CORROBORATED
    report = _report(source, rooms)
    assert report["status"] == "DIAGNOSTIC_ONLY"
    assert len(report["rows"]) == 1
    row = report["rows"][0]
    assert row["status"] == "DIAGNOSTIC_ONLY"
    assert row["source_sha256"] == rooms.rooms[0].source_sha256
    assert row["snapshot_id"] == rooms.rooms[0].snapshot_id
    assert row["decision_scope_id"] == rooms.rooms[0].decision_scope_id
    assert len(row["horizontal_dimensions"]) == 1
    assert len(row["vertical_dimensions"]) == 1
    assert row["local_eligible_pair_count_diagnostic_only"] == 1
    pair = row["pairs"][0]
    assert pair["existing_scale_consistency_gate"] is True
    assert pair["normal_path_eligible_diagnostic_only"] is True
    for item in row["horizontal_dimensions"] + row["vertical_dimensions"]:
        assert item["dimension_id"]
        assert item["text_receipt_id"]
        assert item["text_observation_id"]
        assert len(item["witness_observation_ids"]) >= 2
        assert item["dimension_line_observation_ids"]
        assert item["inferred_ratio_diagnostic_only"] > 0.0
    assert row["producer_area_authority_proven"] is False
    assert row["quantity_published"] is False
    after = SameViewRoomAreaProducer.from_source(source=source, rooms=rooms).publish()
    assert after.records[0].area_evidence == baseline.records[0].area_evidence
    assert _report(source, rooms) == report


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


def test_source_pair_conflicts_never_publish_metric_quantity():
    source, rooms = _source_and_rooms(duplicate_dimension_box=True)
    report = _report(source, rooms)
    row = report["rows"][0]
    assert row["status"] == "DIAGNOSTIC_ONLY"
    assert row["quantity_published"] is False
    assert row["producer_area_authority_proven"] is False
    assert len(row["horizontal_dimensions"]) >= 1
    assert len(row["vertical_dimensions"]) >= 1
    assert len(row["pairs"]) == (
        len(row["horizontal_dimensions"]) * len(row["vertical_dimensions"])
    )


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
