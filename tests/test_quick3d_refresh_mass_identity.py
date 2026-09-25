"""Quick 3D "Build / Refresh 3D Model" keeps zone mass identity.

pb_performance_v1215.refresh_zone_masses_batched (installed over
pb_3d_quickstart_v1213.refresh_zone_masses at startup) deleted every Quick 3D
zone mass and re-inserted them, so each refresh gave the masses new
AUTOINCREMENT ids: the estimator's openings were detached (model_openings
.mass_id ON DELETE SET NULL) and 3D surface edits and editable-3D corrections
keyed by the id were orphaned.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pb_3d_quickstart_v1213 as quick
import pb_performance_v1215 as perf
import pb_planreader_3d_app as app_mod

BUILD_BUTTON = "⚡ Build / Refresh 3D Model"


def _streamlit_pressing_build():
    st = MagicMock()
    st.session_state = {}
    st.columns.side_effect = lambda spec, *args, **kwargs: [MagicMock() for _ in range(spec if isinstance(spec, int) else len(spec))]
    st.button.side_effect = lambda label, *args, **kwargs: label == BUILD_BUTTON
    return st


class _QuickWorkspace:
    """Real schema; one estimator mass with an opening that Quick 3D must never touch."""

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._patch = patch.object(app_mod, "DB_PATH", Path(self._tmp.name) / "planreader.db")
        self._patch.start()
        app_mod.init_local_db()
        self.ws = app_mod.create_standalone_workspace("PB-Q", "Quick 3D", "b", "")
        app_mod.lexecute("INSERT INTO documents(id,workspace_id,file_name,path,sha256,page_count) VALUES(1,?,'p.pdf','p.pdf','sha',1)", (self.ws,))
        app_mod.lexecute("INSERT INTO pages(id,document_id,workspace_id,page_no,page_label,page_type,selected,px_per_m) VALUES(1,1,?,1,'A101','Floor Plan',1,100)", (self.ws,))
        self.app = SimpleNamespace(
            lquery=app_mod.lquery, lexecute=app_mod.lexecute, local_connect=app_mod.local_connect,
            now_stamp=app_mod.now_stamp, st=_streamlit_pressing_build(), resolve_ai_key=lambda *args: "",
            build_3d_figure=lambda workspace_id: SimpleNamespace(data=[]),
        )
        self.estimator_mass = app_mod.lexecute(
            """INSERT INTO model_masses(workspace_id,label,level_name,x,y,z,width,depth,height,finish,source_reference,confidence,notes,created_at)
               VALUES(?,'Estimator block','Ground',0,0,0,4,4,3,'','Site measure','Measured','','x')""",
            (self.ws,),
        )
        self.estimator_opening = self.add_opening(self.estimator_mass)
        return self

    def __exit__(self, *exc):
        self._patch.stop()
        self._tmp.cleanup()

    def add_zone(self, name, w_px=800):
        return app_mod.lexecute(
            """INSERT INTO mapped_zones(workspace_id,page_id,name,view_type,polygon_json,x_px,y_px,w_px,h_px,px_per_m,
                   wall_height_m,area_m2,substrate,finish_system,quantity_status,source_reference,created_at)
               VALUES(?,1,?,'Plan','[]',100,50,?,500,100,2.7,40,'Render','Acrylic','Measured','A101','x')""",
            (self.ws, name, w_px),
        )

    def add_opening(self, mass_id):
        return app_mod.lexecute(
            """INSERT INTO model_openings(workspace_id,mass_id,label,opening_type,face,offset_x,offset_z,width,height,count,notes,source_reference,created_at)
               VALUES(?,?,'Door D01','Door','Front',1,0,.9,2.1,1,'','Site','x')""",
            (self.ws, mass_id),
        )

    def press_build(self):
        # The production wiring: pb_performance_v1215.apply installs the batched refresh.
        with patch.object(quick, "refresh_zone_masses", perf.refresh_zone_masses_batched):
            quick.quick_build_panel(self.app, {"id": self.ws})

    def refresh(self):
        return perf.refresh_zone_masses_batched(self.app, self.ws)

    def zone_masses(self):
        rows = app_mod.lquery("SELECT id,label,width,source_reference FROM model_masses WHERE workspace_id=? ORDER BY id", (self.ws,))
        return {r["label"]: r for r in rows if r["source_reference"].startswith(quick.QUICK_SOURCE_PREFIX)}

    def openings(self):
        return {r["id"]: r["mass_id"] for r in app_mod.lquery("SELECT id,mass_id FROM model_openings WHERE workspace_id=?", (self.ws,))}


class QuickBuildPanelTests(unittest.TestCase):
    def test_pressing_build_again_keeps_zone_masses_and_estimator_work(self):
        with _QuickWorkspace() as q:
            zone = q.add_zone("Ground footprint")
            q.press_build()
            mass_id = q.zone_masses()["Ground footprint"]["id"]
            opening = q.add_opening(mass_id)
            edit = {"substrate": "EC1", "status": "Complete", "progress_pct": 60.0, "notes": "Estimator: first coat"}
            app_mod.set_workspace_setting(q.ws, "3d_surface_editor_v1212", json.dumps({"surfaces": {f"mass:{mass_id}:front": edit}}))
            app_mod.lexecute("UPDATE mapped_zones SET w_px=900 WHERE id=?", (zone,))

            q.press_build()
            masses, openings = q.zone_masses(), q.openings()
            surfaces = json.loads(app_mod.workspace_setting(q.ws, "3d_surface_editor_v1212"))["surfaces"]
            estimator_mass = app_mod.lquery("SELECT id,width FROM model_masses WHERE id=?", (q.estimator_mass,))

        self.assertEqual(masses["Ground footprint"]["id"], mass_id)
        self.assertEqual(masses["Ground footprint"]["width"], 9.0, "the refresh must still apply the zone's new geometry")
        self.assertEqual(openings, {q.estimator_opening: q.estimator_mass, opening: mass_id})
        self.assertEqual(surfaces[f"mass:{mass_id}:front"], edit)
        self.assertEqual(estimator_mass, [{"id": q.estimator_mass, "width": 4.0}])


class RefreshZoneMassesTests(unittest.TestCase):
    def test_removed_zone_loses_its_mass_and_new_zone_gains_one(self):
        with _QuickWorkspace() as q:
            q.add_zone("Zone A")
            zone_b = q.add_zone("Zone B")
            self.assertEqual(q.refresh(), 2)
            before = q.zone_masses()
            opening_b = q.add_opening(before["Zone B"]["id"])
            app_mod.lexecute("DELETE FROM mapped_zones WHERE id=?", (zone_b,))
            q.add_zone("Zone C")

            self.assertEqual(q.refresh(), 2)
            after, openings = q.zone_masses(), q.openings()

        self.assertEqual(set(after), {"Zone A", "Zone C"})
        self.assertEqual(after["Zone A"]["id"], before["Zone A"]["id"])
        self.assertNotIn(after["Zone C"]["id"], {m["id"] for m in before.values()})
        self.assertIsNone(openings[opening_b], "a removed zone's mass keeps the schema's ON DELETE SET NULL")
        self.assertEqual(openings[q.estimator_opening], q.estimator_mass)

    def test_duplicate_zone_masses_collapse_to_the_first(self):
        with _QuickWorkspace() as q:
            zone = q.add_zone("Zone A")
            q.refresh()
            keep = q.zone_masses()["Zone A"]["id"]
            app_mod.lexecute(
                "INSERT INTO model_masses(workspace_id,label,source_reference,confidence,created_at) VALUES(?,'Zone A',?,'Derived','x')",
                (q.ws, f"{quick.QUICK_SOURCE_PREFIX}{zone}"),
            )
            q.refresh()
            rows = app_mod.lquery("SELECT id FROM model_masses WHERE workspace_id=? AND source_reference LIKE ?",
                                  (q.ws, quick.QUICK_SOURCE_PREFIX + "%"))
        self.assertEqual(rows, [{"id": keep}])


if __name__ == "__main__":
    unittest.main()
