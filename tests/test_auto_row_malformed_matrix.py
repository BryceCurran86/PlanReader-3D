"""Malformed automatic take-off rows fail early, explicitly and without corrupting anything.

pb_auto_geometry_v1219 publishes positional rows from several producers. Before
this matrix the publisher checked only the row length and source prefix, so a
producer bug published: rows into another workspace (duplicated there on every
re-run), text in the quantity column, infinite quantities, None locations,
non-automatic roles and inclusions, and - through the builder's rounding - a
NaN quantity as a plausible 0.0 m².
"""
from __future__ import annotations

import math
import unittest

import pb_auto_geometry_v1219 as auto
import pb_planreader_3d_app as app_mod
import pb_room_face_takeoff as room_face
from test_auto_geometry_publication_transactions import _PreparedWorkspace, _snapshot
from test_auto_geometry_takeoff_row_contract import _workspace

FIELDS = auto.TAKEOFF_ROW_FIELDS


def _row(**overrides):
    """A well-formed automatic floor-area row with named overrides."""
    named = dict(zip(FIELDS, auto._takeoff_row(
        workspace_id=1, section="Internal", element="Floor area", location="Unit 1", substrate="Other",
        quantity=85.4, status="Measured", source_page="A101", source_reference=f"{auto.SOURCE_PREFIX} · unit:Unit 1",
        confidence="Documented", notes="Documented unit area.", row_role="floor_area",
    )))
    named.update(overrides)
    return tuple(named[name] for name in FIELDS)


MALFORMED = {
    "13 values (legacy layout)": _row()[:13],
    "20 values": _row()[:20],
    "22 values": _row() + ("extra",),
    "not a tuple": dict(zip(FIELDS, _row())),
    "unit and quantity reversed": _row(quantity="m²", unit=85.4),
    "quantity as text": _row(quantity="85.4"),
    "quantity None": _row(quantity=None),
    "quantity bool": _row(quantity=True),
    "quantity negative": _row(quantity=-3.0),
    "quantity NaN": _row(quantity=math.nan),
    "quantity infinite": _row(quantity=math.inf),
    "commercial rate NaN": _row(rate_per_unit=math.nan),
    "coats negative": _row(coats=-1),
    "another workspace": _row(workspace_id=2),
    "workspace id as text": _row(workspace_id="1"),
    "workspace id None": _row(workspace_id=None),
    "workspace id bool": _row(workspace_id=True),
    "row role model_surface": _row(row_role="model_surface", inclusion_status="PROVISIONAL"),
    "row role wall": _row(row_role="wall", inclusion_status="PROVISIONAL"),
    "row role None": _row(row_role=None),
    "source reference None": _row(source_reference=None),
    "source reference empty": _row(source_reference=""),
    "another producer's prefix": _row(source_reference=f"{room_face.SOURCE_PREFIX} · A101 · page:1"),
    "location None": _row(location=None),
    "section empty": _row(section="  "),
    "notes None": _row(notes=None),
    "unit not canonical (m2)": _row(unit="m2"),
    "inclusion EXCLUSION": _row(inclusion_status="EXCLUSION"),
    "floor area marked provisional": _row(inclusion_status="PROVISIONAL"),
}


def _database():
    return (
        app_mod.lquery("SELECT * FROM takeoff_rows ORDER BY id"),
        app_mod.lquery("SELECT * FROM workspace_settings ORDER BY workspace_id,key"),
    )


