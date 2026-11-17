"""Opt-in, versioned, tenant-scoped SQLite storage for PlanReader VR rate books.

Rates are SERVER-OWNED financial data. This is a repository adapter, not an
HTTP admin editor or a production migration: the application must supply an
authenticated database connection and a real, externally authorized rate-
manager role check. No default rate book, tenant or tax settings are created.

Immutable revisions retain historical rates; an explicit authorized promotion
points to the active revision for the EXACT source SHA/snapshot. Source changes
do not silently inherit old prices. DB integrity hash detects corruption
but is not a substitute for database access controls.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
import sqlite3
from typing import Callable

from pb_builder_edition_architecture import CanonicalCompanyRate
from pb_vr_editor_readonly_wsgi import AuthorizedSceneWorkspace, EditorPrincipal
from pb_vr_editor_scene_manifest import VerifiedSourceWitness
from pb_vr_live_costing import LiveCostBook, LiveRateBinding


def install_rate_book_schema(connection: sqlite3.Connection) -> None:
    """Explicit migration. Call during deployment, NEVER within an HTTP request."""
    if not isinstance(connection, sqlite3.Connection):
        raise TypeError("sqlite_connection_required")
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS vr_live_pricing_books (
        tenant_id TEXT NOT NULL,
        workspace_id TEXT NOT NULL,
        source_sha256 TEXT NOT NULL,
        snapshot_id TEXT NOT NULL,
        revision TEXT NOT NULL,
        content_json TEXT NOT NULL,
        content_sha256 TEXT NOT NULL,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (tenant_id, workspace_id, source_sha256, snapshot_id, revision)
    );
    CREATE TABLE IF NOT EXISTS vr_live_pricing_active (
        tenant_id TEXT NOT NULL,
        workspace_id TEXT NOT NULL,
        source_sha256 TEXT NOT NULL,
        snapshot_id TEXT NOT NULL,
        revision TEXT NOT NULL,
        updated_by TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (tenant_id, workspace_id, source_sha256, snapshot_id)
    );
    """)


def _authorized(principal: EditorPrincipal, workspace: AuthorizedSceneWorkspace) -> None:
    if (not isinstance(principal, EditorPrincipal) or
        not isinstance(workspace, AuthorizedSceneWorkspace) or
        principal.tenant_id != workspace.tenant_id or
        workspace.scope.workspace_id not in principal.allowed_preview_workspace_ids):
        raise PermissionError("rate_book_permission_or_tenant_denied")


def _source_owned_targets(workspace: AuthorizedSceneWorkspace) -> set[str]:
    valid = set()
    for obj in workspace.objects:
        witness = workspace.source_witnesses.get(obj.object_id)
        canonical = workspace.canonical_object_ids.get(obj.object_id)
        if (canonical and isinstance(witness, VerifiedSourceWitness) and
            witness.matches(workspace.scope, obj)):
            valid.add(canonical)
    return valid


def _check_book_scope(book: LiveCostBook, workspace: AuthorizedSceneWorkspace) -> None:
    scope = workspace.scope
    if (type(book) is not LiveCostBook or
        book.tenant_id != workspace.tenant_id or
        book.workspace_id != scope.workspace_id or
        book.source_sha256.lower() != scope.source_sha256.lower() or
        book.snapshot_id != scope.snapshot_id):
        raise ValueError("rate_book_source_scope_mismatch")
    if not all(binding.canonical_object_id in _source_owned_targets(workspace)
               for binding in book.bindings):
        raise ValueError("rate_binding_unwitnessed_canonical_owner")


