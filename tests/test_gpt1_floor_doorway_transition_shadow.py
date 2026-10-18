"""Synthetic positive/negative doorway source boundary tests; no benchmark truth."""
from __future__ import annotations
from dataclasses import replace
import copy
import math
import pytest

from pb_gpt1_floor_doorway_transition_shadow import diagnose_floor_doorway_transition_shadow
from pb_live_canonical_floor_surface import LiveCanonicalFloorSurfaceObject
from pb_opening_host_frame_authority import (
    OpeningHostFrameSelector, OpeningHostFrameEvidence, OpeningHostFrameResult,
)
from pb_opening_kind_authority import resolve_opening_kind
from pb_physical_opening_authority import (
    PhysicalOpeningExistenceRecord, GAP_CORROBORATED_DOOR_JAMB_LEAF,
)
from pb_migration_contracts import EvidenceResolutionStatus as S

SRC = "a"*64
DOC = "synthetic-building"
REV = "rev1"
SNAP = "snapshot1"
PAGE = "1"
HOST = "source-wall-common"


def floor(suffix, points):
    return LiveCanonicalFloorSurfaceObject(
        canonical_floor_id="floor-"+suffix,
        physical_floor_surface_id="floor-"+suffix,
        room_entity_id="room-"+suffix,
        document_id=DOC,revision_id=REV,source_sha256=SRC,
        snapshot_id=SNAP,page_id=PAGE,viewport_id="view1",
        polygon_pdf_pts=tuple(points),area_page_pts2=100.0,
        bounding_wall_ids=(HOST,"outer-"+suffix),
        canonical_bounding_wall_ids=(HOST,),
        source_room_face_record_id="source-face-"+suffix,
        evidence_ids=("original-face-"+suffix,),
        geometry_complete=True,metric_geometry_complete=False,
        metric_area_m2=None,metric_area_quantity_id=None,metric_area_authority=None,
        finish_descriptor=None,structural_slab_id=None,
        physical_floor_surface_identity_resolved=True,
        commercial_quantity_authority=False,
    )


def fixtures():
    left=floor("a",((0.,0.),(10.,0.),(10.,10.),(0.,10.)))
    right=floor("b",((10.,0.),(20.,0.),(20.,10.),(10.,10.)))
    selector=OpeningHostFrameSelector(document_id=DOC,revision_id=REV,source_sha256=SRC,
        snapshot_id=SNAP,page_id=PAGE,decision_scope_id="producer-scope",opening_identity_id="door1")
    ev=OpeningHostFrameEvidence(selector=selector,record_id="frame1",opening_identity_id="door1",
        host_binding_record_id="bind1",host_wall_id=HOST,whole_wall_frame_id="wallframe1",
        whole_wall_candidate_ids=(HOST,),source_observation_ids=("obs-door",),
        origin_pt=(10.,0.),axis_unit=(0.,1.),normal_unit=(1.,0.),
        u0_pt=2.,u1_pt=6.,wall_thickness_pt=0.2,whole_wall_length_pt=10.)
    frame=OpeningHostFrameResult(status=S.CORROBORATED,reason_codes=(),evidence=ev)
    opening=PhysicalOpeningExistenceRecord(
        record_id="exist1",source_observation_ids=("obs-door",),
        source_lineage_root_ids=("root1",),
        document_id=DOC,revision_id=REV,source_sha256=SRC,snapshot_id=SNAP,
        page_id=PAGE,viewport_id="view1",semantic_class="door",status=S.CORROBORATED,
        proposition="physical_opening_exists",structural_pattern=GAP_CORROBORATED_DOOR_JAMB_LEAF,
        diagnostic_confidence=1.,blocking_reasons=(),structural_reason_codes=(),
        producer_method="synthetic-proof",producer_version="v1",producer_generation=1,
    )
    kind=resolve_opening_kind(structural_pattern=GAP_CORROBORATED_DOOR_JAMB_LEAF)
    assert kind.structural_kind=="door"
    return left,right,opening,frame,kind


