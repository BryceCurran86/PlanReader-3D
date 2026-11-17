"""Authenticated, source-scoped metadata packet for a saved PlanReader revision.

A packet records stored lineage; it is not a digital signature, source-page
reauthentication, architectural drawing approval, or customer quantity issuer.
No private PDFs, raw commands, correction reasons or actor IDs are exported.
"""
from __future__ import annotations

from hashlib import sha256
import json
import sqlite3
from typing import Any

from pb_plan_edit_revision_store import get_plan_edit_pdf, get_plan_edit_revision
from pb_vr_editor_readonly_wsgi import AuthorizedSceneWorkspace, EditorPrincipal


class PlanRevisionProvenanceError(ValueError):
    pass


def export_plan_edit_revision_provenance(
    connection: sqlite3.Connection,
    *,
    principal: EditorPrincipal,
    workspace: AuthorizedSceneWorkspace,
    revision_id: str,
) -> dict[str, Any]:
    """Emit a deterministic digest-addressable, review-only metadata packet.

    The private PDF accessor enforces tenant/workspace authorization and checks
    the persisted PDF SHA before any source/actor metadata is returned.
    """
    if not isinstance(connection, sqlite3.Connection):
        raise TypeError("sqlite_connection_required")
    _, verified_pdf_sha = get_plan_edit_pdf(
        connection, principal, workspace, revision_id)
    key = (
        principal.tenant_id,
        workspace.scope.workspace_id,
        workspace.scope.document_id,
        workspace.scope.source_sha256.lower(),
        workspace.scope.snapshot_id,
    )
    saved = get_plan_edit_revision(connection, key, revision_id)
    row = connection.execute(
        """SELECT source_revision_id, parent_pdf_sha256, command_sha256,
                  command_json, actor_id, created_at
           FROM plan_edit_revisions
           WHERE revision_id=? AND tenant_id=? AND workspace_id=?
             AND document_id=? AND source_pdf_sha256=?
             AND source_snapshot_id=?""",
        (revision_id, *key),
    ).fetchone()
    if row is None:
        raise PlanRevisionProvenanceError("revision_record_missing")
    source_revision, parent_pdf_sha, command_sha, command_json, actor, created_at = tuple(row)
    try:
        command = json.loads(command_json)
    except (TypeError, ValueError) as exc:
        raise PlanRevisionProvenanceError("stored_revision_command_invalid") from exc
    if not isinstance(command, dict):
        raise PlanRevisionProvenanceError("stored_revision_command_invalid")
    encoded_command = json.dumps(
        command, allow_nan=False, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    event = saved["event"]
    if (
        source_revision != workspace.scope.revision_id
        or not isinstance(command_sha, str)
        or sha256(encoded_command).hexdigest() != command_sha
        or not isinstance(event, dict)
        or event.get("correction_id") != command.get("commandId")
        or event.get("object_id") != command.get("targetObjectId")
        or not isinstance(actor, str) or not actor
        or event.get("actor") != actor
        or type(saved["revisionNumber"]) is not int
        or saved["revisionNumber"] < 1
        or not isinstance(parent_pdf_sha, str)
        or len(parent_pdf_sha) != 64
        or any(c not in "0123456789abcdef" for c in parent_pdf_sha)
    ):
        raise PlanRevisionProvenanceError("stored_revision_provenance_mismatch")
    pages = saved["pagesRevised"]
    if not isinstance(pages, list) or not pages:
        raise PlanRevisionProvenanceError("revision_page_coverage_missing")
    indices: list[int] = []
    for page in pages:
        if (
            not isinstance(page, dict)
            or type(page.get("pageIndex")) is not int
            or page["pageIndex"] < 0
        ):
            raise PlanRevisionProvenanceError("revision_page_evidence_invalid")
        indices.append(page["pageIndex"])
    if len(indices) != len(set(indices)):
        raise PlanRevisionProvenanceError("revision_page_evidence_duplicated")

    packet: dict[str, Any] = {
        "schema": "planreader.working_revision_provenance.v1",
        "workspaceId": key[1],
        "documentId": key[2],
        "originalSourceRevisionId": source_revision,
        "originalSourcePdfSha256": key[3],
        "originalSourceSnapshotId": key[4],
        "workingRevisionId": revision_id,
        "workingRevisionNumber": saved["revisionNumber"],
        "parentWorkingRevisionId": saved["parentRevisionId"],
        "parentPdfSha256": parent_pdf_sha,
        "workingPdfSha256": verified_pdf_sha,
        "commandSha256": command_sha,
        "modelRevisionBefore": saved["previousModelRevision"],
        "modelRevisionAfter": saved["updatedModelRevision"],
        "reviewPageIndices": sorted(indices),
        "recordedAt": created_at,
        "reviewRevisionOnly": True,
        "requiresApproval": True,
        "commercialPublicationAllowed": False,
        "geometryRedrawn": False,
        "cryptographicallySigned": False,
        "sourceGeometryRevalidated": False,
    }
    # A digest detects later packet changes but cannot authenticate the author.
    packet_bytes = json.dumps(
        packet, allow_nan=False, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    packet["packetSha256"] = sha256(packet_bytes).hexdigest()
    return packet
