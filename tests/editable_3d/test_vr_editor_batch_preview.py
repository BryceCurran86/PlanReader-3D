"""Five integrations: batch core, no partial outputs, source security, HTTP and replay."""
from __future__ import annotations

from dataclasses import replace
from io import BytesIO
import json

from pb_vr_editor_batch_preview import preview_editor_batch
from pb_vr_editor_batch_wsgi import make_editor_batch_wsgi_app
from tests.editable_3d.test_vr_editor_command_preview import _fixture
from tests.editable_3d.test_vr_editor_command_wsgi import _setup


def test_valid_two_wall_source_bound_simulation_never_writes_original_ledger():
    user, ws, ledger, cmd = _fixture()
    original = ledger.get_object("wall-1").to_dict()
    from pb_editable_3d_correction_model import EditableGeometryObject
    from pb_vr_editor_scene_manifest import VerifiedSourceWitness
    second = replace(ws.objects[0], object_id="wall-2", geometry_ref="wall-2",
                     revision_hash="wall2-r0", original_geometry_ref="path-19")
    ledger.register_object(second)
    second_witness = replace(ws.source_witnesses["wall-1"], original_geometry_ref="path-19")
    ws = replace(
        ws, objects=[ws.objects[0], second],
        canonical_object_ids={"wall-1": "canonical-wall-1", "wall-2": "canonical-wall-2"},
        source_witnesses={"wall-1": ws.source_witnesses["wall-1"], "wall-2": second_witness},
    )
    other = {
        **cmd, "commandId": "c2", "idempotencyKey": "k2",
        "targetObjectId": "wall-2", "targetRevisionHash": "wall2-r0",
        "targetCanonicalId": "canonical-wall-2", "payload": {"newValue": 3.2},
    }
    request = {"commands": [cmd, other]}
    result = preview_editor_batch(request, principal=user, workspace=ws, ledger=ledger)
    assert result["accepted"] is True
    assert result["persisted"] is False
    assert result["requiresApproval"] is True
    assert result["commercialPublicationAllowed"] is False
    assert result["rateEstimateAvailable"] is False
    assert result["simulationMode"] == "independent_same_base_not_cumulative"
    assert len(result["commandPreviews"]) == 2
    assert len(result["batchReceiptSha256"]) == 64
    assert result == preview_editor_batch(request, principal=user, workspace=ws, ledger=ledger)
    assert ledger.get_object("wall-1").to_dict() == original
    assert ledger.get_object("wall-2").revision_hash == "wall2-r0"
    assert ledger.events == ()


def test_one_invalid_source_blocks_entire_batch_without_leaking_other_impacts():
    user, ws, ledger, cmd = _fixture()
    valid = dict(cmd)
    invalid = {**cmd, "commandId": "c2", "idempotencyKey": "k2",
               "targetObjectId": "nonexistent", "targetRevisionHash": "different"}
    result = preview_editor_batch({"commands": [valid, invalid]}, principal=user,
                                  workspace=ws, ledger=ledger)
    assert result["accepted"] is False
    assert result["commandPreviews"] == []
    assert not result["commercialPublicationAllowed"]
    assert ledger.events == ()


def test_batch_duplicate_and_oversize_rejected_before_source_preview():
    user, ws, ledger, cmd = _fixture()
    for commands in ([], [cmd] * 2, [cmd] * 21, ["bad"]):
        result = preview_editor_batch({"commands": commands}, principal=user,
                                      workspace=ws, ledger=ledger)
        assert not result["accepted"]
        assert result["commandPreviews"] == []
    assert ledger.events == ()


def test_batch_cross_tenant_readonly_and_missing_source_receipts_deny():
    user, ws, ledger, cmd = _fixture()
    readonly = replace(user, allowed_preview_workspace_ids=frozenset())
    assert not preview_editor_batch({"commands": [cmd]}, principal=readonly,
                                    workspace=ws, ledger=ledger)["accepted"]
    no_source = replace(ws, source_witnesses={})
    result = preview_editor_batch({"commands": [cmd]}, principal=user,
                                  workspace=no_source, ledger=ledger)
    assert result["blockingReasons"] == [
        "command_rejected:original_source_ownership_unverified"
    ]
    assert ledger.events == ()


def _http(app, command, method="POST", path="/api/editor/workspaces/w1/commands/batch-preview",
          raw=None):
    data = json.dumps(command).encode("utf-8") if raw is None else raw
    meta = []
    def start(status, headers):
        meta.append((status, dict(headers)))
    environ = {
        "REQUEST_METHOD": method, "PATH_INFO": path, "CONTENT_TYPE": "application/json",
        "CONTENT_LENGTH": str(len(data)), "wsgi.input": BytesIO(data),
    }
    result = json.loads(b"".join(app(environ, start)))
    return meta[0][0], meta[0][1], result


def test_wsgi_batch_requires_auth_csrf_and_does_not_write_ledger():
    factory, cmd, ledger = _setup()
    user, ws, _, _ = _fixture()
    # The setup's ledger is bound to r0; construct the matching batch payload.
    request = {"commands": [cmd]}
    app = make_editor_batch_wsgi_app(
        lambda env: user,
        lambda p, wid: ws,
        lambda p, workspace: (ledger, ()),
        lambda env, p: True,
    )
    # Source identities mismatch between independent fixtures: reject fail closed.
    status, headers, result = _http(app, request)
    assert status.startswith(("409", "422"))
    assert result.get("accepted") is False or result.get("error")
    assert headers["Cache-Control"] == "no-store, private"
    assert "Access-Control-Allow-Origin" not in headers
    assert ledger.events == ()

    missing_auth = make_editor_batch_wsgi_app(
        lambda env: None, lambda p, wid: ws,
        lambda p, w: (ledger, ()), lambda env, p: True,
    )
    assert _http(missing_auth, request)[0].startswith("401")
    bad_csrf = make_editor_batch_wsgi_app(
        lambda env: user, lambda p, wid: ws,
        lambda p, w: (ledger, ()), lambda env, p: False,
    )
    assert _http(bad_csrf, request)[0].startswith("403")
    assert _http(app, request, method="DELETE")[0].startswith("405")
    assert _http(app, request, raw=b'{"a":1,"a":2}')[0].startswith("400")
    assert ledger.events == ()


def test_wsgi_positive_batch_with_exact_ledger_fixture():
    user, ws, ledger, cmd = _fixture()
    app = make_editor_batch_wsgi_app(
        lambda env: user, lambda p, wid: ws,
        lambda p, w: (ledger, ()), lambda env, p: True,
    )
    status, headers, result = _http(app, {"commands": [cmd]})
    assert status.startswith("200")
    assert result["accepted"]
    assert result["commandPreviews"][0]["targetObjectId"] == "wall-1"
    assert not result["persisted"]
    assert not result["commercialPublicationAllowed"]
    assert ledger.events == ()
