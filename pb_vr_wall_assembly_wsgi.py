"""Authenticated, review-only added-wall cross-trade scope preview WSGI.

A user-drawn wall is NOT an original-source dimension. The only authority here
is an authenticated workspace and an independently retrieved company/project
assembly profile. This POST creates no object, PDF, approval, price or quote.

Production must explicitly wire real auth, original-source workspace, CSRF,
trusted *project-owned* assembly profile and verified electrical/hydraulic route
providers. An unconnected service has no permissive default.
"""
from __future__ import annotations

import json
import re
from typing import Callable, Any, Mapping
from urllib.parse import unquote

from pb_vr_editor_readonly_wsgi import EditorPrincipal, AuthorizedSceneWorkspace
from pb_vr_editor_command_wsgi import _reject_non_json_constant, _unique_object_pairs
from pb_vr_wall_assembly_dependencies import (
    NewWallDesign, ProposedOpening, WallAssemblySpecification,
    KnownServiceRoute, calculate_new_wall_construction_package,
)

_PATH = re.compile(r"/api/editor/workspaces/([^/]+)/walls/add/preview\Z")
_MAX_REQUEST = 32768
_REQUIRED = frozenset({
    "workspaceId", "projectId", "documentId", "revisionId",
    "snapshotId", "sourceSha256", "baseModelRevision", "proposalId",
    "levelId", "startPt", "endPt", "heightM", "openings", "assemblyProfileId",
})
_OPENING_FIELDS = frozenset({
    "openingId", "offsetM", "widthM", "heightM", "sillHeightM", "openingKind",
})
_RESPONSE_HEADERS = [
    ("Cache-Control", "private, no-store"),
    ("Pragma", "no-cache"),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("X-Frame-Options", "DENY"),
    ("Cross-Origin-Resource-Policy", "same-origin"),
    ("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"),
    ("Vary", "Cookie, Authorization"),
]


def _payload(command: object, workspace: AuthorizedSceneWorkspace) -> tuple[
    NewWallDesign, str,
]:
    if not isinstance(command, dict) or set(command) != _REQUIRED:
        raise ValueError("added_wall_command_schema_mismatch")
    scope=workspace.scope
    for field, owned in (
        ("workspaceId",scope.workspace_id),
        ("projectId",scope.project_id),
        ("documentId",scope.document_id),
        ("revisionId",scope.revision_id),
        ("snapshotId",scope.snapshot_id),
        ("sourceSha256",scope.source_sha256.lower()),
        ("baseModelRevision",scope.model_revision),
    ):
        if type(command[field]) is not type(owned) or command[field] != owned:
            raise ValueError("added_wall_" + field + "_stale_or_foreign")
    profile=command["assemblyProfileId"]
    if (type(profile) is not str or not 1 <= len(profile) <= 128 or
        re.fullmatch(r"[A-Za-z0-9_.:-]+",profile) is None):
        raise ValueError("added_wall_profile_identifier_invalid")
    openings=command["openings"]
    if not isinstance(openings,list) or len(openings)>100:
        raise ValueError("added_wall_openings_invalid")
    entries=[]
    for item in openings:
        if type(item) is not dict or set(item) != _OPENING_FIELDS:
            raise ValueError("added_wall_opening_schema_mismatch")
        entries.append(ProposedOpening(
            opening_id=item["openingId"],offset_m=item["offsetM"],
            width_m=item["widthM"],height_m=item["heightM"],
            sill_height_m=item["sillHeightM"],
            opening_kind=item["openingKind"],
        ))
    def point(x):
        if not isinstance(x,list) or len(x)!=2:
            raise ValueError("added_wall_coordinate_pair_required")
        return tuple(x)
    wall=NewWallDesign(
        workspace_id=scope.workspace_id,source_sha256=scope.source_sha256.lower(),
        snapshot_id=scope.snapshot_id,base_model_revision=scope.model_revision,
        proposal_id=command["proposalId"],level_id=command["levelId"],
        start_pt=point(command["startPt"]),end_pt=point(command["endPt"]),
        height_m=command["heightM"],openings=tuple(entries),
    )
    return wall,profile