def _encode(book: LiveCostBook) -> str:
    return json.dumps(asdict(book), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


def _decode(raw: str) -> LiveCostBook:
    def pairs(items):
        data = {}
        for k, v in items:
            if k in data:
                raise ValueError("duplicate_ratebook_json_key")
            data[k] = v
        return data
    values = json.loads(raw, object_pairs_hook=pairs)
    if not isinstance(values, dict):
        raise ValueError("rate_book_json_not_object")
    expected = {
        "tenant_id", "workspace_id", "source_sha256", "snapshot_id",
        "revision", "currency", "tax_pct", "contingency_pct",
        "bindings", "evidence_ids",
    }
    if set(values) != expected or not isinstance(values["bindings"], list):
        raise ValueError("rate_book_document_schema_invalid")
    bindings = []
    for item in values["bindings"]:
        if not isinstance(item, dict) or set(item) != {
            "canonical_object_id", "target", "rate", "binding_evidence_ids"
        } or not isinstance(item["rate"], dict):
            raise ValueError("rate_binding_schema_invalid")
        if set(item["rate"]) != set(CanonicalCompanyRate.__dataclass_fields__):
            raise ValueError("rate_structure_schema_invalid")
        bindings.append(LiveRateBinding(
            canonical_object_id=item["canonical_object_id"],
            target=item["target"],
            rate=CanonicalCompanyRate(**item["rate"]),
            binding_evidence_ids=tuple(item["binding_evidence_ids"]),
        ))
    return LiveCostBook(
        tenant_id=values["tenant_id"], workspace_id=values["workspace_id"],
        source_sha256=values["source_sha256"],
        snapshot_id=values["snapshot_id"], revision=values["revision"],
        currency=values["currency"], tax_pct=values["tax_pct"],
        contingency_pct=values["contingency_pct"], bindings=tuple(bindings),
        evidence_ids=tuple(values["evidence_ids"]),
    )


def activate_rate_book(
    connection: sqlite3.Connection, *, principal: EditorPrincipal,
    workspace: AuthorizedSceneWorkspace, book: LiveCostBook,
    authorize_rate_manager: Callable[[EditorPrincipal, AuthorizedSceneWorkspace], bool],
) -> str:
    """Explicit authorized, immutable staging + active-revision promotion.

    The caller verifies financial admin role externally; an estimator's mere
    correction-preview permission is NOT permission to update rates.
    """
    _authorized(principal, workspace)
    if not callable(authorize_rate_manager) or authorize_rate_manager(
        principal, workspace
    ) is not True:
        raise PermissionError("rate_book_management_permission_denied")
    _check_book_scope(book, workspace)
    data = _encode(book)
    digest = sha256(data.encode("utf-8")).hexdigest()
    key = (book.tenant_id, book.workspace_id, book.source_sha256.lower(),
           book.snapshot_id, book.revision)
    with connection:
        row = connection.execute(
            """SELECT content_sha256 FROM vr_live_pricing_books
            WHERE tenant_id=? AND workspace_id=? AND source_sha256=?
              AND snapshot_id=? AND revision=?""", key,
        ).fetchone()
        if row is not None and row[0] != digest:
            raise ValueError("immutable_rate_revision_conflict")
        if row is None:
            connection.execute(
                """INSERT INTO vr_live_pricing_books
                (tenant_id,workspace_id,source_sha256,snapshot_id,revision,
                 content_json,content_sha256,created_by) VALUES(?,?,?,?,?,?,?,?)""",
                (*key, data, digest, principal.subject_id),
            )
        connection.execute(
            """INSERT INTO vr_live_pricing_active
            (tenant_id,workspace_id,source_sha256,snapshot_id,revision,updated_by)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(tenant_id,workspace_id,source_sha256,snapshot_id)
            DO UPDATE SET revision=excluded.revision,updated_by=excluded.updated_by,
              updated_at=CURRENT_TIMESTAMP""", (*key, principal.subject_id),
        )
    return digest


def load_authorized_cost_book(
    connection: sqlite3.Connection, principal: EditorPrincipal,
    workspace: AuthorizedSceneWorkspace,
) -> LiveCostBook:
    """Drop-in server-owned rate-book callback (bind connection in application).

    Raises when no explicit current revision exists; NEVER supplies a demo
    or zero-price fallback. Matches exact tenant, workspace, SHA and snapshot.
    """
    _authorized(principal, workspace)
    s = workspace.scope
    key = (workspace.tenant_id, s.workspace_id, s.source_sha256.lower(), s.snapshot_id)
    row = connection.execute(
        """SELECT b.content_json,b.content_sha256
        FROM vr_live_pricing_active AS a
        JOIN vr_live_pricing_books AS b
          ON b.tenant_id=a.tenant_id AND b.workspace_id=a.workspace_id
          AND b.source_sha256=a.source_sha256 AND b.snapshot_id=a.snapshot_id
          AND b.revision=a.revision
        WHERE a.tenant_id=? AND a.workspace_id=?
          AND a.source_sha256=? AND a.snapshot_id=?""", key,
    ).fetchone()
    if row is None:
        raise ValueError("no_explicit_rate_book_for_current_source")
    document, digest = row
    if sha256(document.encode("utf-8")).hexdigest() != digest:
        raise ValueError("rate_book_storage_integrity_conflict")
    book = _decode(document)
    _check_book_scope(book, workspace)
    return book
