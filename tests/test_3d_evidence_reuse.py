"""3D evidence reuse must be invisible except for speed.

Opening the 3D model collected workspace evidence by building the registered
walls three times (steps 4, 5 and 7 of ``collect_workspace_3d_evidence``), and
every build re-extracted room faces from the same unchanged PDF pages. Now:

- ``collect_workspace_3d_evidence`` builds the walls once per collection and
  hands every step the same walls, or the same error;
- ``extract_room_faces_from_page`` caches results keyed by the PDF library,
  the file's identity (path, device, inode, size, mtime) and every page field
  the extraction reads, and returns deep copies.

These tests prove a cached result equals a fresh extraction, that any change
to an input is a miss, that callers cannot corrupt the cache, that a
collection never reuses walls from an earlier collection, and that failures
are reported at the same steps as before.
"""
from __future__ import annotations

import copy
import os
import sqlite3
from pathlib import Path

import fitz
import pytest

import pb_room_face_takeoff as room_faces
import pb_roof_envelope_v140 as roof_v140
import pb_unified_building_v139 as unified_v139
from pb_production_3d_adapter_legacy import (
    collect_workspace_3d_evidence,
    registered_wall_to_canonical_input,
)


# ---------------------------------------------------------------------------
# Room-face extraction cache
# ---------------------------------------------------------------------------

TWO_ROOMS = [(100, 100, 300, 250, "KITCHEN"), (300, 100, 450, 250, "BEDROOM")]
ONE_ROOM = [(120, 120, 420, 320, "LOUNGE")]
THREE_ROOMS = TWO_ROOMS + [(100, 250, 450, 400, "DINING")]
DOCUMENT_ID = 7
PAGE = {
    "id": 11, "document_id": DOCUMENT_ID, "page_no": 1, "page_label": "A-101",
    "px_per_m": 28.346, "render_zoom": 1.0, "scale_text": "1:100",
}


def _plan_pdf(path: Path, pages) -> Path:
    """Write a vector plan: one list of labelled rectangular rooms per page."""
    doc = fitz.open()
    for rooms in pages:
        page = doc.new_page(width=842, height=595)
        shape = page.new_shape()
        for x0, y0, x1, y1, _label in rooms:
            corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            for index, start in enumerate(corners):
                # One path per wall, so PyMuPDF reports plain line items.
                shape.draw_line(fitz.Point(*start), fitz.Point(*corners[(index + 1) % 4]))
                shape.finish(color=(0, 0, 0), width=0.5)
        shape.commit()
        for x0, y0, x1, y1, label in rooms:
            page.insert_text(((x0 + x1) / 2 - 20, (y0 + y1) / 2), label, fontsize=9, fontname="helv")
    doc.save(str(path))
    doc.close()
    return path


class _CountingFitz:
    """The fitz module, counting how often a PDF is opened."""

    def __init__(self):
        self.opens = 0

    def open(self, *args, **kwargs):
        self.opens += 1
        return fitz.open(*args, **kwargs)


class _PdfApp:
    def __init__(self, pdf_path: Path, pdf_library):
        self.fitz = pdf_library
        self.pdf_path = pdf_path

    def lquery(self, sql, params=()):
        assert sql == "SELECT path FROM documents WHERE id=?"
        return [{"path": str(self.pdf_path)}] if params == (DOCUMENT_ID,) else []


def _clear_room_face_cache():
    with room_faces._ROOM_FACE_CACHE_LOCK:
        room_faces._ROOM_FACE_CACHE.clear()


@pytest.fixture(autouse=True)
def _isolated_room_face_cache():
    _clear_room_face_cache()
    yield
    _clear_room_face_cache()


@pytest.fixture
def plan(tmp_path):
    pdf = _plan_pdf(tmp_path / "plan.pdf", [TWO_ROOMS, ONE_ROOM, []])
    library = _CountingFitz()
    return _PdfApp(pdf, library), library


def _fresh(app, page):
    _clear_room_face_cache()
    return room_faces.extract_room_faces_from_page(app, page)


