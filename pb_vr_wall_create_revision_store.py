"""Atomic user-authored wall creation and coordinated immutable PDF revision.

This is a WORKING-DESIGN wall, not authenticated as an original-source wall.
Every page receives an independently producer-registered PDF projection;
missing/ambiguous projections fail the whole transaction. No source document,
canonical measured takeoff, architect-issued revision or quote is overwritten.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
import re
import sqlite3
from typing import Mapping

import fitz

from pb_vr_editor_readonly_wsgi import AuthorizedSceneWorkspace, EditorPrincipal
from pb_vr_wall_assembly_dependencies import (
    NewWallDesign, WallAssemblySpecification, KnownServiceRoute,
    calculate_new_wall_construction_package,
)

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
_MAX_BYTES = 80 * 1024 * 1024
_MAX_PAGES = 700


class WallCreateConflict(ValueError):
    """A stale, incomplete or otherwise non-atomic working revision."""


@dataclass(frozen=True)
class VerifiedNewWallPageProjection:
    """Trusted document-local projection of THIS newly drawn wall, not browser data.

    The independent renderer must verify the model-to-sheet registration and
    the visible PDF viewport, including the sheet's own scale/rotation.
    """
    page_index: int
    sheet_id: str
    page_kind: str
    registration_evidence_id: str
    wall_start_pdf: tuple[float, float]
    wall_end_pdf: tuple[float, float]

    def __post_init__(self):
        if type(self.page_index) is not int or not 0 <= self.page_index < _MAX_PAGES:
            raise ValueError("wall_page_index_invalid")
        if any(type(v) is not str or _ID.fullmatch(v) is None for v in
               (self.sheet_id, self.page_kind, self.registration_evidence_id)):
            raise ValueError("wall_page_registration_missing")
        for p in (self.wall_start_pdf, self.wall_end_pdf):
            if type(p) is not tuple or len(p) != 2 or any(
                type(x) not in (int, float) or not math.isfinite(x) or abs(x) > 100000
                for x in p
            ):
                raise ValueError("wall_page_projection_invalid")
        if math.dist(self.wall_start_pdf, self.wall_end_pdf) < 0.05:
            raise ValueError("wall_page_projection_degenerate")


@dataclass(frozen=True)
class VerifiedWallDrawingCoverage:
    """Full affected sheet universe, established only by the trusted host."""
    document_id: str
    source_sha256: str
    snapshot_id: str
    proposal_id: str
    complete: bool
    known_affected_page_indices: tuple[int, ...]
    projections: tuple[VerifiedNewWallPageProjection, ...]

    def __post_init__(self):
        if any(type(x) is not str or _ID.fullmatch(x) is None for x in
               (self.document_id, self.snapshot_id, self.proposal_id)):
            raise ValueError("wall_sheet_scope_invalid")
        if type(self.source_sha256) is not str or _SHA.fullmatch(
            self.source_sha256.lower()
        ) is None:
            raise ValueError("wall_sheet_source_invalid")
        if type(self.complete) is not bool:
            raise ValueError("wall_sheet_completeness_unknown")
        if type(self.known_affected_page_indices) is not tuple or type(
            self.projections
        ) is not tuple or len(self.projections) > _MAX_PAGES:
            raise ValueError("wall_sheet_page_set_invalid")
        if any(type(x) is not VerifiedNewWallPageProjection for x in self.projections):
            raise ValueError("wall_sheet_projections_untrusted")


def install_wall_creation_schema(db: sqlite3.Connection) -> None:
    if not isinstance(db, sqlite3.Connection) or db.in_transaction:
        raise ValueError("wall_create_migration_requires_idle_connection")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS vr_created_wall_heads (
        tenant_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
        document_id TEXT NOT NULL, source_sha256 TEXT NOT NULL,
        snapshot_id TEXT NOT NULL, revision_number INTEGER NOT NULL,
        model_revision INTEGER NOT NULL, revision_id TEXT NOT NULL,
        updated_pdf_sha256 TEXT NOT NULL,
        PRIMARY KEY(tenant_id,workspace_id,document_id,source_sha256,snapshot_id)
    );
    CREATE TABLE IF NOT EXISTS vr_created_wall_revisions (
        revision_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
        workspace_id TEXT NOT NULL, document_id TEXT NOT NULL,
        source_sha256 TEXT NOT NULL, snapshot_id TEXT NOT NULL,
        revision_number INTEGER NOT NULL, base_model_revision INTEGER NOT NULL,
        updated_model_revision INTEGER NOT NULL, proposal_id TEXT NOT NULL,
        idempotency_key TEXT NOT NULL, command_sha256 TEXT NOT NULL,
        actor_id TEXT NOT NULL, canonical_wall_id TEXT NOT NULL,
        wall_json TEXT NOT NULL, assembly_json TEXT NOT NULL,
        package_json TEXT NOT NULL, related_pages_json TEXT NOT NULL,
        pdf_sha256 TEXT NOT NULL, pdf_blob BLOB NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(tenant_id,workspace_id,document_id,source_sha256,snapshot_id,idempotency_key),
        UNIQUE(tenant_id,workspace_id,document_id,source_sha256,snapshot_id,proposal_id)
    );
    CREATE INDEX IF NOT EXISTS idx_vr_created_wall_history
       ON vr_created_wall_revisions(
       tenant_id,workspace_id,document_id,source_sha256,snapshot_id,revision_number);
    """)


