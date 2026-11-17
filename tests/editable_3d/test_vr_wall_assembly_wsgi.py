"""Authenticated wall creation scope previews enforce server-only trade specs."""
from __future__ import annotations
from io import BytesIO
import json

from pb_vr_editor_readonly_wsgi import EditorPrincipal, AuthorizedSceneWorkspace
from pb_vr_editor_scene_manifest import EditorWorkspaceScope
from pb_vr_wall_assembly_dependencies import (
    WallAssemblySpecification,WallServiceItem,KnownServiceRoute,
)
from pb_vr_wall_assembly_wsgi import make_wall_addition_scope_wsgi_app


def _fixture(*,logged=True,authorized=True,csrf=True,profile=True):
    scope=EditorWorkspaceScope(
        "work-1","project-1","doc-1","source-rev","snapshot-1","a"*64,2,
    )
    ws=AuthorizedSceneWorkspace(
        tenant_id="company-1",scope=scope,objects=[],
        canonical_object_ids={},source_witnesses={},
    )
    principal=EditorPrincipal(
        "estimator","company-1",frozenset({"work-1"}),
        frozenset({"work-1"} if authorized else set()),
    )
    calls=[]
    def login(env):
        calls.append("login")
        return principal if logged else None
    def workspace(p,w):
        calls.append("workspace")
        return ws
    def token(e,p):
        calls.append("csrf")
        return csrf
    def assembly(p,w,name):
        calls.append("assembly")
        assert name=="profile-1"
        return WallAssemblySpecification(
            "spec-1",
            framing_system="wood framing",
            stud_spacing_m=0.6,plate_runs=2,noggin_rows=1,
            lining_system="plasterboard",lining_face_ids=("left","right"),
            skirting_system="painted timber",skirting_face_ids=("left","right"),
            services=(WallServiceItem(
                "socket-1","electrical","GPO",1,"No.","elec-plan-source",True,
            ),),
        ) if profile else None
    def routes(p,w,level):
        calls.append("routes")
        assert level=="level-1"
        return (KnownServiceRoute("hydro-line-1","plumbing",level,
                                  (2.,-2.),(2.,2.),True),)
    app=make_wall_addition_scope_wsgi_app(
        login,workspace,token,assembly,routes
    )
    body={
        "workspaceId":"work-1","projectId":"project-1","documentId":"doc-1",
        "revisionId":"source-rev","snapshotId":"snapshot-1",
        "sourceSha256":"a"*64,"baseModelRevision":2,
        "proposalId":"wall-created-1","levelId":"level-1",
        "startPt":[0.,0.],"endPt":[4.,0.],"heightM":2.7,
        "openings":[],"assemblyProfileId":"profile-1",
    }
    return app,body,calls


def _post(app,body,method="POST",raw=None,ctype="application/json",size=None):
    encoded=json.dumps(body).encode() if raw is None else raw
    results=[]
    def start(status,headers):
        results.append((status,dict(headers)))
    env={
        "PATH_INFO":"/api/editor/workspaces/work-1/walls/add/preview",
        "REQUEST_METHOD":method,
        "CONTENT_LENGTH":str(len(encoded) if size is None else size),
        "CONTENT_TYPE":ctype,
        "wsgi.input":BytesIO(encoded),
    }
    result=b"".join(app(env,start))
    return results[0][0],results[0][1],json.loads(result)


def test_previews_framing_lining_skirting_explicit_electrical_and_pipe_conflict():
    app,body,calls=_fixture()
    status,headers,result=_post(app,body)
    assert status.startswith("200")
    assert result["reviewOnly"] is True
    assert result["persisted"] is False
    assert result["commercialPublicationAllowed"] is False
    assert result["sourceGeometryAltered"] is False
    assert result["assemblyProfileId"]=="profile-1"
    elements=[q["element"] for q in result["package"]["quantities"]]
    assert "Preliminary wall stud count" in elements
    assert "Wall plasterboard lining" in elements
    assert "Wall skirting boards" in elements
    assert "Wall electrical item" in elements
    assert "Wall plumbing item" not in elements
    assert "plumbing_route_conflict_hydro-line-1_requires_redesign" in result["package"]["coordination_required"]
    assert result["package"]["original_source_modified"] is False
    assert calls==["login","csrf","workspace","assembly","routes"]
    assert headers["Cache-Control"]=="private, no-store"


def test_anonymous_viewer_csrf_and_invalid_body_rejected_before_profile_read():
    app,body,calls=_fixture(logged=False)
    status,_,result=_post(app,body)
    assert status.startswith("401")
    assert calls==["login"]
    app,body,calls=_fixture(authorized=False)
    status,_,result=_post(app,body)
    assert status.startswith("403")
    assert calls==["login"]
    app,body,calls=_fixture(csrf=False)
    status,_,result=_post(app,body)
    assert status.startswith("403")
    assert calls==["login","csrf"]
    app,body,calls=_fixture()
    status,_,result=_post(app,body,method="GET")
    assert status.startswith("405")
    assert calls==[]
    status,_,result=_post(app,body,ctype="text/plain")
    assert status.startswith("415")
    status,_,result=_post(app,body,size=500_000)
    assert status.startswith("413")


def test_browser_cannot_inject_services_profiles_rates_or_foreign_source_scope():
    app,body,calls=_fixture()
    for attack in (
        {**body,"services":[{"trade":"plumbing","quantity":500}]},
        {**body,"price":0.01},
        {**body,"bracing_area":100},
        {**body,"sourceSha256":"b"*64},
        {**body,"baseModelRevision":1},
        {**body,"assemblyProfileId":"../../etc/passwd"},
        {**body,"heightM":float("nan")},
    ):
        # python serializer permits NaN; API explicitly rejects non-JSON constants
        status,_,result=_post(app,attack)
        assert status.startswith(("400","422")), (attack,result)
    assert calls.count("assembly")==0


def test_cannot_default_fabricated_wall_specs_when_trusted_provider_is_missing():
    app,body,calls=_fixture(profile=False)
    status,_,result=_post(app,body)
    assert status.startswith("422")
    assert result["error"]=="wall_geometry_assembly_or_service_evidence_unverified"
    assert calls==["login","csrf","workspace","assembly"]


def test_duplicate_json_keys_nan_and_unsupported_opening_attributes_refused():
    app,body,calls=_fixture()
    for payload in (
        b'{"x":1,"x":2}',
        b'{"a":NaN}',
        b'{"a":Infinity}',
    ):
        status,_,r=_post(app,body,raw=payload)
        assert status.startswith("400")
    malicious={**body,"openings":[{
        "openingId":"D","offsetM":1,"widthM":0.8,"heightM":2.1,
        "sillHeightM":0,"openingKind":"door",
        "sourceProof":"fake",
    }]}
    status,_,r=_post(app,malicious)
    assert status.startswith("422")
