"""Browser commands never become approval or live ledger writes during preview."""
from __future__ import annotations

from dataclasses import replace
import math

import pytest

from pb_editable_3d_correction_model import Editable3DCorrectionLedger, EditableGeometryObject
from pb_vr_editor_scene_manifest import EditorWorkspaceScope, VerifiedSourceWitness
from pb_vr_editor_readonly_wsgi import EditorPrincipal, AuthorizedSceneWorkspace
from pb_vr_editor_command_preview import preview_editor_command


def _wall(**kwargs):
    data = dict(
        object_id="wall-1", object_type="wall",
        source_file_id="pdf-1", source_page=3, source_sheet="A101",
        original_geometry_ref="path-18", geometry_ref="wall-1",
        revision_hash="original-revision",
        coordinates_or_measurements={
            "start_pt": [0.0, 0.0], "end_pt": [4.0, 0.0],
            "length": 4.0, "height": 2.4,
            "height_authority": "figured_dimension", "openings": [],
        },
    )
    data.update(kwargs)
    return EditableGeometryObject(**data)


def _fixture():
    obj = _wall()
    scope = EditorWorkspaceScope(
        "w1", "p1", "d1", "rev1", "snapshot1", "a" * 64, 5,
    )
    workspace = AuthorizedSceneWorkspace(
        tenant_id="tenant1", scope=scope, objects=[obj],
        canonical_object_ids={"wall-1": "canonical-wall-1"},
        source_witnesses={"wall-1": VerifiedSourceWitness(
            document_id="d1", revision_id="rev1", source_sha256="a" * 64,
            source_file_id="pdf-1", source_page=3, source_sheet="A101",
            original_geometry_ref="path-18",
        )},
    )
    user = EditorPrincipal("estimator-1", "tenant1", frozenset({"w1"}))
    ledger = Editable3DCorrectionLedger()
    ledger.register_object(obj)
    request = {
        "commandId": "c1", "idempotencyKey": "k1",
        "workspaceId": "w1", "projectId": "p1", "documentId": "d1",
        "revisionId": "rev1", "snapshotId": "snapshot1",
        "sourceSha256": "a" * 64, "baseModelRevision": 5,
        "targetObjectId": "wall-1", "targetRevisionHash": "original-revision",
        "targetCanonicalId": "canonical-wall-1",
        "commandType": "SET_WALL_HEIGHT",
        "payload": {"newValue": 3.0},
        "reason": "Verified from source section",
    }
    return user, workspace, ledger, request


def test_valid_height_preview_is_derived_but_does_not_mutate_ledger():
    user, ws, ledger, cmd = _fixture()
    before = ledger.get_object("wall-1").to_dict()
    result = preview_editor_command(cmd, principal=user, workspace=ws, ledger=ledger)
    assert result["accepted"] is True
    assert result["validationState"] == "valid_preview_only"
    assert result["requiresApproval"] is True
    assert result["persisted"] is False
    assert result["commercialPublicationAllowed"] is False
    assert result["previewObjectRevision"] != result["previousObjectRevision"]
    assert any(i["target"] == "wall_gross_area" for i in result["quantityImpacts"])
    assert ledger.get_object("wall-1").to_dict() == before
    assert ledger.events == ()


@pytest.mark.parametrize("field,value,reason", [
    ("sourceSha256", "b" * 64, "sourceSha256_scope_mismatch"),
    ("revisionId", "rev-other", "revisionId_scope_mismatch"),
    ("workspaceId", "w-other", "workspaceId_scope_mismatch"),
    ("projectId", "p-other", "projectId_scope_mismatch"),
    ("snapshotId", "old", "snapshotId_scope_mismatch"),
    ("baseModelRevision", 4, "stale_model_revision"),
    ("targetRevisionHash", "old", "stale_object_revision"),
    ("targetCanonicalId", "wrong", "canonical_identity_missing_or_mismatched"),
    ("commandType", "DELETE_WALL", "unsupported_editor_command"),
])
def test_cross_source_and_stale_requests_fail_closed(field, value, reason):
    user, ws, ledger, cmd = _fixture()
    cmd[field] = value
    result = preview_editor_command(cmd, principal=user, workspace=ws, ledger=ledger)
    assert not result["accepted"]
    assert result["blockingReasons"] == [reason]
    assert ledger.events == ()


