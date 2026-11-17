"""Opt-in WSGI adapter: existing GET / single preview + bounded batch preview.

The owning deployment MUST supply production session authentication, tenant
workspace loader, scoped correction ledger and CSRF verifier; no defaults.
No write route, persistent command, payment or price publication is added.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Mapping
from urllib.parse import unquote

from pb_editable_3d_correction_model import Editable3DCorrectionLedger
from pb_vr_editor_batch_preview import preview_editor_batch
from pb_vr_editor_command_wsgi import (
    _reject_non_json_constant, _unique_object_pairs,
    make_editor_preview_wsgi_app,
)
from pb_vr_editor_readonly_wsgi import EditorPrincipal, AuthorizedSceneWorkspace

_PATH = re.compile(r"/api/editor/workspaces/([^/]+)/commands/batch-preview\Z")
_MAX_BODY = 32 * 1024


def make_editor_batch_wsgi_app(
    authenticate_session: Callable,
    load_authorized_workspace: Callable,
    load_authorized_ledger: Callable,
    verify_csrf: Callable,
):
    """Expose batch preview without altering existing scene/single preview API."""
    if not all(callable(x) for x in (
        authenticate_session, load_authorized_workspace, load_authorized_ledger, verify_csrf,
    )):
        raise ValueError("authenticated VR batch requires all four server providers")
    original = make_editor_preview_wsgi_app(
        authenticate_session, load_authorized_workspace,
        load_authorized_ledger, verify_csrf,
    )
    headers = [
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

    def app(environ: Mapping[str, Any], start_response):
        path = environ.get("PATH_INFO")
        match = _PATH.fullmatch(path) if isinstance(path, str) else None
        if match is None:
            return original(environ, start_response)

        def respond(status: str, data: Mapping[str, Any]):
            payload = json.dumps(data, allow_nan=False, separators=(",", ":")).encode("utf-8")
            start_response(status, [*headers, ("Content-Length", str(len(payload)))])
            return [payload]

        if environ.get("REQUEST_METHOD") != "POST":
            return respond("405 Method Not Allowed", {"error": "unsupported_method"})
        wid = unquote(match.group(1))
        if not wid or "/" in wid or "\\" in wid or len(wid) > 128:
            return respond("404 Not Found", {"error": "invalid_workspace_id"})
        try:
            principal = authenticate_session(environ)
        except Exception:
            principal = None
        if not isinstance(principal, EditorPrincipal):
            return respond("401 Unauthorized", {"error": "authentication_required"})
        if wid not in principal.allowed_workspace_ids or wid not in principal.allowed_preview_workspace_ids:
            return respond("403 Forbidden", {"error": "preview_permission_denied"})
        try:
            valid_csrf = verify_csrf(environ, principal)
        except Exception:
            valid_csrf = False
        if valid_csrf is not True:
            return respond("403 Forbidden", {"error": "csrf_token_invalid"})
        if str(environ.get("CONTENT_TYPE") or "").split(";", 1)[0].strip().lower() != "application/json":
            return respond("415 Unsupported Media Type", {"error": "json_required"})
        try:
            count = int(environ.get("CONTENT_LENGTH"))
        except (TypeError, ValueError):
            return respond("411 Length Required", {"error": "content_length_required"})
        if count < 1 or count > _MAX_BODY:
            return respond("413 Content Too Large", {"error": "batch_body_size_invalid"})
        stream = environ.get("wsgi.input")
        if stream is None or not hasattr(stream, "read"):
            return respond("400 Bad Request", {"error": "missing_request_body"})
        raw = stream.read(count)
        if not isinstance(raw, bytes) or len(raw) != count:
            return respond("400 Bad Request", {"error": "truncated_request_body"})
        try:
            request = json.loads(raw.decode("utf-8"),
                                 object_pairs_hook=_unique_object_pairs,
                                 parse_constant=_reject_non_json_constant)
        except (UnicodeError, ValueError):
            return respond("400 Bad Request", {"error": "invalid_json"})
        if not isinstance(request, dict):
            return respond("400 Bad Request", {"error": "batch_object_required"})
        try:
            ws = load_authorized_workspace(principal, wid)
            if not isinstance(ws, AuthorizedSceneWorkspace):
                return respond("404 Not Found", {"error": "workspace_not_found"})
            if ws.scope.workspace_id != wid or ws.tenant_id != principal.tenant_id:
                return respond("403 Forbidden", {"error": "workspace_scope_mismatch"})
            ledger, rows = load_authorized_ledger(principal, ws)
            if not isinstance(ledger, Editable3DCorrectionLedger):
                raise TypeError("invalid ledger provider")
            result = preview_editor_batch(request, principal=principal,
                                          workspace=ws, ledger=ledger,
                                          existing_rows=rows)
        except Exception:
            return respond("409 Conflict", {"error": "batch_preview_unavailable"})
        return respond("200 OK" if result["accepted"] else "422 Unprocessable Entity", result)

    return app
