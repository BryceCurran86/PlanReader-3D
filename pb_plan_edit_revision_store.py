"""Atomic PlanReader edit -> immutable related-page PDF revision storage.

Uses the actual editable_3d_correction_events + editable_3d_object_state
schema in pb_planreader_3d_app. A single SQLite transaction persists:
- one approved? NO, unapproved correction event + current object state,
- one immutable derived PDF and exact edited-page evidence manifest,
- one new document revision head with optimistic model-revision CAS.
Original documents/pages/takeoff rows and prior revision blobs are untouched.

App must provide a real tenant-authenticated SQLite connection, numerical
workspace DB ID, source-verified workspace/ledger and protected PDF bytes.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import json
import sqlite3
from typing import Any, Mapping, Sequence

from pb_editable_3d_correction_model import (
    CorrectionSource, Editable3DCorrectionLedger,
)
from pb_editable_3d_correction_persistence import (
    correction_event_to_row, object_state_row,
)
from pb_vr_editor_command_preview import _SUPPORTED, preview_editor_command
from pb_vr_editor_readonly_wsgi import AuthorizedSceneWorkspace, EditorPrincipal
from pb_plan_edit_revision_bundle import (
    RelatedPageCoverage, render_related_page_revision,
)
from pb_takeoff_output_authority import TakeoffOutputRow


class PlanRevisionConflict(ValueError):
    pass


def install_plan_edit_revision_schema(connection: sqlite3.Connection) -> None:
    """Run from the app database migration; never lazily from a public route."""
    if not isinstance(connection, sqlite3.Connection):
        raise TypeError("revision_schema_requires_sqlite_connection")
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS plan_edit_revisions (
        revision_id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        workspace_id TEXT NOT NULL,
        workspace_db_id INTEGER NOT NULL,
        document_id TEXT NOT NULL,
        source_revision_id TEXT NOT NULL,
        source_pdf_sha256 TEXT NOT NULL,
        source_snapshot_id TEXT NOT NULL,
        revision_number INTEGER NOT NULL,
        revision_label TEXT NOT NULL,
        parent_revision_id TEXT,
        parent_pdf_sha256 TEXT NOT NULL,
        updated_pdf_sha256 TEXT NOT NULL,
        updated_pdf_blob BLOB NOT NULL,
        previous_model_revision INTEGER NOT NULL,
        updated_model_revision INTEGER NOT NULL,
        command_sha256 TEXT NOT NULL,
        idempotency_key TEXT NOT NULL,
        command_json TEXT NOT NULL,
        corrected_object_json TEXT NOT NULL,
        event_json TEXT NOT NULL,
        related_pages_json TEXT NOT NULL,
        actor_id TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(tenant_id,workspace_id,document_id,source_pdf_sha256,
               source_snapshot_id,revision_number),
        UNIQUE(tenant_id,workspace_id,document_id,source_pdf_sha256,
               source_snapshot_id,idempotency_key)
    );
    CREATE TABLE IF NOT EXISTS plan_edit_revision_heads (
        tenant_id TEXT NOT NULL,
        workspace_id TEXT NOT NULL,
        document_id TEXT NOT NULL,
        source_pdf_sha256 TEXT NOT NULL,
        source_snapshot_id TEXT NOT NULL,
        revision_id TEXT NOT NULL,
        model_revision INTEGER NOT NULL,
        revision_number INTEGER NOT NULL,
        updated_pdf_sha256 TEXT NOT NULL,
        PRIMARY KEY(tenant_id,workspace_id,document_id,
                    source_pdf_sha256,source_snapshot_id)
    );
    CREATE INDEX IF NOT EXISTS idx_plan_edit_revisions_listing
        ON plan_edit_revisions(tenant_id,workspace_id,document_id,
                               source_pdf_sha256,source_snapshot_id,revision_number);
    """)


def _scope_key(principal: EditorPrincipal,
               workspace: AuthorizedSceneWorkspace) -> tuple[str, ...]:
    s = workspace.scope
    return (principal.tenant_id, s.workspace_id, s.document_id,
            s.source_sha256.lower(), s.snapshot_id)


def _require_save_permission(principal: EditorPrincipal,
                             workspace: AuthorizedSceneWorkspace) -> None:
    s = workspace.scope
    if (not isinstance(principal, EditorPrincipal) or
        not isinstance(workspace, AuthorizedSceneWorkspace) or
        workspace.tenant_id != principal.tenant_id or
        s.workspace_id not in principal.allowed_revision_workspace_ids or
        s.workspace_id not in principal.allowed_preview_workspace_ids):
        raise PermissionError("revision_save_permission_denied")


def _encode(value: object) -> str:
    return json.dumps(value, allow_nan=False, sort_keys=True,
                      separators=(",", ":"), ensure_ascii=True)


