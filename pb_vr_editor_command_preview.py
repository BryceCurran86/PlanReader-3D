"""Server-side typed command preflight for the PlanReader desktop/WebXR editor.

NO writes. Browser requests are untrusted and are checked against a server
principal, source-bound workspace and current registered object before an edit
is replayed on a DEEP COPY of the existing correction ledger. Only existing
PlanReader correction and recalculation formulas are called. Live ledger,
persisted history, approvals and commercial rows are never changed.
"""
from __future__ import annotations

from copy import deepcopy
import math
import re
from typing import Any, Mapping, Sequence

from pb_editable_3d_correction_model import (
    CorrectionField, CorrectionSource, Editable3DCorrectionLedger,
)
from pb_editable_3d_quantity_recalculation import recalculate_quantities_for_correction
from pb_takeoff_output_authority import TakeoffOutputRow
from pb_vr_editor_readonly_wsgi import AuthorizedSceneWorkspace, EditorPrincipal
from pb_vr_editor_scene_manifest import VerifiedSourceWitness

_SUPPORTED = {
    "SET_WALL_HEIGHT": ("wall", CorrectionField.HEIGHT.value),
    "SET_WALL_LENGTH": ("wall", CorrectionField.LENGTH.value),
    "ASSIGN_WALL_FINISH": ("wall", CorrectionField.FINISH_TAG.value),
    "ASSIGN_SURFACE_FINISH": ("surface", CorrectionField.FINISH_TAG.value),
}
_REQUIRED = frozenset({
    "commandId", "idempotencyKey", "workspaceId", "projectId",
    "documentId", "revisionId", "snapshotId", "sourceSha256",
    "baseModelRevision", "targetObjectId", "targetRevisionHash",
    "targetCanonicalId", "commandType", "payload", "reason",
})
_TOKEN = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")


def _reject(reason: str) -> dict[str, Any]:
    return {
        "accepted": False,
        "validationState": "invalid",
        "blockingReasons": [reason],
        "commercialPublicationAllowed": False,
    }


