"""Collector must forward the default-off dark-paint / wall-end room flags.

Those flags already exist on compose_live_canonical_rooms. Until the live
claim collector names them, closed dark-fill rings never reach the original
issuers. This is not FIRM, not a room count score, and stays default-off.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from pb_layered_wall_doorway_room_face_scope_shadow import LAYERED_RING_SCOPE_REASON
from pb_layered_wall_doorway_room_ring_shadow import build_from_pdf_bytes
from pb_live_canonical_room_composition import compose_live_canonical_rooms
from pb_live_physical_net_wall_integration import (
    _collect_live_physical_net_wall_claim,
    collect_live_physical_net_wall_claim,
)
from pb_live_floor_area_quantity_publication import publish_live_floor_area_quantities
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer

INK = (0.195, 0.195, 0.195)


def _figured_pair(page, *, y0: float = 80.0) -> None:
    """Unique 3600 x 2400 ticks for inner box (100,y0)-(250,180)."""
    page.draw_line((100.0, 70.0), (250.0, 70.0), color=(0, 0, 0), width=1.0)
    page.draw_line((100.0, 62.0), (100.0, 92.0), color=(0, 0, 0), width=1.0)
    page.draw_line((250.0, 62.0), (250.0, 92.0), color=(0, 0, 0), width=1.0)
    page.insert_text((164.0, 67.0), "3600", fontsize=9.0)
    page.draw_line((290.0, y0), (290.0, 180.0), color=(0, 0, 0), width=1.0)
    page.draw_line((250.0, y0), (298.0, y0), color=(0, 0, 0), width=1.0)
    page.draw_line((278.0, 180.0), (298.0, 180.0), color=(0, 0, 0), width=1.0)
    page.insert_text((287.0, 147.0), "2400", fontsize=9.0, rotate=90)
    page.insert_text((150.0, 130.0), "BED 2", fontsize=10.0)


def _dark_closed_room_pdf() -> bytes:
    """Unnamed dark-grey fills only. No Enclosure layer, no doorway stroke."""
    doc = fitz.open()
    page = doc.new_page(width=400.0, height=300.0)

    def bar(x0, y0, x1, y1):
        page.draw_rect(fitz.Rect(x0, y0, x1, y1), color=None, fill=INK)

    bar(96, 76, 254, 80)
    bar(96, 180, 254, 184)
    bar(96, 80, 100, 180)
    bar(250, 80, 254, 180)
    _figured_pair(page)
    return doc.tobytes()


def _u_room_with_wall_end_pdf() -> bytes:
    """Three dark walls plus one black stroke that already meets both jambs."""
    doc = fitz.open()
    page = doc.new_page(width=400.0, height=300.0)

    def bar(x0, y0, x1, y1):
        page.draw_rect(fitz.Rect(x0, y0, x1, y1), color=None, fill=INK)

    bar(96, 80, 100, 180)
    bar(250, 80, 254, 180)
    bar(96, 180, 254, 184)
    page.draw_line(fitz.Point(100.0, 80.0), fitz.Point(250.0, 80.0), color=(0, 0, 0), width=1.0)
    # Stroke thickness is 1.2 pt about the native line, so the inner face is y=80.6.
    _figured_pair(page, y0=80.6)
    return doc.tobytes()


def _write(tmp_path: Path, data: bytes, name: str = "room.pdf") -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def _parents(**extra):
    return dict(
        pages=(0,), topology_pages=(0,), surface_semantic_pages=(0,),
        layered_doorway_room_rings=True, layered_finished_face_gate=True, **extra,
    )


def _rooms(claim):
    return tuple(getattr(claim.canonical_rooms, "rooms", claim.canonical_rooms) or ())


def _layered_rooms(rooms):
    return tuple(
        room for room in rooms
        if (room.bounding_wall_ids and room.bounding_wall_ids[0].startswith("layered_"))
        or LAYERED_RING_SCOPE_REASON in "".join(room.room_label_reason_codes)
    )


def test_collector_and_compose_need_explicit_bools_and_parent_gates():
    source = SourceVisibilityProducer(producer_method="t", producer_version="1")
    with pytest.raises(ValueError, match="requires"):
        compose_live_canonical_rooms(
            source_visibility_producer=source, wall_opening_composition=None,  # type: ignore[arg-type]
            layered_wall_end_stroke_closures=True,
        )
    with pytest.raises(ValueError, match="explicit boolean"):
        compose_live_canonical_rooms(
            source_visibility_producer=source, wall_opening_composition=None,  # type: ignore[arg-type]
            layered_wall_end_stroke_closures="yes",  # type: ignore[arg-type]
        )
    for call in (collect_live_physical_net_wall_claim, _collect_live_physical_net_wall_claim):
        with pytest.raises(ValueError, match="dark painted"):
            call("does-not-exist.pdf", layered_dark_painted_wall_source=True)
        with pytest.raises(ValueError, match="dark painted"):
            call("does-not-exist.pdf", layered_doorway_room_rings=True,
                 layered_dark_painted_wall_source=True)
        with pytest.raises(ValueError, match="explicit boolean"):
            call("does-not-exist.pdf", layered_doorway_room_rings=True,
                 layered_finished_face_gate=True, layered_dark_painted_wall_source="yes")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="wall end"):
            call("does-not-exist.pdf", layered_doorway_room_rings=True,
                 layered_finished_face_gate=True, layered_wall_end_stroke_closures=True)
        with pytest.raises(ValueError, match="explicit boolean"):
            call("does-not-exist.pdf", layered_doorway_room_rings=True,
                 layered_finished_face_gate=True, layered_dark_painted_wall_source=True,
                 layered_wall_end_stroke_closures="yes")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="dark painted"):
        collect_live_physical_net_wall_claim(
            "does-not-exist.pdf", recover_additional_opening_areas=True,
            layered_dark_painted_wall_source=True,
        )


def test_collector_forwards_both_flags_to_compose_only_when_named(tmp_path, monkeypatch):
    import pb_live_physical_net_wall_integration as integration

    seen: list[dict] = []
    original = integration.compose_live_canonical_rooms

    def spy(*args, **kwargs):
        seen.append(dict(kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(integration, "compose_live_canonical_rooms", spy)
    path = _write(tmp_path, _dark_closed_room_pdf())
    collect_live_physical_net_wall_claim(path, **_parents())
    assert seen[-1].get("layered_dark_painted_wall_source") is not True
    assert seen[-1].get("layered_wall_end_stroke_closures") is not True
    collect_live_physical_net_wall_claim(
        path, **_parents(layered_dark_painted_wall_source=True),
    )
    assert seen[-1].get("layered_dark_painted_wall_source") is True
    assert seen[-1].get("layered_wall_end_stroke_closures") is not True
    collect_live_physical_net_wall_claim(
        path, **_parents(
            layered_dark_painted_wall_source=True,
            layered_wall_end_stroke_closures=True,
        ),
    )
    assert seen[-1].get("layered_dark_painted_wall_source") is True
    assert seen[-1].get("layered_wall_end_stroke_closures") is True


def test_unnamed_dark_fills_close_a_room_only_when_the_collector_opts_in(tmp_path):
    data = _dark_closed_room_pdf()
    sha = hashlib.sha256(data).hexdigest()
    off_rings = build_from_pdf_bytes(data, source_sha256=sha, page_index=0)
    on_rings = build_from_pdf_bytes(
        data, source_sha256=sha, page_index=0, dark_painted_wall_source=True,
    )
    assert not any(r.status is EvidenceResolutionStatus.CANDIDATE for r in off_rings.rings)
    assert any(r.status is EvidenceResolutionStatus.CANDIDATE for r in on_rings.rings)
    path = _write(tmp_path, data)
    off = collect_live_physical_net_wall_claim(path, **_parents())
    on = collect_live_physical_net_wall_claim(
        path, **_parents(layered_dark_painted_wall_source=True),
    )
    assert _layered_rooms(_rooms(off)) == ()
    rooms = _rooms(on)
    assert len(rooms) == 1
    assert _layered_rooms(rooms) == rooms
    assert rooms[0].source_room_face_record_id
    # finished-face gate still withholds area: dark paint is not lining identity
    assert on.room_area_quantity_evidence == ()
    assert publish_live_floor_area_quantities(on) == ()


def test_wall_end_stroke_reaches_the_claim_only_with_both_flags(tmp_path):
    data = _u_room_with_wall_end_pdf()
    sha = hashlib.sha256(data).hexdigest()
    dark_only = build_from_pdf_bytes(
        data, source_sha256=sha, page_index=0, dark_painted_wall_source=True,
    )
    with_end = build_from_pdf_bytes(
        data, source_sha256=sha, page_index=0,
        dark_painted_wall_source=True, wall_end_stroke_closures=True,
    )
    assert not any(r.status is EvidenceResolutionStatus.CANDIDATE for r in dark_only.rings)
    assert any(r.status is EvidenceResolutionStatus.CANDIDATE for r in with_end.rings)
    path = _write(tmp_path, data)
    paint_only = collect_live_physical_net_wall_claim(
        path, **_parents(layered_dark_painted_wall_source=True),
    )
    closed = collect_live_physical_net_wall_claim(
        path, **_parents(
            layered_dark_painted_wall_source=True,
            layered_wall_end_stroke_closures=True,
        ),
    )
    assert _layered_rooms(_rooms(paint_only)) == ()
    rooms = _rooms(closed)
    assert len(rooms) == 1
    assert _layered_rooms(rooms) == rooms
    assert rooms[0].source_room_face_record_id
    assert closed.room_area_quantity_evidence == ()
    assert publish_live_floor_area_quantities(closed) == ()
