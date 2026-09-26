"""Repeatable profile of PlanReader's production data path (SQLite work per operation).

Composes the real production app (``pb_planreader_v133_app``, the Docker entry
point) against a throwaway ``PLANREADER_DATA_DIR``, loads a real document, and
measures the database work of the operations an estimator performs:

    OPEN WORKSPACE, OPEN TAKEOFF, REPROCESS DOCUMENT, AUTO GEOMETRY PUBLICATION,
    TAKEOFF REVIEW, OPEN 3D MODEL, ...

Every SQLite statement is counted through a ``sqlite3.Connection`` subclass
installed with ``sqlite3.connect(factory=...)`` (pandas still sees a real
sqlite3 connection). Per operation it reports wall time, statements, time spent
in SQLite, rows read (fetched), rows written (DML rowcount) and connections
opened; per normalised statement it reports calls, time, rows, the
workspace_settings key when there is one, and ``EXPLAIN QUERY PLAN`` for the
hottest statements.

Pages run in Streamlit bare mode: widgets return their defaults, which is one
rerun of the page with no interaction.

    python scripts/profile_data_path.py --pdf benchmarks/sources/lamu-ishakani-ecd-classrooms-boq.pdf \
        --background 200 --json out.json

This is a measurement tool only. It never touches the production database.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sqlite3
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

REPO = Path(__file__).resolve().parents[1]
_DML = ("INSERT", "UPDATE", "DELETE", "REPLACE")


def normalise_sql(sql: str) -> str:
    text = " ".join(str(sql).split())
    text = re.sub(r"\(\s*\?(\s*,\s*\?)+\s*\)", "(?…)", text)
    text = re.sub(r"'[^']*'", "'…'", text)
    text = re.sub(r"\b\d+(\.\d+)?\b", "N", text)
    return text


class Recorder:
    """Statement statistics grouped by operation label."""

    def __init__(self) -> None:
        self.operation = "(setup)"
        self.ops: Dict[str, Dict[str, Any]] = {}
        self.statements: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.setting_keys: Dict[Tuple[str, str], int] = defaultdict(int)

    def _op(self) -> Dict[str, Any]:
        return self.ops.setdefault(self.operation, {"statements": 0, "db_seconds": 0.0, "rows_read": 0,
                                                    "rows_written": 0, "connections": 0, "wall_seconds": 0.0})

    def connection_opened(self) -> None:
        self._op()["connections"] += 1

    def statement(self, sql: str, params: Any, seconds: float, rows_written: int) -> Tuple[str, str]:
        key = (self.operation, normalise_sql(sql))
        entry = self.statements.setdefault(key, {"calls": 0, "seconds": 0.0, "rows_read": 0, "rows_written": 0,
                                                 "sql": " ".join(str(sql).split()), "params": params})
        entry["calls"] += 1
        entry["seconds"] += seconds
        entry["rows_written"] += max(0, rows_written)
        op = self._op()
        op["statements"] += 1
        op["db_seconds"] += seconds
        op["rows_written"] += max(0, rows_written)
        if "workspace_settings" in key[1] and isinstance(params, (tuple, list)):
            setting = next((p for p in params if isinstance(p, str)), None)
            if setting:
                self.setting_keys[(self.operation, setting)] += 1
        return key

    def fetched(self, key: Optional[Tuple[str, str]], rows: int, seconds: float) -> None:
        if key is None:
            return
        entry = self.statements.get(key)
        if entry is not None:
            entry["rows_read"] += rows
            entry["seconds"] += seconds
        op = self.ops.get(key[0])
        if op is not None:
            op["rows_read"] += rows
            op["db_seconds"] += seconds

    @contextlib.contextmanager
    def measure(self, operation: str) -> Iterator[None]:
        previous, self.operation = self.operation, operation
        self._op()
        started = time.perf_counter()
        try:
            yield
        finally:
            self.ops[operation]["wall_seconds"] += time.perf_counter() - started
            self.operation = previous


RECORDER = Recorder()


class CountingCursor(sqlite3.Cursor):
    _key: Optional[Tuple[str, str]] = None

    def execute(self, sql, parameters=(), /):
        started = time.perf_counter()
        result = super().execute(sql, parameters)
        written = self.rowcount if str(sql).lstrip().upper().startswith(_DML) else 0
        self._key = RECORDER.statement(sql, parameters, time.perf_counter() - started, written)
        return result

    def executemany(self, sql, seq_of_parameters, /):
        rows = list(seq_of_parameters)
        started = time.perf_counter()
        result = super().executemany(sql, rows)
        self._key = RECORDER.statement(sql, rows[0] if rows else (), time.perf_counter() - started, self.rowcount)
        return result

    def executescript(self, sql_script, /):
        started = time.perf_counter()
        result = super().executescript(sql_script)
        self._key = RECORDER.statement("SCRIPT " + str(sql_script)[:80], (), time.perf_counter() - started, 0)
        return result

    def fetchone(self):
        started = time.perf_counter()
        row = super().fetchone()
        RECORDER.fetched(self._key, 0 if row is None else 1, time.perf_counter() - started)
        return row

    def fetchmany(self, size=None):
        started = time.perf_counter()
        rows = super().fetchmany(size) if size is not None else super().fetchmany()
        RECORDER.fetched(self._key, len(rows), time.perf_counter() - started)
        return rows

    def fetchall(self):
        started = time.perf_counter()
        rows = super().fetchall()
        RECORDER.fetched(self._key, len(rows), time.perf_counter() - started)
        return rows

    def __next__(self):
        started = time.perf_counter()
        row = super().__next__()
        RECORDER.fetched(self._key, 1, time.perf_counter() - started)
        return row


class CountingConnection(sqlite3.Connection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        RECORDER.connection_opened()

    def cursor(self, factory=CountingCursor):
        return super().cursor(factory)

    # Connection.execute* build their cursor in C without calling cursor(); route them through it.
    def execute(self, sql, parameters=(), /):
        return self.cursor().execute(sql, parameters)

    def executemany(self, sql, parameters, /):
        return self.cursor().executemany(sql, parameters)

    def executescript(self, sql_script, /):
        return self.cursor().executescript(sql_script)


def install() -> None:
    original = sqlite3.connect

    def connect(*args, **kwargs):
        kwargs.setdefault("factory", CountingConnection)
        return original(*args, **kwargs)

    sqlite3.connect = connect


# ---------------------------------------------------------------------------
# Workload
# ---------------------------------------------------------------------------


def seed_background(app: Any, count: int) -> None:
    """Other jobs in the same database, as a production database accumulates them."""
    conn = sqlite3.connect(str(app.DB_PATH), factory=sqlite3.Connection)
    try:
        for n in range(count):
            cur = conn.execute("INSERT INTO workspaces(job_no,job_name,created_at,updated_at) VALUES(?,?,?,?)",
                               (f"BG-{n}", f"Background job {n}", "2026-01-01", "2026-01-01"))
            ws = cur.lastrowid
            doc = conn.execute("INSERT INTO documents(workspace_id,file_name,path,page_count,uploaded_at) VALUES(?,?,?,?,?)",
                               (ws, f"bg{n}.pdf", f"bg{n}.pdf", 20, "2026-01-01")).lastrowid
            conn.executemany("INSERT INTO pages(document_id,workspace_id,page_no,page_label,page_type,selected,px_per_m) VALUES(?,?,?,?,?,?,?)",
                             [(doc, ws, p, f"A{p:03d}", "Floor Plan" if p % 3 else "Elevation", 1, 50.0) for p in range(1, 21)])
            conn.executemany(
                """INSERT INTO takeoff_rows(workspace_id,section,element,location,substrate,quantity,unit,quantity_status,
                       source_reference,row_role,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                [(ws, "Internal", "Walls", f"Room {r}", "Plasterboard", 12.5, "m²", "Measured",
                  f"PB Auto Geometry v1.2.19 · unit:Room {r}" if r % 2 else "Estimator manual entry", "", "x", "x")
                 for r in range(60)])
            conn.executemany("INSERT INTO workspace_settings(workspace_id,key,value,updated_at) VALUES(?,?,?,?)",
                             [(ws, key, "{}", "x") for key in ("auto_geometry_v1219", "3d_surface_editor_v1212",
                                                                "material_schedule_v1222", "autopilot_v1223")])
            conn.execute("INSERT INTO model_masses(workspace_id,label,level_name,width,depth,height,source_reference,confidence,created_at) "
                         "VALUES(?,?,?,?,?,?,?,?,?)", (ws, "Envelope", "Ground", 20, 12, 6, "PB Auto Geometry v1.2.19 · envelope", "Derived", "x"))
        conn.commit()
    finally:
        conn.close()


