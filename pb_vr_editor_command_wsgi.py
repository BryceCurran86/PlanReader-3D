"""Read-only workspace GET + CSRF-protected typed command impact PREVIEW.

This WSGI adapter exposes NO persistent mutation/approval endpoint. It requires
injected production session auth, a tenant-scoped repository and CSRF verifier.
Source SHA, snapshot, canonical object and revision are checked against the
server-owned workspace before a deep-copy ledger quantity impact preview.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import unquote

from pb_editable_3d_correction_model import Editable3DCorrectionLedger
from pb_takeoff_output_authority import TakeoffOutputRow
from pb_vr_editor_command_preview import preview_editor_command
from pb_vr_editor_readonly_wsgi import (
    AuthorizedSceneWorkspace, EditorPrincipal, make_editor_readonly_wsgi_app,
)

_MAX_REQUEST_BYTES = 32 * 1024
_PREVIEW_PATH = re.compile(r"/api/editor/workspaces/([^/]+)/commands/preview\Z")
LedgerLoader = Callable[
    [EditorPrincipal, AuthorizedSceneWorkspace],
    tuple[Editable3DCorrectionLedger, Sequence[TakeoffOutputRow]],
]
CsrfVerifier = Callable[[Mapping[str, Any], EditorPrincipal], bool]


def _unique_object_pairs(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError("duplicate JSON key")
        result[k] = v
    return result


def _reject_non_json_constant(value: str):
    # Python's default json.loads accepts NaN / Infinity, which are NOT JSON.
    # Never let a nonstandard number enter an editing/quantity command.
    raise ValueError(f"nonfinite JSON constant is forbidden: {value}")


def make_editor_preview_wsgi_app(
    authenticate_session: Callable[[Mapping[str, Any]], EditorPrincipal | None],
    load_authorized_workspace: Callable[
        [EditorPrincipal, str], AuthorizedSceneWorkspace | None
    ],
    load_authorized_ledger: LedgerLoader,
    verify_csrf: CsrfVerifier,
):
    """Expose read-only scene and impact-preview routes; no state writes."""
    if not all(callable(p) for p in (
        authenticate_session, load_authorized_workspace,
        load_authorized_ledger, verify_csrf,
    )):
        raise ValueError("editor command API requires auth, repository and CSRF providers")
    read_only = make_editor_readonly_wsgi_app(
        authenticate_session, load_authorized_workspace
    )
    headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Cache-Control", "no-store, private"),
        ("X-Content-Type-Options", "nosniff"),
        ("Referrer-Policy", "no-referrer"),
        ("Vary", "Cookie, Authorization"),
    ]

    def app(environ, start_response):
        method = environ.get("REQUEST_METHOD")
        if method == "GET":
            return read_only(environ, start_response)

        def respond(status, body):
            data = json.dumps(body, allow_nan=False, separators=(",", ":")).encode("utf-8")
            start_response(status, [*headers, ("Content-Length", str(len(data)))])
            return [data]

        if method != "POST":
            return respond("405 Method Not Allowed", {"error": "unsupported_method"})
        path = environ.get("PATH_INFO")
        match = _PREVIEW_PATH.fullmatch(path) if isinstance(path, str) else None
        if match is None:
            return respond("404 Not Found", {"error": "not_found"})
        workspace_id = unquote(match.group(1))
        if not workspace_id or "/" in workspace_id or "\\" in workspace_id:
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
            return respond("403 Forbidden", {"error": "correction_preview_permission_denied"})
        try:
            csrf_ok = verify_csrf(environ, principal)
        except Exception:
            csrf_ok = False
        if csrf_ok is not True:
            return respond("403 Forbidden", {"error": "csrf_token_invalid"})

        media_type = str(environ.get("CONTENT_TYPE") or "").split(";", 1)[0].lower().strip()
        if media_type != "application/json":
            return respond("415 Unsupported Media Type", {"error": "json_required"})
        raw_length = environ.get("CONTENT_LENGTH")
        try:
            count = int(raw_length)
        except (TypeError, ValueError):
            return respond("411 Length Required", {"error": "content_length_required"})
        if count <= 0 or count > _MAX_REQUEST_BYTES:
            return respond("413 Content Too Large", {"error": "command_body_size_invalid"})
        stream = environ.get("wsgi.input")
        if stream is None or not hasattr(stream, "read"):
            return respond("400 Bad Request", {"error": "missing_request_body"})
        data = stream.read(count)
        if not isinstance(data, bytes) or len(data) != count:
            return respond("400 Bad Request", {"error": "truncated_request_body"})
        try:
            command = json.loads(
                data.decode("utf-8"),
                object_pairs_hook=_unique_object_pairs,
                parse_constant=_reject_non_json_constant,
            )
        except (UnicodeError, ValueError):
            return respond("400 Bad Request", {"error": "invalid_json"})
        if not isinstance(command, dict):
            return respond("400 Bad Request", {"error": "expected_json_object"})

        try:
            ws = load_authorized_workspace(principal, workspace_id)
            if not isinstance(ws, AuthorizedSceneWorkspace):
                return respond("404 Not Found", {"error": "workspace_not_found"})
            if (ws.tenant_id != principal.tenant_id
                    or ws.scope.workspace_id != workspace_id):
                return respond("403 Forbidden", {"error": "workspace_scope_mismatch"})
            ledger, rows = load_authorized_ledger(principal, ws)
            if not isinstance(ledger, Editable3DCorrectionLedger):
                raise TypeError("ledger provider returned invalid type")
            result = preview_editor_command(
                command, principal=principal, workspace=ws,
                ledger=ledger, existing_rows=rows,
            )
        except Exception:
            return respond("409 Conflict", {"error": "editor_preview_unavailable"})
        status = "200 OK" if result["accepted"] else "422 Unprocessable Entity"
        if not result["accepted"] and any(
            "stale" in item or "mismatch" in item or "conflict" in item
            for item in result["blockingReasons"]
        ):
            status = "409 Conflict"
        return respond(status, result)

    return app
