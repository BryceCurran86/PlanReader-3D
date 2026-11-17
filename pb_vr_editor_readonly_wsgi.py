"""Authenticated, read-only WSGI boundary for the PlanReader evidence scene.

This is an application FACTORY, not a server that accepts anonymous traffic.
The owning PlanReader deployment must provide its real session authenticator
and workspace/tenant-scoped DB loader. Neither query strings nor browser JSON
are permitted to establish identity. No POST or model write route exists.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import unquote

from pb_editable_3d_correction_model import EditableGeometryObject
from pb_vr_editor_scene_manifest import (
    EditorWorkspaceScope, VerifiedSourceWitness, compile_editor_scene,
)


@dataclass(frozen=True)
class EditorPrincipal:
    subject_id: str
    tenant_id: str
    allowed_workspace_ids: frozenset[str]
    # Reading a workspace does NOT grant access to geometry/quantity impact
    # previews. A production permission resolver must populate this explicitly.
    allowed_preview_workspace_ids: frozenset[str] = frozenset()
    # Revision writes are strictly stronger than preview access and default off.
    # The production permission resolver must opt in explicitly per workspace.
    allowed_revision_workspace_ids: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.subject_id or not self.tenant_id:
            raise ValueError("principal identity and tenant required")
        if not isinstance(self.allowed_workspace_ids, frozenset):
            raise ValueError("allowed_workspace_ids must be an immutable server-side grant set")
        if not isinstance(self.allowed_preview_workspace_ids, frozenset):
            raise ValueError("allowed_preview_workspace_ids must be an immutable server-side grant set")
        if not self.allowed_preview_workspace_ids.issubset(self.allowed_workspace_ids):
            raise ValueError("preview grants must be included in allowed readable workspaces")
        if not isinstance(self.allowed_revision_workspace_ids, frozenset):
            raise ValueError("revision grants must be an immutable server-side grant set")
        if not self.allowed_revision_workspace_ids.issubset(self.allowed_preview_workspace_ids):
            raise ValueError("revision grants must be included in previewable workspaces")


@dataclass(frozen=True)
class AuthorizedSceneWorkspace:
    """Returned only from the trusted scoped repository callback."""

    tenant_id: str
    scope: EditorWorkspaceScope
    objects: Sequence[EditableGeometryObject]
    canonical_object_ids: Mapping[str, str]
    # Only the trusted original-source resolver may provide these exact
    # document/revision/native-path receipts. Default empty = all REVIEW.
    source_witnesses: Mapping[str, VerifiedSourceWitness] = field(default_factory=dict)


Authenticate = Callable[[Mapping[str, Any]], EditorPrincipal | None]
LoadWorkspace = Callable[[EditorPrincipal, str], AuthorizedSceneWorkspace | None]
_PATH = re.compile(r"/api/editor/workspaces/([^/]+)/manifest\Z")


def make_editor_readonly_wsgi_app(
    authenticate_session: Authenticate,
    load_authorized_workspace: LoadWorkspace,
):
    """Construct a GET-only scene service using injected REAL auth & database.

    This adapter cannot be deployed as an anonymous file server. Its callers
    must verify sessions against the existing PlanReader user/tenant database
    and load the exact workspace from server-owned records. The returned
    read-only scene is always marked noncommercial.
    """
    if not callable(authenticate_session) or not callable(load_authorized_workspace):
        raise ValueError("authenticated scene service requires auth and workspace providers")

    def application(environ: Mapping[str, Any], start_response):
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
            # Intentionally no CORS opt-in: only same-origin authenticated UI.
        ]

        def respond(status: str, payload: dict[str, Any]):
            data = json.dumps(payload, allow_nan=False, separators=(",", ":")).encode("utf-8")
            start_response(status, [*headers, ("Content-Length", str(len(data)))])
            return [data]

        if environ.get("REQUEST_METHOD") != "GET":
            return respond("405 Method Not Allowed", {"error": "read_only_editor_api"})
        path = environ.get("PATH_INFO", "")
        match = _PATH.fullmatch(path) if isinstance(path, str) else None
        if match is None:
            return respond("404 Not Found", {"error": "not_found"})
        workspace_id = unquote(match.group(1))
        if not workspace_id or "/" in workspace_id or "\\" in workspace_id:
            return respond("404 Not Found", {"error": "invalid_workspace_id"})

        try:
            principal = authenticate_session(environ)
        except Exception:
            return respond("401 Unauthorized", {"error": "authentication_required"})
        if not isinstance(principal, EditorPrincipal):
            return respond("401 Unauthorized", {"error": "authentication_required"})
        if workspace_id not in principal.allowed_workspace_ids:
            return respond("403 Forbidden", {"error": "workspace_access_denied"})

        try:
            workspace = load_authorized_workspace(principal, workspace_id)
            if workspace is None:
                return respond("404 Not Found", {"error": "workspace_not_found"})
            if not isinstance(workspace, AuthorizedSceneWorkspace):
                raise TypeError("workspace provider returned invalid payload")
            if (workspace.tenant_id != principal.tenant_id
                    or workspace.scope.workspace_id != workspace_id):
                return respond("403 Forbidden", {"error": "workspace_scope_mismatch"})
            scene = compile_editor_scene(
                workspace.scope, workspace.objects,
                canonical_object_ids=workspace.canonical_object_ids,
                source_witnesses=workspace.source_witnesses,
            )
        except Exception:
            # Do not leak source SHA, private paths, object IDs, DB errors, or
            # stack traces to clients. Server observability is the caller's job.
            return respond("409 Conflict", {"error": "workspace_scene_unavailable"})
        return respond("200 OK", scene)

    return application