def run(pdfs: Sequence[str], background: int, operations: Sequence[str], session: bool = False) -> Dict[str, Any]:
    os.environ.setdefault("PLANREADER_DATA_DIR", tempfile.mkdtemp(prefix="pr_profile_"))
    os.environ.setdefault("STREAMLIT_LOGGER_LEVEL", "error")  # bare-mode widget warnings
    sys.path.insert(0, str(REPO))
    os.chdir(REPO)
    install()
    import pb_planreader_v133_app as entry  # noqa: E402  (production composition)

    app = entry.app
    with RECORDER.measure("(startup init)"):
        app.init_local_db()
    seed_background(app, background)

    workspace_id = app.create_standalone_workspace("PB-PROFILE", "Data path profile", "b", "")
    workspace = app.lquery("SELECT * FROM workspaces WHERE id=?", (workspace_id,))[0]
    documents: List[int] = []
    for pdf in pdfs:
        path = (REPO / pdf) if not Path(pdf).is_absolute() else Path(pdf)
        documents.append(app.lexecute(
            "INSERT INTO documents(workspace_id,file_name,mime_type,path,page_count,extracted_text,uploaded_at) VALUES(?,?,?,?,?,?,?)",
            (workspace_id, path.name, "application/pdf", str(path), 0, "", app.now_stamp())))

    steps = {
        "UPLOAD: INDEX DOCUMENT": lambda: [app.index_document_pages(d) for d in documents],
        "UPLOAD: PROCESS DOCUMENT": lambda: [app.process_document(d, force=False) for d in documents],
        "AUTOPILOT (first run)": lambda: app.run_planreader_autopilot(workspace_id, force=True),
        "OPEN WORKSPACE (dashboard)": lambda: app.dashboard_page(workspace),
        "OPEN JOB & DOCUMENTS": lambda: app.project_documents_page(workspace, None, {"email": "profile@example.com"}),
        "OPEN TAKEOFF": lambda: app.subscription_takeoff_page(workspace, "", "OpenAI"),
        "TAKEOFF REVIEW QUERY": lambda: app.dataframe_for_takeoff(workspace_id),
        "OPEN REVIEW & QA": lambda: __import__("pb_commercial_review_v161").render_commercial_review_workspace(app, workspace),
        "OPEN PLAN MAPPER": lambda: app.plan_mapper_page(workspace),
        "OPEN 3D MODEL": lambda: app.model_3d_page(workspace, "", "OpenAI"),
        "AUTO GEOMETRY PUBLICATION": lambda: app.run_auto_geometry(workspace_id),
        "REPROCESS DOCUMENT": lambda: [app.process_document(d, force=True) for d in documents],
    }
    errors: Dict[str, str] = {}
    for name, step in steps.items():
        if operations and name not in operations:
            continue
        # --session runs each operation as main() runs a rerun: inside app.db_session().
        scope = app.db_session() if session and hasattr(app, "db_session") else contextlib.nullcontext()
        with RECORDER.measure(name):
            try:
                with scope:
                    step()
            except BaseException as exc:  # a page may stop on st.rerun/st.stop in bare mode
                errors[name] = f"{type(exc).__name__}: {str(exc)[:200]}"

    volume = {table: app.lquery(f"SELECT COUNT(*) AS n FROM {table} WHERE workspace_id=?", (workspace_id,))[0]["n"]
              for table in ("documents", "pages", "takeoff_rows", "model_masses", "model_openings",
                            "measurement_lines", "workspace_settings", "register_items", "mapped_zones")}
    return {"operations": RECORDER.ops, "errors": errors, "volume": volume,
            "statements": _statement_report(app), "settings": _settings_report()}