def test_cached_rooms_equal_a_fresh_extraction(plan):
    app, library = plan
    first = room_faces.extract_room_faces_from_page(app, PAGE)
    second = room_faces.extract_room_faces_from_page(app, PAGE)

    assert library.opens == 1, "an unchanged page must not reopen the PDF"
    assert sorted(room.label for room in first) == ["BEDROOM", "KITCHEN"]
    assert all(room.floor_area_m2 for room in first)
    assert second == first
    assert _fresh(app, PAGE) == first


@pytest.mark.parametrize("field, value", [
    ("page_no", 2),
    ("page_label", "A-102"),
    ("px_per_m", 56.692),
    ("render_zoom", 2.0),
    ("scale_text", "1:50"),
])
def test_every_page_input_is_part_of_the_key(plan, field, value):
    app, library = plan
    before = room_faces.extract_room_faces_from_page(app, PAGE)
    changed = dict(PAGE, **{field: value})

    after = room_faces.extract_room_faces_from_page(app, changed)

    assert library.opens == 2, f"changing {field} must re-extract"
    assert after != before
    assert after == _fresh(app, changed)


def test_rewritten_pdf_is_extracted_again_even_with_its_old_mtime(plan):
    app, library = plan
    assert len(room_faces.extract_room_faces_from_page(app, PAGE)) == 2
    old = app.pdf_path.stat()

    _plan_pdf(app.pdf_path, [THREE_ROOMS])
    os.utime(app.pdf_path, ns=(old.st_atime_ns, old.st_mtime_ns))
    rooms = room_faces.extract_room_faces_from_page(app, PAGE)

    assert library.opens == 2
    assert sorted(room.label for room in rooms) == ["BEDROOM", "DINING", "KITCHEN"]


def test_touched_pdf_is_extracted_again(plan):
    app, library = plan
    before = room_faces.extract_room_faces_from_page(app, PAGE)
    stat = app.pdf_path.stat()
    os.utime(app.pdf_path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10**9))

    assert room_faces.extract_room_faces_from_page(app, PAGE) == before
    assert library.opens == 2


def test_each_pdf_library_instance_has_its_own_entries(plan):
    app, library = plan
    room_faces.extract_room_faces_from_page(app, PAGE)
    other = _CountingFitz()

    room_faces.extract_room_faces_from_page(_PdfApp(app.pdf_path, other), PAGE)

    assert (library.opens, other.opens) == (1, 1)


def test_callers_cannot_change_cached_rooms(plan):
    app, _library = plan
    original = copy.deepcopy(room_faces.extract_room_faces_from_page(app, PAGE))

    returned = room_faces.extract_room_faces_from_page(app, PAGE)
    returned[0].label = "CHANGED"
    returned[0].polygon_pdf_pts.append((0.0, 0.0))
    returned[0].evidence.append("caller note")
    returned.clear()

    assert room_faces.extract_room_faces_from_page(app, PAGE) == original


def test_least_recently_used_entry_is_evicted(plan, monkeypatch):
    app, library = plan
    monkeypatch.setattr(room_faces, "_ROOM_FACE_CACHE_SIZE", 2)
    a, b, c = PAGE, dict(PAGE, page_label="B"), dict(PAGE, page_label="C")

    for page in (a, b, a, c):  # a is used again, so b is the oldest when c arrives
        room_faces.extract_room_faces_from_page(app, page)
    assert library.opens == 3

    room_faces.extract_room_faces_from_page(app, a)
    assert library.opens == 3
    room_faces.extract_room_faces_from_page(app, b)
    assert library.opens == 4
    assert len(room_faces._ROOM_FACE_CACHE) == 2