def run(left=None,right=None,opening=None,frame=None,kind=None):
    base=fixtures()
    args=[
        left if left is not None else base[0],
        right if right is not None else base[1],
        opening if opening is not None else base[2],
        frame if frame is not None else base[3],
        kind if kind is not None else base[4],
    ]
    return diagnose_floor_doorway_transition_shadow(
        args[0],args[1],opening=args[2],host_frame=args[3],kind=args[4],
    )


def test_shared_original_doorway_source_edge_is_candidate_never_firm():
    result=run()
    assert result.status is S.CANDIDATE
    assert result.threshold_pdf_pts==((10.,2.),(10.,6.))
    assert result.source_floor_ids==("floor-a","floor-b")
    assert result.candidate_id
    assert result.diagnostic_only and not result.finish_transition_authorized
    assert not result.commercial_projection_allowed
    assert not hasattr(result,"quantity")


def test_reverse_input_and_vertex_winding_are_invariant():
    a,b,op,fr,k=fixtures()
    base=run()
    reversed_result=run(b,a,op,fr,k)
    rotated_a=replace(a,polygon_pdf_pts=a.polygon_pdf_pts[2:]+a.polygon_pdf_pts[:2])
    reversed_b=replace(b,polygon_pdf_pts=tuple(reversed(b.polygon_pdf_pts)))
    other=run(rotated_a,reversed_b,op,fr,k)
    assert base.candidate_id==reversed_result.candidate_id==other.candidate_id
    assert other.threshold_pdf_pts==base.threshold_pdf_pts


def test_split_collinear_source_polygon_edge_invariance():
    a,b,op,fr,k=fixtures()
    a=replace(a,polygon_pdf_pts=((0.,0.),(10.,0.),(10.,4.),(10.,10.),(0.,10.)))
    b=replace(b,polygon_pdf_pts=((10.,0.),(20.,0.),(20.,10.),(10.,10.),(10.,4.)))
    assert run(a,b,op,fr,k).candidate_id==run().candidate_id


@pytest.mark.parametrize("field,new",[
    ("snapshot_id","unrelated-snapshot"),
    ("revision_id","stale"),
    ("source_sha256","b"*64),
    ("document_id","unrelated-building"),
    ("page_id","2"),
])
def test_floor_lineage_conflict_abstains(field,new):
    a,b,op,fr,k=fixtures()
    assert run(a,replace(b,**{field:new}),op,fr,k).status is S.CONFLICT


def test_missing_original_floor_geometry_abstains():
    a,b,op,fr,k=fixtures()
    assert run(replace(a,geometry_complete=False),b,op,fr,k).status is S.ABSTAINED
    assert run(replace(a,physical_floor_surface_identity_resolved=False),b,op,fr,k).status is S.ABSTAINED
    assert run(a,a,op,fr,k).status is S.CONFLICT


def test_door_kind_requires_same_physical_structural_pattern():
    a,b,op,fr,k=fixtures()
    label=resolve_opening_kind(structural_pattern="unsupported",label_kind="door")
    window=resolve_opening_kind(structural_pattern="gap_corroborated_window_jamb_pair")
    for other in (label,window):
        assert run(a,b,op,fr,other).status is S.ABSTAINED
    assert run(a,b,replace(op,structural_pattern="unsourced_annotation"),fr,k).status is S.ABSTAINED
    assert run(a,b,replace(op,semantic_class="window"),fr,k).status is S.ABSTAINED


