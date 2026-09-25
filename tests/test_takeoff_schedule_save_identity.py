"""Saving the take-off schedule keeps take-off row identity (pb_takeoff_row_contract.save_schedule).

Both production schedule saves - "Save no-AI take-off schedule" (the default
route, pb_no_ai_takeoff_v1216.save_schedule_batched) and "Save take-off
schedule" (the AI route, pb_planreader_3d_app.subscription_takeoff_page) -
deleted every take-off row of the workspace and re-inserted the edited rows.
Even a save with no edits gave every row a new AUTOINCREMENT id and reset its
created_at: drawn measurement lines (measurement_lines.takeoff_row_id, no
foreign key) were left pointing at deleted rows, and 3D commercial sync audit
events (ON DELETE CASCADE) were deleted. The AI-route save also committed the
delete before re-inserting row by row.
"""
from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pb_no_ai_takeoff_v1216 as noai
import pb_planreader_3d_app as app_mod
import pb_takeoff_row_contract as contract

EDITOR_COLUMNS = ["id"] + list(app_mod.TAKEOFF_COLUMNS) + ["row_role"]


class _Schedule:
    """A drawn manual row with a measurement line and a 3D commercial sync event, plus another job."""

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._patch = patch.object(app_mod, "DB_PATH", Path(self._tmp.name) / "planreader.db")
        self._patch.start()
        app_mod.init_local_db()
        self.ws = app_mod.create_standalone_workspace("PB-T", "Take-off", "b", "")
        self.other_ws = app_mod.create_standalone_workspace("PB-O", "Other", "b", "")
        app_mod.lexecute("INSERT INTO documents(id,workspace_id,file_name,path,sha256,page_count) VALUES(1,?,'p.pdf','p.pdf','sha',1)", (self.ws,))
        app_mod.lexecute("INSERT INTO pages(id,document_id,workspace_id,page_no,page_label,page_type,selected,px_per_m) VALUES(1,1,?,1,'A101','Floor Plan',1,100)", (self.ws,))
        self.walls = self._row(self.ws, "Lounge walls", 42.0)
        self.ceiling = self._row(self.ws, "Lounge ceiling", 20.0)
        self.foreign = self._row(self.other_ws, "Other job walls", 10.0)
        self.line = app_mod.lexecute(
            "INSERT INTO measurement_lines(workspace_id,page_id,takeoff_row_id,label,unit,kind,area_m2,created_at) VALUES(?,1,?,'Lounge walls','m²','polygon',42.0,'x')",
            (self.ws, self.walls),
        )
        app_mod.lexecute(
            """INSERT INTO editable_3d_commercial_sync_events(workspace_id,object_id,object_type,quantity_id,revision_hash,
                   takeoff_row_id,approval_approved_by,approval_approved_at,synced_by,synced_at)
               VALUES(?,'MASS-1','wall','q1','h1',?,'Estimator','2026-09-02','Estimator','2026-09-02')""",
            (self.ws, self.walls),
        )
        self.app = SimpleNamespace(local_connect=app_mod.local_connect, now_stamp=app_mod.now_stamp,
                                   lquery=app_mod.lquery, lexecute=app_mod.lexecute)
        return self

    def __exit__(self, *exc):
        self._patch.stop()
        self._tmp.cleanup()

    @staticmethod
    def _row(workspace_id, location, quantity):
        return app_mod.lexecute(
            """INSERT INTO takeoff_rows(workspace_id,section,element,location,substrate,finish_system,quantity,unit,
                   quantity_status,source_page,source_reference,inclusion_status,coats,coverage_m2_per_litre,
                   productivity_m2_per_hour,rate_per_unit,confidence,notes,row_role,created_at,updated_at)
               VALUES(?,'Internal','Walls',?,'Plasterboard','Low sheen',?,'m²','Measured','A101','Mapper line',
                   'INCLUSION',2,12,8,4.5,'Measured','drawn','','2026-09-01T08:00:00','2026-09-01T08:00:00')""",
            (workspace_id, location, quantity),
        )

    def editor_frame(self):
        """The schedule grid exactly as both pages load it."""
        frame = app_mod.ldf("SELECT * FROM takeoff_rows WHERE workspace_id=? ORDER BY id", (self.ws,))
        return frame.reindex(columns=EDITOR_COLUMNS)

    def rows(self, workspace_id=None):
        return {r["location"]: r for r in app_mod.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=? ORDER BY id",
                                                         (workspace_id or self.ws,))}

    def links(self):
        line = app_mod.lquery("SELECT takeoff_row_id FROM measurement_lines WHERE id=?", (self.line,))[0]["takeoff_row_id"]
        sync = app_mod.lquery("SELECT takeoff_row_id FROM editable_3d_commercial_sync_events WHERE workspace_id=?", (self.ws,))
        return line, [r["takeoff_row_id"] for r in sync]


