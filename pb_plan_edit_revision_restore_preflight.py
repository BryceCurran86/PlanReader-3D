"""Read-only, fail-closed restore *preview* for saved PlanReader working revisions.

A past PDF is immutable. Restoring it must create a NEW authorized revision;
this module cannot modify, delete or roll back any document or model state.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from pb_plan_edit_revision_chain_audit import audit_plan_edit_revision_chain
from pb_plan_edit_revision_store import get_plan_edit_pdf, get_plan_edit_revision
from pb_vr_editor_readonly_wsgi import AuthorizedSceneWorkspace, EditorPrincipal


class PlanRevisionRestoreBlocked(ValueError):
    pass


def preview_plan_edit_restore(
    connection: sqlite3.Connection,
    *,
    principal: EditorPrincipal,
    workspace: AuthorizedSceneWorkspace,
    target_revision_id: str,
) -> dict[str, Any]:
    """Describe changes since an older version, without producing a save.

    The caller must load the current source-scoped workspace from the trusted
    host, not from a browser-supplied modelRevision. No write grant is given
    even when this source-consistency preview succeeds.
    """
    if not isinstance(connection, sqlite3.Connection):
        raise TypeError("sqlite_connection_required")
    # Authenticated read + stored target PDF byte hash gate.
    _, target_pdf_sha = get_plan_edit_pdf(
        connection, principal, workspace, target_revision_id)
    key = (
        principal.tenant_id, workspace.scope.workspace_id,
        workspace.scope.document_id, workspace.scope.source_sha256.lower(),
        workspace.scope.snapshot_id,
    )
    count = connection.execute(
        """SELECT COUNT(*) FROM plan_edit_revisions
           WHERE tenant_id=? AND workspace_id=? AND document_id=?
             AND source_pdf_sha256=? AND source_snapshot_id=?""",
        key,
    ).fetchone()[0]
    if type(count) is not int or count < 1 or count > 200:
        raise PlanRevisionRestoreBlocked("restore_revision_count_unsupported")
    audit = audit_plan_edit_revision_chain(connection, key)
    if not audit.intact:
        raise PlanRevisionRestoreBlocked(
            "restore_blocked_by_corrupt_revision_chain:" + ",".join(audit.errors))
    current = connection.execute(
        """SELECT revision_id, revision_number, updated_pdf_sha256,
                  model_revision
           FROM plan_edit_revision_heads
           WHERE tenant_id=? AND workspace_id=? AND document_id=?
             AND source_pdf_sha256=? AND source_snapshot_id=?""",
        key,
    ).fetchone()
    if current is None:
        raise PlanRevisionRestoreBlocked("restore_head_missing")
    head_id, head_number, head_sha, head_model_revision = tuple(current)
    if (type(workspace.scope.model_revision) is not int
        or workspace.scope.model_revision != head_model_revision):
        raise PlanRevisionRestoreBlocked("restore_current_head_not_loaded")
    _, verified_head_sha = get_plan_edit_pdf(
        connection, principal, workspace, head_id)
    if verified_head_sha != head_sha:
        raise PlanRevisionRestoreBlocked("restore_current_pdf_head_mismatch")
    target = get_plan_edit_revision(connection, key, target_revision_id)
    number = target["revisionNumber"]
    if type(number) is not int or number < 1 or number >= head_number:
        raise PlanRevisionRestoreBlocked("restore_target_must_be_older_than_current")
    rows = connection.execute(
        """SELECT related_pages_json FROM plan_edit_revisions
           WHERE tenant_id=? AND workspace_id=? AND document_id=?
             AND source_pdf_sha256=? AND source_snapshot_id=?
             AND revision_number>? AND revision_number<=?
           ORDER BY revision_number""",
        (*key, number, head_number),
    ).fetchall()
    if len(rows) != head_number - number:
        raise PlanRevisionRestoreBlocked("restore_incomplete_intervening_history")
    pages: set[int] = set()
    for (serialized,) in rows:
        try:
            records = json.loads(serialized)
        except (TypeError, ValueError) as exc:
            raise PlanRevisionRestoreBlocked("restore_invalid_page_evidence") from exc
        if not isinstance(records, list) or not records:
            raise PlanRevisionRestoreBlocked("restore_invalid_page_evidence")
        for record in records:
            if (
                not isinstance(record, dict)
                or type(record.get("pageIndex")) is not int
                or record["pageIndex"] < 0
            ):
                raise PlanRevisionRestoreBlocked("restore_invalid_page_evidence")
            pages.add(record["pageIndex"])
    return {
        "documentId": key[2],
        "sourcePdfSha256": key[3],
        "sourceSnapshotId": key[4],
        "currentRevisionId": head_id,
        "currentPdfSha256": verified_head_sha,
        "currentModelRevision": head_model_revision,
        "targetRevisionId": target_revision_id,
        "targetPdfSha256": target_pdf_sha,
        "targetModelRevision": target["updatedModelRevision"],
        "interveningRevisionCount": len(rows),
        "potentiallyAffectedPageIndices": sorted(pages),
        "restorePerformed": False,
        "restoreWriteAuthorized": False,
        "newAtomicRevisionRequired": True,
        "sourceRevalidationRequired": True,
        "commercialPublicationAllowed": False,
    }
