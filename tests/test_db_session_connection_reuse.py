"""One SQLite connection per rerun for the query helpers (pb_planreader_3d_app.db_session).

lquery/ldf/lexecute/lexecutemany opened a new connection for every call. A new
connection costs ~1.3-2.8 ms before its first statement returns (WAL mapping and
schema load), a warm query ~0.004 ms, and one rerun makes hundreds of helper
calls (processing one 45-page document opened 1,327 connections). Inside
db_session the helpers share one connection; nothing else about them changes.
"""
from __future__ import annotations

import ast
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import pb_planreader_3d_app as app_mod

REPO = Path(__file__).resolve().parents[1]


class DbSessionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "planreader.db"
        self._patch = patch.object(app_mod, "DB_PATH", self.db)
        self._patch.start()
        app_mod.init_local_db()
        self.ws = app_mod.create_standalone_workspace("PB-S", "Session", "b", "")
        self.opened = 0
        base = app_mod.local_connect

        def counting_connect():
            self.opened += 1
            return base()

        self._connect_patch = patch.object(app_mod, "local_connect", counting_connect)
        self._connect_patch.start()

    def tearDown(self):
        self._connect_patch.stop()
        self._patch.stop()
        self._tmp.cleanup()

    def _other(self):
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        return conn

    def _work(self):
        app_mod.set_workspace_setting(self.ws, "k", "v")
        app_mod.lexecutemany("INSERT INTO register_items(workspace_id,register_name,title,created_at) VALUES(?,?,?,?)",
                             [(self.ws, "clarifications", f"Item {n}", "x") for n in range(3)])
        row_id = app_mod.lexecute("INSERT INTO takeoff_rows(workspace_id,section,element,location,quantity,unit,created_at,updated_at) "
                                  "VALUES(?,'Internal','Walls','Lounge',42.0,'m²','x','x')", (self.ws,))
        return (
            app_mod.workspace_setting(self.ws, "k"),
            app_mod.lquery("SELECT title FROM register_items WHERE workspace_id=? ORDER BY id", (self.ws,)),
            app_mod.ldf("SELECT id,location,quantity FROM takeoff_rows WHERE workspace_id=?", (self.ws,)).to_dict("records"),
            row_id,
        )

    def test_helpers_share_one_connection_and_return_the_same_results(self):
        outside = self._work()
        opened_outside = self.opened
        app_mod.lexecute("DELETE FROM register_items")
        app_mod.lexecute("DELETE FROM takeoff_rows")
        self.opened = 0
        with app_mod.db_session():
            inside = self._work()
        self.assertEqual(self.opened, 1)
        self.assertGreaterEqual(opened_outside, 6, "outside a session every call opens its own connection")
        self.assertEqual(inside[:2], outside[:2])
        self.assertEqual([{k: v for k, v in r.items() if k != "id"} for r in inside[2]],
                         [{k: v for k, v in r.items() if k != "id"} for r in outside[2]])

    def test_every_write_commits_immediately(self):
        with app_mod.db_session():
            app_mod.lexecute("INSERT INTO workspace_settings(workspace_id,key,value,updated_at) VALUES(?,?,?,?)", (self.ws, "a", "1", "x"))
            other = self._other()
            try:
                seen = other.execute("SELECT value FROM workspace_settings WHERE workspace_id=? AND key='a'", (self.ws,)).fetchall()
                other.execute("INSERT INTO workspace_settings(workspace_id,key,value,updated_at) VALUES(?,?,?,?)", (self.ws, "b", "2", "x"))
                other.commit()
            finally:
                other.close()
            self.assertEqual([tuple(r) for r in seen], [("1",)])
            # ...and reads see what other connections committed meanwhile.
            self.assertEqual(app_mod.workspace_setting(self.ws, "b"), "2")

    def test_a_failed_write_leaves_no_transaction_open(self):
        with app_mod.db_session():
            with self.assertRaises(sqlite3.IntegrityError):
                app_mod.lexecute("INSERT INTO takeoff_rows(workspace_id,section) VALUES(NULL,'x')")  # workspace_id NOT NULL
            other = self._other()
            try:
                other.execute("PRAGMA busy_timeout=0")
                other.execute("INSERT INTO workspace_settings(workspace_id,key,value,updated_at) VALUES(?,?,?,?)", (self.ws, "c", "3", "x"))
                other.commit()  # would raise "database is locked" if the session kept a write transaction
            finally:
                other.close()
            # The session connection keeps working (an UPDATE reports no new rowid, as before).
            self.assertEqual(app_mod.lexecute("UPDATE workspaces SET job_name='Renamed' WHERE id=?", (self.ws,)), 0)
        self.assertEqual(app_mod.lquery("SELECT job_name FROM workspaces WHERE id=?", (self.ws,))[0]["job_name"], "Renamed")

    def test_session_is_closed_on_exit_and_on_interruption(self):
        class Rerun(BaseException):
            """Like Streamlit's RerunException."""

        with self.assertRaises(Rerun):
            with app_mod.db_session():
                with app_mod.db_session():  # nested: shares the outer connection
                    app_mod.lquery("SELECT 1")
                raise Rerun()
        self.assertIsNone(getattr(app_mod._DB_SESSION, "conn", None))
        self.assertEqual(self.opened, 1)
        app_mod.lquery("SELECT 1")
        self.assertEqual(self.opened, 2, "outside the session helpers open their own connections again")

    def test_other_threads_never_use_the_session_connection(self):
        seen = {}
        with app_mod.db_session():
            session_conn = app_mod._DB_SESSION.conn

            def worker():
                conn, owned = app_mod._helper_connection()
                seen["same"], seen["owned"] = conn is session_conn, owned
                conn.close()

            thread = threading.Thread(target=worker)
            thread.start()
            thread.join()
        self.assertEqual(seen, {"same": False, "owned": True})

    def test_a_different_database_gets_its_own_connection(self):
        other_db = Path(self._tmp.name) / "other.db"
        with app_mod.db_session():
            app_mod.lquery("SELECT 1")
            with patch.object(app_mod, "DB_PATH", other_db):
                app_mod.lquery("SELECT 1")
                self.assertTrue(other_db.exists())
        self.assertEqual(self.opened, 2)

    def test_each_rerun_runs_inside_a_session(self):
        tree = ast.parse((REPO / "pb_planreader_3d_app.py").read_text(encoding="utf-8-sig"))
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
        withs = [n for n in ast.walk(main) if isinstance(n, ast.With)]
        self.assertTrue(any(isinstance(item.context_expr, ast.Call) and getattr(item.context_expr.func, "id", "") == "db_session"
                            for w in withs for item in w.items))
        seen = {}
        with patch.object(app_mod, "_main_rerun", lambda: seen.setdefault("conn", app_mod._DB_SESSION.conn)):
            app_mod.main()
        self.assertIsNotNone(seen["conn"])
        self.assertIsNone(getattr(app_mod._DB_SESSION, "conn", None))


if __name__ == "__main__":
    unittest.main()
