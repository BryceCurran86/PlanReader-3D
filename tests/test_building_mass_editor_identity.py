"""The Building masses editor keeps mass identity (pb_planreader_3d_app.save_building_masses).

Saving the 3D Building Model page's mass editor deleted every mass in the
workspace and re-inserted the rows, so one width correction gave every mass a
new AUTOINCREMENT id: the estimator's openings were detached
(model_openings.mass_id ON DELETE SET NULL) and 3D surface edits and
editable-3D corrections keyed by the id were orphaned. The rows were also
written under separate commits.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pb_planreader_3d_app as app

INSERT_MASS = """INSERT INTO model_masses(workspace_id,label,level_name,x,y,z,width,depth,height,finish,source_reference,confidence,notes,created_at)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
# The columns the page loads into st.data_editor.
EDITOR_COLUMNS = "id,label,level_name,x,y,z,width,depth,height,finish,source_reference,confidence,notes"


class _Masses:
    """Two estimator masses with an opening each, plus another workspace's mass."""

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._patch = patch.object(app, "DB_PATH", Path(self._tmp.name) / "planreader.db")
        self._patch.start()
        app.init_local_db()
        self.ws = app.create_standalone_workspace("PB-M", "Masses", "b", "")
        other = app.create_standalone_workspace("PB-O", "Other", "b", "")
        self.a = app.lexecute(INSERT_MASS, (self.ws, "Block A", "Ground", 0, 0, 0, 10, 8, 3, "", "Site", "Measured", "", "x"))
        self.b = app.lexecute(INSERT_MASS, (self.ws, "Block B", "Ground", 12, 0, 0, 6, 8, 3, "", "Site", "Measured", "", "x"))
        self.foreign = app.lexecute(INSERT_MASS, (other, "Other job", "Ground", 0, 0, 0, 5, 5, 3, "", "", "Derived", "", "x"))
        self.door = self._add_opening(self.a)
        self.window = self._add_opening(self.b)
        return self

    def __exit__(self, *exc):
        self._patch.stop()
        self._tmp.cleanup()

    def _add_opening(self, mass_id):
        # The page's "Add opening" statement.
        return app.lexecute(
            """INSERT INTO model_openings(workspace_id,mass_id,label,opening_type,face,offset_x,offset_z,width,height,count,notes,source_reference,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (self.ws, mass_id, f"Opening on {mass_id}", "Door", "Front", 1, 0, .9, 2.1, 1, "", "Site", "x"),
        )

    def editor_frame(self):
        return app.ldf(f"SELECT {EDITOR_COLUMNS} FROM model_masses WHERE workspace_id=? ORDER BY id", (self.ws,))

    def masses(self):
        return {r["label"]: r for r in app.lquery("SELECT * FROM model_masses WHERE workspace_id=? ORDER BY id", (self.ws,))}

    def openings(self):
        return {r["id"]: r["mass_id"] for r in app.lquery("SELECT id,mass_id FROM model_openings WHERE workspace_id=?", (self.ws,))}


def _streamlit_saving(edited_frame):
    """A Streamlit stub on which the estimator edited the grid and pressed Save building masses."""
    st = MagicMock()
    st.session_state = {}
    st.tabs.side_effect = lambda labels: [MagicMock() for _ in labels]
    st.columns.side_effect = lambda spec, *args, **kwargs: [MagicMock() for _ in range(spec if isinstance(spec, int) else len(spec))]
    st.data_editor.return_value = edited_frame
    st.button.side_effect = lambda label, *args, **kwargs: label == "Save building masses"
    st.form_submit_button.return_value = False
    return st


class BuildingMassEditorPageTests(unittest.TestCase):
    def test_saving_an_edit_on_the_page_keeps_every_mass_and_opening(self):
        with _Masses() as m:
            frame = m.editor_frame()
            frame.loc[frame["label"] == "Block A", "width"] = 10.5
            with patch.object(app, "st", _streamlit_saving(frame)), patch.object(app, "hero", lambda *_: None):
                app.model_3d_page({"id": m.ws, "job_no": "PB-M", "job_name": "Masses"})
            masses, openings = m.masses(), m.openings()

        self.assertEqual({k: v["id"] for k, v in masses.items()}, {"Block A": m.a, "Block B": m.b})
        self.assertEqual(masses["Block A"]["width"], 10.5)
        self.assertEqual(openings, {m.door: m.a, m.window: m.b})


class SaveBuildingMassesTests(unittest.TestCase):
    def test_new_and_removed_rows(self):
        with _Masses() as m:
            records = [r for r in m.editor_frame().to_dict("records") if r["label"] != "Block B"]
            records.append({"id": float("nan"), "label": "Garage", "level_name": "Ground", "width": 6.0, "depth": 6.0,
                            "height": 2.7, "confidence": "Measured"})
            records.append({"id": None, "label": "Store", "width": 2.0, "depth": 2.0})
            app.save_building_masses(m.ws, records)
            masses, openings = m.masses(), m.openings()
            foreign = app.lquery("SELECT id,label FROM model_masses WHERE id=?", (m.foreign,))

        self.assertEqual(set(masses), {"Block A", "Garage", "Store"})
        self.assertEqual(masses["Block A"]["id"], m.a)
        self.assertTrue(masses["Garage"]["id"] > m.foreign and masses["Store"]["id"] > m.foreign)
        self.assertEqual(masses["Store"]["level_name"], "Ground")
        # Only the removed mass loses its openings' link (the schema's ON DELETE SET NULL).
        self.assertEqual(openings, {m.door: m.a, m.window: None})
        self.assertEqual(foreign, [{"id": m.foreign, "label": "Other job"}])

    def test_blank_label_still_removes_the_row(self):
        with _Masses() as m:
            records = m.editor_frame().to_dict("records")
            for record in records:
                if record["label"] == "Block B":
                    record["label"] = "  "
            app.save_building_masses(m.ws, records)
            masses = m.masses()
        self.assertEqual(set(masses), {"Block A"})
        self.assertEqual(masses["Block A"]["id"], m.a)

    def test_copied_or_foreign_ids_never_rewrite_another_mass(self):
        with _Masses() as m:
            records = m.editor_frame().to_dict("records")
            copy = dict(records[0], label="Block A copy")
            foreign = dict(records[0], id=m.foreign, label="Pasted from another job")
            app.save_building_masses(m.ws, records + [copy, foreign])
            masses = m.masses()
            other = app.lquery("SELECT label FROM model_masses WHERE id=?", (m.foreign,))

        self.assertEqual(masses["Block A"]["id"], m.a)
        self.assertEqual(masses["Block B"]["id"], m.b)
        self.assertNotIn(masses["Block A copy"]["id"], {m.a, m.b, m.foreign})
        self.assertNotIn(masses["Pasted from another job"]["id"], {m.a, m.b, m.foreign})
        self.assertEqual(other, [{"label": "Other job"}])

    def test_a_failed_save_changes_nothing(self):
        with _Masses() as m:
            before = (m.masses(), m.openings())
            records = m.editor_frame().to_dict("records")
            records[0]["width"] = 99.0
            records.append({"label": "Garage"})
            app.lexecute("CREATE TRIGGER fail_insert BEFORE INSERT ON model_masses BEGIN SELECT RAISE(ABORT, 'disk full'); END")
            with self.assertRaisesRegex(Exception, "disk full"):
                app.save_building_masses(m.ws, records)
            app.lexecute("DROP TRIGGER fail_insert")
            after = (m.masses(), m.openings())
        self.assertEqual(after, before)

    def test_editor_row_ids(self):
        for value, expected in ((3, 3), (3.0, 3), ("4", 4), (None, None), (float("nan"), None),
                                (float("inf"), None), (2.5, None), ("abc", None), ("", None)):
            with self.subTest(value=value):
                self.assertEqual(app._mass_editor_id(value), expected)


if __name__ == "__main__":
    unittest.main()
