"""Original PlanReader: real dark native PDF wall ink into room-face source path.

This is a SOURCE trace only: PDF paint is not finished-face ownership,
metric area or customer quantity. The feature is default-off and the
canonical room entrypoint requires its existing finished-face gate.
"""
from __future__ import annotations
from pathlib import Path
import os

import fitz
import pytest

from pb_layered_wall_doorway_room_ring_shadow import (
    _collect_dark_painted_source_wall_strips,
    _source_wall_ink_candidate_drawings,
    _owner_excluded_green_ink,
    build_layered_wall_doorway_room_rings,
)
from pb_layered_wall_doorway_room_face_scope_shadow import (
    LAYERED_RING_FINISHED_FACE_GATE_REASON,
    layered_ring_room_face_scope,
)
from pb_live_canonical_room_composition import compose_live_canonical_rooms
from pb_migration_contracts import EvidenceResolutionStatus

SHA = "ab" * 32


def _rect(x0, y0, x1, y1, color, *, layer="", opacity=1.0, stroke=None):
    return {
        "fill": color,
        "fill_opacity": opacity,
        "color": stroke,
        "layer": layer,
        "items": [("re", fitz.Rect(x0, y0, x1, y1), 1)],
    }


def _dark_rect_room():
    ink = (0.195, 0.195, 0.195)
    return (
        _rect(0, 0, 100, 4, ink),
        _rect(0, 4, 4, 96, ink),
        _rect(96, 4, 100, 96, ink),
        _rect(0, 96, 100, 100, ink),
    )


def _candidates(packet):
    return tuple(
        r for r in packet.rings
        if r.status is EvidenceResolutionStatus.CANDIDATE
    )


def test_original_room_tracer_reads_real_dark_gray_wall_fill_when_enabled():
    source=_dark_rect_room()
    disabled=build_layered_wall_doorway_room_rings(source,source_sha256=SHA,page_index=0)
    assert not disabled.rings
    assert not disabled.closures
    enabled=build_layered_wall_doorway_room_rings(
        source,source_sha256=SHA,page_index=0,dark_painted_wall_source=True,
    )
    closed=_candidates(enabled)
    assert len(closed)==1
    assert closed[0].bbox_pdf_pts==(4,4,96,96)
    assert set(closed[0].bounding_wall_path_indices)=={0,1,2,3}
    assert closed[0].closure_edge_count==0
    assert all(closed[0].edge_owner_ids)
    assert closed[0].takeoff_eligible is False
    assert closed[0].commercial_projection_allowed is False
    assert closed[0].metric_area_issued is False


def test_no_invented_wall_from_white_mask_or_dark_short_decorations():
    original=list(_dark_rect_room())
    original.pop(1)  # missing left structural wall
    added=[
        _rect(0,0,100,100,(1.0,1.0,1.0)),
        _rect(0,4,4,11,(.195,.195,.195)),
        _rect(0,11,4,96,(.195,.195,.195),opacity=.5),
        _rect(0,11,4,96,(.195,.195,.195),stroke=(0,0,0)),
        _rect(0,11,4,96,(.195,.1,.195)),
    ]
    packet=build_layered_wall_doorway_room_rings(
        tuple(original+added),source_sha256=SHA,page_index=0,
        dark_painted_wall_source=True,
    )
    assert not _candidates(packet)
    # The white layout mask and bogus source ink do not close the missing wall.
    assert len(_collect_dark_painted_source_wall_strips(tuple(original+added)))==3


def test_dark_fill_candidates_pass_to_original_room_face_scope_without_area():
    rings=build_layered_wall_doorway_room_rings(
        _dark_rect_room(),source_sha256=SHA,page_index=0,
        dark_painted_wall_source=True,
    )
    scope=layered_ring_room_face_scope(
        rings,document_id="test-doc",revision_id="test-rev",
        source_sha256=SHA,snapshot_id="test-snapshot",
        page_id="1",decision_scope_id="wall-source:page-1",
        finished_face_gate=True,
    )
    assert scope is not None
    assert scope.records and len(scope.records)==1
    assert LAYERED_RING_FINISHED_FACE_GATE_REASON in scope.reason_codes
    assert any(x.startswith("layered_ring_finished_face_required:")
               for x in scope.reason_codes)
    assert all(record.area_page_pts2>0 for record in scope.records)
    # This authority is NOT the quantity issuer. Page-space points^2
    # can never be treated as a finished-face m^2 customer row.
    assert rings.rings[0].metric_area_issued is False


@pytest.mark.parametrize("wrong",("yes",1,None))
def test_source_paint_mode_requires_explicit_bool(wrong):
    with pytest.raises(ValueError,match="explicit boolean"):
        build_layered_wall_doorway_room_rings(
            _dark_rect_room(),source_sha256=SHA,page_index=0,
            dark_painted_wall_source=wrong,
        )


def test_canonical_room_source_dark_mode_requires_both_production_gates():
    kwargs={
        "source_visibility_producer": None,
        "wall_opening_composition": None,
    }
    with pytest.raises(ValueError,match="requires"):
        compose_live_canonical_rooms(
            **kwargs,layered_dark_painted_wall_source=True,
        )
    with pytest.raises(ValueError,match="requires"):
        compose_live_canonical_rooms(
            **kwargs,layered_doorway_room_rings=True,
            layered_dark_painted_wall_source=True,
        )
    with pytest.raises(ValueError,match="explicit boolean"):
        compose_live_canonical_rooms(
            **kwargs,layered_dark_painted_wall_source="true",
        )


