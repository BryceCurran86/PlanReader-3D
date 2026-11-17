"""Fail-closed, server-authorized MULTI-wall VR impact simulation.

Each command is checked independently by the existing exact-source correction
preview against the same immutable initial ledger. No cumulative corrections,
pricing, approval, persistence or customer quantity publication occur.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from pb_editable_3d_correction_model import Editable3DCorrectionLedger
from pb_takeoff_output_authority import TakeoffOutputRow
from pb_vr_editor_command_preview import preview_editor_command
from pb_vr_editor_readonly_wsgi import AuthorizedSceneWorkspace, EditorPrincipal

_MAX_COMMANDS = 20
_MAX_TOTAL_IMPACTS = 200


def _refuse(reason: str) -> dict[str, Any]:
    return {
        "accepted": False, "validationState": "invalid_batch",
        "blockingReasons": [reason], "persisted": False,
        "requiresApproval": True, "commercialPublicationAllowed": False,
        "commandPreviews": [],
    }


def preview_editor_batch(
    request: Mapping[str, Any], *, principal: EditorPrincipal,
    workspace: AuthorizedSceneWorkspace, ledger: Editable3DCorrectionLedger,
    existing_rows: Sequence[TakeoffOutputRow] = (),
) -> dict[str, Any]:
    """All-or-nothing preview, with one trusted source witness per target.

    No data or individual quantity results are returned if any command fails.
    This is NOT a cumulative transaction or a promise that edits may be saved.
    """
    if not isinstance(request, Mapping) or set(request) != {"commands"}:
        return _refuse("batch_schema_mismatch")
    commands = request.get("commands")
    if not isinstance(commands, list) or not 1 <= len(commands) <= _MAX_COMMANDS:
        return _refuse("batch_size_invalid")
    if not isinstance(principal, EditorPrincipal) or not isinstance(workspace, AuthorizedSceneWorkspace):
        return _refuse("batch_authorization_required")
    if (workspace.tenant_id != principal.tenant_id
            or workspace.scope.workspace_id not in principal.allowed_preview_workspace_ids):
        return _refuse("batch_workspace_permission_denied")
    if len(existing_rows) > 2000:
        return _refuse("batch_quantity_safety_cap_exceeded")
    targets, command_ids, idempotency_keys = set(), set(), set()
    for command in commands:
        if not isinstance(command, Mapping):
            return _refuse("batch_command_not_object")
        target = command.get("targetObjectId")
        cid = command.get("commandId")
        key = command.get("idempotencyKey")
        if not all(isinstance(x, str) and x for x in (target, cid, key)):
            return _refuse("batch_identity_invalid")
        if target in targets or cid in command_ids or key in idempotency_keys:
            return _refuse("batch_duplicate_target_or_command")
        targets.add(target)
        command_ids.add(cid)
        idempotency_keys.add(key)
    previews = []
    total = 0
    for command in commands:
        target = command["targetObjectId"]
        scoped_rows = tuple(row for row in existing_rows if row.geometry_ref == target)
        result = preview_editor_command(
            command, principal=principal, workspace=workspace,
            ledger=ledger, existing_rows=scoped_rows,
        )
        if result.get("accepted") is not True:
            # Strip all successful previews rather than allowing misleading
            # partial price/quantity readiness from a multi-wall proposal.
            reasons = result.get("blockingReasons") or ["batch_source_preview_rejected"]
            return _refuse("command_rejected:" + str(reasons[0])[:160])
        total += len(result["quantityImpacts"])
        if total > _MAX_TOTAL_IMPACTS:
            return _refuse("batch_impact_safety_cap_exceeded")
        previews.append(result)

    receipt_source = {
        "sourceSha256": workspace.scope.source_sha256.lower(),
        "documentId": workspace.scope.document_id,
        "revisionId": workspace.scope.revision_id,
        "snapshotId": workspace.scope.snapshot_id,
        "modelRevision": workspace.scope.model_revision,
        "actor": principal.subject_id,
        "commands": [
            [p["commandId"], p["targetObjectId"],
             p["previousObjectRevision"], p["previewObjectRevision"]]
            for p in previews
        ],
    }
    digest = sha256(json.dumps(receipt_source, sort_keys=True,
                               separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "accepted": True, "validationState": "valid_batch_preview_only",
        "persisted": False, "requiresApproval": True,
        "commercialPublicationAllowed": False,
        "batchReceiptSha256": digest,
        "simulationMode": "independent_same_base_not_cumulative",
        "commandPreviews": previews,
        "blockingReasons": [],
        "rateEstimateAvailable": False,
    }
