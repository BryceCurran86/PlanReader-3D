"""Local, source-bound user review drafts; never automatic quantity evidence.

The editor uses display-image percentages, not native PDF geometry. A future
consumer must authenticate the image-to-native transform and validate every
correction before rebuilding topology or issuing user-assisted quantities.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import re

# Fixed synthetic editor rows, NOT takeoff row identities.
KINDS = (
    ("external_wall", "Missing / corrected external wall", "#d13c86", "line"),
    ("internal_wall", "Missing / corrected internal wall", "#d13c86", "line"),
    ("swing_door", "Door / frame", "#d97706", "line"),
    ("cavity_slider", "Cavity slider", "#d97706", "line"),
    ("garage_door", "Garage panel door", "#d97706", "line"),
    ("window", "Window", "#2563eb", "line"),
    ("opening", "Other opening", "#d97706", "line"),
    ("boundary", "Room / finish transition", "#a855f7", "line"),
    ("room_outline", "Room outline for review", "#a855f7", "polygon"),
    ("exclusion", "Exclude from measured scope", "#dc2626", "polygon"),
    ("dimension_witness", "Known dimension line", "#0891b2", "line"),
    ("reject_candidate", "Reject an existing wall / opening candidate", "#dc2626", "line"),
)
ISSUES = {
    "exterior": "Check the external footprint (include garage, exclude porch / alfresco where applicable)",
    "wall_gaps": "Check unresolved wall endpoints and connections",
    "openings": "Check door, window, slider and frame ownership",
    "rooms": "Check room closure and finish transitions",
    "scale": "Confirm drawing scale / known figured dimension",
    "height": "Confirm wall, ceiling and opening heights from source",
    "finishes": "Confirm floor, wall and ceiling finish assignments",
    "exclusions": "Confirm exclusions and unmeasured areas",
}
DECISIONS = ("needs_information", "correction_recorded", "reviewed_no_change")
_SHA = re.compile(r"[0-9a-f]{64}")
_ID = re.compile(r"[A-Za-z0-9_-]{1,96}")


@dataclass(frozen=True)
class ReviewScope:
    workspace_id: int
    page_id: int
    pdf_page: int
    source_sha256: str
    image_sha256: str

    def __post_init__(self):
        for value in (self.workspace_id, self.page_id, self.pdf_page):
            if type(value) is not int or value <= 0:
                raise ValueError("Invalid review page identity")
        for value in (self.source_sha256, self.image_sha256):
            if type(value) is not str or not _SHA.fullmatch(value):
                raise ValueError("Review requires exact source and image SHA-256")

    @property
    def key(self):
        return hashlib.sha256(json.dumps([
            self.workspace_id, self.page_id, self.pdf_page,
            self.source_sha256, self.image_sha256,
        ]).encode("ascii")).hexdigest()


def editor_rows():
    return [
        {"id": i, "label": label, "colour": colour, "unit": "review",
         "quantity": 0, "group": "User corrections"}
        for i, (_, label, colour, _) in enumerate(KINDS, 1)
    ]


def review_issues(report, *, scale_verified=False):
    """Questions, not an automatic completeness score or claim of missing ink."""
    report = report if isinstance(report, dict) else {}
    result = []
    network = report.get("exterior_source_wall_network") or {}
    gaps = report.get("unresolved_wall_gap_count")
    tips = network.get("source_endpoint_near_miss_total")
    if report.get("exterior_physical_wall_authenticated") is not True:
        result.append(("exterior", "Exterior ownership not authenticated in preview"))
    if type(gaps) is int and gaps > 0:
        result.append(("wall_gaps", f"{gaps} unresolved topology gaps"))
    elif type(tips) is int and tips > 0:
        result.append(("wall_gaps", f"{tips} endpoint near-miss candidates; not necessarily missing walls"))
    else:
        result.append(("wall_gaps", "Inspect wall connections; preview is not a completeness proof"))
    result.append(("openings", "Opening candidates are not authenticated installed openings"))
    result.append(("rooms", "Candidate regions are not verified finished room faces"))
    if not scale_verified:
        result.append(("scale", "Page calibration not marked verified"))
    result.extend([
        ("height", "Heights are not verified by the topology preview"),
        ("finishes", "Material assignments are not verified by the topology preview"),
        ("exclusions", "Review external areas and material exclusions"),
    ])
    return result


def _point(raw):
    if not isinstance(raw, (tuple, list)) or len(raw) != 2:
        raise ValueError("Correction needs a two-coordinate point")
    result = []
    for v in raw:
        if type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 100:
            raise ValueError("Correction lies outside the displayed plan")
        result.append(float(v))
    return result


def normalise_editor_shapes(shapes):
    if not isinstance(shapes, list) or len(shapes) > 500:
        raise ValueError("Expected at most 500 correction shapes")
    out, seen = [], set()
    for raw in shapes:
        if not isinstance(raw, dict):
            raise ValueError("Invalid correction")
        identity = raw.get("id")
        row = raw.get("takeoff_row_id")
        if type(identity) is not str or not _ID.fullmatch(identity) or identity in seen:
            raise ValueError("Invalid or repeated correction identity")
        if type(row) is not int or not 1 <= row <= len(KINDS):
            raise ValueError("Select a valid correction category")
        category, _, _, kind = KINDS[row - 1]
        if raw.get("kind") != kind:
            raise ValueError("Use Line for walls/openings/dimensions and Outline for rooms/exclusions")
        if kind == "line":
            points = [_point([raw.get("x1"), raw.get("y1")]),
                      _point([raw.get("x2"), raw.get("y2")])]
            if points[0] == points[1]:
                raise ValueError("Correction line needs two distinct points")
        else:
            values = raw.get("points")
            if not isinstance(values, list) or not 3 <= len(values) <= 128:
                raise ValueError("Outline needs 3–128 corners")
            points = [_point(p) for p in values]
            if points[0] == points[-1]:
                points.pop()
            if len(points) < 3 or len({tuple(p) for p in points}) != len(points):
                raise ValueError("Outline contains repeated corners")
            from shapely.geometry import Polygon
            ring = Polygon(points)
            if not ring.is_valid or ring.area <= 0:
                raise ValueError("Outline must be a simple nonzero polygon")
        seen.add(identity)
        # Discard every client-derived quantity, note, authority and colour.
        out.append({"id": identity, "category": category, "kind": kind, "points": points})
    return out


def editor_shapes(shapes):
    by_category = {item[0]: (i, item) for i, item in enumerate(KINDS, 1)}
    out = []
    for shape in shapes:
        row, (_, label, colour, kind) = by_category[shape["category"]]
        points = shape["points"]
        out.append({
            "id": shape["id"], "takeoff_row_id": row, "kind": kind,
            "label": label, "colour": colour, "unit": "review",
            "x1": points[0][0], "y1": points[0][1],
            "x2": points[1][0], "y2": points[1][1],
            "points": points if kind == "polygon" else [],
            "quantity_status": "User correction – not measured",
        })
    return out


def normalise_answer(issue, decision, note, dimension_mm=None):
    if issue not in ISSUES or decision not in DECISIONS:
        raise ValueError("Unknown review question or decision")
    if not isinstance(note, str) or not note.strip() or len(note) > 2000:
        raise ValueError("Enter a source reference or explanation (up to 2000 characters)")
    if dimension_mm is not None:
        if (issue not in {"scale", "height", "openings"} or
                type(dimension_mm) not in (float, int) or
                not math.isfinite(dimension_mm) or dimension_mm <= 0 or
                dimension_mm > 1_000_000):
            raise ValueError("Enter a positive relevant dimension in mm")
    return {"decision": decision, "note": note.strip(), "dimension_mm": dimension_mm}


def _ensure(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS guided_plan_review_drafts (
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        page_id INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
        scope_key TEXT PRIMARY KEY,
        pdf_page INTEGER NOT NULL,
        source_sha256 TEXT NOT NULL,
        image_sha256 TEXT NOT NULL,
        revision INTEGER NOT NULL,
        payload_json TEXT NOT NULL
    )""")


