"""The take-off source summary must not re-read the same data for every row.

``review_panel`` builds a "Source page(s) / Source geometry" summary for every
take-off row on each rerun of the take-off page. Each row used to reload and
re-parse the whole provenance map (a JSON setting that grows with the job),
re-run the same page queries and re-parse the same Takeoff Studio state. One
render now shares a ``_SummaryLookups``: the map is loaded once and each
distinct page or Studio lookup runs once, through the same ``_page`` query, so
duplicate labels, NULL labels, unselected pages and the ``page_id=0``
fallback behave exactly as before.

These tests prove the shared lookups give every row the same summary and
provenance as the per-row path, that loads no longer grow with the number of
rows, and that nothing is reused between renders.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

import pb_selected_evidence_floor_v1226 as selected
import pb_takeoff_review_v1226 as review

WORKSPACE_ID = 1
PROVENANCE_KEY = selected.PROVENANCE_SETTING_KEY
STUDIO = "PB Takeoff Studio v1.2.11"
SQUARE_PX = [[100, 100], [300, 100], [300, 300], [100, 300]]

PAGES = [
    # id, workspace, label, type, width, height, px_per_m, selected
    (1, 1, "A101", "Floor Plan", 1000, 1000, 50, 1),
    (2, 1, "A101", "Floor Plan", 2000, 2000, 50, 1),   # duplicate label: the lower id wins
    (3, 1, "A102", "Floor Plan", 1000, 1000, 50, 0),   # not selected
    (4, 1, None, "Floor Plan", 1000, 1000, 50, 1),     # NULL label never matches ""
    (5, 1, "", "Elevation", 1000, 1000, 50, 1),        # empty label: matches "" and page_id 0
    (6, 1, "A103", "Section", 0, 0, 0, 1),             # no size: pixel polygons do not convert
    (7, 2, "A101", "Floor Plan", 1000, 1000, 50, 1),   # another workspace
]

PROVENANCE = {
    "prov-area": {"kind": "area", "unit": "m²", "sources": [
        {"page_id": 1, "page_label": "A101", "source_kind": "Unit schedule", "polygon": SQUARE_PX}]},
    "prov-box": {"kind": "area", "unit": "m²", "sources": [
        {"page_id": 2, "page_label": "A101", "source_kind": "Unit schedule", "text_bbox": [1, 2, 3, 4]}]},
    "prov-page0": {"kind": "reference", "unit": "", "sources": [
        {"page_id": 0, "page_label": "", "source_kind": "Drawing reference", "points": []}]},
    "prov-multi": {"kind": "area", "unit": "m²", "sources": [
        {"page_id": 1, "page_label": "A101", "polygon": SQUARE_PX},
        {"page_id": 6, "page_label": "A103", "polygon": SQUARE_PX},
        {"page_id": 7, "page_label": "A101", "polygon": SQUARE_PX}]},
}

STUDIO_STATE = {"areas": [{"id": "a1", "notes": "Lounge", "points": [
    {"x": 10, "y": 10}, {"x": 40, "y": 10}, {"x": 40, "y": 30}]}]}

ROWS = [
    # unit, source_page, source_reference
    ("lm", "A101", "prov-area"),   # first row: the panel shows it, and it is not m²
    ("m²", "A101", "prov-box"),
    ("m²", "", "prov-page0"),
    ("m²", "A101", "prov-multi"),
    ("m²", "A101", f"{STUDIO} · page:1 · area:a1"),
    ("m²", "A101", f"{STUDIO} · page:1 · area:a2"),
    ("m²", "A101", f"{STUDIO} · page:99 · area:a1"),
    ("m²", "A101", f"{STUDIO} · page:1 · area:a1"),
    ("m²", "A102", "Mapper · zone:1"),
    ("lm", "A101", "Mapper · measurement:1"),
    ("m²", "A101", "plain-1"),
    ("m²", "A102", "plain-2"),
    ("m²", "", "plain-3"),
    ("m²", "MISSING", "plain-4"),
    ("item", None, ""),
    ("m²", "A101", "plain-5"),
]


class _App:
    """Real SQLite, with every query and setting read recorded."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.settings = {}
        self.queries = []
        self.setting_reads = []

    def lquery(self, sql, params=()):
        self.queries.append((" ".join(sql.split()), tuple(params)))
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            return [dict(row) for row in conn.execute(sql, tuple(params)).fetchall()]
        finally:
            conn.close()

    def workspace_setting(self, workspace_id, key, default=""):
        self.setting_reads.append(str(key))
        return self.settings.get((int(workspace_id), str(key)), default)

    def set_workspace_setting(self, workspace_id, key, value):
        self.settings[(int(workspace_id), str(key))] = value

    def page_queries(self):
        return [q for q in self.queries if q[0].startswith("SELECT id,page_label,page_type,image_path")]


