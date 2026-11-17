"""Actual source-authenticated room, ceiling and roof surfaces in VR."""
from __future__ import annotations
from dataclasses import replace
import math
import pytest

from pb_vr_verified_surface_patches import SourceVerified3DSurface
from pb_vr_editor_scene_manifest import compile_editor_scene
from test_vr_editor_scene_manifest import _scope, _wall, _source_witness


def _mesh(**overrides):
    obj = _wall(object_id="room-1",object_type="room",
                authority_status="firm")
    vertices=(
        (0.,0.,0.),(4.,0.,0.),(4.,0.,3.),
        (0.,0.,0.),(4.,0.,3.),(0.,0.,3.),
    )
    props=dict(
        surface_id="floor-room-1", object_id=obj.object_id,
        object_revision=obj.revision_hash,
        canonical_object_id="canonical-room-1",
        surface_kind="floor",
        document_id="doc-1", revision_id="rev-1",
        source_sha256="a"*64, source_file_id="source-1",
        source_page=2, source_sheet="A100",
        original_geometry_ref="source-segment-17", snapshot_id="snap-1",
        vertices=vertices, source_area_m2=12.0,
        geometry_evidence_id="original-perimeter-hash",
        triangulation_evidence_id="signed-source-triangulation-hash",
        producer_accepted=True,
    )
    props.update(overrides)
    return obj,SourceVerified3DSurface(**props)


def _scene(obj,surface,**kwargs):
    return compile_editor_scene(
        _scope(),[obj],
        canonical_object_ids={obj.object_id:"canonical-room-1"},
        source_witnesses={obj.object_id:_source_witness()},
        source_surfaces=(surface,),
        **kwargs,
    )


def test_existing_room_floor_from_original_witness_is_planar_12m2():
    obj,s=_mesh()
    scene=_scene(obj,s)
    assert scene["schemaVersion"]=="1.0.0"
    assert len(scene["sourceSurfaces"])==1
    surface=scene["sourceSurfaces"][0]
    assert surface["kind"]=="floor"
    assert surface["areaM2"]==12.0
    assert len(surface["vertices"])==6
    assert surface["renderState"]=="verified"
    assert surface["commercialAuthority"] is False
    assert scene["commercialQuantityPublicationAllowed"] is False
    assert scene["objects"][0]["geometry"] is None  # no guessed solid
    assert scene==_scene(obj,s)


def test_verified_ceilings_and_roof_are_distinct_source_meshes():
    obj,s=_mesh()
    ceiling=replace(s,surface_id="ceiling-1",surface_kind="ceiling",
                    vertices=tuple((x,2.8,z) for x,_,z in s.vertices))
    scene=compile_editor_scene(
        _scope(),[obj],
        canonical_object_ids={obj.object_id:"canonical-room-1"},
        source_witnesses={obj.object_id:_source_witness()},
        source_surfaces=(ceiling,s),
    )
    assert [p["kind"] for p in scene["sourceSurfaces"]]==["ceiling","floor"]
    roof_obj=replace(obj,object_id="roof-1",object_type="roof")
    roof=replace(s,object_id="roof-1",object_revision=roof_obj.revision_hash,
                 canonical_object_id="canonical-roof-1",surface_id="roof-1",
                 surface_kind="roof",vertices=(
                     (0.,3.,0.),(4.,3.,0.),(2.,5.,3.)
                 ),source_area_m2=math.sqrt(13.)*2.)
    result=compile_editor_scene(
        _scope(),[roof_obj],
        canonical_object_ids={"roof-1":"canonical-roof-1"},
        source_witnesses={"roof-1":_source_witness()},
        source_surfaces=(roof,),
    )
    assert result["sourceSurfaces"][0]["kind"]=="roof"


def test_missing_source_or_wrong_revision_or_unapproved_room_cannot_render():
    obj,s=_mesh()
    cases=[
        (replace(obj,authority_status="review_required"),s),
        (obj,replace(s,object_revision="stale")),
        (obj,replace(s,source_sha256="b"*64)),
        (obj,replace(s,original_geometry_ref="wrong-path")),
        (obj,replace(s,canonical_object_id="someone-else")),
    ]
    for candidate,patch in cases:
        with pytest.raises(ValueError):
            _scene(candidate,patch)
    with pytest.raises(ValueError):
        compile_editor_scene(_scope(),[obj],source_surfaces=(s,))


def test_degenerate_nonplanar_unreasonably_large_and_unproven_meshes_refused():
    _,s=_mesh()
    for edits in (
        {"vertices":((0.,0.,0.),(1.,0.,0.),(2.,0.,0.))},
        {"vertices":((0.,0.,0.),(1.,0.1,0.),(1.,0.,1.))},
        {"vertices":((0.,0.,0.),(math.nan,0.,0.),(1.,0.,1.))},
        {"source_area_m2":80.0},
        {"geometry_evidence_id":s.triangulation_evidence_id},
        {"producer_accepted":False},
        {"surface_kind":"invented_glazing"},
        {"vertices":s.vertices+(s.vertices[0],)},
    ):
        with pytest.raises(ValueError):
            replace(s,**edits)


def test_source_surface_duplicate_identity_is_rejected():
    obj,s=_mesh()
    with pytest.raises(ValueError,match="duplicate_source_surface_id"):
        compile_editor_scene(
            _scope(),[obj],
            canonical_object_ids={"room-1":"canonical-room-1"},
            source_witnesses={"room-1":_source_witness()},
            source_surfaces=(s,s),
        )
