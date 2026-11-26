"""Source-neutral review tests: draft data cannot enter automatic measurements."""
import json
import sqlite3
from dataclasses import replace
import pytest

from pb_guided_plan_review import (
    ReviewScope, editor_shapes, load_review, normalise_answer,
    normalise_editor_shapes, review_issues, save_review,
)


def _scope():
    return ReviewScope(1, 11, 2, "a" * 64, "b" * 64)


def _line(**overrides):
    return dict(id="shape1", takeoff_row_id=1, kind="line",
                x1=10, y1=20, x2=30, y2=40, **overrides)


def _db(tmp_path):
    path = tmp_path / "review.db"
    def connect():
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE workspaces(id INTEGER PRIMARY KEY);
        CREATE TABLE documents(id INTEGER PRIMARY KEY, workspace_id INTEGER, sha256 TEXT);
        CREATE TABLE pages(id INTEGER PRIMARY KEY, document_id INTEGER, workspace_id INTEGER, page_no INTEGER);
        CREATE TABLE takeoff_rows(id INTEGER PRIMARY KEY, quantity REAL);
        INSERT INTO workspaces VALUES (1), (2);
        INSERT INTO pages VALUES (11, 101, 1, 2), (12, 102, 2, 2);
        INSERT INTO takeoff_rows VALUES (1, 55.0);
        """)
        conn.executemany("INSERT INTO documents VALUES (?,?,?)",
                         [(101, 1, "a" * 64), (102, 2, "a" * 64)])
    return connect


def test_review_roundtrip_strips_client_authority_and_keeps_takeoff(tmp_path):
    connect = _db(tmp_path)
    scope = _scope()
    assert load_review(connect, scope)["revision"] == 0
    shapes = [_line(area_m2=9999, quantity_status="FIRM",
                    automatic_source_verified=True)]
    answers = {"height": normalise_answer("height", "correction_recorded",
                                         "Ceiling schedule", 2700)}
    assert save_review(connect, scope, expected_revision=0, shapes=shapes, answers=answers) == 1
    saved = load_review(connect, scope)
    assert saved["shapes"] == [{
        "id": "shape1", "category": "external_wall", "kind": "line",
        "points": [[10.0, 20.0], [30.0, 40.0]],
    }]
    assert saved["answers"] == answers
    assert editor_shapes(saved["shapes"])[0]["quantity_status"] == "User correction – not measured"
    with connect() as conn:
        payload = json.loads(conn.execute("SELECT payload_json FROM guided_plan_review_drafts").fetchone()[0])
        assert payload["automatic_source_verified"] is False
        assert payload["commercial_projection_allowed"] is False
        assert payload["frozen_benchmark_allowed"] is False
        assert conn.execute("SELECT quantity FROM takeoff_rows").fetchone()[0] == 55.0


def test_revision_and_image_isolation(tmp_path):
    connect = _db(tmp_path)
    scope = _scope()
    save_review(connect, scope, expected_revision=0, shapes=[_line()], answers={})
    assert load_review(connect, replace(scope, image_sha256="c"*64))["shapes"] == []
    with pytest.raises(ValueError, match="another session"):
        save_review(connect, scope, expected_revision=0, shapes=[], answers={})
    with pytest.raises(ValueError, match="registration changed"):
        load_review(connect, replace(scope, workspace_id=2))
    with connect() as conn:
        conn.execute("UPDATE documents SET sha256=? WHERE id=101", ("d"*64,))
    with pytest.raises(ValueError, match="registration changed"):
        load_review(connect, scope)


@pytest.mark.parametrize("changes", [
    {"x1": float("nan")}, {"x1": -1}, {"y2": 101},
    {"takeoff_row_id": True}, {"takeoff_row_id": 999},
    {"x2": 10, "y2": 20}, {"kind": "polygon"},
])
def test_invalid_geometry_cannot_be_saved(changes):
    shape = _line()
    shape.update(changes)
    with pytest.raises(ValueError):
        normalise_editor_shapes([shape])


def test_outline_rejects_crossed_geometry():
    shape = {"id": "room1", "takeoff_row_id": 9, "kind": "polygon",
             "points": [[10,10], [40,40], [10,40], [40,10]]}
    with pytest.raises(ValueError, match="simple"):
        normalise_editor_shapes([shape])
    shape["points"] = [[10,10], [40,10], [40,40], [10,40]]
    assert normalise_editor_shapes([shape])[0]["category"] == "room_outline"


def test_preview_questions_never_claim_completion():
    issues = dict(review_issues({"unresolved_wall_gap_count": 3}, scale_verified=False))
    assert "3 unresolved topology gaps" == issues["wall_gaps"]
    assert {"exterior", "openings", "rooms", "scale", "height", "finishes", "exclusions"} <= issues.keys()
    assert "scale" not in dict(review_issues({}, scale_verified=True))


@pytest.mark.parametrize("value", [0, -1, float("inf"), True])
def test_invalid_dimension_rejected(value):
    with pytest.raises(ValueError):
        normalise_answer("height", "correction_recorded", "Source note", value)


def test_original_plan_mapper_mounts_guided_review_first():
    import ast
    from pathlib import Path
    tree = ast.parse((Path(__file__).resolve().parents[1] / "pb_planreader_3d_app.py").read_text(encoding="utf-8"))
    mapper = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "plan_mapper_page")
    calls = [n for n in ast.walk(mapper) if isinstance(n, ast.Call)]
    tabs = [n for n in calls if isinstance(n.func, ast.Attribute) and n.func.attr == "tabs"]
    assert any(isinstance(n.args[0], ast.List) and
               isinstance(n.args[0].elts[0], ast.Constant) and
               n.args[0].elts[0].value == "Guided plan review" for n in tabs if n.args)
    assert any(isinstance(n.func, ast.Name) and n.func.id == "render_guided_plan_review" for n in calls)
    assert any(isinstance(n.func, ast.Name) and n.func.id == "source_native_trace_preview" for n in calls)