def test_pages_without_a_readable_pdf_return_nothing_and_are_not_cached(plan, tmp_path):
    app, library = plan
    text_file = tmp_path / "plan.txt"
    text_file.write_text("not a drawing")

    assert room_faces.extract_room_faces_from_page(_PdfApp(app.pdf_path, None), PAGE) == []
    assert room_faces.extract_room_faces_from_page(app, dict(PAGE, document_id=0)) == []
    assert room_faces.extract_room_faces_from_page(app, dict(PAGE, document_id=8)) == []
    assert room_faces.extract_room_faces_from_page(_PdfApp(text_file, library), PAGE) == []
    assert room_faces.extract_room_faces_from_page(_PdfApp(tmp_path / "gone.pdf", library), PAGE) == []

    assert library.opens == 0
    assert len(room_faces._ROOM_FACE_CACHE) == 0


def test_malformed_calibration_fails_where_it_did_before(plan):
    app, _library = plan
    malformed = dict(PAGE, px_per_m="not a number")

    # A page with linework reads the calibration and rejects it, every time.
    for _attempt in range(2):
        with pytest.raises(ValueError):
            room_faces.extract_room_faces_from_page(app, malformed)
    # A page without linework never reads the calibration.
    assert room_faces.extract_room_faces_from_page(app, dict(malformed, page_no=3)) == []
    assert len(room_faces._ROOM_FACE_CACHE) == 0


# ---------------------------------------------------------------------------
# One registered-wall build per evidence collection
# ---------------------------------------------------------------------------

WORKSPACE_ID = 301


def _workspace_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE workspaces (id INTEGER PRIMARY KEY, job_no TEXT, job_name TEXT, builder_client TEXT, site_address TEXT)")
    conn.execute("CREATE TABLE documents (id INTEGER PRIMARY KEY, workspace_id INTEGER, file_name TEXT, sha256 TEXT, category TEXT, page_count INTEGER, source_type TEXT)")
    conn.execute("CREATE TABLE pages (id INTEGER PRIMARY KEY, workspace_id INTEGER, document_id INTEGER, page_no INTEGER, page_label TEXT, page_type TEXT, scale_text TEXT, px_per_m REAL, width_px REAL, height_px REAL, render_zoom REAL, selected INTEGER, extracted_text TEXT)")
    conn.execute("INSERT INTO workspaces (id, job_no, job_name) VALUES (?, 'JOB-3D', 'Evidence reuse')", (WORKSPACE_ID,))
    conn.execute("INSERT INTO documents (id, workspace_id, file_name) VALUES (60, ?, 'plans.pdf')", (WORKSPACE_ID,))
    conn.execute(
        "INSERT INTO pages (id, workspace_id, document_id, page_no, page_label, page_type, scale_text, px_per_m, width_px, height_px, render_zoom, selected, extracted_text) "
        "VALUES (4, ?, 60, 1, 'Elevations', 'Elevation', '1:100', 28.346, 1000.0, 700.0, 1.0, 1, 'FLAT ROOF with parapet')",
        (WORKSPACE_ID,),
    )
    conn.commit()
    return conn


class _WallProducerApp:
    """Collector inputs with the real v1.3.9 take-off and v1.4.0 roof producers."""

    def __init__(self, conn, build=None):
        self.conn = conn
        self.height_m = 3.0
        self.builds = 0
        self.returned = []
        self.as_built = []
        self.takeoff_inputs = []
        self.roof_inputs = []
        self._build = build or self._walls

    def lquery(self, sql, params=()):
        cur = self.conn.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def workspace_setting(self, wid, key, default=None):
        return default

    def _walls(self, wid):
        def wall(ref, side, a, b, length):
            gross = round(length * self.height_m, 3)
            return {
                "wall_ref": ref, "side": side, "substrate": "Masonry", "level": "Ground",
                "a": list(a), "b": list(b), "length_m": length, "height_m": self.height_m,
                "height_status": "Registered elevation height", "height_confidence": "Verified",
                "gross_m2": gross, "opening_deduction_m2": 0.0, "net_m2": gross, "openings": [],
                "provenance": {"wall_ref": ref, "page_no": 1},
            }
        return [wall("W-N1", "North", (0.0, 0.0), (10.0, 0.0), 10.0),
                wall("W-E1", "East", (10.0, 0.0), (10.0, 6.0), 6.0)]

    def build_registered_walls_v139(self, wid):
        self.builds += 1
        walls = self._build(wid)
        self.returned.append(walls)
        self.as_built.append(copy.deepcopy(walls))
        return walls

    def registered_wall_takeoff_rows_v139(self, walls):
        self.takeoff_inputs.append(walls)
        return unified_v139.takeoff_rows(walls)

    def build_precision_prisms(self, wid):
        return [{"points": [[0, 0], [10, 0], [10, 6], [0, 6]], "triangles": [[0, 1, 2], [0, 2, 3]], "level_name": "Ground"}]

    def roof_evidence_v140(self, wid):
        return roof_v140.roof_evidence(self, wid)

    def roof_caps_v140(self, wid, walls):
        self.roof_inputs.append(walls)
        return roof_v140.roof_caps(self, wid, walls)


