"""Read-only, fail-closed integrity audit for an original PlanReader revision chain.

No table mutation, PDF rewriting, approval, or automatic repair. The audit
verifies recorded hashes and ancestry; it does not authenticate source ink.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import sqlite3


@dataclass(frozen=True)
class RevisionChainAudit:
    intact: bool
    revision_count: int
    errors: tuple[str, ...]


def audit_plan_edit_revision_chain(
    connection: sqlite3.Connection, key: tuple[str, str, str, str, str]
) -> RevisionChainAudit:
    """Audit a server-authorized (tenant, workspace, document, SHA, snapshot).

    The caller must authorize access to this exact scope before invoking.
    Fail closed on missing heads, non-contiguous revisions, broken PDF
    ancestry, hash changes, and model-revision gaps.
    """
    if not isinstance(connection, sqlite3.Connection):
        raise TypeError("sqlite_connection_required")
    if (
        type(key) is not tuple or len(key) != 5
        or any(type(part) is not str or not part for part in key)
        or len(key[3]) != 64
        or any(char not in "0123456789abcdef" for char in key[3])
    ):
        raise ValueError("authorized_revision_scope_required")
    # Stream indexed PDF rows instead of materializing every immutable PDF BLOB.
    rows = connection.execute(
        """SELECT revision_id, revision_number, parent_revision_id,
                  parent_pdf_sha256, updated_pdf_sha256, updated_pdf_blob,
                  previous_model_revision, updated_model_revision
           FROM plan_edit_revisions
           WHERE tenant_id=? AND workspace_id=? AND document_id=?
             AND source_pdf_sha256=? AND source_snapshot_id=?
           ORDER BY revision_number ASC""",
        key,
    )
    head = connection.execute(
        """SELECT revision_id, revision_number, updated_pdf_sha256,
                  model_revision
           FROM plan_edit_revision_heads
           WHERE tenant_id=? AND workspace_id=? AND document_id=?
             AND source_pdf_sha256=? AND source_snapshot_id=?""",
        key,
    ).fetchone()
    errors: list[str] = []
    previous_id = None
    previous_pdf_sha = key[3]
    previous_model_revision = None
    count = 0
    for index, row in enumerate(rows, 1):
        count = index
        (revision_id, number, parent_id, parent_sha, pdf_sha,
         pdf_blob, before_model, after_model) = tuple(row)
        if type(number) is not int or number != index:
            errors.append(f"revision_{index}_number_gap")
        if parent_id != previous_id or parent_sha != previous_pdf_sha:
            errors.append(f"revision_{index}_parent_mismatch")
        if type(pdf_blob) is not bytes and not isinstance(pdf_blob, memoryview):
            errors.append(f"revision_{index}_pdf_blob_invalid")
        elif type(pdf_sha) is not str or sha256(bytes(pdf_blob)).hexdigest() != pdf_sha:
            errors.append(f"revision_{index}_pdf_hash_mismatch")
        if (type(before_model) is not int or type(after_model) is not int
            or before_model < 0 or after_model != before_model + 1
            or (previous_model_revision is not None
                and before_model != previous_model_revision)):
            errors.append(f"revision_{index}_model_revision_gap")
        previous_id = revision_id
        previous_pdf_sha = pdf_sha
        previous_model_revision = after_model
    if count == 0:
        if head is not None:
            errors.append("orphan_revision_head")
        return RevisionChainAudit(not errors, 0, tuple(errors))
    if head is None:
        errors.append("revision_head_missing")
    elif tuple(head) != (
        previous_id, count, previous_pdf_sha, previous_model_revision
    ):
        errors.append("revision_head_mismatch")
    return RevisionChainAudit(not errors, count, tuple(errors))