def _read_head(connection: sqlite3.Connection, key: tuple[str, ...]):
    return connection.execute(
        """SELECT revision_id, model_revision, revision_number, updated_pdf_sha256
        FROM plan_edit_revision_heads
        WHERE tenant_id=? AND workspace_id=? AND document_id=?
          AND source_pdf_sha256=? AND source_snapshot_id=?""",
        key,
    ).fetchone()


def _idempotent_result(connection: sqlite3.Connection, key: tuple[str, ...],
                       token: str, command_sha: str) -> dict[str, Any] | None:
    row = connection.execute(
        """SELECT revision_id, command_sha256 FROM plan_edit_revisions
        WHERE tenant_id=? AND workspace_id=? AND document_id=?
          AND source_pdf_sha256=? AND source_snapshot_id=?
          AND idempotency_key=?""", (*key, token),
    ).fetchone()
    if row is None:
        return None
    if row[1] != command_sha:
        raise PlanRevisionConflict("idempotency_key_reused_for_different_edit")
    return get_plan_edit_revision(connection, key, row[0])


def _persist_existing_editable3d_tables(
    connection: sqlite3.Connection, workspace_db_id: int,
    event, corrected_object,
) -> None:
    """Identical column mapping to the original Streamlit editable-3D save path.

    All statements occur in the *same transaction* as the PDF and revision
    head. If the table is absent, fail rather than silently save only the PDF.
    """
    event_row = correction_event_to_row(workspace_db_id, event)
    # A command may never reuse a correction ID outside its idempotent revision.
    duplicate = connection.execute(
        """SELECT 1 FROM editable_3d_correction_events
        WHERE workspace_id=? AND correction_id=?""",
        (workspace_db_id, event.correction_id),
    ).fetchone()
    if duplicate:
        raise PlanRevisionConflict("correction_id_already_persisted")
    connection.execute(
        """INSERT INTO editable_3d_correction_events (
            workspace_id, correction_id, object_id, object_type, field,
            old_value_json, new_value_json, reason, actor, source,
            previous_revision_hash, new_revision_hash, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        tuple(event_row[field] for field in (
            "workspace_id", "correction_id", "object_id", "object_type",
            "field", "old_value_json", "new_value_json", "reason",
            "actor", "source", "previous_revision_hash",
            "new_revision_hash", "created_at",
        )),
    )
    state = object_state_row(workspace_db_id, corrected_object)
    connection.execute(
        """INSERT INTO editable_3d_object_state (
            workspace_id, object_id, authority_status, approved_by,
            approved_at, revision_hash, correction_ids_json, updated_at
        ) VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(workspace_id,object_id) DO UPDATE SET
            authority_status=excluded.authority_status,
            approved_by=excluded.approved_by,
            approved_at=excluded.approved_at,
            revision_hash=excluded.revision_hash,
            correction_ids_json=excluded.correction_ids_json,
            updated_at=excluded.updated_at""",
        tuple(state[field] for field in (
            "workspace_id", "object_id", "authority_status", "approved_by",
            "approved_at", "revision_hash", "correction_ids_json",
            "updated_at",
        )),
    )


def save_plan_edit_revision(
    connection: sqlite3.Connection, *, principal: EditorPrincipal,
    workspace: AuthorizedSceneWorkspace, workspace_db_id: int,
    ledger: Editable3DCorrectionLedger,
    command: Mapping[str, Any],
    original_pdf_bytes: bytes,
    page_coverage: RelatedPageCoverage,
    existing_rows: Sequence[TakeoffOutputRow] = (),
) -> dict[str, Any]:
    """Atomically save an edited model revision + all verified related PDF pages.

    The original drawing PDF is source-owned. A follow-up version starts from
    the prior immutable PDF, maintaining previous page annotations. The app
    must reload current ledger and modelRevision from SQLite after success.
    """
    _require_save_permission(principal, workspace)
    if not isinstance(connection, sqlite3.Connection) or connection.in_transaction:
        raise ValueError("revision_store_requires_idle_sqlite_transaction")
    if type(workspace_db_id) is not int or workspace_db_id <= 0:
        raise ValueError("trusted_workspace_db_id_required")
    if type(ledger) is not Editable3DCorrectionLedger or not isinstance(command, Mapping):
        raise ValueError("trusted_correction_ledger_required")
    if (type(original_pdf_bytes) is not bytes or
        sha256(original_pdf_bytes).hexdigest() != workspace.scope.source_sha256.lower()):
        raise PlanRevisionConflict("original_source_pdf_identity_mismatch")
    raw = dict(command)
    token = raw.get("idempotencyKey")
    if not isinstance(token, str) or not 1 <= len(token) <= 128:
        raise ValueError("revision_idempotency_key_required")
    command_sha = sha256(_encode(raw).encode("utf-8")).hexdigest()
    key = _scope_key(principal, workspace)
    cached = _idempotent_result(connection, key, token, command_sha)
    if cached is not None:
        return cached

    # Exact same server-side source, tenant, revision and geometry preflight
    # as the existing VR preview endpoint (which never writes).
    preflight = preview_editor_command(
        raw, principal=principal, workspace=workspace,
        ledger=ledger, existing_rows=existing_rows,
    )
    if preflight.get("accepted") is not True:
        raise PlanRevisionConflict(
            "source_or_editor_preflight_denied:" +
            ",".join(preflight.get("blockingReasons", []))
        )
    owner = ledger.get_object(raw["targetObjectId"])
    if owner is None:
        raise PlanRevisionConflict("revision_target_missing")
    witness = workspace.source_witnesses.get(owner.object_id)
    canonical = workspace.canonical_object_ids.get(owner.object_id)
    if witness is None or not canonical:
        raise PlanRevisionConflict("original_witness_or_canonical_missing")
    shadow = deepcopy(ledger)
    mapping = _SUPPORTED[raw["commandType"]]
    outcome = shadow.apply_correction(
        correction_id=raw["commandId"],
        object_id=owner.object_id,
        field=mapping[1],
        new_value=raw["payload"]["newValue"],
        reason=raw["reason"].strip(),
        actor=principal.subject_id,
        source=CorrectionSource.EDITOR_3D.value,
        expected_revision_hash=owner.revision_hash,
    )
    revised_object = shadow.get_object(owner.object_id)
    if not outcome.ok or outcome.event is None or revised_object is None:
        raise PlanRevisionConflict("revision_ledger_correction_failed")
    if outcome.event.new_revision_hash != preflight["previewObjectRevision"]:
        raise PlanRevisionConflict("revision_preview_vs_persisted_hash_mismatch")

    head = _read_head(connection, key)
    if head is None:
        number, parent_id, parent_sha = 1, None, workspace.scope.source_sha256.lower()
        parent_bytes = original_pdf_bytes
    else:
        parent_id, last_model_rev, last_number, parent_sha = head
        if last_model_rev != workspace.scope.model_revision:
            raise PlanRevisionConflict("stale_document_model_revision")
        number = last_number + 1
        row = connection.execute(
            """SELECT updated_pdf_blob FROM plan_edit_revisions
            WHERE revision_id=? AND tenant_id=? AND workspace_id=?
              AND document_id=? AND source_pdf_sha256=?
              AND source_snapshot_id=?""", (parent_id, *key),
        ).fetchone()
        if row is None:
            raise PlanRevisionConflict("parent_pdf_revision_missing")
        parent_bytes = bytes(row[0])
    if number > 999999:
        raise ValueError("revision_count_limit_reached")
    label = f"PR-R{number:04d}"
    pdf = render_related_page_revision(
        parent_bytes, scope=workspace.scope,
        edited=owner, witness=witness,
        canonical_object_id=canonical,
        coverage=page_coverage, revision_label=label,
        correction_field=outcome.event.field,
        prior_value=outcome.event.old_value,
        new_value=outcome.event.new_value,
        base_pdf_sha256=parent_sha,
    )
    revision_id = sha256(_encode({
        "scope": key, "number": number, "commandSha": command_sha,
        "parentSha": parent_sha, "artifact": pdf.sha256,
    }).encode("utf-8")).hexdigest()[:40]
    after_model_rev = workspace.scope.model_revision + 1

    # This transaction is all-or-nothing. No partial PDF when the app correction
    # fails; no app edit without a persisted revision and related-page bundle.
    connection.execute("BEGIN IMMEDIATE")
    try:
        current = _read_head(connection, key)
        if current != head:
            raise PlanRevisionConflict("concurrent_document_revision_conflict")
        if head is None and workspace.scope.model_revision < 0:
            raise PlanRevisionConflict("negative_initial_model_revision")
        if head is not None and head[1] != workspace.scope.model_revision:
            raise PlanRevisionConflict("stale_document_model_revision")
        if not connection.execute(
            "SELECT 1 FROM workspaces WHERE id=?", (workspace_db_id,)
        ).fetchone():
            raise PlanRevisionConflict("app_workspace_database_record_missing")
        _persist_existing_editable3d_tables(
            connection, workspace_db_id, outcome.event, revised_object,
        )
        connection.execute(
            """INSERT INTO plan_edit_revisions (
                revision_id,tenant_id,workspace_id,workspace_db_id,document_id,
                source_revision_id,source_pdf_sha256,source_snapshot_id,
                revision_number,revision_label,parent_revision_id,
                parent_pdf_sha256,updated_pdf_sha256,updated_pdf_blob,
                previous_model_revision,updated_model_revision,command_sha256,
                idempotency_key,command_json,corrected_object_json,event_json,
                related_pages_json,actor_id
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (revision_id, principal.tenant_id, workspace.scope.workspace_id,
             workspace_db_id, workspace.scope.document_id,
             workspace.scope.revision_id, workspace.scope.source_sha256.lower(),
             workspace.scope.snapshot_id, number, label, parent_id,
             parent_sha, pdf.sha256, pdf.bytes, workspace.scope.model_revision,
             after_model_rev, command_sha, token, _encode(raw),
             _encode(revised_object.to_dict()), _encode(outcome.event.to_dict()),
             _encode(pdf.related_pages), principal.subject_id),
        )
        connection.execute(
            """INSERT INTO plan_edit_revision_heads (
                tenant_id,workspace_id,document_id,source_pdf_sha256,
                source_snapshot_id,revision_id,model_revision,
                revision_number,updated_pdf_sha256
            ) VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(tenant_id,workspace_id,document_id,
                        source_pdf_sha256,source_snapshot_id)
            DO UPDATE SET revision_id=excluded.revision_id,
                model_revision=excluded.model_revision,
                revision_number=excluded.revision_number,
                updated_pdf_sha256=excluded.updated_pdf_sha256""",
            (*key, revision_id, after_model_rev, number, pdf.sha256),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return get_plan_edit_revision(connection, key, revision_id)


def get_plan_edit_revision(connection: sqlite3.Connection,
                           key: tuple[str, ...], revision_id: str) -> dict[str, Any]:
    row = connection.execute(
        """SELECT revision_id, revision_number, revision_label,
                  parent_revision_id, previous_model_revision,
                  updated_model_revision, updated_pdf_sha256, related_pages_json,
                  event_json
        FROM plan_edit_revisions
        WHERE revision_id=? AND tenant_id=? AND workspace_id=?
          AND document_id=? AND source_pdf_sha256=?
          AND source_snapshot_id=?""", (revision_id, *key),
    ).fetchone()
    if row is None:
        raise KeyError("revision_not_in_authorized_workspace")
    return {
        "saved": True, "revisionId": row[0], "revisionNumber": row[1],
        "revisionLabel": row[2], "parentRevisionId": row[3],
        "previousModelRevision": row[4], "updatedModelRevision": row[5],
        "updatedPdfSha256": row[6],
        "pagesRevised": json.loads(row[7]), "event": json.loads(row[8]),
        "requiresApproval": True, "commercialPublicationAllowed": False,
        "geometryRedrawn": False, "reviewRevisionOnly": True,
    }


def list_plan_edit_revisions(
    connection: sqlite3.Connection, principal: EditorPrincipal,
    workspace: AuthorizedSceneWorkspace,
) -> list[dict[str, Any]]:
    if not isinstance(principal, EditorPrincipal) or not isinstance(
        workspace, AuthorizedSceneWorkspace
    ) or principal.tenant_id != workspace.tenant_id or workspace.scope.workspace_id not in principal.allowed_workspace_ids:
        raise PermissionError("revision_history_access_denied")
    key = _scope_key(principal, workspace)
    rows = connection.execute(
        """SELECT revision_id FROM plan_edit_revisions
        WHERE tenant_id=? AND workspace_id=? AND document_id=?
          AND source_pdf_sha256=? AND source_snapshot_id=?
        ORDER BY revision_number DESC LIMIT 200""", key,
    ).fetchall()
    return [get_plan_edit_revision(connection, key, rid) for (rid,) in rows]


def get_plan_edit_pdf(
    connection: sqlite3.Connection, principal: EditorPrincipal,
    workspace: AuthorizedSceneWorkspace, revision_id: str,
) -> tuple[bytes, str]:
    if not isinstance(principal, EditorPrincipal) or not isinstance(
        workspace, AuthorizedSceneWorkspace
    ) or principal.tenant_id != workspace.tenant_id or workspace.scope.workspace_id not in principal.allowed_workspace_ids:
        raise PermissionError("revision_pdf_access_denied")
    if type(revision_id) is not str or len(revision_id) != 40:
        raise KeyError("invalid_revision_id")
    key = _scope_key(principal, workspace)
    row = connection.execute(
        """SELECT updated_pdf_blob,updated_pdf_sha256
        FROM plan_edit_revisions
        WHERE revision_id=? AND tenant_id=? AND workspace_id=?
          AND document_id=? AND source_pdf_sha256=?
          AND source_snapshot_id=?""", (revision_id, *key),
    ).fetchone()
    if row is None:
        raise KeyError("revision_pdf_not_in_workspace")
    blob = bytes(row[0])
    if sha256(blob).hexdigest() != row[1]:
        raise ValueError("revision_pdf_integrity_failed")
    return blob, row[1]