def test_collection_builds_the_walls_once_and_every_step_uses_them():
    app = _WallProducerApp(_workspace_db())

    snapshot = collect_workspace_3d_evidence(app, WORKSPACE_ID)

    assert app.builds == 1
    walls = app.returned[0]
    assert app.takeoff_inputs == [walls] and app.takeoff_inputs[0] is walls
    expected_inputs = [registered_wall_to_canonical_input(w) for w in app._walls(WORKSPACE_ID)]
    assert snapshot["registered_walls"] == expected_inputs
    assert snapshot["takeoff_rows"] == unified_v139.takeoff_rows(app._walls(WORKSPACE_ID))
    assert app.roof_inputs == [expected_inputs]
    assert [cap["z"] for cap in snapshot["roof_data"]["caps"]] == [3.0]
    assert walls == app.as_built[0], "no step may modify the shared walls"
    assert not [d for d in snapshot["diagnostics_log"] if d["type"].startswith(("v139", "v140"))]


def test_each_collection_builds_fresh_walls():
    app = _WallProducerApp(_workspace_db())
    first = collect_workspace_3d_evidence(app, WORKSPACE_ID)

    app.height_m = 3.4
    second = collect_workspace_3d_evidence(app, WORKSPACE_ID)

    assert app.builds == 2
    assert {w["height_m"] for w in first["registered_walls"]} == {3.0}
    assert {w["height_m"] for w in second["registered_walls"]} == {3.4}
    assert [cap["z"] for cap in second["roof_data"]["caps"]] == [3.4]
    assert [row["quantity"] for row in second["takeoff_rows"]] == [34.0, 20.4]


def _wall_diagnostics(snapshot):
    return [(d["type"], d["msg"]) for d in snapshot["diagnostics_log"] if d["type"].startswith(("v139", "v140"))]


def test_a_failed_wall_build_is_reported_by_every_step_that_needs_walls():
    def fail(wid):
        raise RuntimeError("elevation registration failed")

    app = _WallProducerApp(_workspace_db(), build=fail)
    snapshot = collect_workspace_3d_evidence(app, WORKSPACE_ID)

    assert app.builds == 1
    assert _wall_diagnostics(snapshot) == [
        ("v139_wall_error", "elevation registration failed"),
        ("v139_takeoff_error", "elevation registration failed"),
        ("v140_roof_error", "elevation registration failed"),
    ]
    assert snapshot["registered_walls"] == [] and snapshot["takeoff_rows"] == []
    assert snapshot["roof_data"] is None
    assert app.takeoff_inputs == [] and app.roof_inputs == []


def test_a_non_callable_wall_producer_fails_at_the_same_steps_as_before():
    app = _WallProducerApp(_workspace_db())
    app.build_registered_walls_v139 = "not a producer"
    try:
        app.build_registered_walls_v139(WORKSPACE_ID)
    except TypeError as exc:
        message = str(exc)

    snapshot = collect_workspace_3d_evidence(app, WORKSPACE_ID)

    # Step 4 checks callable() and skips; steps 5 and 7 only check hasattr().
    assert _wall_diagnostics(snapshot) == [
        ("v139_takeoff_error", message),
        ("v140_roof_error", message),
    ]
