"""Fail-closed, read-only workspace export for the separate PlanReader VR viewer.

Existing model_masses and model_openings have no original PDF path ownership
foreign key or verified canonical wall ID. This adapter deliberately exports
ONLY a review scene, never treats a document in the same workspace as a
physical-wall source witness, and never creates a billable quantity.

The original document SHA is a *document identity only* in this export.
It must not be interpreted as a native wall or opening lineage receipt.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from pb_editable_3d_correction_model import EditableGeometryObject
from pb_vr_editor_scene_manifest import EditorWorkspaceScope, compile_editor_scene


_SHA256 = re.compile(r"[0-9a-fA-F]{64}\Z")


def export_workspace_review_scene(
    *,
    workspace: Mapping[str, Any],
    document: Mapping[str, Any],
    objects: Sequence[EditableGeometryObject],
    correction_count: int,
) -> dict[str, Any]:
    """Make a deterministic *untrusted* browser-review scene for one PDF.

    The caller must already have loaded the current workspace through the
    authenticated PlanReader session. This pure function is not an auth API.
    A selected document identifies the drawing to review, but does not assign
    that drawing as the source of every mass in the workspace.
    """
    try:
        workspace_id = int(workspace["id"])
        document_id = int(document["id"])
        document_workspace_id = int(document["workspace_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("review_scene_missing_workspace_or_document_identity") from exc
    if (workspace_id <= 0 or document_id <= 0
            or document_workspace_id != workspace_id):
        raise ValueError("review_scene_document_outside_workspace")
    if type(correction_count) is not int or correction_count < 0:
        raise ValueError("review_scene_invalid_correction_count")
    sha = document.get("sha256")
    if not isinstance(sha, str) or not _SHA256.fullmatch(sha):
        raise ValueError("review_scene_original_document_sha256_missing")
    sha = sha.lower()
    mime = str(document.get("mime_type") or "").lower().strip()
    name = str(document.get("file_name") or "")
    if mime != "application/pdf" and not name.lower().endswith(".pdf"):
        raise ValueError("review_scene_requires_pdf_document")
    if len(objects) > 20_000:
        raise ValueError("review_scene_safety_cap_exceeded")
    if any(not isinstance(obj, EditableGeometryObject) for obj in objects):
        raise ValueError("review_scene_invalid_geometry_object")

    # Captures changed geometry even if a mass was edited independently of
    # the append-only correction log. Never substitutes for a sealed model
    # snapshot, and does not authorize a billable measurement.
    snapshot_bytes = json.dumps(
        {
            "workspaceId": workspace_id,
            "documentId": document_id,
            "documentSha256": sha,
            "correctionCount": correction_count,
            "objects": [obj.to_dict() for obj in sorted(objects, key=lambda x: x.object_id)],
        },
        sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    snapshot = hashlib.sha256(snapshot_bytes).hexdigest()
    job_no = workspace.get("job_no")
    project_id = str(job_no).strip() if job_no else f"workspace:{workspace_id}"

    scope = EditorWorkspaceScope(
        workspace_id=str(workspace_id),
        project_id=project_id,
        document_id=str(document_id),
        revision_id=f"document-sha256:{sha}",
        snapshot_id=f"unverified-workspace-review:{snapshot}",
        source_sha256=sha,
        model_revision=correction_count,
    )
    # No canonical IDs and no source-native witnesses: an editable mass may
    # happen to share its workspace with this PDF but is NOT proven to derive
    # from that PDF. All rows must stay REVIEW even after user approval.
    manifest = compile_editor_scene(
        scope, objects, canonical_object_ids={},
    )
    if (manifest["commercialQuantityPublicationAllowed"] is not False
            or manifest["readOnly"] is not True
            or any(row["renderState"] != "review" or row["canEdit"]
                   for row in manifest["objects"])):
        raise ValueError("review_scene_commercial_authority_leak")
    return manifest