def _check_scope(conn, scope):
    found = conn.execute(
        """SELECT p.page_no, d.sha256 FROM pages p JOIN documents d
           ON p.document_id=d.id AND p.workspace_id=d.workspace_id
           WHERE p.id=? AND p.workspace_id=?""",
        (scope.page_id, scope.workspace_id),
    ).fetchone()
    if found is None or found[0] != scope.pdf_page or str(found[1] or "").lower() != scope.source_sha256:
        raise ValueError("Drawing registration changed; reload the original before editing")


def load_review(connect, scope):
    conn = connect()
    try:
        _ensure(conn)
        _check_scope(conn, scope)
        row = conn.execute(
            "SELECT revision,payload_json FROM guided_plan_review_drafts WHERE scope_key=?",
            (scope.key,),
        ).fetchone()
        if row is None:
            return {"revision": 0, "shapes": [], "answers": {}}
        payload = json.loads(row[1])
        shapes = normalise_editor_shapes(editor_shapes(payload["shapes"]))
        answers = {issue: normalise_answer(issue, **answer)
                   for issue, answer in payload["answers"].items()}
        return {"revision": row[0], "shapes": shapes, "answers": answers}
    finally:
        conn.close()


def save_review(connect, scope, *, expected_revision, shapes, answers):
    """Explicit local save with optimistic locking; never modifies takeoff rows."""
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValueError("Invalid review revision")
    clean_shapes = normalise_editor_shapes(shapes)
    if not isinstance(answers, dict):
        raise ValueError("Invalid review answers")
    clean_answers = {issue: normalise_answer(issue, **answer)
                     for issue, answer in answers.items()}
    payload = json.dumps({
        "coordinate_frame": "displayed_image_percent",
        "authority": "user_review_draft",
        "automatic_source_verified": False,
        "commercial_projection_allowed": False,
        "frozen_benchmark_allowed": False,
        "shapes": clean_shapes,
        "answers": clean_answers,
    }, sort_keys=True, allow_nan=False)
    conn = connect()
    try:
        _ensure(conn)
        conn.execute("BEGIN IMMEDIATE")
        _check_scope(conn, scope)
        row = conn.execute(
            "SELECT revision FROM guided_plan_review_drafts WHERE scope_key=?",
            (scope.key,),
        ).fetchone()
        if (0 if row is None else row[0]) != expected_revision:
            raise ValueError("Review changed in another session; reload before saving")
        revision = expected_revision + 1
        conn.execute("""INSERT INTO guided_plan_review_drafts
            (workspace_id,page_id,scope_key,pdf_page,source_sha256,image_sha256,revision,payload_json)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(scope_key) DO UPDATE SET revision=excluded.revision,
            payload_json=excluded.payload_json""",
            (scope.workspace_id,scope.page_id,scope.key,scope.pdf_page,
             scope.source_sha256,scope.image_sha256,revision,payload))
        conn.commit()
        return revision
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