def _as_json(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True, allow_nan=False)


def _scope(principal, workspace):
    s = workspace.scope
    return (principal.tenant_id, s.workspace_id, s.document_id,
            s.source_sha256.lower(), s.snapshot_id)


def _assert_scope(principal, workspace, wall, coverage):
    if not isinstance(principal, EditorPrincipal) or not isinstance(
        workspace, AuthorizedSceneWorkspace
    ) or type(wall) is not NewWallDesign or type(coverage) is not VerifiedWallDrawingCoverage:
        raise ValueError("trusted_wall_create_types_required")
    s = workspace.scope
    if (workspace.tenant_id != principal.tenant_id or
        s.workspace_id not in principal.allowed_revision_workspace_ids or
        s.workspace_id not in principal.allowed_preview_workspace_ids or
        (wall.workspace_id, wall.source_sha256.lower(), wall.snapshot_id,
         wall.base_model_revision) !=
        (s.workspace_id, s.source_sha256.lower(), s.snapshot_id, s.model_revision)):
        raise PermissionError("wall_create_scope_or_permission_denied")
    if (not coverage.complete or
        (coverage.document_id, coverage.source_sha256.lower(),
         coverage.snapshot_id, coverage.proposal_id) !=
        (s.document_id, s.source_sha256.lower(), s.snapshot_id, wall.proposal_id)):
        raise WallCreateConflict("wall_create_related_sheet_universe_incomplete")
    expected = coverage.known_affected_page_indices
    actual = tuple(sorted(p.page_index for p in coverage.projections))
    if (not expected or len(set(expected)) != len(expected) or
        tuple(sorted(expected)) != actual or len(set(actual)) != len(actual) or
        len({p.sheet_id for p in coverage.projections}) != len(actual)):
        raise WallCreateConflict("wall_create_missing_or_duplicate_page_projection")