@pytest.fixture
def app(tmp_path):
    db = tmp_path / "review.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE pages(id INTEGER PRIMARY KEY, workspace_id INTEGER, page_label TEXT, page_type TEXT,
            image_path TEXT, width_px REAL, height_px REAL, px_per_m REAL, selected INTEGER);
        CREATE TABLE takeoff_rows(id INTEGER PRIMARY KEY AUTOINCREMENT, workspace_id INTEGER, section TEXT,
            element TEXT, location TEXT, quantity REAL, unit TEXT, source_page TEXT, source_reference TEXT,
            confidence TEXT);
        CREATE TABLE mapped_zones(id INTEGER PRIMARY KEY, workspace_id INTEGER, page_id INTEGER, name TEXT,
            polygon_json TEXT, x_px REAL, y_px REAL, w_px REAL, h_px REAL, source_reference TEXT);
        CREATE TABLE measurement_lines(id INTEGER PRIMARY KEY, workspace_id INTEGER, page_id INTEGER,
            points TEXT, label TEXT, notes TEXT);
        """
    )
    conn.executemany(
        "INSERT INTO pages VALUES(?,?,?,?,'',?,?,?,?)", PAGES,
    )
    conn.execute("INSERT INTO mapped_zones VALUES(1,1,3,'Hall',?,0,0,0,0,'Mapper · zone:1')",
                 (json.dumps([[100, 100], [400, 100], [400, 300]]),))
    conn.execute("INSERT INTO measurement_lines VALUES(1,1,1,?,'Skirting','')",
                 (json.dumps([[10, 10], [50, 10], [50, 40]]),))
    for index, (unit, page, ref) in enumerate(ROWS, 1):
        conn.execute(
            "INSERT INTO takeoff_rows(workspace_id,section,element,location,quantity,unit,source_page,source_reference,confidence) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (WORKSPACE_ID, "Internal", "Floor", f"Room {index}", float(index), unit, page, ref, "Measured"),
        )
    conn.execute(
        "INSERT INTO takeoff_rows(workspace_id,section,element,location,quantity,unit,source_page,source_reference,confidence) "
        "VALUES(2,'Internal','Floor','Elsewhere',1.0,'m²','A101','prov-area','Measured')"
    )
    conn.commit()
    conn.close()
    app = _App(db)
    app.set_workspace_setting(WORKSPACE_ID, PROVENANCE_KEY, json.dumps(PROVENANCE))
    app.set_workspace_setting(WORKSPACE_ID, "takeoff_studio_v1211_page_1", json.dumps(STUDIO_STATE))
    return app


def _rows(app):
    return app.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=? ORDER BY id", (WORKSPACE_ID,))


def test_shared_lookups_give_every_row_its_per_row_summary(app):
    rows = _rows(app)
    expected = [(review.provenance_for_row(app, WORKSPACE_ID, row), review.source_summary(app, WORKSPACE_ID, row))
                for row in rows]

    lookups = review._SummaryLookups(app, WORKSPACE_ID)
    shared = [(review.provenance_for_row(app, WORKSPACE_ID, row, lookups=lookups),
               review.source_summary(app, WORKSPACE_ID, row, lookups=lookups))
              for row in rows]

    assert shared == expected


def test_page_lookups_keep_the_query_semantics(app):
    lookups = review._SummaryLookups(app, WORKSPACE_ID)

    assert lookups.page(page_label="A101")["id"] == 1        # first selected page with the label
    assert lookups.page(page_label="A102") is None            # not selected
    assert lookups.page(page_label="")["id"] == 5             # the NULL label does not match
    assert lookups.page(page_id=0)["id"] == 5                 # page_id 0 falls back to the label ""
    assert lookups.page(page_id=3)["id"] == 3                 # by id, selected or not
    assert lookups.page(page_id=7) is None                    # another workspace's page
    for kwargs in ({"page_label": "A101"}, {"page_label": ""}, {"page_id": 3}, {"page_id": 7}, {"page_id": 0}):
        assert lookups.page(**kwargs) == review._page(app, WORKSPACE_ID, **kwargs)


def test_callers_cannot_change_a_shared_page(app):
    lookups = review._SummaryLookups(app, WORKSPACE_ID)
    page = lookups.page(page_id=1)
    page["page_label"] = "CHANGED"
    page["width_px"] = 0

    assert lookups.page(page_id=1) == review._page(app, WORKSPACE_ID, page_id=1)


def _summary_pass(app, shared=False):
    rows = _rows(app)
    app.queries.clear()
    app.setting_reads.clear()
    lookups = review._SummaryLookups(app, WORKSPACE_ID) if shared else None
    for row in rows:
        review.source_summary(app, WORKSPACE_ID, row, lookups=lookups)


def test_one_summary_pass_loads_each_input_once(app):
    rows = len(_rows(app))
    _summary_pass(app)
    per_row = (app.setting_reads.count(PROVENANCE_KEY), len(app.page_queries()))

    _summary_pass(app, shared=True)

    assert per_row[0] == rows
    assert app.setting_reads.count(PROVENANCE_KEY) == 1
    assert app.setting_reads.count("takeoff_studio_v1211_page_1") == 1
    assert len(app.page_queries()) == len(set(app.page_queries())), "each distinct page lookup runs once"
    assert len(app.page_queries()) < per_row[1]


def test_page_queries_do_not_grow_with_rows(app):
    _summary_pass(app, shared=True)
    before = (len(app.page_queries()), app.setting_reads.count(PROVENANCE_KEY))

    conn = sqlite3.connect(app.db_path)
    conn.executemany(
        "INSERT INTO takeoff_rows(workspace_id,section,element,location,quantity,unit,source_page,source_reference,confidence) "
        "VALUES(1,'Internal','Floor','More',1.0,'m²',?,?,'Measured')",
        [(page, f"extra-{i}") for i, page in enumerate(["A101", "A102", "", "MISSING"] * 25)],
    )
    conn.commit()
    conn.close()
    _summary_pass(app, shared=True)

    assert (len(app.page_queries()), app.setting_reads.count(PROVENANCE_KEY)) == before


def test_each_render_reads_current_data(app):
    rows = _rows(app)
    first = review._SummaryLookups(app, WORKSPACE_ID)
    assert review.source_summary(app, WORKSPACE_ID, rows[10], lookups=first) == ("A101", "page")

    app.set_workspace_setting(WORKSPACE_ID, PROVENANCE_KEY, json.dumps(dict(PROVENANCE, **{"plain-1": {
        "sources": [{"page_id": 1, "page_label": "A101", "polygon": SQUARE_PX}]}})))
    conn = sqlite3.connect(app.db_path)
    conn.execute("UPDATE pages SET page_label='A101-rev' WHERE id=1")
    conn.commit()
    conn.close()

    second = review._SummaryLookups(app, WORKSPACE_ID)
    assert review.source_summary(app, WORKSPACE_ID, rows[10], lookups=second) == ("A101", "polygon")
    assert second.page(page_label="A101")["id"] == 2
    assert review.source_summary(app, WORKSPACE_ID, rows[15], lookups=second) == \
        review.source_summary(app, WORKSPACE_ID, rows[15])


def _render(app):
    st = MagicMock()
    st.selectbox.side_effect = lambda label, options, **kwargs: options[0]
    st.multiselect.return_value = []
    st.button.return_value = False
    app.st, app.pd = st, pd
    app.queries.clear()
    app.setting_reads.clear()
    review.review_panel(app, {"id": WORKSPACE_ID})
    return st


def test_review_panel_shows_the_per_row_summary(app):
    rows = _rows(app)
    expected = []
    for row in rows:
        pages, geometry = review.source_summary(app, WORKSPACE_ID, row)
        expected.append({"ID": int(row["id"]), "Element": row.get("element"), "Location": row.get("location"),
                         "Qty": row.get("quantity"), "Unit": row.get("unit"),
                         "Source page(s)": pages, "Source geometry": geometry})

    st = _render(app)

    table = st.dataframe.call_args_list[0].args[0]
    assert table.to_dict("records") == expected


def test_review_panel_loads_do_not_grow_with_rows(app):
    _render(app)
    before = (app.setting_reads.count(PROVENANCE_KEY), len(app.page_queries()))

    conn = sqlite3.connect(app.db_path)
    conn.executemany(
        "INSERT INTO takeoff_rows(workspace_id,section,element,location,quantity,unit,source_page,source_reference,confidence) "
        "VALUES(1,'Internal','Floor','More',1.0,'m²','A101',?,'Measured')",
        [(f"extra-{i}",) for i in range(200)],
    )
    conn.commit()
    conn.close()
    _render(app)

    assert (app.setting_reads.count(PROVENANCE_KEY), len(app.page_queries())) == before


def test_review_panel_shows_changes_made_between_renders(app):
    _render(app)
    app.set_workspace_setting(WORKSPACE_ID, PROVENANCE_KEY, json.dumps(dict(PROVENANCE, **{"plain-1": {
        "sources": [{"page_id": 6, "page_label": "A103", "points": [{"x": 1, "y": 1}, {"x": 9, "y": 1}, {"x": 9, "y": 9}]}]}})))
    conn = sqlite3.connect(app.db_path)
    conn.execute("UPDATE pages SET selected=0 WHERE id=1")
    conn.commit()
    conn.close()

    st = _render(app)

    table = {row["ID"]: row for row in st.dataframe.call_args_list[0].args[0].to_dict("records")}
    for row in _rows(app):
        assert (table[row["id"]]["Source page(s)"], table[row["id"]]["Source geometry"]) == \
            review.source_summary(app, WORKSPACE_ID, row)
    assert (table[11]["Source page(s)"], table[11]["Source geometry"]) == ("A103", "polygon")