def _streamlit_pressing(label, edited_frame):
    """A Streamlit stub: the estimator edited the schedule grid and pressed ``label``."""
    pressed = lambda text, *args, **kwargs: text == label  # noqa: E731

    def column(*args, **kwargs):
        col = MagicMock()
        col.button.side_effect = pressed
        return col

    st = MagicMock()
    st.session_state = {}
    st.tabs.side_effect = lambda labels, *args, **kwargs: [MagicMock() for _ in labels]
    st.columns.side_effect = lambda spec, *args, **kwargs: [column() for _ in range(spec if isinstance(spec, int) else len(spec))]
    st.button.side_effect = pressed
    st.checkbox.return_value = False
    st.data_editor.side_effect = lambda frame, *args, **kwargs: edited_frame
    st.form_submit_button.return_value = False
    # Every other input widget returns its default, as an untouched widget does.
    st.selectbox.side_effect = lambda label, options=(), index=0, *args, **kwargs: list(options)[index or 0] if list(options) else None
    st.radio.side_effect = lambda label, options=(), index=0, *args, **kwargs: list(options)[index or 0] if list(options) else None
    st.multiselect.side_effect = lambda label, options=(), default=None, *args, **kwargs: list(default or [])
    st.text_input.side_effect = lambda label, value="", *args, **kwargs: value
    st.text_area.side_effect = lambda label, value="", *args, **kwargs: value
    st.number_input.side_effect = lambda label, *args, value=0, **kwargs: value
    return st


class NoAiScheduleSaveTests(unittest.TestCase):
    """The default Subscription Take-off route."""

    def test_saving_on_the_panel_keeps_ids_links_and_created_at(self):
        with _Schedule() as s:
            frame = s.editor_frame()
            frame.loc[frame["location"] == "Lounge walls", "quantity"] = 44.5
            with patch.object(app_mod, "st", _streamlit_pressing("Save no-AI take-off schedule", frame)):
                noai.no_ai_takeoff_panel(app_mod, {"id": s.ws, "job_no": "PB-T", "job_name": "Take-off"})
            rows, links, foreign = s.rows(), s.links(), s.rows(s.other_ws)

        self.assertEqual({k: v["id"] for k, v in rows.items()}, {"Lounge walls": s.walls, "Lounge ceiling": s.ceiling})
        self.assertEqual(rows["Lounge walls"]["quantity"], 44.5)
        self.assertEqual(rows["Lounge walls"]["created_at"], "2026-09-01T08:00:00")
        self.assertNotEqual(rows["Lounge walls"]["updated_at"], "2026-09-01T08:00:00")
        self.assertEqual(links, (s.walls, [s.walls]), "the drawn line and the 3D sync event must stay attached")
        self.assertEqual(foreign["Other job walls"]["id"], s.foreign)

    def test_new_removed_copied_and_foreign_rows(self):
        with _Schedule() as s:
            records = [r for r in s.editor_frame().to_dict("records") if r["location"] != "Lounge ceiling"]
            copy = dict(records[0], location="Lounge walls (copy)")
            pasted = dict(records[0], id=float(s.foreign), location="Pasted from another job")
            new = dict(records[0], id=math.nan, location="Bedroom walls")
            count = noai.save_schedule_batched(s.app, s.ws, records + [copy, pasted, new])
            rows, links, foreign = s.rows(), s.links(), s.rows(s.other_ws)

        self.assertEqual(count, 4)
        self.assertEqual(set(rows), {"Lounge walls", "Lounge walls (copy)", "Pasted from another job", "Bedroom walls"})
        self.assertEqual(rows["Lounge walls"]["id"], s.walls)
        self.assertEqual(len({r["id"] for r in rows.values()} & {s.ceiling, s.foreign}), 0)
        self.assertEqual(links, (s.walls, [s.walls]))
        self.assertEqual(foreign, {"Other job walls": foreign["Other job walls"]})
        self.assertEqual(foreign["Other job walls"]["id"], s.foreign)

    def test_a_failed_save_changes_nothing(self):
        with _Schedule() as s:
            before = (s.rows(), s.links())
            records = s.editor_frame().to_dict("records")
            records[0]["quantity"] = 99.0
            records.append(dict(records[1], id=None, location="Bedroom walls"))
            app_mod.lexecute("CREATE TRIGGER fail_insert BEFORE INSERT ON takeoff_rows BEGIN SELECT RAISE(ABORT, 'disk full'); END")
            with self.assertRaisesRegex(Exception, "disk full"):
                noai.save_schedule_batched(s.app, s.ws, records)
            app_mod.lexecute("DROP TRIGGER fail_insert")
            after = (s.rows(), s.links())
        self.assertEqual(after, before)


