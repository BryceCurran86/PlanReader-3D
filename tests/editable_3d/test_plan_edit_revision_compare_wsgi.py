"""Synthetic tenant-isolated HTTP tests; no customer plan files."""
from dataclasses import replace
from io import BytesIO
import json
import sqlite3

import pytest

from pb_plan_edit_revision_compare_wsgi import (
    make_plan_edit_revision_compare_wsgi_app,
)
from pb_vr_editor_readonly_wsgi import EditorPrincipal
from test_plan_edit_revision_compare import RIDS, fixture

PATH = "/api/editor/workspaces/w/revisions/compare/" + RIDS[0] + "/" + RIDS[2]


def service(tmp_path, *, anonymous=False, viewer=True, other_tenant=False):
    source_db, principal, workspace = fixture()
    db_path = str(tmp_path / "revision-synthetic.sqlite")
    destination = sqlite3.connect(db_path)
    source_db.backup(destination)
    source_db.close()
    destination.close()
    if not viewer:
        principal = replace(principal, allowed_workspace_ids=frozenset())
    if other_tenant:
        principal = replace(principal, tenant_id="other")
    called = []
    def delegate(env, response):
        called.append("delegate")
        body = b"delegated"
        response("200 OK", [
            ("Content-Type", "text/plain"),
            ("Content-Length", str(len(body))),
        ])
        return [body]
    def session(env):
        called.append("session")
        return None if anonymous else principal
    def load_workspace(user, requested):
        called.append("workspace")
        return workspace
    def open_db(user, ws):
        called.append("database")
        return sqlite3.connect(db_path)
    app = make_plan_edit_revision_compare_wsgi_app(
        delegate, authenticate_session=session,
        load_authorized_workspace=load_workspace,
        get_revision_db_connection=open_db,
    )
    return app, called, db_path


def request(app, *, path=PATH, method="GET"):
    states = []
    def respond(status, headers):
        states.append((status, dict(headers)))
    body = b"".join(app({
        "PATH_INFO": path, "REQUEST_METHOD": method,
        "wsgi.input": BytesIO(b""), "CONTENT_LENGTH": "0",
    }, respond))
    content_type = states[0][1].get("Content-Type", "")
    return states[0][0], states[0][1], (
        json.loads(body) if "application/json" in content_type else body)


def test_authenticated_review_only_comparison_and_no_database_writes(tmp_path):
    app, calls, db_path = service(tmp_path)
    with sqlite3.connect(db_path) as db:
        before = db.execute("SELECT COUNT(*) FROM plan_edit_revisions").fetchone()[0]
    status, headers, result = request(app)
    assert status.startswith("200")
    assert result["interveningRevisionCount"] == 2
    assert result["affectedPageIndices"] == [0, 1]
    assert result["requiresApproval"] and not result["commercialPublicationAllowed"]
    assert headers["Cache-Control"] == "private, no-store"
    assert "Access-Control-Allow-Origin" not in headers
    assert calls == ["session", "workspace", "database"]
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM plan_edit_revisions").fetchone()[0] == before


def test_no_session_or_grant_prevents_db_connection(tmp_path):
    app, calls, _ = service(tmp_path, anonymous=True)
    status, _, body = request(app)
    assert status.startswith("401") and body["error"] == "authentication_required"
    assert calls == ["session"]
    app, calls, _ = service(tmp_path, viewer=False)
    status, _, _ = request(app)
    assert status.startswith("403") and calls == ["session"]


def test_tenant_mismatch_cannot_read_private_revision(tmp_path):
    app, calls, _ = service(tmp_path, other_tenant=True)
    status, _, body = request(app)
    assert status.startswith("403") and body["error"] == "workspace_scope_mismatch"
    assert calls == ["session", "workspace"]


def test_read_only_route_blocks_write_verbs_without_auth_or_database(tmp_path):
    app, calls, _ = service(tmp_path)
    for method in ("POST", "PUT", "DELETE", "PATCH"):
        status, _, body = request(app, method=method)
        assert status.startswith("405") and body["error"] == "revision_comparison_read_only"
    assert calls == []


def test_corrupt_pdf_blocks_http_comparison_and_no_bytes_leak(tmp_path):
    app, calls, db_path = service(tmp_path)
    with sqlite3.connect(db_path) as db:
        db.execute("UPDATE plan_edit_revisions SET updated_pdf_blob=? WHERE revision_id=?",
                   (b"PRIVATE REDACTED ALTERED", RIDS[1]))
    status, headers, body = request(app)
    assert status.startswith("409")
    assert body == {"error": "revision_comparison_unverified"}
    assert "PRIVATE" not in str(body)


def test_unknown_revision_and_bad_order_are_fail_closed(tmp_path):
    app, _, _ = service(tmp_path)
    unknown = PATH.replace(RIDS[0], "a" * 40, 1)
    status, _, body = request(app, path=unknown)
    assert status.startswith("404") and body["error"] == "revision_not_found"
    backwards = "/api/editor/workspaces/w/revisions/compare/" + RIDS[2] + "/" + RIDS[0]
    status, _, body = request(app, path=backwards)
    assert status.startswith("409") and body["error"] == "revision_comparison_unverified"


def test_other_original_service_routes_delegate_unchanged(tmp_path):
    app, calls, _ = service(tmp_path)
    status, _, body = request(app, path="/api/editor/workspaces/w/revisions")
    assert status.startswith("200") and body == b"delegated"
    assert calls == ["delegate"]


def test_bad_workspace_id_rejected(tmp_path):
    app, calls, _ = service(tmp_path)
    path = PATH.replace("/workspaces/w/", "/workspaces/%2fsecret/")
    status, _, body = request(app, path=path)
    assert status.startswith("404") and body["error"] == "invalid_workspace_id"
    assert calls == []