def _new_pdf(parent: bytes, coverage: VerifiedWallDrawingCoverage,
             number: int, wall: NewWallDesign) -> tuple[bytes, tuple[dict, ...]]:
    if type(parent) is not bytes or len(parent) > _MAX_BYTES or not parent:
        raise WallCreateConflict("wall_create_parent_pdf_unavailable")
    try:
        doc = fitz.open(stream=parent, filetype="pdf")
    except Exception as exc:
        raise WallCreateConflict("wall_create_invalid_pdf") from exc
    try:
        if (doc.needs_pass or doc.is_encrypted or doc.is_form_pdf or
            not 1 <= doc.page_count <= _MAX_PAGES):
            raise WallCreateConflict("wall_create_pdf_not_editable")
        result = []
        for registration in sorted(coverage.projections, key=lambda p: p.page_index):
            if registration.page_index >= doc.page_count:
                raise WallCreateConflict("wall_create_page_outside_pdf")
            page = doc[registration.page_index]
            start = fitz.Point(*registration.wall_start_pdf)
            end = fitz.Point(*registration.wall_end_pdf)
            # A verified new wall has no native old stroke to erase. Draw a
            # review-only vector with its own lineage; do not cover originals.
            if not page.rect.contains(start) or not page.rect.contains(end):
                raise WallCreateConflict("wall_create_pdf_projection_outside_page")
            shape = page.new_shape()
            shape.draw_line(start, end)
            shape.finish(color=(0, 0.45, 0.9), width=2.0, dashes="[4 3] 0")
            shape.commit(overlay=True)
            label = ("PR-W%04d | PROPOSED NEW WALL | REVIEW ONLY\
"
                     "%.3f m length × %.3f m height; %d openings (coordination required)"
                     % (number, wall.length_m, wall.height_m, len(wall.openings)))
            loc = fitz.Rect(page.rect.x0 + 8, page.rect.y0 + 8,
                            min(page.rect.x1 - 8, page.rect.x0 + 290),
                            min(page.rect.y1 - 8, page.rect.y0 + 42))
            if loc.width <= 0 or loc.height <= 0:
                raise WallCreateConflict("wall_create_page_too_small_to_annotate")
            a = page.add_freetext_annot(loc, label, fontsize=8,
                                       text_color=(0, 0.15, 0.45),
                                       fill_color=(0.9, 0.96, 1))
            a.set_info(title="PlanReader proposed wall", subject=wall.proposal_id,
                       content=label)
            a.update()
            result.append({
                "pageIndex": registration.page_index,
                "sheetId": registration.sheet_id,
                "pageKind": registration.page_kind,
                "registrationEvidenceId": registration.registration_evidence_id,
                "newWallVectorDrawn": True, "approved": False,
            })
        data = doc.tobytes(garbage=3, deflate=True)
        if len(data) > 100 * 1024 * 1024:
            raise WallCreateConflict("wall_create_revised_pdf_size_limit")
        return data, tuple(result)
    finally:
        doc.close()



def _segment_conflict(a, b, c, d) -> bool:
    """Reject overlapping segments and mid-wall intersections, allow joined endpoints."""
    def cross(u, v, w):
        return (v[0]-u[0])*(w[1]-u[1])-(v[1]-u[1])*(w[0]-u[0])
    def on_segment(u, v, w):
        return (abs(cross(u,v,w)) <= 1e-7 and
                min(u[0],v[0])-1e-7 <= w[0] <= max(u[0],v[0])+1e-7 and
                min(u[1],v[1])-1e-7 <= w[1] <= max(u[1],v[1])+1e-7)
    if all(abs(cross(a,b,p)) <= 1e-7 for p in (c,d)):
        axis = 0 if abs(a[0]-b[0]) >= abs(a[1]-b[1]) else 1
        lo1,hi1 = sorted([a[axis],b[axis]])
        lo2,hi2 = sorted([c[axis],d[axis]])
        return min(hi1,hi2)-max(lo1,lo2) > 1e-7
    signs = (cross(a,b,c),cross(a,b,d),cross(c,d,a),cross(c,d,b))
    intersects = ((signs[0]*signs[1] < 0 and signs[2]*signs[3] < 0) or
                  any(on_segment(a,b,p) for p in (c,d)) or
                  any(on_segment(c,d,p) for p in (a,b)))
    if not intersects:
        return False
    return not any(math.dist(p, q) < 1e-7 for p in (a,b) for q in (c,d))


def _check_existing_created_wall_clashes(db, key, wall):
    existing = db.execute("""
        SELECT wall_json FROM vr_created_wall_revisions
         WHERE tenant_id=? AND workspace_id=? AND document_id=?
           AND source_sha256=? AND snapshot_id=?
    """, key).fetchall()
    for (raw,) in existing:
        prior = json.loads(raw)
        if prior["level_id"] == wall.level_id and _segment_conflict(
            wall.start_pt, wall.end_pt, prior["start_pt"], prior["end_pt"]
        ):
            raise WallCreateConflict("created_wall_intersection_requires_topology_review")