def _statement_report(app: Any, top: int = 10_000) -> List[Dict[str, Any]]:
    rows = []
    for (operation, sql_key), entry in RECORDER.statements.items():
        rows.append({"operation": operation, "sql": sql_key, "calls": entry["calls"],
                     "ms": round(entry["seconds"] * 1000, 2), "rows_read": entry["rows_read"],
                     "rows_written": entry["rows_written"], "_raw": entry["sql"], "_params": entry["params"]})
    rows.sort(key=lambda r: (-r["ms"], -r["calls"]))
    plan_conn = sqlite3.connect(str(app.DB_PATH), factory=sqlite3.Connection)
    try:
        for row in rows[:top]:
            raw, params = row.pop("_raw"), row.pop("_params")
            if raw.upper().startswith(("SELECT", "UPDATE", "DELETE", "WITH")):
                try:
                    plan = plan_conn.execute("EXPLAIN QUERY PLAN " + raw, params if isinstance(params, (tuple, list, dict)) else ()).fetchall()
                    row["plan"] = [str(step[-1]) for step in plan]
                except sqlite3.Error as exc:
                    row["plan"] = [f"(plan unavailable: {exc})"]
        for row in rows[top:]:
            row.pop("_raw", None)
            row.pop("_params", None)
    finally:
        plan_conn.close()
    return rows


