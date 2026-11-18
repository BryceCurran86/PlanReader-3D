"""Authenticated wall CREATE endpoint; no browser page, rate, PDF or proof input.

Production host provides all authoritative callbacks. PUT/POST does not
authenticate with browser identity, and GET never makes a public PDF.
"""
from __future__ import annotations

import json
import re
import sqlite3
from typing import Callable, Mapping, Any
from urllib.parse import unquote

from pb_vr_editor_readonly_wsgi import EditorPrincipal, AuthorizedSceneWorkspace
from pb_vr_editor_command_wsgi import _unique_object_pairs, _reject_non_json_constant
from pb_vr_wall_assembly_wsgi import _payload as parse_wall_payload, _REQUIRED as WALL_FIELDS
from pb_vr_wall_assembly_dependencies import WallAssemblySpecification, KnownServiceRoute
from pb_vr_wall_create_revision_store import (
    VerifiedWallDrawingCoverage, WallCreateConflict,
    create_wall_and_related_page_revision, list_created_walls, get_created_wall_pdf,
)

_CREATE = re.compile(r"/api/editor/workspaces/([^/]+)/walls/add/commit\Z")
_LIST = re.compile(r"/api/editor/workspaces/([^/]+)/walls/created\Z")
_PDF = re.compile(r"/api/editor/workspaces/([^/]+)/walls/revisions/([a-f0-9]{40})/pdf\Z")
_MAX = 32768
_HEADERS = [
    ("Cache-Control", "private, no-store"), ("Pragma", "no-cache"),
    ("X-Content-Type-Options", "nosniff"), ("Referrer-Policy", "no-referrer"),
    ("X-Frame-Options", "DENY"), ("Cross-Origin-Resource-Policy", "same-origin"),
    ("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"),
    ("Vary", "Cookie, Authorization"),
]


