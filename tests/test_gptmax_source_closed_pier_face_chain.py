"""Bounded native W2 face-chain proof, not a physical-wall or metric issuer.

Every positive derives from exact, independently owned source parent geometry
and a previously source-proven G17 right-flank face/endcap. Missing, competing,
overlapping and snapped-gap fragments must abstain; benchmark files and
original drawing-specific numeric assertions are intentionally absent.
"""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as Obj
import math

import pytest

from pb_physical_wall_candidate_authority import PhysicalWallSourceEdgeFragment
from pb_raster_source_wall_frame_projection import (
    SourceClosedPierFaceChain,
    source_closed_pier_face_chains,
)


def _fragment_record(name, start, end, face):
    source = "native-source-" + name
    edge = "w2-edge-" + name
    line = (float(start), float(face), float(end), float(face))
    identity = Obj(usable=True, edge_ids=(edge,), source_primitive_ids=(source,))
    wall = Obj(is_curved=False, reason_codes=(),
               centerline_pts=((line[0],line[1]),(line[2],line[3])))
    return Obj(
        wall_candidate_id="w4-" + name, wall_candidate=wall,
        physical_identity=identity,
        source_edge_fragments=(
            PhysicalWallSourceEdgeFragment(edge, line, (source,)),
        ),
    ), source, line


def _faces():
    geometry=Obj(origin=(0.0,0.0),axis=(1.0,0.0),normal=(0.0,1.0),
                 thickness=4.0,length=10.0)
    flank=(10.0,30.0,-2.0,2.0,10.0)
    specs=(
        ("minus-first",10.0,20.0,-2.0),
        ("minus-second",20.0,30.0,-2.0),
        ("plus-first",10.0,17.0,2.0),
        ("plus-second",17.0,30.0,2.0),
    )
    records=[]
    lines={}
    for args in specs:
        record,source,line=_fragment_record(*args)
        records.append(record)
        lines[source]=line
    return geometry,flank,records,lines


def _change_fragment(records,lines,index,*,start=None,end=None,face=None):
    current=records[index]
    fragment=current.source_edge_fragments[0]
    x0,y0,x1,y1=fragment.geometry
    x0=x0 if start is None else start
    x1=x1 if end is None else end
    y0=y1=y0 if face is None else face
    changed=(float(x0),float(y0),float(x1),float(y1))
    current.source_edge_fragments=(replace(fragment,geometry=changed),)
    current.wall_candidate.centerline_pts=((changed[0],changed[1]),
                                            (changed[2],changed[3]))
    lines[current.physical_identity.source_primitive_ids[0]]=changed


def test_complete_staggered_native_pier_faces_come_from_owned_edges_only():
    geometry,flank,records,lines=_faces()
    before=repr((records,lines,geometry))
    proof=source_closed_pier_face_chains(records,geometry,lines,flank)
    assert isinstance(proof,SourceClosedPierFaceChain)
    assert proof.right_flank_interval_pt==(10.0,30.0)
    assert proof.wall_face_offsets_pt==(-2.0,2.0)
    assert proof.face_wall_ids==(
        ("w4-minus-first","w4-minus-second"),
        ("w4-plus-first","w4-plus-second"),
    )
    assert len(proof.face_edge_ids[0])==len(proof.face_edge_ids[1])==2
    assert set(proof.face_primitive_ids[0]).isdisjoint(
        proof.face_primitive_ids[1])
    assert source_closed_pier_face_chains(
        tuple(reversed(records)),geometry,dict(reversed(tuple(lines.items()))),
        flank,
    )==proof
    assert repr((records,lines,geometry))==before
    # This observation has deliberately no frame_id, measurement or issuer.
    assert not hasattr(proof,"whole_wall_frame_id")
    assert not hasattr(proof,"quantity")


@pytest.mark.parametrize("gap", [0.0001,0.01,0.5,2.0])
def test_even_sub_snap_original_source_gap_stays_unknown(gap):
    geometry,flank,records,lines=_faces()
    _change_fragment(records,lines,1,start=20.0+gap)
    assert source_closed_pier_face_chains(records,geometry,lines,flank) is None


@pytest.mark.parametrize("overlap", [0.0001,0.01,0.5])
def test_original_source_overlap_competing_wall_does_not_get_elected(overlap):
    geometry,flank,records,lines=_faces()
    _change_fragment(records,lines,1,start=20.0-overlap)
    assert source_closed_pier_face_chains(records,geometry,lines,flank) is None