def preview_editor_command(
    raw: Mapping[str, Any],
    *,
    principal: EditorPrincipal,
    workspace: AuthorizedSceneWorkspace,
    ledger: Editable3DCorrectionLedger,
    existing_rows: Sequence[TakeoffOutputRow] = (),
) -> dict[str, Any]:
    """Validate one command and preview using existing trusted formulas only.

    A separate persistent command service must provide atomic idempotency,
    CSRF, permission and approval transitions before any live mutation. No
    caller may interpret this preview as an approved correction.
    """
    if not isinstance(raw, Mapping) or set(raw) != _REQUIRED:
        return _reject("typed_command_schema_mismatch")
    if not isinstance(principal, EditorPrincipal):
        return _reject("authentication_required")
    if not isinstance(workspace, AuthorizedSceneWorkspace):
        return _reject("workspace_not_authorized")
    scope = workspace.scope
    if (workspace.tenant_id != principal.tenant_id
        or scope.workspace_id not in principal.allowed_workspace_ids):
        return _reject("tenant_or_workspace_access_denied")
    identities = (
        ("workspaceId", scope.workspace_id),
        ("projectId", scope.project_id),
        ("documentId", scope.document_id),
        ("revisionId", scope.revision_id),
        ("snapshotId", scope.snapshot_id),
        ("sourceSha256", scope.source_sha256.lower()),
    )
    for field, trusted in identities:
        value = raw.get(field)
        if not isinstance(value, str) or value != trusted:
            return _reject(f"{field}_scope_mismatch")
    if type(raw["baseModelRevision"]) is not int or raw["baseModelRevision"] != scope.model_revision:
        return _reject("stale_model_revision")
    for key in ("commandId", "idempotencyKey"):
        if not isinstance(raw[key], str) or not _TOKEN.fullmatch(raw[key]):
            return _reject(f"{key}_invalid")
    if not isinstance(raw["reason"], str) or not 8 <= len(raw["reason"].strip()) <= 1024:
        return _reject("correction_reason_invalid")
    if not isinstance(raw["targetObjectId"], str) or not raw["targetObjectId"]:
        return _reject("target_object_id_missing")
    object_id = raw["targetObjectId"]
    registered = ledger.get_object(object_id)
    owner = next((o for o in workspace.objects if o.object_id == object_id), None)
    if registered is None or owner is None:
        return _reject("target_object_not_in_workspace")
    if (owner.revision_hash != registered.revision_hash
        or owner.source_file_id != registered.source_file_id
        or owner.source_page != registered.source_page
        or owner.source_sheet != registered.source_sheet
        or owner.original_geometry_ref != registered.original_geometry_ref):
        # The workspace provider and the mutable ledger must refer to the
        # SAME source observation. Same object ID alone is not sufficient.
        return _reject("workspace_ledger_source_conflict")
    if (not isinstance(raw["targetRevisionHash"], str)
            or raw["targetRevisionHash"] != registered.revision_hash):
        return _reject("stale_object_revision")
    # An authenticated workspace or editable model mass is not, by itself,
    # evidence that this object comes from the pinned original PDF revision.
    # The trusted server-side source resolver must supply a matching receipt.
    witness = workspace.source_witnesses.get(object_id)
    if (not isinstance(witness, VerifiedSourceWitness)
            or not witness.matches(scope, registered)):
        return _reject("original_source_ownership_unverified")
    server_canonical = workspace.canonical_object_ids.get(object_id)
    if (not server_canonical or not isinstance(raw["targetCanonicalId"], str)
            or raw["targetCanonicalId"] != server_canonical):
        return _reject("canonical_identity_missing_or_mismatched")
    command = raw.get("commandType")
    mapping = _SUPPORTED.get(command) if isinstance(command, str) else None
    if mapping is None:
        return _reject("unsupported_editor_command")
    expected_type, correction_field = mapping
    if registered.object_type != expected_type:
        return _reject("correction_object_type_conflict")
    payload = raw.get("payload")
    if not isinstance(payload, Mapping) or set(payload) != {"newValue"}:
        return _reject("correction_payload_schema_mismatch")
    new_value = payload["newValue"]
    if correction_field in (CorrectionField.LENGTH.value, CorrectionField.HEIGHT.value):
        if type(new_value) not in (int, float):
            return _reject("dimension_requires_numeric_value")
        if not math.isfinite(float(new_value)) or float(new_value) <= 0:
            return _reject("dimension_must_be_finite_positive")
    else:
        if not isinstance(new_value, str) or not 1 <= len(new_value.strip()) <= 64:
            return _reject("finish_assignment_invalid")

    if len(existing_rows) > 2000:
        return _reject("quantity_preview_safety_cap_exceeded")
    for row in existing_rows:
        if not isinstance(row, TakeoffOutputRow) or row.geometry_ref != object_id:
            return _reject("quantity_preview_cross_object_scope")

    # Reuse the real correction engine on an isolated copy. The returned
    # candidate rows are intentionally never persisted, approved or published.
    shadow = deepcopy(ledger)
    outcome = shadow.apply_correction(
        correction_id=raw["commandId"],
        object_id=object_id,
        field=correction_field,
        new_value=new_value,
        reason=raw["reason"].strip(),
        actor=principal.subject_id,
        source=CorrectionSource.EDITOR_3D.value,
        expected_revision_hash=raw["targetRevisionHash"],
    )
    if not outcome.ok or outcome.event is None:
        return _reject("correction_invalid:" + ";".join(outcome.blocking_reasons))
    after = shadow.get_object(object_id)
    if after is None:
        return _reject("correction_target_lost")
    try:
        changes = recalculate_quantities_for_correction(
            outcome.event, after, existing_rows=existing_rows,
        )
    except Exception:
        # A malformed or oversized preview is never allowed to reach a
        # commercial writer; do not expose internal source/database errors.
        return _reject("quantity_preview_calculation_unavailable")
    return {
        "accepted": True,
        "validationState": "valid_preview_only",
        "commandId": raw["commandId"],
        "idempotencyKey": raw["idempotencyKey"],
        "targetObjectId": object_id,
        "previousObjectRevision": registered.revision_hash,
        "previewObjectRevision": after.revision_hash,
        "requiresApproval": True,
        "persisted": False,
        "commercialPublicationAllowed": False,
        "quantityImpacts": [
            {
                "target": item.target,
                "status": item.status,
                "oldValue": item.old_value,
                "proposedValue": item.new_value,
                "unit": item.unit,
                "reason": getattr(item, "reason", None),
            }
            for item in changes
        ],
        "blockingReasons": [],
    }
