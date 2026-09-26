"""Ownership invariants for generated take-off rows.

Every generator that replaces its own take-off rows deletes by workspace and a
source_reference prefix. These invariants keep a generator from deleting the
estimator's rows or another generator's, from reaching into another
workspace, and from duplicating its own rows on re-run:

1. every DELETE FROM takeoff_rows is scoped to one workspace;
2. no owner's LIKE pattern can match another owner's references (LIKE is
   case-insensitive and treats ``%``/``_`` as wildcards);
3. each production replacer removes exactly the rows it owns;
4. replacing twice with the same rows leaves one copy.
"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pb_3d_surface_editor_v1212 as surface
import pb_auto_geometry_v1219 as auto
import pb_floor_mapper_v127 as floor_mapper
import pb_full_reconstruction_v141 as reconstruction
import pb_no_ai_takeoff_v1216 as noai
import pb_performance_v1215 as perf
import pb_planreader_3d_app as app_mod
import pb_premier_takeoff_v1225 as premier
import pb_room_face_takeoff as room_face
import pb_takeoff_studio_v1211 as studio
import pb_unified_building_v139 as unified

REPO = Path(__file__).resolve().parents[1]

# Owner -> the prefix its replacement deletes by (per-page owners add " · page:N ·").
OWNER_PREFIXES = {
    "auto geometry": auto.SOURCE_PREFIX,
    "no-AI": noai.SOURCE_PREFIX,
    "commercial": premier.SOURCE_PREFIX,
    "3D surfaces": surface.SOURCE_PREFIX,
    "Takeoff Studio": studio.SOURCE_PREFIX,
    "floor mapper": floor_mapper.SOURCE_PREFIX,
    "unified building": reconstruction.SOURCE_PREFIX,
}

# One row per owner and per kind of row a replacer must never touch.
SEED = {
    "auto: unit": f"{auto.SOURCE_PREFIX} · unit:Unit 1",
    "auto: room face": f"{auto.SOURCE_PREFIX} · {room_face.SOURCE_PREFIX} · A101 · page:1",
    "no-AI": f"{noai.SOURCE_PREFIX} · zone:3",
    "commercial": f"{premier.SOURCE_PREFIX} · item:4",
    "3D surfaces": f"{surface.SOURCE_PREFIX} · mass:1:front",
    "Studio page 1": f"{studio.SOURCE_PREFIX} · page:1 · area:5",
    "Studio page 10": f"{studio.SOURCE_PREFIX} · page:10 · area:6",
    "floor mapper page 1": f"{floor_mapper.SOURCE_PREFIX} · page:1 · box:7",
    "floor mapper page 10": f"{floor_mapper.SOURCE_PREFIX} · page:10 · box:8",
    "unified building": f"{reconstruction.SOURCE_PREFIX} · N01",
    "merged in review": "PB Merge v1.2.26 · rows:1,2",
    "manual": "Estimator manual entry",
    "manual, blank reference": "",
    "manual, no reference": None,
}


def _row(reference, **overrides):
    """A complete named row in the widest canonical layout."""
    row = {
        "section": "Internal", "element": "Walls", "location": "Lounge", "substrate": "Plasterboard",
        "finish_system": "Low sheen", "quantity": 12.5, "unit": "m²", "quantity_status": "Measured",
        "source_page": "A101", "source_reference": reference, "inclusion_status": "INCLUSION", "coats": 2,
        "coverage_m2_per_litre": 12, "productivity_m2_per_hour": 8, "rate_per_unit": 0.0, "confidence": "Measured",
        "notes": "", "row_role": "", "commercial_authority_status": "", "commercial_authority_source": "",
        "commercial_authority_reviewed_by": "", "commercial_authority_reviewed_at": "",
        "commercial_authority_fingerprint": "", "ai_baseline_quantity": None, "pre_map_quantity": None,
        "pre_map_quantity_status": None, "origin": "",
        # Commercial (premier) schedule fields.
        "sync": True, "item": 4, "net_qty": 12.5, "level": "Ground", "area": "Lounge",
    }
    row.update(overrides)
    return row


class _Workspaces:
    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._patch = patch.object(app_mod, "DB_PATH", Path(self._tmp.name) / "planreader.db")
        self._patch.start()
        app_mod.init_local_db()
        self.ws = app_mod.create_standalone_workspace("PB-1", "Owner", "b", "")
        self.other = app_mod.create_standalone_workspace("PB-2", "Other", "b", "")
        for workspace_id in (self.ws, self.other):
            for reference in SEED.values():
                self.insert(workspace_id, reference)
            app_mod.lexecute(
                "INSERT INTO takeoff_rows(workspace_id,section,element,location,source_page,source_reference,created_at,updated_at) "
                "VALUES(?,'Imported','Walls','JobHub','JobHub import','JH-1','x','x')", (workspace_id,))
        self.app = SimpleNamespace(lquery=app_mod.lquery, lexecute=app_mod.lexecute, local_connect=app_mod.local_connect,
                                   now_stamp=app_mod.now_stamp,
                                   registered_wall_takeoff_rows_v139=unified.takeoff_rows)
        return self

    def __exit__(self, *exc):
        self._patch.stop()
        self._tmp.cleanup()

    @staticmethod
    def insert(workspace_id, reference):
        app_mod.lexecute(
            "INSERT INTO takeoff_rows(workspace_id,section,element,location,unit,quantity,source_reference,created_at,updated_at) "
            "VALUES(?,'Internal','Walls','Lounge','m²',12.5,?,'x','x')", (workspace_id, reference))

    @staticmethod
    def rows():
        return {(r["workspace_id"], r["source_reference"], r["source_page"]) for r in
                app_mod.lquery("SELECT workspace_id,source_reference,source_page FROM takeoff_rows")}


# Each production replacer, called with no rows (so it only deletes) and with one row of its own.
REPLACERS = {
    "auto geometry": (lambda app, ws, rows: auto._replace_auto_rows(app, ws, rows),
                      lambda ws: [auto._takeoff_row(workspace_id=ws, section="Internal", element="Floor area",
                                                    location="Unit 1", substrate="Other", quantity=85.4,
                                                    status="Measured", source_page="A101",
                                                    source_reference=SEED["auto: unit"], confidence="Documented",
                                                    notes="n", row_role="floor_area")],
                      {"auto: unit", "auto: room face"}),
    "no-AI": (noai.replace_no_ai_rows, lambda ws: [_row(SEED["no-AI"])], {"no-AI"}),
    "commercial": (premier.sync_pb_generated_rows, lambda ws: [_row(SEED["commercial"])], {"commercial"}),
    "3D surfaces": (perf.replace_surface_rows_batched, lambda ws: [_row(SEED["3D surfaces"])], {"3D surfaces"}),
    "Takeoff Studio page 1": (lambda app, ws, rows: perf.replace_studio_rows_batched(app, ws, 1, rows),
                              lambda ws: [_row(SEED["Studio page 1"])], {"Studio page 1"}),
    "floor mapper page 1": (lambda app, ws, rows: floor_mapper._replace_generated_rows(app, ws, 1, rows),
                            lambda ws: [_row(SEED["floor mapper page 1"])], {"floor mapper page 1"}),
    "unified building": (lambda app, ws, rows: reconstruction.sync_rows(app, ws, rows),
                         lambda ws: [{"side": "North", "wall_ref": "N01", "substrate": "Render", "net_m2": 12.5}],
                         {"unified building"}),
}


class StaticOwnershipTests(unittest.TestCase):
    def test_every_takeoff_delete_is_scoped_to_one_workspace(self):
        found = 0
        for path in sorted(REPO.glob("pb_*.py")):
            text = path.read_text(encoding="utf-8-sig")
            for match in re.finditer(r"DELETE\s+FROM\s+takeoff_rows\b[^\"']*", text, re.I):
                found += 1
                line = text[:match.start()].count("\n") + 1
                self.assertIn("workspace_id=?", match.group(0).replace(" ", ""), f"{path.name}:{line} {match.group(0)!r}")
        self.assertGreaterEqual(found, 10)

    def test_no_owner_pattern_can_match_another_owners_rows(self):
        for owner, prefix in OWNER_PREFIXES.items():
            self.assertFalse(set(prefix) & {"%", "_"}, f"{owner} prefix {prefix!r} contains a LIKE wildcard")
            for other, other_prefix in OWNER_PREFIXES.items():
                if other != owner:
                    self.assertFalse(other_prefix.lower().startswith(prefix.lower()),
                                     f"{owner}'s LIKE {prefix!r}% would delete {other}'s rows")


class ReplacerOwnershipTests(unittest.TestCase):
    def test_each_replacer_removes_exactly_the_rows_it_owns(self):
        for name, (replace, _build, owned) in REPLACERS.items():
            with self.subTest(name), _Workspaces() as w:
                before = w.rows()
                replace(w.app, w.ws, [])
                removed = before - w.rows()
                self.assertEqual(removed, {(w.ws, SEED[label], None) for label in owned})

    def test_replacing_twice_keeps_one_copy(self):
        for name, (replace, build, owned) in REPLACERS.items():
            with self.subTest(name), _Workspaces() as w:
                replace(w.app, w.ws, build(w.ws))
                first = sorted(r["source_reference"] for r in app_mod.lquery("SELECT source_reference FROM takeoff_rows WHERE workspace_id=?", (w.ws,)) if r["source_reference"])
                replace(w.app, w.ws, build(w.ws))
                second = sorted(r["source_reference"] for r in app_mod.lquery("SELECT source_reference FROM takeoff_rows WHERE workspace_id=?", (w.ws,)) if r["source_reference"])
                self.assertEqual(second, first)
                self.assertEqual(len(second), len(set(second)))


if __name__ == "__main__":
    unittest.main()
