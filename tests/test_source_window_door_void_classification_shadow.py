"""Tests for producer-owned window vs door physical void classification shadow authority (Item 61)."""
from __future__ import annotations

import pytest
from shapely import wkb

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_window_door_void_classification_shadow import (
    DOOR_SWING_ARC_PROVEN,
    FLOOR_CONTINUITY_PROVEN,
    FLOOR_INTERRUPTION_PROVEN,
    OPENING_EVIDENCE_CONFLICT,
    OPENING_KIND_AMBIGUOUS,
    OPENING_KIND_DOOR,
    OPENING_KIND_WINDOW,
    SCHEDULE_TAG_DOOR_MATCH,
    SCHEDULE_TAG_WINDOW_MATCH,
    SOURCE_OPENING_VOID_CLASSIFIED_DOOR,
    SOURCE_OPENING_VOID_CLASSIFIED_WINDOW,
    SOURCE_OPENING_VOID_UNAVAILABLE,
    WINDOW_SILL_LINE_PROVEN,
    SourceWindowDoorVoidClassificationAuthority,
    SourceWindowDoorVoidClassificationProducer,
    SourceWindowDoorVoidRecord,
    SourceWindowDoorVoidSelector,
)


def _make_selector(
    *,
    doc="doc-arch",
    rev="rev-01",
    sha="a" * 64,
    snap="snap-01",
    page="1",
    opening_id="OP_01",
) -> SourceWindowDoorVoidSelector:
    return SourceWindowDoorVoidSelector(
        document_id=doc,
        revision_id=rev,
        source_sha256=sha,
        snapshot_id=snap,
        page_id=page,
        opening_id=opening_id,
    )


def test_sealing_raises_permission_error():
    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceWindowDoorVoidClassificationProducer(object())

    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceWindowDoorVoidClassificationAuthority(object(), {})

    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceWindowDoorVoidRecord(
            record_id="rec-1",
            document_id="doc",
            revision_id="rev",
            source_sha256="sha",
            snapshot_id="snap",
            page_id="1",
            opening_id="D01",
            opening_kind=OPENING_KIND_DOOR,
            host_wall_id="wall-1",
            clear_width_m=0.82,
            sill_height_m=0.0,
            head_height_m=2.04,
            floor_interrupted=True,
            sill_line_present=False,
            swing_arc_present=True,
            schedule_code="D01",
            chord_pts=((0.0, 0.0), (0.82, 0.0)),
            wkb_hex=None,
            reason_codes=(),
        )


def test_positive_door_void_classification():
    producer = SourceWindowDoorVoidClassificationProducer.create()
    producer.register_opening_void(
        document_id="doc-arch",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="1",
        opening_id="D01",
        host_wall_id="WALL_SOUTH",
        chord_pts=((100.0, 0.0), (141.0, 0.0)),
        clear_width_m=0.82,
        sill_line_present=False,
        floor_interrupted=True,
        swing_arc_present=True,
        schedule_code="D01",
        sill_height_m=0.0,
        head_height_m=2.04,
    )
    authority = producer.authority()
    sel = _make_selector(opening_id="D01")
    res = authority.resolve(sel)

    assert res.status == EvidenceResolutionStatus.CORROBORATED.value
    assert res.opening_kind == OPENING_KIND_DOOR
    assert SOURCE_OPENING_VOID_CLASSIFIED_DOOR in res.reason_codes
    assert DOOR_SWING_ARC_PROVEN in res.reason_codes
    assert FLOOR_INTERRUPTION_PROVEN in res.reason_codes
    assert SCHEDULE_TAG_DOOR_MATCH in res.reason_codes

    rec = res.record
    assert rec is not None
    assert rec.clear_width_m == 0.82
    assert rec.status == EvidenceResolutionStatus.CANDIDATE.value
    assert rec.commercial_projection_allowed is False
    assert rec.takeoff_eligible is False

    geom = wkb.loads(bytes.fromhex(rec.wkb_hex))
    assert geom.geom_type == "LineString"
    assert geom.is_valid


def test_positive_window_void_classification():
    producer = SourceWindowDoorVoidClassificationProducer.create()
    producer.register_opening_void(
        document_id="doc-arch",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="1",
        opening_id="W01",
        host_wall_id="WALL_NORTH",
        chord_pts=((200.0, 100.0), (300.0, 100.0)),
        clear_width_m=1.80,
        sill_line_present=True,
        floor_interrupted=False,
        swing_arc_present=False,
        schedule_code="W01",
        sill_height_m=0.90,
        head_height_m=2.10,
    )
    authority = producer.authority()
    sel = _make_selector(opening_id="W01")
    res = authority.resolve(sel)

    assert res.status == EvidenceResolutionStatus.CORROBORATED.value
    assert res.opening_kind == OPENING_KIND_WINDOW
    assert SOURCE_OPENING_VOID_CLASSIFIED_WINDOW in res.reason_codes
    assert WINDOW_SILL_LINE_PROVEN in res.reason_codes
    assert FLOOR_CONTINUITY_PROVEN in res.reason_codes
    assert SCHEDULE_TAG_WINDOW_MATCH in res.reason_codes

    rec = res.record
    assert rec is not None
    assert rec.sill_height_m == 0.90
    assert rec.head_height_m == 2.10


def test_conflicting_evidence_fails_closed():
    producer = SourceWindowDoorVoidClassificationProducer.create()
    # Swing arc + door tag D05, but continuous floor + sill line (contradiction!)
    producer.register_opening_void(
        document_id="doc-arch",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="1",
        opening_id="CONFLICT_01",
        host_wall_id="WALL_WEST",
        chord_pts=((0.0, 50.0), (0.0, 100.0)),
        clear_width_m=1.0,
        sill_line_present=True,  # window evidence
        floor_interrupted=False,  # window evidence
        swing_arc_present=True,   # door evidence
        schedule_code="D05",      # door evidence
    )
    authority = producer.authority()
    res = authority.resolve(_make_selector(opening_id="CONFLICT_01"))

    assert res.status == EvidenceResolutionStatus.ABSTAINED.value
    assert res.opening_kind == OPENING_KIND_AMBIGUOUS
    assert OPENING_EVIDENCE_CONFLICT in res.reason_codes
    assert res.resolution_mode == "abstain_opening_evidence_conflict"


def test_unregistered_selector_returns_unavailable():
    producer = SourceWindowDoorVoidClassificationProducer.create()
    authority = producer.authority()
    res = authority.resolve(_make_selector(opening_id="NON_EXISTENT"))

    assert res.status == EvidenceResolutionStatus.ABSTAINED.value
    assert SOURCE_OPENING_VOID_UNAVAILABLE in res.reason_codes
    assert res.record is None
