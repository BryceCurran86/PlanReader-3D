"""Focused tests for AG-R10/R11 generic room finish, wet-area tile-height, and setback witness."""
from __future__ import annotations

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_room_finish_setback_witness_shadow import (
    RoomFinishSetbackWitness,
    compile_room_finish_setback_witnesses_shadow,
)

SHA = "c" * 64


def _w(
    wid: str,
    room: str,
    role: str,
    mat: str,
    *,
    page="3",
    height=None,
    full=False,
    setback=None,
    rev="rev1",
):
    return RoomFinishSetbackWitness(
        witness_id=wid,
        document_id="doc1",
        revision_id=rev,
        source_sha256=SHA,
        page_id=page,
        room_key=room,
        surface_role=role,
        material_label=mat,
        tile_height_mm=height,
        full_height_lining=full,
        setback_mm=setback,
    )


def test_wet_area_tile_height_setback_and_multiwall_room_cross_sheet_corroboration() -> None:
    witnesses = (
        _w("w1", "WET_ROOM_1", "wet_area_wall", "Ceramic Wall Tile", page="3", height=2100.0, setback=50.0),
        _w("w2", "WET_ROOM_1", "wet_area_wall", "ceramic wall tile", page="6", height=2100.0, setback=50.0),
        _w("w3", "MAIN_ZONE", "floor", "Engineered Timber", page="3"),
        _w("w4", "MAIN_ZONE", "floor", "Engineered Timber", page="8"),
        _w("w5", "MAIN_ZONE", "floor", "Other Spec", page="9", rev="stale_rev"),  # ignored cross-rev
    )
    res = compile_room_finish_setback_witnesses_shadow(
        witnesses=witnesses,
        expected_document_id="doc1",
        expected_revision_id="rev1",
        expected_source_sha256=SHA,
    )
    assert len(res) == 2
    by_key = {(r.room_key, r.surface_role): r for r in res}

    wet = by_key[("WET_ROOM_1", "wet_area_wall")]
    assert wet.status is EvidenceResolutionStatus.CORROBORATED
    assert wet.tile_height_mm == 2100.0
    assert wet.setback_mm == 50.0
    assert wet.source_page_ids == ("3", "6")
    assert wet.shadow_only is True
    assert wet.commercial_authority_granted is False

    main = by_key[("MAIN_ZONE", "floor")]
    assert main.status is EvidenceResolutionStatus.CORROBORATED
    assert main.source_page_ids == ("3", "8")


def test_conflicting_heights_and_invalid_ranges_fail_closed() -> None:
    witnesses = (
        _w("w1", "R_CONFLICT", "wet_area_wall", "Tile", height=1800.0),
        _w("w2", "R_CONFLICT", "wet_area_wall", "Tile", height=2400.0),
        _w("w3", "R_INVALID", "wet_area_wall", "Tile", height=2100.0, full=True),
    )
    res = compile_room_finish_setback_witnesses_shadow(
        witnesses=witnesses,
        expected_document_id="doc1",
        expected_revision_id="rev1",
        expected_source_sha256=SHA,
    )
    by_room = {r.room_key: r for r in res}
    assert by_room["R_CONFLICT"].status is EvidenceResolutionStatus.CONFLICT
    assert by_room["R_INVALID"].status is EvidenceResolutionStatus.ABSTAINED