def test_source_opening_and_host_ancestry_required():
    a,b,op,fr,k=fixtures()
    assert run(a,b,replace(op,status=S.CANDIDATE),fr,k).status is S.ABSTAINED
    assert run(a,b,replace(op,source_observation_ids=("other-obs",)),fr,k).status is S.ABSTAINED
    assert run(a,b,replace(op,revision_id="rev2"),fr,k).status is S.CONFLICT
    assert run(a,b,op,replace(fr,status=S.CONFLICT),k).status is S.ABSTAINED
    ev=fr.evidence
    assert run(a,b,op,replace(fr,evidence=replace(ev,host_wall_id="wrong-wall")),k).status is S.ABSTAINED
    assert run(a,b,op,replace(fr,evidence=replace(ev,coordinate_unit="metre")),k).status is S.ABSTAINED
    assert run(a,b,op,replace(fr,evidence=replace(ev,whole_wall_length_pt=None)),k).status is S.ABSTAINED
    assert run(a,b,op,replace(fr,evidence=replace(ev,whole_wall_candidate_ids=("different",))),k).status is S.ABSTAINED
    assert run(a,b,op,replace(fr,evidence=replace(ev,opening_identity_id="wrong-id")),k).status is S.ABSTAINED
    wrong=replace(ev.selector,source_sha256="c"*64)
    assert run(a,b,op,replace(fr,evidence=replace(ev,selector=wrong)),k).status is S.CONFLICT


def test_unproven_gap_cannot_be_drawn_as_a_wall():
    a,b,op,fr,k=fixtures()
    clipped=replace(b,polygon_pdf_pts=((11.,0.),(20.,0.),(20.,10.),(11.,10.)))
    result=run(a,clipped,op,fr,k)
    assert result.status is S.ABSTAINED
    assert result.threshold_pdf_pts is None
    assert result.reason_codes==("original_doorway_threshold_not_on_both_floor_edges",)


def test_overlapping_rooms_or_frame_beyond_wall_cannot_publish():
    a,b,op,fr,k=fixtures()
    overlap=replace(b,polygon_pdf_pts=((8.,0.),(20.,0.),(20.,10.),(8.,10.)))
    assert run(a,overlap,op,fr,k).status is S.ABSTAINED
    outside=replace(fr.evidence,u0_pt=2.,u1_pt=15.)
    assert run(a,b,op,replace(fr,evidence=outside),k).status is S.ABSTAINED


def test_missing_wall_owner_or_nonunit_frame_abstains():
    a,b,op,fr,k=fixtures()
    assert run(a,replace(b,bounding_wall_ids=("different-wall",)),op,fr,k).status is S.ABSTAINED
    bad=replace(fr.evidence,axis_unit=(0.,2.))
    assert run(a,b,op,replace(fr,evidence=bad),k).status is S.ABSTAINED


def test_translation_scale_rotation_equivariance_and_stable_identity():
    a,b,op,fr,k=fixtures()
    base=run(a,b,op,fr,k)
    def tf(point,mode):
        x,y=point
        if mode=="translate":return x+100.,y-200.
        if mode=="scale":return 2*x,2*y
        return -y,x
    for mode in ("translate","scale","rotate"):
        aa=replace(a,polygon_pdf_pts=tuple(tf(p,mode) for p in a.polygon_pdf_pts))
        bb=replace(b,polygon_pdf_pts=tuple(tf(p,mode) for p in b.polygon_pdf_pts))
        ev=fr.evidence
        origin=tf(ev.origin_pt,mode)
        axis=tf(ev.axis_unit,"rotate") if mode=="rotate" else ev.axis_unit
        normal=tf(ev.normal_unit,"rotate") if mode=="rotate" else ev.normal_unit
        scale=2 if mode=="scale" else 1
        transformed=replace(ev,origin_pt=origin,axis_unit=axis,normal_unit=normal,
            u0_pt=ev.u0_pt*scale,u1_pt=ev.u1_pt*scale,
            wall_thickness_pt=ev.wall_thickness_pt*scale,
            whole_wall_length_pt=ev.whole_wall_length_pt*scale)
        result=run(aa,bb,op,replace(fr,evidence=transformed),k)
        assert result.status is S.CANDIDATE,result.reason_codes
        assert result.candidate_id==base.candidate_id
        assert all(math.dist(x,y)<1e-8 for x,y in zip(
            result.threshold_pdf_pts,[tf(p,mode) for p in base.threshold_pdf_pts],
        ))


def test_replay_determinism_and_no_input_mutation():
    a,b,op,fr,k=fixtures()
    before=copy.deepcopy((a,b,op,fr,k))
    assert run(a,b,op,fr,k)==run(a,b,op,fr,k)
    assert before==(a,b,op,fr,k)
