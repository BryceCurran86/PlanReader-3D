"""Per-document page lookups use an index (pages(document_id, page_no)).

Processing, rendering and page selection look pages up by document, and the
documents foreign key checks pages on delete. No index led with document_id,
so every such query scanned the whole pages table of every job: at 100,000
page rows ~17-28 ms per query, against ~0.03-0.2 ms with the index.
"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pb_planreader_3d_app as app_mod

# The hot per-document statements, as the profiler captured them.
HOT_QUERIES = (
    "SELECT id FROM pages WHERE document_id=? AND page_no=?",
    "SELECT * FROM pages WHERE document_id=? ORDER BY page_no,id",
    "SELECT id FROM pages WHERE document_id=? AND COALESCE(selected,0)=1",
    "SELECT page_no FROM pages WHERE document_id=? AND COALESCE(selected,0)=1 ORDER BY page_no",
    "SELECT COUNT(*) AS n FROM pages WHERE document_id=?",
    "SELECT id,page_no,page_label,page_type,extracted_text,selected FROM pages WHERE document_id=? ORDER BY page_no,id",
)


class PagesDocumentIndexTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._patch = patch.object(app_mod, "DB_PATH", Path(self._tmp.name) / "planreader.db")
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def _plans(self):
        conn = sqlite3.connect(app_mod.DB_PATH)
        try:
            return {sql: " | ".join(row[-1] for row in conn.execute("EXPLAIN QUERY PLAN " + sql, (1, 2)[:sql.count("?")]).fetchall())
                    for sql in HOT_QUERIES}
        finally:
            conn.close()

    def test_hot_page_queries_search_the_document_index(self):
        app_mod.init_local_db()
        for sql, plan in self._plans().items():
            with self.subTest(sql=sql):
                self.assertIn("USING", plan)
                self.assertIn("idx_pages_document_page", plan)
                self.assertNotIn("SCAN pages", plan)
                self.assertNotIn("TEMP B-TREE", plan)

    def test_existing_databases_gain_the_index_at_startup(self):
        app_mod.init_local_db()
        conn = sqlite3.connect(app_mod.DB_PATH)
        conn.execute("DROP INDEX idx_pages_document_page")  # a database created before this index existed
        conn.commit()
        conn.close()
        self.assertIn("SCAN pages", self._plans()[HOT_QUERIES[0]])
        app_mod.init_local_db()
        self.assertIn("idx_pages_document_page", self._plans()[HOT_QUERIES[0]])

    def test_results_are_unchanged(self):
        app_mod.init_local_db()
        ws = app_mod.create_standalone_workspace("PB", "Pages", "b", "")
        for doc in (1, 2):
            app_mod.lexecute("INSERT INTO documents(id,workspace_id,file_name,path,page_count) VALUES(?,?,'f','p',3)", (doc, ws))
            for page_no in (3, 1, 2):
                app_mod.lexecute("INSERT INTO pages(document_id,workspace_id,page_no,page_label,selected) VALUES(?,?,?,?,?)",
                                 (doc, ws, page_no, f"D{doc}P{page_no}", int(page_no != 2)))
        self.assertEqual([r["page_label"] for r in app_mod.lquery(HOT_QUERIES[1], (2,))], ["D2P1", "D2P2", "D2P3"])
        self.assertEqual([r["page_no"] for r in app_mod.lquery(HOT_QUERIES[3], (1,))], [1, 3])
        self.assertEqual(app_mod.lquery(HOT_QUERIES[4], (1,))[0]["n"], 3)


if __name__ == "__main__":
    unittest.main()