def _settings_report() -> List[Dict[str, Any]]:
    out = [{"operation": op, "key": key, "queries": n} for (op, key), n in RECORDER.setting_keys.items()]
    return sorted(out, key=lambda r: -r["queries"])


def print_report(result: Dict[str, Any]) -> None:
    print(f"{'OPERATION':32s} {'TIME s':>8s} {'DB QUERIES':>10s} {'DB s':>7s} {'ROWS READ':>10s} {'ROWS WRITTEN':>12s} {'CONNS':>6s}")
    for name, op in result["operations"].items():
        print(f"{name:32s} {op['wall_seconds']:8.2f} {op['statements']:10d} {op['db_seconds']:7.2f} "
              f"{op['rows_read']:10d} {op['rows_written']:12d} {op['connections']:6d}")
    if result["errors"]:
        print("errors:", json.dumps(result["errors"], indent=1))
    print("volume (profiled workspace):", result["volume"])
    print("\nHOTTEST STATEMENTS")
    for row in result["statements"][:25]:
        plan = " | ".join(row.get("plan", []))
        print(f"{row['ms']:9.1f} ms {row['calls']:6d}x rr={row['rows_read']:7d} rw={row['rows_written']:6d} "
              f"[{row['operation']}] {row['sql'][:150]}" + (f"\n{'':16s}plan: {plan}" if plan else ""))
    scans: Dict[str, Dict[str, Any]] = {}
    for row in result["statements"]:
        for step in row.get("plan", []):
            if step.startswith("SCAN ") and "USING" not in step:
                entry = scans.setdefault(row["sql"], {"calls": 0, "ms": 0.0, "rows_read": 0, "step": step, "ops": set()})
                entry["calls"] += row["calls"]
                entry["ms"] += row["ms"]
                entry["rows_read"] += row["rows_read"]
                entry["ops"].add(row["operation"])
    print("\nFULL-TABLE SCANS (all operations)")
    for sql, entry in sorted(scans.items(), key=lambda kv: -kv[1]["ms"]):
        print(f"{entry['ms']:9.1f} ms {entry['calls']:6d}x {entry['step']:28s} {sql[:130]}  ops={sorted(entry['ops'])[:3]}")
    print("\nWORKSPACE SETTING LOOKUPS (per operation, top 20)")
    for row in result["settings"][:20]:
        print(f"{row['queries']:6d}x [{row['operation']}] {row['key']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--pdf", action="append", default=[], help="document(s) to load (repeatable)")
    parser.add_argument("--background", type=int, default=200, help="other workspaces in the database")
    parser.add_argument("--operation", action="append", default=[], help="only these operations (repeatable)")
    parser.add_argument("--json", help="write the full result here")
    parser.add_argument("--session", action="store_true", help="run each operation inside app.db_session(), as main() does")
    args = parser.parse_args()
    result = run(args.pdf or ["benchmarks/sources/lamu-ishakani-ecd-classrooms-boq.pdf"], args.background, args.operation,
                 session=args.session)
    print_report(result)
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
