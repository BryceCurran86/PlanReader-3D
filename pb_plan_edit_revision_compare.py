"""Authenticated, read-only comparison of saved PlanReader working revisions.

Compares stored revision events and corroborated page manifests, not inferred
PDF vectors or commercial quantities. No source drawings are rewritten.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from pb_plan_edit_revision_store import get_plan_edit_pdf, get_plan_edit_revision
from pb_vr_editor_readonly_wsgi import AuthorizedSceneWorkspace, EditorPrincipal


class PlanRevisionComparisonError(ValueError):
    """The requested comparison has no complete verified revision chain."""


def compare_plan_edit_revisions(
    connection: sqlite3.Connection,
    *,
    principal: EditorPrincipal,
    workspace: AuthorizedSceneWorkspace,
    older_revision_id: str,
    newer_revision_id: str,
) -> dict[str, Any]:
    """Compare two revisions in the caller's already authorized document scope.

    Every intervening PDF is read and checked against its recorded SHA-256.
    Discontinuous ancestry or model revisions fail closed. A result is review
    evidence only; it never approves model geometry or recalculates quantities.
    """
    if not isinstance(connection, sqlite3.Connection):
        raise TypeError("sqlite_connection_required")
    # The existing private-PDF accessor enforces tenant and workspace grants
    # before any history rows or private events are returned.
    _, older_sha = get_plan_edit_pdf(
        connection, principal, workspace, older_revision_id)
    _, newer_sha = get_plan_edit_pdf(
        connection, principal, workspace, newer_revision_id)
    key = (
        principal.tenant_id, workspace.scope.workspace_id,
        workspace.scope.document_id, workspace.scope.source_sha256.lower(),
        workspace.scope.snapshot_id,
    )
    old = get_plan_edit_revision(connection, key, older_revision_id)
    new = get_plan_edit_revision(connection, key, newer_revision_id)
    start, stop = old["revisionNumber"], new["revisionNumber"]
    if (type(start) is not int or type(stop) is not int or start < 1
        or stop <= start or stop - start > 200):
        raise PlanRevisionComparisonError("invalid_or_oversized_revision_range")
    rows = connection.execute(
        """SELECT revision_id, revision_number, parent_revision_id,
                  parent_pdf_sha256, previous_model_revision,
                  updated_model_revision
           FROM plan_edit_revisions
           WHERE tenant_id=? AND workspace_id=? AND document_id=?
             AND source_pdf_sha256=? AND source_snapshot_id=?
             AND revision_number>? AND revision_number<=?
           ORDER BY revision_number ASC""",
        (*key, start, stop),
    ).fetchall()
    if len(rows) != stop - start:
        raise PlanRevisionComparisonError("revision_range_has_missing_records")
    parent_id, parent_sha = older_revision_id, older_sha
    model_revision = old["updatedModelRevision"]
    events: list[dict[str, Any]] = []
    affected_pages: set[int] = set()
    for expected_number, row in enumerate(rows, start + 1):
        rid, number, linked_parent, linked_pdf, before, after = tuple(row)
        if (
            type(number) is not int or number != expected_number
            or linked_parent != parent_id or linked_pdf != parent_sha
            or type(before) is not int or before != model_revision
            or type(after) is not int or after != before + 1
        ):
            raise PlanRevisionComparisonError("revision_parent_or_model_gap")
        _, digest = get_plan_edit_pdf(connection, principal, workspace, rid)
        saved = get_plan_edit_revision(connection, key, rid)
        if (digest != saved["updatedPdfSha256"]
            or saved["revisionNumber"] != number
            or not isinstance(saved["event"], dict)
            or not isinstance(saved["pagesRevised"], list)):
            raise PlanRevisionComparisonError("revision_evidence_invalid")
        for page in saved["pagesRevised"]:
            if (not isinstance(page, dict)
                or type(page.get("pageIndex")) is not int
                or page["pageIndex"] < 0):
                raise PlanRevisionComparisonError("revision_page_manifest_invalid")
            affected_pages.add(page["pageIndex"])
        events.append({
            "revisionId": rid,
            "revisionNumber": number,
            "event": saved["event"],
            "pagesRevised": saved["pagesRevised"],
        })
        parent_id, parent_sha, model_revision = rid, digest, after
    if (parent_id != newer_revision_id or parent_sha != newer_sha
        or model_revision != new["updatedModelRevision"]):
        raise PlanRevisionComparisonError("revision_range_end_mismatch")
    return {
        "olderRevisionId": older_revision_id,
        "newerRevisionId": newer_revision_id,
        "interveningRevisionCount": len(events),
        "affectedPageIndices": sorted(affected_pages),
        "changes": events,
        "reviewRevisionOnly": True,
        "requiresApproval": True,
        "geometryRedrawn": False,
        "commercialPublicationAllowed": False,
    }