class AiRouteScheduleSaveTests(unittest.TestCase):
    def test_saving_on_the_page_keeps_ids_links_and_created_at(self):
        with _Schedule() as s:
            frame = s.editor_frame()
            frame.loc[frame["location"] == "Lounge walls", "quantity"] = 44.5
            with patch.object(app_mod, "st", _streamlit_pressing("Save take-off schedule", frame)), \
                    patch.object(app_mod, "hero", lambda *_: None), \
                    patch.object(app_mod, "takeoff_import_panel", lambda *_: None):
                app_mod.subscription_takeoff_page({"id": s.ws, "job_no": "PB-T", "job_name": "Take-off"}, "")
            rows, links = s.rows(), s.links()

        self.assertEqual({k: v["id"] for k, v in rows.items()}, {"Lounge walls": s.walls, "Lounge ceiling": s.ceiling})
        self.assertEqual(rows["Lounge walls"]["quantity"], 44.5)
        self.assertEqual(rows["Lounge walls"]["created_at"], "2026-09-01T08:00:00")
        self.assertEqual(links, (s.walls, [s.walls]))

    def test_a_failed_save_on_the_page_changes_nothing(self):
        # The old handler committed the DELETE first: a failing insert wiped the take-off.
        with _Schedule() as s:
            before = (s.rows(), s.links())
            frame = s.editor_frame()
            frame.loc[len(frame)] = dict(frame.iloc[0].to_dict(), id=None, location="Bedroom walls")
            app_mod.lexecute("CREATE TRIGGER fail_insert BEFORE INSERT ON takeoff_rows BEGIN SELECT RAISE(ABORT, 'disk full'); END")
            with patch.object(app_mod, "st", _streamlit_pressing("Save take-off schedule", frame)), \
                    patch.object(app_mod, "hero", lambda *_: None), \
                    patch.object(app_mod, "takeoff_import_panel", lambda *_: None), \
                    self.assertRaisesRegex(Exception, "disk full"):
                app_mod.subscription_takeoff_page({"id": s.ws, "job_no": "PB-T", "job_name": "Take-off"}, "")
            app_mod.lexecute("DROP TRIGGER fail_insert")
            after = (s.rows(), s.links())
        self.assertEqual(after, before)


class SaveScheduleContractTests(unittest.TestCase):
    def test_update_sql_keeps_workspace_and_created_at_and_binds_every_other_field(self):
        for name, fields in contract.LAYOUTS.items():
            with self.subTest(name):
                sql = contract.update_sql(fields)
                assigned = sql.split(" SET ", 1)[1].split(" WHERE ", 1)[0].split(",")
                self.assertEqual([a.split("=")[0] for a in assigned],
                                 [f for f in fields if f not in ("workspace_id", "created_at")])
                self.assertEqual(sql.count("?"), len(fields))
                self.assertTrue(sql.endswith("WHERE id=? AND workspace_id=?"))
        with self.assertRaises(contract.TakeoffRowContractError):
            contract.update_sql(contract.CORE_FIELDS[:13])

    def test_rows_of_another_workspace_or_malformed_rows_are_refused(self):
        with _Schedule() as s:
            values = tuple(dict(zip(contract.CORE_FIELDS, [None] * 21), workspace_id=s.other_ws).values())
            conn = app_mod.local_connect()
            try:
                with self.assertRaises(contract.TakeoffRowContractError):
                    contract.save_schedule(conn, s.ws, [(None, values)], contract.CORE_FIELDS)
                with self.assertRaises(contract.TakeoffRowContractError):
                    contract.save_schedule(conn, s.ws, [(s.walls, values[:13])], contract.CORE_FIELDS)
            finally:
                conn.rollback()
                conn.close()
            self.assertEqual(set(s.rows()), {"Lounge walls", "Lounge ceiling"})

    def test_row_ids(self):
        for value, expected in ((3, 3), (3.0, 3), ("4", 4), (None, None), (math.nan, None), (math.inf, None),
                                (2.5, None), ("", None), ("abc", None)):
            with self.subTest(value=value):
                self.assertEqual(contract.row_id_of(value), expected)


if __name__ == "__main__":
    unittest.main()
