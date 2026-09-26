"""Saving a workspace setting that already holds the same value must not write.

Read paths re-save derived settings on every rerun. Opening the 3D model saved
elevation_registration_v135 (9x), elevation_profiles_v136, height_evidence_v150
and opening_geometry_v137 (3x each) on every open, all unchanged on a reopen.
Each save was a write transaction: it took SQLite's write lock, waiting up to
the busy timeout behind any other writer, and committed nothing new.
set_workspace_setting now compares with the stored text first.
"""
from __future__ import annotations

import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import pb_planreader_3d_app as app_mod


class UnchangedSettingWriteTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "planreader.db"
        self._patch = patch.object(app_mod, "DB_PATH", self.db)
        self._patch.start()
        app_mod.init_local_db()
        self.ws = app_mod.create_standalone_workspace("PB-S", "Settings", "b", "")
        self.writes = []
        base = app_mod.lexecute

        def recording_lexecute(sql, params=()):
            if "workspace_settings" in sql:
                self.writes.append(tuple(params))
            return base(sql, params)

        self._write_patch = patch.object(app_mod, "lexecute", recording_lexecute)
        self._write_patch.start()

    def tearDown(self):
        self._write_patch.stop()
        self._patch.stop()
        self._tmp.cleanup()

    def _stored(self, key):
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute("SELECT value, updated_at FROM workspace_settings WHERE workspace_id=? AND key=?",
                                (self.ws, key)).fetchone()
        finally:
            conn.close()

    def test_new_and_changed_values_are_written(self):
        app_mod.set_workspace_setting(self.ws, "k", "first")
        app_mod.set_workspace_setting(self.ws, "k", "second")

        self.assertEqual(len(self.writes), 2)
        self.assertEqual(self._stored("k")[0], "second")
        self.assertEqual(app_mod.workspace_setting(self.ws, "k"), "second")

    def test_identical_value_is_not_rewritten(self):
        with patch.object(app_mod, "now_stamp", return_value="2026-09-27T09:00:00"):
            app_mod.set_workspace_setting(self.ws, "k", '{"a": 1}')
        with patch.object(app_mod, "now_stamp", return_value="2026-09-27T10:00:00"):
            app_mod.set_workspace_setting(self.ws, "k", '{"a": 1}')

        self.assertEqual(len(self.writes), 1)
        self.assertEqual(self._stored("k"), ('{"a": 1}', "2026-09-27T09:00:00"))

    def test_values_compare_as_the_text_that_would_be_stored(self):
        app_mod.set_workspace_setting(self.ws, "k", 5)
        app_mod.set_workspace_setting(self.ws, "k", "5")       # same stored text
        app_mod.set_workspace_setting(self.ws, "k", None)      # stored as ""
        app_mod.set_workspace_setting(self.ws, "k", "")        # same stored text
        app_mod.set_workspace_setting(self.ws, "k", 5.0)       # "5.0" is not "5"
        app_mod.set_workspace_setting(self.ws, "other", "5.0")  # another key is its own setting

        self.assertEqual([w[1:3] for w in self.writes], [("k", "5"), ("k", ""), ("k", "5.0"), ("other", "5.0")])
        self.assertEqual(self._stored("k")[0], "5.0")

    def test_a_null_stored_value_is_replaced(self):
        conn = sqlite3.connect(self.db)
        conn.executemany("INSERT INTO workspace_settings(workspace_id,key,value,updated_at) VALUES(?,?,NULL,'x')",
                         [(self.ws, "k"), (self.ws, "text")])
        conn.commit()
        conn.close()

        app_mod.set_workspace_setting(self.ws, "k", None)
        app_mod.set_workspace_setting(self.ws, "text", "None")

        self.assertEqual(len(self.writes), 2)
        self.assertEqual(self._stored("k")[0], "")
        self.assertEqual(self._stored("text")[0], "None")

    def test_settings_are_per_workspace(self):
        other = app_mod.create_standalone_workspace("PB-T", "Other", "b", "")
        app_mod.set_workspace_setting(self.ws, "k", "v")
        app_mod.set_workspace_setting(other, "k", "v")

        self.assertEqual(len(self.writes), 2)
        self.assertEqual(app_mod.workspace_setting(other, "k"), "v")

    def test_identical_save_inside_a_session_is_skipped_and_changes_commit(self):
        with app_mod.db_session():
            app_mod.set_workspace_setting(self.ws, "k", "v")
            app_mod.set_workspace_setting(self.ws, "k", "v")
            app_mod.set_workspace_setting(self.ws, "k", "w")
            self.assertEqual(self._stored("k")[0], "w", "a change is committed immediately")

        self.assertEqual(len(self.writes), 2)

    def test_identical_save_does_not_wait_for_another_writer(self):
        app_mod.set_workspace_setting(self.ws, "k", "v")

        def quick_connect():
            conn = sqlite3.connect(app_mod.DB_PATH, timeout=0.2, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn

        writer = sqlite3.connect(self.db, timeout=0)
        writer.execute("BEGIN IMMEDIATE")  # another session holds the write lock
        try:
            with patch.object(app_mod, "local_connect", quick_connect):
                started = time.perf_counter()
                app_mod.set_workspace_setting(self.ws, "k", "v")
                self.assertLess(time.perf_counter() - started, 0.15)
                with self.assertRaises(sqlite3.OperationalError):  # a real change still needs the lock
                    app_mod.set_workspace_setting(self.ws, "k", "changed")
        finally:
            writer.rollback()
            writer.close()
        self.assertEqual(self._stored("k")[0], "v")


if __name__ == "__main__":
    unittest.main()
