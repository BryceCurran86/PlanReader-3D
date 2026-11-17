"""Authenticated PlanReader: save and download immutable multi-page revisions.

Opt-in WSGI factory; does not expose an anonymous development endpoint.
Reuses existing typed edit preview for request/source vetting, then commits
one real editable-3D correction and related PDF version atomically via SQLite.

POST /api/editor/workspaces/{id}/revisions   typed correction command ONLY
GET  /api/editor/workspaces/{id}/revisions   immutable revision history
GET  /api/editor/workspaces/{id}/revisions/{sha40}/pdf private reviewed PDF

No route approves, publishes, prices, or overwrites original PDFs. Every
trusted callback must be wired by the production application. No fallback.
"""
from __future__ import annotations

import json
import re
import sqlite3
from typing import Callable, Mapping, Any
from urllib.parse import unquote, quote

from pb_vr_editor_command_wsgi import (
    make_editor_preview_wsgi_app, _reject_non_json_constant, _unique_object_pairs,
)
from pb_vr_editor_readonly_wsgi import EditorPrincipal, AuthorizedSceneWorkspace
from pb_editable_3d_correction_model import Editable3DCorrectionLedger
from pb_plan_edit_revision_store import (
    PlanRevisionConflict, save_plan_edit_revision,
    list_plan_edit_revisions, get_plan_edit_pdf,
)
from pb_plan_edit_revision_bundle import RelatedPageCoverage

_ROOT = re.compile(r"/api/editor/workspaces/([^/]+)/revisions\Z")
_PDF = re.compile(r"/api/editor/workspaces/([^/]+)/revisions/([a-f0-9]{40})/pdf\Z")
_MAX_BODY = 32 * 1024
_HEADERS = [
    ("Cache-Control", "private, no-store"),
    ("Pragma", "no-cache"),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("X-Frame-Options", "DENY"),
    ("Cross-Origin-Resource-Policy", "same-origin"),
    ("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"),
    ("Vary", "Cookie, Authorization"),
]


