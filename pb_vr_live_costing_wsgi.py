"""Same-origin authenticated live-costing preview endpoint.

POST /api/editor/workspaces/<workspace>/costing/preview takes exactly the
existing typed correction command (no rates, amounts or quantity overrides).
Authenticates tenant, workspace and CSRF, calls existing source-witness-bound
quantity preview on a deep-copy ledger, and THEN independently loads a
server-owned company rate book for exact-cent what-if costing.

This adapter deliberately has NO write, publish, company-rate editor, quote,
invoice or approval route. It composes the existing preview/manifest WSGI app.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Mapping
from urllib.parse import unquote

from pb_editable_3d_correction_model import Editable3DCorrectionLedger
from pb_vr_editor_command_preview import preview_editor_command
from pb_vr_editor_command_wsgi import (
    _reject_non_json_constant, _unique_object_pairs, make_editor_preview_wsgi_app,
)
from pb_vr_editor_readonly_wsgi import AuthorizedSceneWorkspace, EditorPrincipal
from pb_vr_live_costing import LiveCostBook, price_live_correction_preview

_PATH = re.compile(r"/api/editor/workspaces/([^/]+)/costing/preview\Z")
_MAX_REQUEST_BYTES = 32 * 1024
_HEADERS = [
    ("Content-Type", "application/json; charset=utf-8"),
    ("Cache-Control", "no-store, private"),
    ("Pragma", "no-cache"),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("X-Frame-Options", "DENY"),
    ("Cross-Origin-Resource-Policy", "same-origin"),
    ("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"),
    ("Vary", "Cookie, Authorization"),
]


def make_vr_live_costing_wsgi_app(
    authenticate_session: Callable,
    load_authorized_workspace: Callable,
    load_authorized_ledger: Callable,
    verify_csrf: Callable,
    load_authorized_cost_book: Callable,
):
    """All five required providers are owned by the production application.

    Missing providers fail during setup. No anonymous demonstration fallback.
    """
    if not all(callable(x) for x in (
        authenticate_session, load_authorized_workspace,
        load_authorized_ledger, verify_csrf, load_authorized_cost_book,
    )):
        raise ValueError("live_costing_requires_five_authenticated_providers")
    legacy = make_editor_preview_wsgi_app(
        authenticate_session, load_authorized_workspace,
        load_authorized_ledger, verify_csrf,
    )

    def app(environ: Mapping[str, Any], start_response):
        path = environ.get("PATH_INFO")
        match = _PATH.fullmatch(path) if isinstance(path, str) else None
        if match is None:
            return legacy(environ, start_response)

        def respond(status: str, payload: Mapping[str, Any]):
            raw = json.dumps(payload, allow_nan=False, separators=(",", ":")).encode("utf-8")
            start_response(status, [*_HEADERS, ("Content-Length", str(len(raw)))])
            return [raw]

        if environ.get("REQUEST_METHOD") != "POST":
            return respond("405 Method Not Allowed", {"error": "unsupported_method"})
        workspace_id = unquote(match.group(1))
        if not workspace_id or "/" in workspace_id or "\\" in workspace_id or len(workspace_id) > 128:
            return respond("404 Not Found", {"error": "invalid_workspace_id"})
        try:
            principal = authenticate_session(environ)
        except Exception:
            principal = None
        if not isinstance(principal, EditorPrincipal):
            return respond("401 Unauthorized", {"error": "authentication_required"})
        if workspace_id not in principal.allowed_workspace_ids:
            return respond("403 Forbidden", {"error": "workspace_access_denied"})
        if workspace_id not in principal.allowed_preview_workspace_ids:
            return respond("403 Forbidden", {"error": "cost_preview_permission_denied"})
        try:
            csrf_ok = verify_csrf(environ, principal)
        except Exception:
            csrf_ok = False
        if csrf_ok is not True:
            return respond("403 Forbidden", {"error": "csrf_token_invalid"})
        content_type = str(environ.get("CONTENT_TYPE") or "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            return respond("415 Unsupported Media Type", {"error": "json_required"})
        try:
            count = int(environ.get("CONTENT_LENGTH"))
        except (TypeError, ValueError):
            return respond("411 Length Required", {"error": "content_length_required"})
        if count < 1 or count > _MAX_REQUEST_BYTES:
            return respond("413 Content Too Large", {"error": "cost_preview_body_size_invalid"})
        stream = environ.get("wsgi.input")
        if stream is None or not hasattr(stream, "read"):
            return respond("400 Bad Request", {"error": "missing_request_body"})
        raw = stream.read(count)
        if not isinstance(raw, bytes) or len(raw) != count:
            return respond("400 Bad Request", {"error": "truncated_request_body"})
        try:
            command = json.loads(raw.decode("utf-8"),
                                 object_pairs_hook=_unique_object_pairs,
                                 parse_constant=_reject_non_json_constant)
        except (UnicodeError, ValueError):
            return respond("400 Bad Request", {"error": "invalid_json"})
        if not isinstance(command, dict):
            return respond("400 Bad Request", {"error": "cost_preview_object_required"})
        # Browser must never supply rates, tax, approvals or publication flags.
        # Reject these before quantity/revision evaluation so the denial stays a
        # validation failure (422), not a stale-revision conflict (409).
        forbidden = (
            "rates", "taxPct", "approved", "commercialPublicationAllowed",
        )
        if any(key in command for key in forbidden):
            return respond(
                "422 Unprocessable Entity",
                {
                    "accepted": False,
                    "quantityPreview": {
                        "blockingReasons": ["browser_cost_override_forbidden"],
                    },
                    "costingPreview": None,
                },
            )
        try:
            workspace = load_authorized_workspace(principal, workspace_id)
            if not isinstance(workspace, AuthorizedSceneWorkspace):
                return respond("404 Not Found", {"error": "workspace_not_found"})
            if (workspace.tenant_id != principal.tenant_id or
                workspace.scope.workspace_id != workspace_id):
                return respond("403 Forbidden", {"error": "workspace_scope_mismatch"})
            ledger, rows = load_authorized_ledger(principal, workspace)
            if not isinstance(ledger, Editable3DCorrectionLedger):
                raise TypeError("ledger_provider_invalid")
            quantity = preview_editor_command(
                command, principal=principal, workspace=workspace,
                ledger=ledger, existing_rows=rows,
            )
            if quantity.get("accepted") is not True:
                reason_codes = quantity.get("blockingReasons") or []
                conflict = any("stale" in s or "mismatch" in s or "conflict" in s
                               for s in reason_codes)
                return respond(
                    "409 Conflict" if conflict else "422 Unprocessable Entity",
                    {"accepted": False, "quantityPreview": quantity,
                     "costingPreview": None},
                )
            book = load_authorized_cost_book(principal, workspace)
            if type(book) is not LiveCostBook:
                raise TypeError("server_rate_book_required")
            costing = price_live_correction_preview(
                command, quantity, principal=principal, workspace=workspace,
                book=book,
            )
        except Exception:
            # No internal DB paths, private rates, source geometry or traceback
            # can be disclosed on misconfiguration/price failure.
            return respond("409 Conflict", {"error": "cost_preview_unavailable"})
        return respond("200 OK", {
            "accepted": True, "quantityPreview": quantity, "costingPreview": costing,
        })

    return app