@pytest.mark.parametrize("damage", [
    "missing_parent","wrong_parent","offset_parent","deleted_edge",
    "foreign_edge","non_simple","curved","unusable","step_face","too_short",
    "extended_remote","missing_face","third_competing_face","source_less_local",
    "duplicate_wall","shared_parent_both_faces","unknown_right_endcap",
    "unproven_thickness","wrong_left_jamb","wrong_face_sign",
])
def test_neither_unowned_ink_nor_proximity_can_complete_a_source_pier(damage):
    geometry,flank,records,lines=_faces()
    if damage=="missing_parent":
        lines.pop("native-source-plus-first")
    elif damage=="wrong_parent":
        lines["native-source-plus-first"]=(10.,-2.,17.,-2.)
    elif damage=="offset_parent":
        lines["native-source-plus-first"]=(10.,2.1,17.,2.1)
    elif damage=="deleted_edge":
        records[2].source_edge_fragments=()
    elif damage=="foreign_edge":
        x=records[2].source_edge_fragments[0]
        records[2].source_edge_fragments=(replace(x,edge_id="foreign"),)
    elif damage=="non_simple":
        records[2].wall_candidate.reason_codes=(
            "non_simple_chain_topology_fallback_ordering",)
    elif damage=="curved":
        records[2].wall_candidate.is_curved=True
    elif damage=="unusable":
        records[2].physical_identity.usable=False
    elif damage=="step_face":
        _change_fragment(records,lines,2,face=1.9)
    elif damage=="too_short":
        _change_fragment(records,lines,3,end=29.9)
    elif damage=="extended_remote":
        _change_fragment(records,lines,3,end=31.)
    elif damage=="missing_face":
        records.pop()
    elif damage=="third_competing_face":
        rival,source,line=_fragment_record("extra-rival",11.,18.,0.)
        records.append(rival)
        lines[source]=line
    elif damage=="source_less_local":
        rival,_,_=_fragment_record("unknown-local",11.,18.,0.)
        rival.source_edge_fragments=()
        records.append(rival)
    elif damage=="duplicate_wall":
        records.append(deepcopy(records[0]))
    elif damage=="shared_parent_both_faces":
        records[3].physical_identity.source_primitive_ids=(
            "native-source-minus-first",)
        original=records[3].source_edge_fragments[0]
        records[3].source_edge_fragments=(
            replace(original,source_primitive_ids=("native-source-minus-first",)),
        )
    elif damage=="unknown_right_endcap":
        flank=(10.,30.,-2.,2.,10.01)
    elif damage=="unproven_thickness":
        flank=(10.,30.,-2.,1.9,10.)
    elif damage=="wrong_left_jamb":
        flank=(10.01,30.,-2.,2.,10.01)
    elif damage=="wrong_face_sign":
        flank=(10.,30.,0.,4.,10.)
    assert source_closed_pier_face_chains(records,geometry,lines,flank) is None


def test_unrelated_outside_flank_fragment_does_not_extend_local_pier():
    geometry,flank,records,lines=_faces()
    remote,source,line=_fragment_record("remote",50.,60.,-2.)
    records.append(remote)
    lines[source]=line
    baseline=source_closed_pier_face_chains(records[:-1],geometry,lines,flank)
    assert source_closed_pier_face_chains(records,geometry,lines,flank)==baseline


@pytest.mark.parametrize("angle,shift,scale", [
    (0.,(33.,-17.),1.),(math.pi/2.,(200.,50.),1.),
    (math.pi/3.,(100.,200.),2.),
])
def test_exact_original_face_proof_rotation_translation_scale_invariance(
    angle,shift,scale,
):
    geometry,flank,records,lines=_faces()
    c,s=math.cos(angle),math.sin(angle)
    def point(x,y):
        return (scale*(x*c-y*s)+shift[0],
                scale*(x*s+y*c)+shift[1])
    original_lines=dict(lines)
    for record in records:
        line=record.source_edge_fragments[0].geometry
        start,end=point(*line[:2]),point(*line[2:])
        transformed=(*start,*end)
        edge=record.source_edge_fragments[0]
        record.source_edge_fragments=(replace(edge,geometry=transformed),)
        record.wall_candidate.centerline_pts=(start,end)
        lines[record.physical_identity.source_primitive_ids[0]]=transformed
    geometry.origin=point(0.,0.)
    geometry.axis=(c,s)
    geometry.normal=(-s,c)
    geometry.length*=scale
    geometry.thickness*=scale
    scaled_flank=tuple(x*scale for x in flank)
    actual=source_closed_pier_face_chains(records,geometry,lines,scaled_flank)
    assert actual is not None
    assert actual.right_flank_interval_pt==pytest.approx(
        (10.*scale,30.*scale),abs=1e-6)
    assert len(original_lines)==4


def test_default_live_frame_publisher_cannot_consume_local_pier_candidate():
    from test_raster_connected_host_frame import _fixture as live_fixture
    from test_raster_connected_host_frame import _publish
    from pb_migration_contracts import EvidenceResolutionStatus as Status

    source,composition,producer,bound=live_fixture()
    before=_publish(producer,bound)
    assert all(x.status is Status.CORROBORATED for x in before)
    for selector,opening,binding_selector,binding in bound:
        assert producer.source_closed_right_pier_shadow(
            opening_selector=selector,
            host_binding_selector=binding_selector,
        ) is None
    assert _publish(producer,tuple(reversed(bound)))==tuple(reversed(before))