class MalformedPublicationTests(unittest.TestCase):
    def test_every_malformed_row_is_rejected_before_anything_changes(self):
        with _workspace() as ws:
            for workspace_id in (1, 2):
                app_mod.lexecute("INSERT INTO workspaces(id,job_name,created_at,updated_at) VALUES(?,'job','x','x')", (workspace_id,))
            app_mod.lexecute(
                """INSERT INTO takeoff_rows(workspace_id,section,element,location,substrate,quantity,unit,
                       source_reference,row_role,created_at,updated_at)
                   VALUES(1,'Internal','Walls','Kitchen','Plasterboard',18.0,'m²','Estimator manual entry','','x','x')"""
            )
            auto._replace_auto_rows(ws.app, 1, [_row()])
            auto._replace_auto_rows(ws.app, 2, [_row(workspace_id=2, location="Unit 9")])
            before = _database()
            for name, malformed in MALFORMED.items():
                with self.subTest(name):
                    with self.assertRaises(auto.TakeoffRowContractError) as caught:
                        auto._replace_auto_rows(ws.app, 1, [_row(location="Unit 2"), malformed])
                    self.assertIn("row 1", str(caught.exception))
                    self.assertEqual(_database(), before, "a rejected publication must not change any workspace")

    def test_well_formed_automatic_rows_are_accepted(self):
        accepted = [
            _row(),
            _row(row_role="", inclusion_status="PROVISIONAL", section="External", location="North · Render"),
            _row(unit="lm", location="Skirting", quantity=0),
            _row(source_page="", notes=""),
        ]
        with _workspace() as ws:
            app_mod.lexecute("INSERT INTO workspaces(id,job_name,created_at,updated_at) VALUES(1,'job','x','x')")
            auto._replace_auto_rows(ws.app, 1, accepted)
            rows = app_mod.lquery("SELECT unit,quantity,row_role,inclusion_status FROM takeoff_rows ORDER BY id")
        self.assertEqual(len(rows), 4)

    def test_error_names_the_field_and_the_producer(self):
        with self.assertRaises(auto.TakeoffRowContractError) as caught:
            auto._validate_auto_rows([_row(), _row(workspace_id=2)], 1)
        message = str(caught.exception)
        for part in ("row 1", "workspace_id 2", "(1)", auto.SOURCE_PREFIX):
            self.assertIn(part, message)


class MalformedProducerInChainTests(unittest.TestCase):
    """Producers A (units) and B (facades) succeed; producer C, outermost, is malformed."""

    def test_analysis_publishes_nothing_when_one_producer_is_malformed(self):
        def other_workspace_row(rows, workspace_id):
            return rows + [_row(workspace_id=workspace_id + 1, location="Unit 7")]

        def nan_geometry(rows, workspace_id):
            area = math.nan  # e.g. a degenerate polygon
            return rows + [auto._takeoff_row(
                workspace_id=workspace_id, section="Internal", element="Floor area", location="Unit 8",
                substrate="Other", quantity=area, status="Measured", source_page="A101",
                source_reference=f"{auto.SOURCE_PREFIX} · unit:Unit 8", confidence="Derived", notes="n",
                row_role="floor_area",
            )]

        for name, producer_c in {"row for another workspace": other_workspace_row, "NaN area": nan_geometry}.items():
            with self.subTest(name), _PreparedWorkspace() as ws:
                auto.analyse_workspace(ws.app, 1)
                before = _snapshot()
                base_units = auto._build_unit_rows

                def with_producer_c(app_obj, workspace_id, pages):
                    rows, summary = base_units(app_obj, workspace_id, pages)
                    return producer_c(list(rows), int(workspace_id)), summary

                auto._build_unit_rows = with_producer_c
                try:
                    with self.assertRaises(auto.TakeoffRowContractError):
                        auto.analyse_workspace(ws.app, 1)
                finally:
                    auto._build_unit_rows = base_units
                self.assertEqual(_snapshot(), before, "rows, 3D mass, surfaces and report must be untouched")
                self.assertEqual(app_mod.lquery("SELECT COUNT(*) AS n FROM takeoff_rows WHERE workspace_id<>1")[0]["n"], 0)


class BuilderTests(unittest.TestCase):
    def _build(self, quantity):
        return auto._takeoff_row(
            workspace_id=1, section="Internal", element="Floor area", location="Unit 1", substrate="Other",
            quantity=quantity, status="Measured", source_page="A101", source_reference=f"{auto.SOURCE_PREFIX} · x",
            confidence="Documented", notes="n", row_role="floor_area",
        )

    def test_non_finite_or_non_numeric_quantity_fails_at_construction(self):
        for quantity in (math.nan, math.inf, -math.inf, "85.4", None, True):
            with self.subTest(quantity=quantity):
                with self.assertRaises(auto.TakeoffRowContractError) as caught:
                    self._build(quantity)
                self.assertIn(f"{auto.SOURCE_PREFIX} · x", str(caught.exception))

    def test_finite_quantities_are_rounded_and_negatives_clamped_as_before(self):
        index = FIELDS.index("quantity")
        self.assertEqual(self._build(12.345)[index], 12.35)
        self.assertEqual(self._build(7)[index], 7)
        self.assertEqual(self._build(-0.4)[index], 0.0)


if __name__ == "__main__":
    unittest.main()