def make_wall_create_revision_wsgi_app(
    authenticate_session: Callable,
    load_authorized_workspace: Callable,
    verify_csrf: Callable,
    load_project_assembly_profile: Callable,
    load_verified_service_routes: Callable,
    load_verified_wall_sheet_coverage: Callable,
    load_original_pdf_bytes: Callable,
    get_wall_create_db_connection: Callable,
    verify_unified_document_head: Callable,
):
    """Fail closed if any tenant authority, source or model revision is missing.

    verify_unified_document_head must check original source, current model head
    and OTHER editors' revision heads under a production document lock.
    No standalone WSGI instance is considered safely deployable without this.
    """
    callbacks = (authenticate_session, load_authorized_workspace, verify_csrf,
                 load_project_assembly_profile, load_verified_service_routes,
                 load_verified_wall_sheet_coverage, load_original_pdf_bytes,
                 get_wall_create_db_connection, verify_unified_document_head)
    if not all(callable(x) for x in callbacks):
        raise ValueError("wall_create_requires_nine_real_providers")

    def application(environ: Mapping[str, Any], start_response):
        path = environ.get("PATH_INFO")
        create = _CREATE.fullmatch(path) if isinstance(path, str) else None
        listing = _LIST.fullmatch(path) if isinstance(path, str) else None
        pdf = _PDF.fullmatch(path) if isinstance(path, str) else None

        def reply(status, obj):
            raw = json.dumps(obj, separators=(",", ":"), allow_nan=False).encode()
            start_response(status, [*_HEADERS, ("Content-Type", "application/json; charset=utf-8"),
                                    ("Content-Length", str(len(raw)))])
            return [raw]

        if not (create or listing or pdf):
            return reply("404 Not Found", {"error": "wall_create_endpoint_unknown"})
        method = environ.get("REQUEST_METHOD")
        if (create and method != "POST") or ((listing or pdf) and method != "GET"):
            return reply("405 Method Not Allowed", {"error": "unsupported_method"})
        wid = unquote((create or listing or pdf).group(1))
        if not wid or len(wid) > 128 or "/" in wid or "\\" in wid:
            return reply("404 Not Found", {"error": "invalid_workspace"})
        try:
            principal = authenticate_session(environ)
        except Exception:
            principal = None
        if not isinstance(principal, EditorPrincipal):
            return reply("401 Unauthorized", {"error": "authentication_required"})
        if wid not in principal.allowed_workspace_ids:
            return reply("403 Forbidden", {"error": "workspace_denied"})
        if create:
            if (wid not in principal.allowed_revision_workspace_ids or
                wid not in principal.allowed_preview_workspace_ids):
                return reply("403 Forbidden", {"error": "wall_create_grant_required"})
            try:
                csrf_ok = verify_csrf(environ, principal)
            except Exception:
                csrf_ok = False
            if csrf_ok is not True:
                return reply("403 Forbidden", {"error": "csrf_invalid"})
            if str(environ.get("CONTENT_TYPE") or "").split(";", 1)[0].strip().lower() != "application/json":
                return reply("415 Unsupported Media Type", {"error": "json_required"})
            try:
                length = int(environ.get("CONTENT_LENGTH"))
            except (TypeError, ValueError):
                return reply("411 Length Required", {"error": "length_required"})
            if not 1 <= length <= _MAX:
                return reply("413 Content Too Large", {"error": "body_limit"})
            stream = environ.get("wsgi.input")
            if stream is None or not hasattr(stream, "read"):
                return reply("400 Bad Request", {"error": "body_required"})
            raw = stream.read(length)
            if type(raw) is not bytes or len(raw) != length:
                return reply("400 Bad Request", {"error": "body_truncated"})
            try:
                command = json.loads(raw.decode("utf-8"),
                                     object_pairs_hook=_unique_object_pairs,
                                     parse_constant=_reject_non_json_constant)
            except (ValueError, UnicodeError):
                return reply("400 Bad Request", {"error": "invalid_json"})
            if type(command) is not dict or set(command) != set(WALL_FIELDS) | {"idempotencyKey"}:
                return reply("422 Unprocessable Entity", {"error": "wall_create_schema_mismatch"})
            token = command["idempotencyKey"]
            request_wall = {k: v for k, v in command.items() if k != "idempotencyKey"}
        else:
            token, command, request_wall = None, None, None
        try:
            ws = load_authorized_workspace(principal, wid)
            if (not isinstance(ws, AuthorizedSceneWorkspace) or
                ws.tenant_id != principal.tenant_id or ws.scope.workspace_id != wid):
                return reply("403 Forbidden", {"error": "wall_create_workspace_denied"})
            db = get_wall_create_db_connection(principal, ws)
            if not isinstance(db, sqlite3.Connection):
                raise ValueError("wall_create_db_unavailable")
        except Exception:
            return reply("409 Conflict", {"error": "wall_create_workspace_unavailable"})

        try:
            if listing:
                return reply("200 OK", {"createdWalls": list_created_walls(db, principal, ws)})
            if pdf:
                content = get_created_wall_pdf(db, principal, ws, pdf.group(2))
                start_response("200 OK", [*_HEADERS, ("Content-Type", "application/pdf"),
                     ("Content-Length", str(len(content))),
                     ("Content-Disposition", 'attachment; filename="planreader-working-wall-revision.pdf"')])
                return [content]
            wall, profile_id = parse_wall_payload(request_wall, ws)
            assembly = load_project_assembly_profile(principal, ws, profile_id)
            routes = load_verified_service_routes(principal, ws, wall.level_id)
            coverage = load_verified_wall_sheet_coverage(principal, ws, wall)
            original = load_original_pdf_bytes(principal, ws)
            if type(assembly) is not WallAssemblySpecification or type(routes) is not tuple or any(
                type(r) is not KnownServiceRoute for r in routes
            ) or type(coverage) is not VerifiedWallDrawingCoverage:
                raise WallCreateConflict("trusted_construction_and_sheet_evidence_missing")
            # The host must check all other editing tracks' persisted heads.
            # This MUST be enforced under the host's shared document lock.
            if verify_unified_document_head(principal, ws, db) is not True:
                raise WallCreateConflict("another_editor_or_document_revision_unresolved")
            result = create_wall_and_related_page_revision(
                db, principal=principal, workspace=ws, wall=wall,
                assembly=assembly, routes=routes, coverage=coverage,
                original_pdf=original, idempotency_key=token,
                command_identity=command,
            )
            result["downloadPath"] = (
                "/api/editor/workspaces/" + wid + "/walls/revisions/" +
                result["revisionId"] + "/pdf"
            )
            return reply("201 Created", result)
        except PermissionError:
            return reply("403 Forbidden", {"error": "wall_create_permission_denied"})
        except WallCreateConflict:
            return reply("409 Conflict", {"error": "wall_create_stale_or_incomplete_revision"})
        except (TypeError, KeyError, ValueError):
            return reply("422 Unprocessable Entity", {"error": "wall_create_validation_denied"})
        except Exception:
            return reply("409 Conflict", {"error": "wall_create_commit_unavailable"})
        finally:
            db.close()

    return application
