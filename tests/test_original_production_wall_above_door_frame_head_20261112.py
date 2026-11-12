"""Original app production wall/door head rule, not the Next quantity engine."""
from __future__ import annotations

from shapely.geometry import box
from shapely import wkb
from shapely.ops import unary_union

from pb_live_external_physical_net_wall_publication import (
    LIVE_EXTERNAL_PHYSICAL_NET_WALL_GEOMETRY_INVALID,
    _source_wall_above_frame_head_is_retained,
    compose_live_external_physical_net_wall_publication,
)
from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_live_external_physical_net_wall_publication import _chain


def test_authentic_source_opening_leaves_wall_from_frame_head_to_ceiling():
    wall_opening, physical_void, gross, roles, void, original_wall = _chain()
    output=compose_live_external_physical_net_wall_publication(
        wall_opening_composition=wall_opening,
        physical_void_composition=physical_void,
        gross_wall_composition=gross,
        whole_wall_role_composition=roles,
    )
    assert output.status is EvidenceResolutionStatus.CORROBORATED
    wall=output.canonical_walls[0]
    assert wall.height_m > float(void.z1)
    source_head=box(void.u0,void.z1,void.u1,wall.height_m)
    net=wkb.loads(bytes.fromhex(wall.net_polygon_wkb_hex))
    assert net.covers(source_head)
    assert source_head.area>0
    assert wall.net_area_m2 == round(
        float(original_wall.gross_area_m2) -
        (float(void.u1)-float(void.u0))*(float(void.z1)-float(void.z0)),
        6,
    )
    assert output.quantity_evidence is not None
    assert output.quantity_evidence.value==wall.net_area_m2


def test_false_full_height_door_cut_is_rejected_inside_live_production(monkeypatch):
    wall_opening, physical_void, gross, roles, void, original_wall = _chain()
    # Bad implementer assumes a door deletes its full-height wall bay:
    # this is the original defect owner's rule must permanently prevent.
    assert void.z1 < original_wall.height_m
    def incorrectly_cut_wall_to_ceiling(gross_wall_polygon, void_polygons):
        opening=tuple(void_polygons)[0]
        x0,_,x1,_=opening.bounds
        return gross_wall_polygon.difference(box(x0,0,x1,original_wall.height_m))
    monkeypatch.setattr(
        "pb_live_external_physical_net_wall_publication.subtract_void_union_from_wall_polygon",
        incorrectly_cut_wall_to_ceiling,
    )
    output=compose_live_external_physical_net_wall_publication(
        wall_opening_composition=wall_opening,
        physical_void_composition=physical_void,
        gross_wall_composition=gross,
        whole_wall_role_composition=roles,
    )
    assert output.status is EvidenceResolutionStatus.CONFLICT
    assert LIVE_EXTERNAL_PHYSICAL_NET_WALL_GEOMETRY_INVALID in output.reason_codes
    assert output.quantity_evidence is None
    assert output.canonical_walls == ()


def test_actual_full_height_source_opening_has_no_required_wall_above_it():
    wall=box(0,0,4,3)
    void=box(1,0,2,3)
    assert _source_wall_above_frame_head_is_retained(
        wall_length_m=4.0,
        wall_height_m=3.0,
        opening_void_polygons=(void,),
        net_wall_polygon=wall.difference(void),
    )


def test_source_attested_transom_above_door_is_respected():
    gross=box(0,0,4,3)
    door=box(1,0,2,2.1)
    transom=box(1,2.1,2,2.6)
    true_net=gross.difference(unary_union([door,transom]))
    assert _source_wall_above_frame_head_is_retained(
        wall_length_m=4.0,
        wall_height_m=3.0,
        opening_void_polygons=(door,transom),
        net_wall_polygon=true_net,
    )
    # Only 0.4 m of wall remains above the transom.
    assert true_net.covers(box(1,2.6,2,3))


def test_unproved_opening_does_not_create_a_fake_header_or_extra_deduction():
    gross=box(0,0,4,3)
    void=box(1,0,2,2.1)
    wrong_net=gross.difference(box(1,0,2,3))
    assert not _source_wall_above_frame_head_is_retained(
        wall_length_m=4.0,
        wall_height_m=3.0,
        opening_void_polygons=(void,),
        net_wall_polygon=wrong_net,
    )
    assert not _source_wall_above_frame_head_is_retained(
        wall_length_m=4.0,
        wall_height_m=3.0,
        opening_void_polygons=(box(1,0,5,2.1),),
        net_wall_polygon=gross,
    )


def test_door_frame_height_is_not_assumed_when_source_does_not_authenticate_it():
    # No door void evidence means no source-verified door head height,
    # no opening area and no invented physical-wall deletion.
    gross=box(0,0,4,3)
    assert _source_wall_above_frame_head_is_retained(
        wall_length_m=4.0,
        wall_height_m=3.0,
        opening_void_polygons=(),
        net_wall_polygon=gross,
    )