def make_plan_edit_revision_wsgi_app(
    authenticate_session: Callable,
    load_authorized_workspace: Callable,
    load_authorized_ledger: Callable,
    verify_csrf: Callable,
    get_revision_db_connection: Callable,
    load_original_pdf_bytes: Callable,
    resolve_verified_related_pages: Callable,
    resolve_workspace_database_id: Callable,
):
    """Caller connects the existing session, DB, originals and cross-sheet truth.

    All page relationships must come from a trusted server-side producer.
    The caller is responsible for closing the returned SQLite connection,
    and must not expose a globally shared, cross-tenant connection.
    """
    callbacks = (
        authenticate_session, load_authorized_workspace,
        load_authorized_ledger, verify_csrf, get_revision_db_connection,
        load_original_pdf_bytes, resolve_verified_related_pages,
        resolve_workspace_database_id,
    )
    if not all(callable(x) for x in callbacks):
        raise ValueError("plan_revision_requires_all_eight_real_providers")

    existing = make_editor_preview_wsgi_app(
        authenticate_session, load_authorized_workspace,
        load_authorized_ledger, verify_csrf,
    )

    def application(environ: Mapping[str, Any], start_response):
        path = environ.get("PATH_INFO")
        p = _PDF.fullmatch(path) if isinstance(path, str) else None
        root = _ROOT.fullmatch(path) if isinstance(path, str) else None
        if not root and not p:
            return existing(environ, start_response)
        method = environ.get("REQUEST_METHOD")
        def reply(status: str, body: Mapping[str, Any]):
            raw = json.dumps(body, separators=(",", ":"), allow_nan=False).encode("utf-8")
            start_response(status, [*_HEADERS,
                                   ("Content-Type", "application/json; charset=utf-8"),
                                   ("Content-Length", str(len(raw)))])
            return [raw]
        workspace_id = unquote((root or p).group(1))
        if (not workspace_id or "/" in workspace_id or "\\" in workspace_id or
            len(workspace_id) > 128):
            return reply("404 Not Found", {"error": "invalid_workspace_id"})
        if p and method != "GET":
            return reply("405 Method Not Allowed", {"error": "revision_pdf_read_only"})
        if root and method not in ("GET", "POST"):
            return reply("405 Method Not Allowed", {"error": "unsupported_revision_method"})
        try:
            principal = authenticate_session(environ)
        except Exception:
            principal = None
        if not isinstance(principal, EditorPrincipal):
            return reply("401 Unauthorized", {"error": "authentication_required"})
        if workspace_id not in principal.allowed_workspace_ids:
            return reply("403 Forbidden", {"error": "workspace_access_denied"})
        if method == "POST":
            if workspace_id not in principal.allowed_revision_workspace_ids:
                return reply("403 Forbidden", {"error": "revision_save_permission_denied"})
            try:
                csrf = verify_csrf(environ, principal)
            except Exception:
                csrf = False
            if csrf is not True:
                return reply("403 Forbidden", {"error": "csrf_token_invalid"})
            if (str(environ.get("CONTENT_TYPE") or "").split(";", 1)[0]
                    .strip().lower() != "application/json"):
                return reply("415 Unsupported Media Type", {"error": "json_required"})
            try:
                length = int(environ.get("CONTENT_LENGTH"))
            except (ValueError, TypeError):
                return reply("411 Length Required", {"error": "content_length_required"})
            if length < 1 or length > _MAX_BODY:
                return reply("413 Content Too Large", {"error": "revision_body_limit"})
            source = environ.get("wsgi.input")
            if source is None or not hasattr(source, "read"):
                return reply("400 Bad Request", {"error": "missing_request_body"})
            raw = source.read(length)
            if not isinstance(raw, bytes) or len(raw) != length:
                return reply("400 Bad Request", {"error": "truncated_request_body"})
            try:
                command = json.loads(raw.decode("utf-8"),
                                     object_pairs_hook=_unique_object_pairs,
                                     parse_constant=_reject_non_json_constant)
            except (ValueError, UnicodeError):
                return reply("400 Bad Request", {"error": "invalid_json"})
            if not isinstance(command, dict):
                return reply("400 Bad Request", {"error": "typed_command_required"})
        else:
            command = None
        try:
            ws = load_authorized_workspace(principal, workspace_id)
            if not isinstance(ws, AuthorizedSceneWorkspace):
                return reply("404 Not Found", {"error": "workspace_not_found"})
            if ws.tenant_id != principal.tenant_id or ws.scope.workspace_id != workspace_id:
                return reply("403 Forbidden", {"error": "workspace_scope_mismatch"})
            connection = get_revision_db_connection(principal, ws)
            if not isinstance(connection, sqlite3.Connection):
                raise TypeError("revision_sqlite_connection_unavailable")
        except Exception:
            return reply("409 Conflict", {"error": "revision_workspace_unavailable"})
        try:
            if p:
                blob, digest = get_plan_edit_pdf(connection, principal, ws, p.group(2))
                headers = [
                    *_HEADERS, ("Content-Type", "application/pdf"),
                    ("Content-Length", str(len(blob))),
                    ("Content-Disposition", 'attachment; filename="planreader-revision-' +
                     p.group(2)[:12] + '.pdf"'),
                    ("ETag", '"' + digest + '"'),
                ]
                start_response("200 OK", headers)
                return [blob]
            if method == "GET":
                items = list_plan_edit_revisions(connection, principal, ws)
                return reply("200 OK", {"revisions": items, "readOnly": True})
            ledger, existing_rows = load_authorized_ledger(principal, ws)
            if type(ledger) is not Editable3DCorrectionLedger:
                raise TypeError("editor_ledger_unavailable")
            original_bytes = load_original_pdf_bytes(principal, ws)
            # The backend resolver (not the browser) owns the complete
            # document-wide cross-sheet correspondence universe.
            coverage = resolve_verified_related_pages(principal, ws, command)
            if type(coverage) is not RelatedPageCoverage:
                raise ValueError("cross_sheet_page_universe_unavailable")
            workspace_db_id = resolve_workspace_database_id(principal, ws)
            saved = save_plan_edit_revision(
                connection, principal=principal, workspace=ws,
                workspace_db_id=workspace_db_id, ledger=ledger,
                command=command, original_pdf_bytes=original_bytes,
                page_coverage=coverage, existing_rows=existing_rows,
            )
            saved["downloadPath"] = (
                "/api/editor/workspaces/" + quote(workspace_id, safe="") +
                "/revisions/" + saved["revisionId"] + "/pdf"
            )
            return reply("201 Created", saved)
        except PermissionError:
            return reply("403 Forbidden", {"error": "revision_permission_denied"})
        except PlanRevisionConflict:
            return reply("409 Conflict", {"error": "stale_or_conflicting_plan_revision"})
        except (ValueError, KeyError):
            return reply("422 Unprocessable Entity", {
                "error": "original_source_or_related_page_revision_unverified",
            })
        except Exception:
            # Never leak private PDF path, authentication details, DB info,
            # source geometry or raw exception messages to browser clients.
            return reply("409 Conflict", {"error": "revision_commit_unavailable"})
        finally:
            connection.close()

    return application
