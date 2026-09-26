"""Review, QA and mapper reads no longer rewrite the whole take-off table (pb_takeoff_accuracy_v125.schema).

schema() runs on every review dataframe, QA check and mapper save. It ran the
full column migration and three full-table UPDATEs that normalise legacy
units and floor rows, then committed. At 60,000 take-off rows that cost
~169 ms per call, and because it wrote, a read path waited for any other
session's write lock: the review dataframe blocked 3.28 s behind a 3-second
write, where a plain read took 5 ms.

Now the structure is migrated once per database file and schema version, and
each call only looks for legacy rows through expression indexes, writing
only when it finds some. Legacy spellings that arrive later (imports, AI
drafts) are still normalised on the next call.
"""
from __future__ import annotations

import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pb_performance_v1215 as perf
import pb_planreader_3d_app as app_mod
import pb_takeoff_accuracy_v125 as accuracy

INSERT = """INSERT INTO takeoff_rows(workspace_id,section,element,location,substrate,quantity,unit,notes,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,'x','x')"""


class SchemaFastPathTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._patch = patch.object(app_mod, "DB_PATH", Path(self._tmp.name) / "planreader.db")
        self._patch.start()
        app_mod.init_local_db()
        perf.prepare_local_database(app_mod)  # WAL, as in production
        self.ws = app_mod.create_standalone_workspace("PB-A", "Accuracy", "b", "")
        accuracy.schema(app_mod)  # startup: the full migration

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def _insert_legacy_rows(self):
        rows = [
            ("Internal", "Walls", "Lounge", "Plasterboard", 42.0, "m2", ""),
            ("Internal", "Ceilings", "Lounge", "Plasterboard", 20.0, " SQM ", ""),
            ("Internal", "Skirting", "Lounge", "Timber", 12.0, "lin m", ""),
            ("Internal", "Cornice", "Lounge", "Timber", 9.0, "M", ""),
            ("Internal", "Floor plan", "Level 1 floor area", "Other", 85.0, "m²", "Auto-detected from A101"),
            ("Internal", "Walls", "Kitchen", "Plasterboard", 18.0, "m²", ""),
        ]
        for row in rows:
            app_mod.lexecute(INSERT, (self.ws, *row))

    def _rows(self):
        return app_mod.lquery("SELECT element,unit,row_role,rate_per_unit FROM takeoff_rows WHERE workspace_id=? ORDER BY id", (self.ws,))

    def test_legacy_rows_written_later_are_still_normalised_exactly_as_before(self):
        self._insert_legacy_rows()
        accuracy.schema(app_mod)  # fast path
        fast = self._rows()
        app_mod.lexecute("DELETE FROM takeoff_rows")
        self._insert_legacy_rows()
        accuracy._migrate(app_mod)  # the previous behaviour: the full migration
        self.assertEqual(fast, self._rows())
        self.assertEqual([r["unit"] for r in fast], ["m²", "m²", "lm", "lm", "m²", "m²"])
        self.assertEqual(fast[4]["element"], "Floor area")
        self.assertEqual(fast[4]["row_role"], "floor_area")

    def test_a_clean_database_is_not_written_so_readers_never_wait_for_writers(self):
        held, release = threading.Event(), threading.Event()

        def writer():
            conn = sqlite3.connect(app_mod.DB_PATH, timeout=10)
            conn.execute("BEGIN IMMEDIATE")  # another session publishing, saving, processing...
            conn.execute("UPDATE workspaces SET job_name=job_name WHERE id=?", (self.ws,))
            held.set()
            release.wait(5)
            conn.commit()
            conn.close()

        thread = threading.Thread(target=writer)
        thread.start()
        held.wait(5)
        try:
            started = time.perf_counter()
            accuracy.schema(app_mod)
            elapsed = time.perf_counter() - started
        finally:
            release.set()
            thread.join()
        self.assertLess(elapsed, 1.0, "a read path must not wait for another session's write lock")

    def test_legacy_checks_search_the_expression_indexes(self):
        conn = sqlite3.connect(app_mod.DB_PATH)
        try:
            for _update, where in accuracy._NORMALISATIONS:
                plan = " | ".join(r[-1] for r in conn.execute(f"EXPLAIN QUERY PLAN SELECT 1 FROM takeoff_rows WHERE {where} LIMIT 1"))
                with self.subTest(where=where[:40]):
                    self.assertIn("SEARCH takeoff_rows USING", plan)
                    self.assertIn("idx_takeoff_", plan)
                    self.assertNotIn("SCAN takeoff_rows", plan)
        finally:
            conn.close()

    def test_a_schema_change_migrates_the_structure_again(self):
        app_mod.lexecute("DROP INDEX idx_takeoff_unit_normalised")  # any schema change bumps schema_version
        accuracy.schema(app_mod)
        names = {r["name"] for r in app_mod.lquery("SELECT name FROM sqlite_master WHERE type='index'")}
        self.assertIn("idx_takeoff_unit_normalised", names)

    def test_apps_without_a_database_path_keep_the_full_migration(self):
        runs = []
        fake = SimpleNamespace(local_connect=app_mod.local_connect, lquery=app_mod.lquery)
        with patch.object(accuracy, "_migrate", side_effect=lambda app: runs.append(app)):
            accuracy.schema(fake)
            accuracy.schema(fake)
        self.assertEqual(len(runs), 2)


if __name__ == "__main__":
    unittest.main()
