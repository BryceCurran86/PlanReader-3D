"""Strict WSGI access: source data never crosses tenant or session boundary."""
from __future__ import annotations

import json
from dataclasses import replace

import pytest

from pb_editable_3d_correction_model import EditableGeometryObject
from pb_vr_editor_scene_manifest import EditorWorkspaceScope, VerifiedSourceWitness
from pb_vr_editor_readonly_wsgi import (
    EditorPrincipal, AuthorizedSceneWorkspace, make_editor_readonly_wsgi_app,
)


def _test_call(app, path="/api/editor/workspaces/w1/manifest", method="GET"):
    response = []
    def start(status, headers):
        response.append((status, dict(headers)))
    body = b"".join(app({"PATH_INFO": path, "REQUEST_METHOD": method}, start))
    status, headers = response[0]
    return status, headers, json.loads(body)


def _workspace(tenant="tenant-1", workspace="w1"):
    obj = EditableGeometryObject(
        object_id="wall-1", object_type="wall", source_page=3,
        source_sheet="A101", original_geometry_ref="native:d2i3",
        geometry_ref="wall-1", revision_hash="wall-rev-1",
        coordinates_or_measurements={
            "start_pt": [0.0, 0.0], "end_pt": [3.0, 0.0],
            "length": 3.0, "height": 2.4,
            "height_authority": "figured_dimension",
        },
    )
    return AuthorizedSceneWorkspace(
        tenant_id=tenant,
        scope=EditorWorkspaceScope(
            workspace, "project-1", "document-1", "revision-1", "snapshot-1",
            "a" * 64, 0,
        ),
        objects=[obj],
        canonical_object_ids={"wall-1": "canonical-1"},
    )


def _principal(tenant="tenant-1", grants=frozenset({"w1"})):
    return EditorPrincipal("user-1", tenant, grants)


def test_no_anonymous_scene_and_no_workspace_loader_called():
    invoked = []
    app = make_editor_readonly_wsgi_app(
        lambda env: None,
        lambda principal, workspace: invoked.append(workspace),
    )
    status, headers, result = _test_call(app)
    assert status.startswith("401")
    assert result == {"error": "authentication_required"}
    assert invoked == []
    assert "Access-Control-Allow-Origin" not in headers
    assert headers["Cache-Control"] == "no-store, private"


def test_authenticated_same_workspace_scene_contains_original_refs():
    app = make_editor_readonly_wsgi_app(
        lambda env: _principal(), lambda principal, workspace: _workspace(),
    )
    status, headers, result = _test_call(app)
    assert status.startswith("200")
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert result["commercialQuantityPublicationAllowed"] is False
    assert result["readOnly"] is True
    assert result["scope"]["sourceSha256"] == "a" * 64
    assert result["objects"][0]["source"]["originalGeometryRef"] == "native:d2i3"
    assert result["objects"][0]["canonicalObjectId"] == "canonical-1"
    assert result["objects"][0]["canEdit"] is False


def test_grant_denied_before_workspace_fetch():
    invoked = []
    app = make_editor_readonly_wsgi_app(
        lambda env: _principal(grants=frozenset({"w2"})),
        lambda principal, workspace: invoked.append(workspace),
    )
    status, _, result = _test_call(app)
    assert status.startswith("403")
    assert result["error"] == "workspace_access_denied"
    assert invoked == []


@pytest.mark.parametrize("tenant,workspace", [
    ("tenant-other", "w1"), ("tenant-1", "w2"),
])
def test_tenant_or_workspace_mismatch_never_returns_geometry(tenant, workspace):
    app = make_editor_readonly_wsgi_app(
        lambda env: _principal(),
        lambda principal, requested: _workspace(tenant=tenant, workspace=workspace),
    )
    status, _, result = _test_call(app)
    assert status.startswith("403")
    assert result == {"error": "workspace_scope_mismatch"}
    assert "wall-1" not in str(result)


def test_no_mutation_routes_or_cross_origin_headers():
    invoked = []
    app = make_editor_readonly_wsgi_app(
        lambda env: _principal(),
        lambda principal, requested: invoked.append(requested),
    )
    status, headers, result = _test_call(app, method="POST")
    assert status.startswith("405")
    assert result["error"] == "read_only_editor_api"
    assert "Access-Control-Allow-Origin" not in headers
    assert invoked == []


def test_malformed_workspace_id_and_private_provider_failure_are_masked():
    app = make_editor_readonly_wsgi_app(
        lambda env: _principal(),
        lambda principal, requested: (_ for _ in ()).throw(
            RuntimeError("secret production database path")
        ),
    )
    invalid, _, _ = _test_call(app, path="/api/editor/workspaces/w1%2Fother/manifest")
    assert invalid.startswith("404")
    status, _, result = _test_call(app)
    assert status.startswith("409")
    assert result == {"error": "workspace_scene_unavailable"}
    assert "secret" not in str(result)


def test_provider_hooks_required_by_factory():
    with pytest.raises(ValueError, match="requires auth"):
        make_editor_readonly_wsgi_app(None, lambda p, w: None)


def test_provider_must_supply_matching_native_source_receipt_for_verified_scene():
    base = _workspace()
    wall = replace(
        base.objects[0], source_file_id="original-file-1",
        authority_status="firm",
    )
    receipt = VerifiedSourceWitness(
        document_id="document-1", revision_id="revision-1",
        source_sha256="a" * 64, source_file_id="original-file-1",
        source_page=3, source_sheet="A101",
        original_geometry_ref="native:d2i3",
    )
    verified = replace(base, objects=[wall], source_witnesses={"wall-1": receipt})
    app = make_editor_readonly_wsgi_app(
        lambda env: _principal(),
        lambda principal, workspace: verified,
    )
    status, _, result = _test_call(app)
    assert status.startswith("200")
    assert result["objects"][0]["renderState"] == "verified"

    mismatch = replace(verified, source_witnesses={
        "wall-1": replace(receipt, revision_id="unrelated-revision"),
    })
    app = make_editor_readonly_wsgi_app(
        lambda env: _principal(),
        lambda principal, workspace: mismatch,
    )
    status, _, result = _test_call(app)
    assert status.startswith("200")
    assert result["objects"][0]["renderState"] == "review"
    assert "source_ownership_unverified" in result["objects"][0]["unresolvedIssues"]
