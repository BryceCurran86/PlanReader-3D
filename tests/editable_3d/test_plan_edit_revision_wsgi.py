"""Revision WSGI route: authorization, CSRF, version/download, no fallback."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import json
import sqlite3

import pytest

from pb_plan_edit_revision_wsgi import make_plan_edit_revision_wsgi_app
from test_plan_edit_revision_store import _fixture, _conn


def _service(tmp_path, *, auth=True, csrf=True, save_grant=True,
             coverage_complete=True, same_tenant=True):
    original,user,ws,ledger,coverage,command=_fixture()
    source_db=_conn()
    db_path=str(tmp_path/"workspaces.sqlite")
    out=sqlite3.connect(db_path)
    source_db.backup(out)
    source_db.close();out.close()
    if not save_grant:
        user=replace(user,allowed_revision_workspace_ids=frozenset())
    if not same_tenant:
        user=replace(user,tenant_id="other-tenant")
    calls=[]
    def session(env):
        calls.append("session")
        return user if auth else None
    def load_workspace(p,wid):
        calls.append("workspace")
        return ws
    def load_ledger(p,current):
        calls.append("ledger")
        return ledger,()
    def verify_csrf(env,p):
        calls.append("csrf")
        return csrf
    def load_db(p,current):
        calls.append("database")
        return sqlite3.connect(db_path)
    def load_source(p,current):
        calls.append("source")
        return original
    def related(p,current,cmd):
        calls.append("coverage")
        return replace(coverage, complete=coverage_complete)
    def workspace_db_id(p,current):
        calls.append("workspace_db_id")
        return 1
    app=make_plan_edit_revision_wsgi_app(
        session,load_workspace,load_ledger,verify_csrf,
        load_db,load_source,related,workspace_db_id,
    )
    return app,command,original,calls,db_path


def _request(app,*,method="POST",path="/api/editor/workspaces/w1/revisions",
             data=None,raw=None,ctype="application/json",declared=None):
    b=json.dumps(data or {}).encode("utf-8") if raw is None else raw
    state=[]
    def start(status,headers):
        state.append((status,dict(headers)))
    env={
        "REQUEST_METHOD":method,
        "PATH_INFO":path,
        "CONTENT_TYPE":ctype,
        "CONTENT_LENGTH":str(len(b) if declared is None else declared),
        "wsgi.input":BytesIO(b),
    }
    body=b"".join(app(env,start))
    content=body if state[0][1].get("Content-Type")=="application/pdf" else json.loads(body)
    return state[0][0],state[0][1],content


def test_post_creates_revision_get_history_and_download_edited_pdf(tmp_path):
    app,command,original,calls,db_path=_service(tmp_path)
    status,headers,saved=_request(app,data=command)
    assert status.startswith("201")
    assert saved["saved"] is True
    assert saved["revisionLabel"]=="PR-R0001"
    assert saved["geometryRedrawn"] is False
    assert [row["sheet"] for row in saved["pagesRevised"]]==["A101","A201"]
    assert saved["downloadPath"].endswith("/pdf")
    assert headers["Cache-Control"]=="private, no-store"
    assert "Access-Control-Allow-Origin" not in headers
    assert "csrf" in calls
    assert "source" in calls
    assert "coverage" in calls

    status,headers,history=_request(app,method="GET",data={})
    assert status.startswith("200")
    assert len(history["revisions"])==1
    assert history["revisions"][0]["revisionId"]==saved["revisionId"]

    status,headers,blob=_request(app,method="GET",
                                  path=saved["downloadPath"],data={})
    assert status.startswith("200")
    assert headers["Content-Type"]=="application/pdf"
    assert headers["Content-Disposition"].startswith("attachment")
    assert sha256(blob).hexdigest()==saved["updatedPdfSha256"]
    assert blob != original
    assert sha256(original).hexdigest()==command["sourceSha256"]
    # Idempotent submit can never create duplicate PDF or correction.
    status,_,again=_request(app,data=command)
    assert status.startswith("201")
    assert again["revisionId"]==saved["revisionId"]
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM plan_edit_revisions").fetchone()[0]==1
        assert db.execute("SELECT COUNT(*) FROM editable_3d_correction_events").fetchone()[0]==1


def test_anonymous_and_preview_only_cannot_trigger_save_or_read_private_pdf(tmp_path):
    app,cmd,_,calls,_=_service(tmp_path,auth=False)
    status,_,r=_request(app,data=cmd)
    assert status.startswith("401")
    assert calls==["session"]
    assert r["error"]=="authentication_required"

    app,cmd,_,calls,_=_service(tmp_path,save_grant=False)
    status,_,r=_request(app,data=cmd)
    assert status.startswith("403")
    assert calls==["session"]
    assert r["error"]=="revision_save_permission_denied"

    app,cmd,_,calls,_=_service(tmp_path,same_tenant=False)
    status,_,r=_request(app,data=cmd)
    assert status.startswith("403")
    assert r["error"]=="workspace_scope_mismatch"


def test_csrf_body_and_untrusted_page_link_or_authority_injection_fail(tmp_path):
    app,cmd,_,calls,db_path=_service(tmp_path,csrf=False)
    status,_,r=_request(app,data=cmd)
    assert status.startswith("403")
    assert calls==["session","csrf"]
    assert r["error"]=="csrf_token_invalid"
    app,cmd,_,_,_=_service(tmp_path)
    status,_,r=_request(app,data={**cmd,"pageIndex":100})
    assert status.startswith("409")
    assert r["error"]=="stale_or_conflicting_plan_revision"
    status,_,r=_request(app,data={**cmd,"approved":True})
    assert status.startswith("409")
    status,_,r=_request(app,data=cmd,ctype="text/plain")
    assert status.startswith("415")
    status,_,r=_request(app,data=cmd,declared=50_000)
    assert status.startswith("413")
    status,_,r=_request(app,data=cmd,declared=10_000)
    assert status.startswith("400")
    status,_,r=_request(app,raw=b'{"a":1,"a":2}')
    assert status.startswith("400")
    for token in (b"NaN",b"Infinity",b"-Infinity"):
        status,_,r=_request(app,raw=b'{"n":'+token+b'}')
        assert status.startswith("400")


def test_incomplete_source_cross_page_universe_refuses_save_without_event(tmp_path):
    app,cmd,_,_,db_path=_service(tmp_path,coverage_complete=False)
    status,_,r=_request(app,data=cmd)
    assert status.startswith("422")
    assert r["error"]=="original_source_or_related_page_revision_unverified"
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM plan_edit_revisions").fetchone()[0]==0
        assert db.execute("SELECT COUNT(*) FROM editable_3d_correction_events").fetchone()[0]==0


def test_nonexistent_pdf_and_non_post_methods_cannot_escape_scope(tmp_path):
    app,cmd,_,_,_=_service(tmp_path)
    status,_,r=_request(app,method="PUT",data=cmd)
    assert status.startswith("405")
    status,_,r=_request(app,method="GET",
      path="/api/editor/workspaces/w1/revisions/"+"a"*40+"/pdf")
    assert status.startswith("422")
    assert r["error"]=="original_source_or_related_page_revision_unverified"
    status,_,r=_request(app,method="DELETE",path="/api/editor/workspaces/w1/revisions",
                       data={})
    assert status.startswith("405")
    # Existing quantity preview and scene GET remain independently available.
    status,_,r=_request(app,method="GET",path="/api/editor/workspaces/w1/manifest")
    assert status.startswith("200")
    assert r["readOnly"] is True
    status,_,r=_request(app,path="/api/editor/workspaces/w1/commands/preview",data=cmd)
    assert status.startswith("200")
    assert r["persisted"] is False