@pytest.mark.parametrize("value", [math.nan, math.inf, -5.0, 0.0, True, "3.0"])
def test_bad_dimensions_refused_without_geometry_mutation(value):
    user, ws, ledger, cmd = _fixture()
    cmd["payload"] = {"newValue": value}
    result = preview_editor_command(cmd, principal=user, workspace=ws, ledger=ledger)
    assert not result["accepted"]
    assert ledger.get_object("wall-1").revision_hash == "original-revision"
    assert ledger.events == ()


def test_unrecognized_payload_cannot_inject_publishable_or_authority_fields():
    user, ws, ledger, cmd = _fixture()
    cmd["payload"] = {"newValue": 3.0, "is_publishable": True}
    result = preview_editor_command(cmd, principal=user, workspace=ws, ledger=ledger)
    assert result["blockingReasons"] == ["correction_payload_schema_mismatch"]
    cmd["payload"] = {"newValue": 3.0}
    cmd["approvedBy"] = "admin"
    assert preview_editor_command(cmd, principal=user, workspace=ws, ledger=ledger)["accepted"] is False


def test_cross_tenant_or_workspace_grants_block_preview():
    user, ws, ledger, cmd = _fixture()
    user = EditorPrincipal("estimator-1", "different-tenant", frozenset({"w1"}))
    result = preview_editor_command(cmd, principal=user, workspace=ws, ledger=ledger)
    assert result["blockingReasons"] == ["tenant_or_workspace_access_denied"]
    no_grant = EditorPrincipal("estimator-1", "tenant1", frozenset({"w2"}))
    assert not preview_editor_command(cmd, principal=no_grant, workspace=ws, ledger=ledger)["accepted"]


def test_workspace_source_object_must_match_live_ledger_observation():
    user, ws, ledger, cmd = _fixture()
    impostor = replace(ws.objects[0], original_geometry_ref="another-document:line-7")
    ws = replace(ws, objects=[impostor])
    result = preview_editor_command(cmd, principal=user, workspace=ws, ledger=ledger)
    assert result["blockingReasons"] == ["workspace_ledger_source_conflict"]


def test_canonical_identity_required_no_geometry_only_editing():
    user, ws, ledger, cmd = _fixture()
    ws = replace(ws, canonical_object_ids={})
    result = preview_editor_command(cmd, principal=user, workspace=ws, ledger=ledger)
    assert result["blockingReasons"] == ["canonical_identity_missing_or_mismatched"]


def test_invalid_command_does_not_emit_correction_event():
    user, ws, ledger, cmd = _fixture()
    cmd["commandType"] = "ASSIGN_SURFACE_FINISH"
    result = preview_editor_command(cmd, principal=user, workspace=ws, ledger=ledger)
    assert result["blockingReasons"] == ["correction_object_type_conflict"]
    assert ledger.events == ()


def test_preview_rejects_missing_or_wrong_original_source_receipt():
    user, ws, ledger, cmd = _fixture()
    missing = replace(ws, source_witnesses={})
    result = preview_editor_command(cmd, principal=user, workspace=missing, ledger=ledger)
    assert result["blockingReasons"] == ["original_source_ownership_unverified"]
    assert ledger.events == ()
    receipt = ws.source_witnesses["wall-1"]
    for changed in (
        replace(receipt, source_sha256="b" * 64),
        replace(receipt, revision_id="stale-drawing"),
        replace(receipt, original_geometry_ref="other-native-path"),
    ):
        mismatched = replace(ws, source_witnesses={"wall-1": changed})
        result = preview_editor_command(cmd, principal=user, workspace=mismatched, ledger=ledger)
        assert result["blockingReasons"] == ["original_source_ownership_unverified"]
        assert ledger.events == ()
