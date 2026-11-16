"""CSRF, auth, body bounds and source revision gates for preview HTTP."""
from __future__ import annotations

from io import BytesIO
import json

from pb_editable_3d_correction_model import Editable3DCorrectionLedger, EditableGeometryObject
from pb_vr_editor_scene_manifest import EditorWorkspaceScope, VerifiedSourceWitness
from pb_vr_editor_readonly_wsgi import EditorPrincipal, AuthorizedSceneWorkspace
from pb_vr_editor_command_wsgi import make_editor_preview_wsgi_app


def _setup():
    obj = EditableGeometryObject(
        object_id="wall-1", object_type="wall", source_file_id="pdf-1",
        source_page=3, source_sheet="A101", original_geometry_ref="path-18",
        geometry_ref="wall-1", revision_hash="r0",
        coordinates_or_measurements={
            "start_pt": [0.0, 0.0], "end_pt": [4.0, 0.0],
            "length": 4.0, "height": 2.4,
            "height_authority": "figured_dimension",
            "openings": [],
        },
    )
    scope = EditorWorkspaceScope("w1", "p1", "d1", "rev1", "snap1", "a" * 64, 0)
    workspace = AuthorizedSceneWorkspace(
        tenant_id="tenant1", scope=scope, objects=[obj],
        canonical_object_ids={"wall-1": "canonical-wall-1"},
        source_witnesses={"wall-1": VerifiedSourceWitness(
            document_id="d1", revision_id="rev1", source_sha256="a" * 64,
            source_file_id="pdf-1", source_page=3, source_sheet="A101",
            original_geometry_ref="path-18",
        )},
    )
    principal = EditorPrincipal("user1", "tenant1", frozenset({"w1"}))
    ledger = Editable3DCorrectionLedger()
    ledger.register_object(obj)
    command = {
        "commandId": "c1", "idempotencyKey": "i1",
        "workspaceId": "w1", "projectId": "p1",
        "documentId": "d1", "revisionId": "rev1", "snapshotId": "snap1",
        "sourceSha256": "a" * 64, "baseModelRevision": 0,
        "targetObjectId": "wall-1", "targetRevisionHash": "r0",
        "targetCanonicalId": "canonical-wall-1",
        "commandType": "SET_WALL_HEIGHT",
        "payload": {"newValue": 2.6},
        "reason": "Correct source elevation",
    }
    def factory(*, csrf=True, auth=True, tenant=True):
        return make_editor_preview_wsgi_app(
            lambda env: principal if auth else None,
            lambda p, w: workspace if tenant else None,
            lambda p, w: (ledger, ()),
            lambda env, p: csrf,
        )
    return factory, command, ledger


def _request(app, command, *, method="POST", ctype="application/json",
             path="/api/editor/workspaces/w1/commands/preview",
             raw=None, declared_size=None):
    payload = raw if raw is not None else json.dumps(command).encode("utf-8")
    status_headers = []
    def start_response(status, headers):
        status_headers.append((status, dict(headers)))
    env = {
        "REQUEST_METHOD": method, "PATH_INFO": path,
        "CONTENT_TYPE": ctype, "CONTENT_LENGTH": str(
            declared_size if declared_size is not None else len(payload)
        ),
        "wsgi.input": BytesIO(payload),
    }
    body = b"".join(app(env, start_response))
    return status_headers[0][0], status_headers[0][1], json.loads(body)


def test_actual_preview_route_returns_derived_impact_without_mutation():
    factory, command, ledger = _setup()
    before = ledger.get_object("wall-1").to_dict()
    status, headers, result = _request(factory(), command)
    assert status.startswith("200")
    assert result["accepted"] is True
    assert result["persisted"] is False
    assert result["commercialPublicationAllowed"] is False
    assert result["quantityImpacts"]
    assert ledger.get_object("wall-1").to_dict() == before
    assert ledger.events == ()
    assert "Access-Control-Allow-Origin" not in headers
    assert headers["Cache-Control"] == "no-store, private"


def test_auth_and_csrf_block_without_ledger_mutation():
    factory, command, ledger = _setup()
    status, _, result = _request(factory(auth=False), command)
    assert status.startswith("401")
    assert result["error"] == "authentication_required"
    status, _, result = _request(factory(csrf=False), command)
    assert status.startswith("403")
    assert result["error"] == "csrf_token_invalid"
    assert ledger.events == ()


def test_cross_workspace_source_revision_and_write_method_block():
    factory, command, ledger = _setup()
    command["sourceSha256"] = "b" * 64
    status, _, result = _request(factory(), command)
    assert status.startswith("409")
    assert result["accepted"] is False
    assert result["blockingReasons"] == ["sourceSha256_scope_mismatch"]
    status, _, result = _request(factory(), command, method="PUT")
    assert status.startswith("405")
    assert result["error"] == "unsupported_method"
    assert ledger.events == ()


def test_duplicate_keys_invalid_json_and_wrong_content_type():
    factory, command, _ = _setup()
    status, _, result = _request(factory(), command, raw=b'{"a":1,"a":2}')
    assert status.startswith("400")
    assert result["error"] == "invalid_json"
    status, _, result = _request(factory(), command, ctype="text/plain")
    assert status.startswith("415")
    assert result["error"] == "json_required"


def test_oversized_and_truncated_uploads_rejected_before_work():
    factory, command, _ = _setup()
    status, _, result = _request(factory(), command, declared_size=100000)
    assert status.startswith("413")
    assert result["error"] == "command_body_size_invalid"
    status, _, result = _request(factory(), command, declared_size=2000)
    assert status.startswith("400")
    assert result["error"] == "truncated_request_body"


def test_get_readonly_route_still_works_through_combined_factory():
    factory, _, _ = _setup()
    status, _, result = _request(
        factory(), {}, method="GET", path="/api/editor/workspaces/w1/manifest",
    )
    assert status.startswith("200")
    assert result["readOnly"] is True


def test_anonymous_or_wrong_tenant_never_leaks_private_source_geometry():
    factory, command, _ = _setup()
    status, _, result = _request(factory(auth=False), command)
    assert status.startswith("401")
    assert "path-18" not in str(result)
    status, _, result = _request(factory(tenant=False), command)
    assert status.startswith("404")
    assert "path-18" not in str(result)
