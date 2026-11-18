"""Opt-in, authenticated HTTP GET for immutable saved PlanReader revision comparisons.

Adapter wraps the existing original-app revision service; does not replace the
writer, its session provider, or its SQLite revision head. Host must supply
real production providers, not development fixtures.
"""
from __future__ import annotations

import json
import re
import sqlite3
from typing import Any, Callable, Mapping
from urllib.parse import unquote

from pb_plan_edit_revision_compare import (
    PlanRevisionComparisonError, compare_plan_edit_revisions,
)
from pb_plan_edit_revision_wsgi import _HEADERS
from pb_vr_editor_readonly_wsgi import AuthorizedSceneWorkspace, EditorPrincipal


_COMPARE = re.compile(
    r"/api/editor/workspaces/([^/]+)/revisions/compare/([0-9a-f]{40})/([0-9a-f]{40})\Z"
)


def make_plan_edit_revision_compare_wsgi_app(
    existing_revision_app: Callable,
    *,
    authenticate_session: Callable,
    load_authorized_workspace: Callable,
    get_revision_db_connection: Callable,
):
    """Install the private comparison route alongside an existing revision app.

    Workspace/document scope comes exclusively from the authenticated loader;
    the client provides only two immutable revision IDs. Neither the route nor
    its response can save, approve, publish or price quantities.
    """
    if not all(callable(x) for x in (
        existing_revision_app, authenticate_session, load_authorized_workspace,
        get_revision_db_connection,
    )):
        raise ValueError("comparison_requires_real_authenticated_host_providers")

    def application(environ: Mapping[str, Any], start_response):
        path = environ.get("PATH_INFO")
        match = _COMPARE.fullmatch(path) if isinstance(path, str) else None
        if match is None:
            return existing_revision_app(environ, start_response)

        def respond(status: str, payload: Mapping[str, Any]):
            data = json.dumps(payload, allow_nan=False,
                              separators=(",", ":")).encode("utf-8")
            start_response(status, [
                *_HEADERS, ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(data))),
            ])
            return [data]

        if environ.get("REQUEST_METHOD") != "GET":
            return respond("405 Method Not Allowed",
                           {"error": "revision_comparison_read_only"})
        workspace_id = unquote(match.group(1))
        if (not workspace_id or "/" in workspace_id or "\\" in workspace_id
            or len(workspace_id) > 128):
            return respond("404 Not Found", {"error": "invalid_workspace_id"})
        try:
            principal = authenticate_session(environ)
        except Exception:
            principal = None
        if not isinstance(principal, EditorPrincipal):
            return respond("401 Unauthorized", {"error": "authentication_required"})
        if workspace_id not in principal.allowed_workspace_ids:
            return respond("403 Forbidden", {"error": "workspace_access_denied"})
        try:
            workspace = load_authorized_workspace(principal, workspace_id)
        except Exception:
            return respond("404 Not Found", {"error": "workspace_not_found"})
        if not isinstance(workspace, AuthorizedSceneWorkspace):
            return respond("404 Not Found", {"error": "workspace_not_found"})
        if (workspace.tenant_id != principal.tenant_id
            or workspace.scope.workspace_id != workspace_id):
            return respond("403 Forbidden", {"error": "workspace_scope_mismatch"})
        try:
            connection = get_revision_db_connection(principal, workspace)
        except Exception:
            return respond("409 Conflict", {"error": "revision_database_unavailable"})
        if not isinstance(connection, sqlite3.Connection):
            return respond("409 Conflict", {"error": "revision_database_unavailable"})
        try:
            result = compare_plan_edit_revisions(
                connection, principal=principal, workspace=workspace,
                older_revision_id=match.group(2),
                newer_revision_id=match.group(3),
            )
            return respond("200 OK", result)
        except PermissionError:
            return respond("403 Forbidden", {"error": "revision_permission_denied"})
        except KeyError:
            return respond("404 Not Found", {"error": "revision_not_found"})
        except (PlanRevisionComparisonError, ValueError, sqlite3.Error):
            return respond("409 Conflict", {"error": "revision_comparison_unverified"})
        except Exception:
            # Never disclose raw source geometry, SQL errors or tenant metadata.
            return respond("409 Conflict", {"error": "revision_comparison_unavailable"})
        finally:
            connection.close()

    return application