def test_original_maryborough_a120_contains_actual_dark_wall_bars_not_white_masks():
    name=os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF")
    if not name or not Path(name).is_file():
        pytest.skip("private original Maryborough not provisioned")
    p=Path(name)
    assert __import__("hashlib").sha256(p.read_bytes()).hexdigest() == (
        "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
    )
    with fitz.open(p) as doc:
        rows=doc[8].get_drawings()
    source=_collect_dark_painted_source_wall_strips(rows)
    assert source
    refs={strip.path_index for strip in source}
    assert 73 in refs
    assert 63 in refs
    assert 56 in refs
    # The white source mask p141 is NOT a wall, and the real dark
    # wall 56 does not extend across x694..1217 into Sales.
    assert 141 not in refs
    dark=next(r for r in source if r.path_index==56)
    assert dark.x1<=694.08
    assert all(r.path_index!=141 for r in source)


def test_green_aisle_equipment_coldroom_details_never_enter_wall_tracing():
    assert _owner_excluded_green_ink((0.0, .5, 0.0))
    assert _owner_excluded_green_ink((.465088, .730469, .465088))
    assert _owner_excluded_green_ink((.589844, .792969, .589844))
    assert not _owner_excluded_green_ink((0.0, 0.0, 0.0))
    assert not _owner_excluded_green_ink((.195, .195, .195))
    assert not _owner_excluded_green_ink((1., 1., 1.))
    paint = list(_dark_rect_room())
    paint.extend([
        _rect(0, 20, 4, 96, (.0, .5, .0)),
        _rect(0, 20, 4, 96, (.195, .195, .195), stroke=(.0, .5, .0)),
        _rect(0, 20, 4, 96, (.59, .793, .59)),
    ])
    original_ids=tuple(range(len(paint)))
    filtered, kept, dropped=_source_wall_ink_candidate_drawings(paint)
    assert len(filtered)==len(original_ids)
    assert dropped==3
    assert kept==4
    assert all(not filtered[i]["items"] for i in (4,5,6))
    assert len(filtered)==len(paint)


def test_real_maryborough_green_exclusion_unblocks_bounded_original_floor_wall_trace():
    name=os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF")
    if not name or not Path(name).is_file():
        pytest.skip("private original Maryborough not provisioned")
    with fitz.open(name) as doc:
        drawings=doc[6].get_drawings()
    assert len(drawings)==109_354
    eligible, source_count, green_count=_source_wall_ink_candidate_drawings(drawings)
    assert green_count==64_333
    assert source_count==14_038
    assert len(eligible)==len(drawings)
    assert len(drawings)-green_count==45_021
    # The actual original tracer, not just a test helper, uses these
    # SOURCE-PAINTED black paired lines with their ORIGINAL path indices.
    result=build_layered_wall_doorway_room_rings(
        drawings,source_sha256=SHA,page_index=6,
        dark_painted_wall_source=True,
    )
    assert result.wall_strip_count==116
    assert len(result.rings)>0
    assert sum(r.status is EvidenceResolutionStatus.CANDIDATE for r in result.rings)==6
    assert len(result.closures)==0  # doorways still await verified source witness
    assert all(not r.metric_area_issued and not r.commercial_projection_allowed
               for r in result.rings)
    assert all(all(0<=i<len(drawings) for i in r.bounding_wall_path_indices)
               for r in result.rings)


def test_opt_in_never_truncates_more_than_20000_qualifying_source_graphics():
    sources=list(_dark_rect_room())
    black=_rect(1,1,2,2,None,stroke=(0.0,0.0,0.0))
    sources.extend([black]*(20_001-len(sources)))
    got=build_layered_wall_doorway_room_rings(
        sources,source_sha256=SHA,page_index=0,dark_painted_wall_source=True,
    )
    assert got.status is EvidenceResolutionStatus.ABSTAINED
    assert got.reason_codes == (
        "unlabelled_dark_wall_page_exceeds_20000_primitive_cap_needs_bounded_viewport",
    )
    assert got.wall_strip_count==0
    assert got.rings==()


def test_20000_cap_counts_native_items_not_just_pdf_path_containers():
    line=(("l",fitz.Point(1,1),fitz.Point(7,1)))
    compound={
        "layer":"",
        "fill":None,
        "color":(0.0,0.0,0.0),
        "items":[line,line,line],
    }
    drawings=[compound]*6_668
    assert len(drawings)<20_000
    assert sum(len(p["items"]) for p in drawings)>20_000
    report=build_layered_wall_doorway_room_rings(
        drawings,source_sha256=SHA,page_index=0,
        dark_painted_wall_source=True,
    )
    assert report.status is EvidenceResolutionStatus.ABSTAINED
    assert report.reason_codes==(
        "unlabelled_dark_wall_page_exceeds_20000_primitive_cap_needs_bounded_viewport",
    )


def test_source_original_dark_wall_path_is_strictly_default_off():
    original=_dark_rect_room()
    old=build_layered_wall_doorway_room_rings(
        original,source_sha256=SHA,page_index=0,
    )
    default_explicit=build_layered_wall_doorway_room_rings(
        original,source_sha256=SHA,page_index=0,
        dark_painted_wall_source=False,
    )
    assert old==default_explicit