def make_wall_addition_scope_wsgi_app(
    authenticate_session: Callable,
    load_authorized_workspace: Callable,
    verify_csrf: Callable,
    load_project_assembly_profile: Callable,
    load_verified_service_routes: Callable,
):
    """Build a deployment-controlled endpoint. No anonymous/demo fallback."""
    callbacks=(
        authenticate_session,load_authorized_workspace,verify_csrf,
        load_project_assembly_profile,load_verified_service_routes,
    )
    if not all(callable(x) for x in callbacks):
        raise ValueError("wall_scope_requires_all_five_trusted_providers")

    def application(environ: Mapping[str,Any], start_response):
        def reply(status: str,body: Mapping[str,Any]):
            payload=json.dumps(body,allow_nan=False,separators=(",",":")).encode()
            start_response(status,[*_RESPONSE_HEADERS,
                ("Content-Type","application/json; charset=utf-8"),
                ("Content-Length",str(len(payload)))])
            return [payload]
        path=environ.get("PATH_INFO")
        matched=_PATH.fullmatch(path) if isinstance(path,str) else None
        if matched is None:
            return reply("404 Not Found",{"error":"wall_scope_endpoint_unknown"})
        if environ.get("REQUEST_METHOD")!="POST":
            return reply("405 Method Not Allowed",{"error":"wall_scope_post_only"})
        wid=unquote(matched.group(1))
        if not wid or len(wid)>128 or "/" in wid or "\\" in wid:
            return reply("404 Not Found",{"error":"invalid_workspace_id"})
        try:
            principal=authenticate_session(environ)
        except Exception:
            principal=None
        if not isinstance(principal,EditorPrincipal):
            return reply("401 Unauthorized",{"error":"authentication_required"})
        if wid not in principal.allowed_preview_workspace_ids:
            return reply("403 Forbidden",{"error":"wall_scope_permission_denied"})
        try:
            valid_csrf=verify_csrf(environ,principal)
        except Exception:
            valid_csrf=False
        if valid_csrf is not True:
            return reply("403 Forbidden",{"error":"csrf_invalid"})
        content_type=str(environ.get("CONTENT_TYPE") or "").split(";",1)[0].strip().lower()
        if content_type!="application/json":
            return reply("415 Unsupported Media Type",{"error":"json_required"})
        try:
            length=int(environ.get("CONTENT_LENGTH"))
        except (ValueError,TypeError):
            return reply("411 Length Required",{"error":"content_length_required"})
        if length<1 or length>_MAX_REQUEST:
            return reply("413 Content Too Large",{"error":"wall_scope_body_limit"})
        input_stream=environ.get("wsgi.input")
        if input_stream is None or not hasattr(input_stream,"read"):
            return reply("400 Bad Request",{"error":"missing_json_input"})
        raw=input_stream.read(length)
        if type(raw) is not bytes or len(raw)!=length:
            return reply("400 Bad Request",{"error":"truncated_json_input"})
        try:
            command=json.loads(raw.decode("utf-8"),
                object_pairs_hook=_unique_object_pairs,
                parse_constant=_reject_non_json_constant)
        except (ValueError,UnicodeError):
            return reply("400 Bad Request",{"error":"invalid_json"})
        try:
            workspace=load_authorized_workspace(principal,wid)
            if (not isinstance(workspace,AuthorizedSceneWorkspace) or
                workspace.tenant_id!=principal.tenant_id or
                workspace.scope.workspace_id!=wid):
                return reply("403 Forbidden",{"error":"workspace_scope_denied"})
            wall,profile_id=_payload(command,workspace)
            # A user cannot smuggle their own framing, studs, bracing or MEP
            # scope, price or proof into the body: only server project config.
            assembly=load_project_assembly_profile(
                principal,workspace,profile_id,
            )
            if type(assembly) is not WallAssemblySpecification:
                raise ValueError("wall_scope_project_profile_unavailable")
            routes=load_verified_service_routes(principal,workspace,wall.level_id)
            if not isinstance(routes,(tuple,list)) or not all(
                type(x) is KnownServiceRoute for x in routes
            ):
                raise ValueError("trusted_service_route_census_unavailable")
            pkg=calculate_new_wall_construction_package(
                wall,assembly,known_service_routes=routes,
            )
            return reply("200 OK",{
                "accepted":True,
                "reviewOnly":True,
                "persisted":False,
                "commercialPublicationAllowed":False,
                "sourceGeometryAltered":False,
                "workspaceId":wid,
                "proposalId":wall.proposal_id,
                "baseModelRevision":wall.base_model_revision,
                "assemblyProfileId":profile_id,
                "package":pkg.to_dict(),
            })
        except (TypeError,ValueError,KeyError):
            return reply("422 Unprocessable Entity",{
                "error":"wall_geometry_assembly_or_service_evidence_unverified",
            })
        except Exception:
            return reply("409 Conflict",{
                "error":"wall_scope_project_provider_unavailable",
            })
    return application