def create_wall_and_related_page_revision(
    db: sqlite3.Connection, *, principal: EditorPrincipal,
    workspace: AuthorizedSceneWorkspace, wall: NewWallDesign,
    assembly: WallAssemblySpecification, routes: tuple[KnownServiceRoute, ...],
    coverage: VerifiedWallDrawingCoverage, original_pdf: bytes,
    idempotency_key: str, command_identity: Mapping[str, object],
) -> dict:
    """Commit a working-design wall, all verified page vectors and event atomically.

    The host must load the returned wall ledger/revision head into the next
    working scene and invalidate dependent quantities and published approvals.
    """
    _assert_scope(principal, workspace, wall, coverage)
    if not isinstance(db, sqlite3.Connection) or db.in_transaction:
        raise ValueError("wall_create_requires_idle_sqlite_transaction")
    if type(assembly) is not WallAssemblySpecification or type(routes) is not tuple or any(
        type(x) is not KnownServiceRoute for x in routes
    ):
        raise ValueError("trusted_wall_assembly_and_routes_required")
    if type(idempotency_key) is not str or _ID.fullmatch(idempotency_key) is None:
        raise ValueError("wall_create_idempotency_required")
    if not isinstance(command_identity, Mapping):
        raise ValueError("wall_create_command_identity_required")
    if type(original_pdf) is not bytes or sha256(original_pdf).hexdigest() != (
        workspace.scope.source_sha256.lower()
    ):
        raise WallCreateConflict("wall_create_original_source_mismatch")
    key = _scope(principal, workspace)
    command_hash = sha256(_as_json(dict(command_identity)).encode()).hexdigest()
    package = calculate_new_wall_construction_package(
        wall, assembly, known_service_routes=routes
    )
    canonical_id = "vr-wall:" + sha256(
        _as_json([*key, wall.proposal_id]).encode()
    ).hexdigest()[:32]
    # Rely on SQLite write lock AND CAS; independent readers never see
    # a partial wall/head/PDF, even when the PDF writer fails midway.
    db.execute("BEGIN IMMEDIATE")
    try:
        previous = db.execute("""
            SELECT revision_id, command_sha256, canonical_wall_id,
                   revision_number, updated_model_revision, pdf_sha256,
                   related_pages_json
              FROM vr_created_wall_revisions
             WHERE tenant_id=? AND workspace_id=? AND document_id=?
               AND source_sha256=? AND snapshot_id=? AND idempotency_key=?
        """, (*key, idempotency_key)).fetchone()
        if previous:
            if previous[1] != command_hash:
                raise WallCreateConflict("wall_create_idempotency_key_reused")
            result = {
                "revisionId": previous[0], "canonicalWallId": previous[2],
                "revisionNumber": previous[3], "modelRevision": previous[4],
                "pdfSha256": previous[5],
                "pagesRevised": json.loads(previous[6]),
                "persisted": True, "workingDesignOnly": True,
                "commercialPublicationAllowed": False,
                "idempotentReplay": True,
            }
            db.commit()
            return result
        duplicate = db.execute("""
            SELECT 1 FROM vr_created_wall_revisions
             WHERE tenant_id=? AND workspace_id=? AND document_id=?
               AND source_sha256=? AND snapshot_id=? AND proposal_id=?
        """, (*key, wall.proposal_id)).fetchone()
        if duplicate:
            raise WallCreateConflict("wall_create_proposal_already_exists")
        _check_existing_created_wall_clashes(db, key, wall)
        head = db.execute("""
            SELECT revision_number, model_revision, revision_id, updated_pdf_sha256
              FROM vr_created_wall_heads
             WHERE tenant_id=? AND workspace_id=? AND document_id=?
               AND source_sha256=? AND snapshot_id=?
        """, key).fetchone()
        if head:
            last_number, current_revision, last_id, last_pdf_sha = head
            if current_revision != wall.base_model_revision:
                raise WallCreateConflict("wall_create_stale_model_revision")
            prior = db.execute("""
                SELECT pdf_blob FROM vr_created_wall_revisions
                 WHERE revision_id=? AND tenant_id=? AND workspace_id=?
                   AND document_id=? AND source_sha256=? AND snapshot_id=?
            """, (last_id, *key)).fetchone()
            if prior is None or sha256(prior[0]).hexdigest() != last_pdf_sha:
                raise WallCreateConflict("wall_create_previous_pdf_corrupt")
            parent = bytes(prior[0])
            number = last_number + 1
        else:
            # A host must pass a model revision reflecting ALL separate edits;
            # this first wall branch cannot silently override revised PDFs.
            number, parent = 1, original_pdf
        if number > 999999:
            raise WallCreateConflict("wall_create_revision_limit")
        new_pdf, pages = _new_pdf(parent, coverage, number, wall)
        digest = sha256(new_pdf).hexdigest()
        rev_id = sha256(_as_json([*key, canonical_id, number, command_hash,
                                  digest]).encode()).hexdigest()[:40]
        from dataclasses import asdict
        db.execute("""
            INSERT INTO vr_created_wall_revisions (
              revision_id,tenant_id,workspace_id,document_id,source_sha256,
              snapshot_id,revision_number,base_model_revision,
              updated_model_revision,proposal_id,idempotency_key,command_sha256,
              actor_id,canonical_wall_id,wall_json,assembly_json,package_json,
              related_pages_json,pdf_sha256,pdf_blob
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (rev_id, *key, number, wall.base_model_revision,
              wall.base_model_revision + 1, wall.proposal_id, idempotency_key,
              command_hash, principal.subject_id, canonical_id,
              _as_json(asdict(wall)), _as_json(asdict(assembly)),
              _as_json(package.to_dict()), _as_json(pages), digest, new_pdf))
        db.execute("""
            INSERT INTO vr_created_wall_heads (
              tenant_id,workspace_id,document_id,source_sha256,snapshot_id,
              revision_number,model_revision,revision_id,updated_pdf_sha256
            ) VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(tenant_id,workspace_id,document_id,source_sha256,snapshot_id)
            DO UPDATE SET revision_number=excluded.revision_number,
                          model_revision=excluded.model_revision,
                          revision_id=excluded.revision_id,
                          updated_pdf_sha256=excluded.updated_pdf_sha256
        """, (*key, number, wall.base_model_revision + 1, rev_id, digest))
        db.commit()
        return {
            "revisionId": rev_id, "revisionNumber": number,
            "canonicalWallId": canonical_id,
            "modelRevision": wall.base_model_revision + 1,
            "pdfSha256": digest, "pagesRevised": list(pages),
            "persisted": True, "workingDesignOnly": True,
            "commercialPublicationAllowed": False,
            "idempotentReplay": False,
        }
    except Exception:
        db.rollback()
        raise


def list_created_walls(db: sqlite3.Connection, principal: EditorPrincipal,
                       workspace: AuthorizedSceneWorkspace) -> list[dict]:
    """Trusted working-model hydration: never add these to original wall truth."""
    if workspace.tenant_id != principal.tenant_id or (
        workspace.scope.workspace_id not in principal.allowed_workspace_ids
    ):
        raise PermissionError("wall_list_denied")
    rows = db.execute("""
        SELECT canonical_wall_id,wall_json,revision_id,updated_model_revision
          FROM vr_created_wall_revisions
         WHERE tenant_id=? AND workspace_id=? AND document_id=?
           AND source_sha256=? AND snapshot_id=? ORDER BY revision_number
    """, _scope(principal, workspace)).fetchall()
    return [{
        "canonicalWallId": r[0], "wall": json.loads(r[1]),
        "revisionId": r[2], "modelRevision": r[3],
        "workingDesignOnly": True,
    } for r in rows]


def get_created_wall_pdf(db: sqlite3.Connection, principal: EditorPrincipal,
                         workspace: AuthorizedSceneWorkspace, revision_id: str) -> bytes:
    if type(revision_id) is not str or re.fullmatch("[0-9a-f]{40}", revision_id) is None:
        raise ValueError("invalid_wall_revision_id")
    if workspace.tenant_id != principal.tenant_id or (
        workspace.scope.workspace_id not in principal.allowed_workspace_ids
    ):
        raise PermissionError("wall_revision_read_denied")
    row = db.execute("""
        SELECT pdf_blob,pdf_sha256 FROM vr_created_wall_revisions
         WHERE revision_id=? AND tenant_id=? AND workspace_id=?
           AND document_id=? AND source_sha256=? AND snapshot_id=?
    """, (revision_id, *_scope(principal, workspace))).fetchone()
    if row is None or sha256(row[0]).hexdigest() != row[1]:
        raise WallCreateConflict("wall_revision_not_found_or_corrupt")
    return bytes(row[0])


def attach_created_walls_to_scene(scene: dict, records: list[dict]) -> dict:
    """Render persisted working walls as REVIEW geometry, never source objects.

    The optional authenticated manifest loader must fetch records using
    list_created_walls() for the exact same principal/workspace. The model
    revision in the workspace scope must already include all wall events.
    """
    if type(scene) is not dict or type(records) is not list or len(records) > 10000:
        raise ValueError("created_wall_manifest_invalid")
    if scene.get("schemaVersion") != "1.0.0" or scene.get("readOnly") is not True or (
        scene.get("commercialQuantityPublicationAllowed") is not False
    ):
        raise ValueError("created_wall_manifest_authority_invalid")
    scope = scene.get("scope")
    objects = scene.get("objects")
    if not isinstance(scope, dict) or not isinstance(objects, list):
        raise ValueError("created_wall_manifest_scope_invalid")
    existing = {obj["objectId"] for obj in objects}
    additions = []
    for entry in records:
        if type(entry) is not dict or entry.get("workingDesignOnly") is not True:
            raise ValueError("created_wall_record_untrusted")
        cid = entry.get("canonicalWallId")
        wall = entry.get("wall")
        model_rev = entry.get("modelRevision")
        revision_id = entry.get("revisionId")
        if (type(cid) is not str or re.fullmatch(r"vr-wall:[0-9a-f]{32}", cid) is None or
            type(revision_id) is not str or re.fullmatch("[0-9a-f]{40}", revision_id) is None or
            type(model_rev) is not int or model_rev > scope.get("modelRevision", -1) or
            type(wall) is not dict):
            raise ValueError("created_wall_record_revision_invalid")
        if (wall.get("workspace_id") != scope.get("workspaceId") or
            wall.get("snapshot_id") != scope.get("snapshotId") or
            wall.get("source_sha256", "").lower() != scope.get("sourceSha256", "").lower()):
            raise ValueError("created_wall_record_source_scope_invalid")
        start, end, h = wall.get("start_pt"), wall.get("end_pt"), wall.get("height_m")
        level = wall.get("level_id")
        if (not isinstance(start, list) or not isinstance(end, list) or
            len(start) != 2 or len(end) != 2 or
            any(type(v) not in (float, int) or not math.isfinite(v) for v in start+end) or
            type(h) not in (float, int) or not math.isfinite(h) or h <= 0 or
            type(level) is not str or not level):
            raise ValueError("created_wall_geometry_invalid")
        length = math.dist(start, end)
        if not 0.05 <= length <= 200:
            raise ValueError("created_wall_geometry_length_invalid")
        if cid in existing:
            raise ValueError("created_wall_duplicate_canonical_id")
        existing.add(cid)
        additions.append({
            "objectId": cid, "canonicalObjectId": cid,
            "objectType": "wall", "levelId": level,
            "objectRevision": revision_id,
            "authority": "provisional", "renderState": "review",
            "geometry": {"kind": "wallFace", "start": start,
                         "end": end, "heightM": h},
            "dimensions": {"lengthM": length, "heightM": h},
            "source": {"sourceFileId": None, "page": None, "sheet": None,
                       "sourceRegion": None, "originalGeometryRef": None,
                       "currentGeometryRef": "working-design:" + revision_id},
            "quantityLinks": [], "unresolvedIssues": [
                "user_authored_working_design_not_original_source",
                "structural_and_services_approval_required",
            ], "canEdit": False,
        })
    result = dict(scene)
    result["objects"] = sorted([*objects, *additions], key=lambda r: r["objectId"])
    if len(result["objects"]) > 20000:
        raise ValueError("created_wall_manifest_render_cap")
    return result
