"""Drift guard for the canonical takeoff_rows contract (pb_takeoff_row_contract).

These tests fail when any PlanReader writer drifts from the one contract:
every INSERT column list must be a canonical layout, every positional tuple
builder must match its layout, the app's editable columns come from the
contract, and batch replacers must delete exactly the prefix they insert.
TradeReader modules (tradereader_*.py) are a separate product and schema.
"""
from __future__ import annotations

import ast
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pb_takeoff_row_contract as contract

REPO = Path(__file__).resolve().parents[1]
_INSERT_RE = re.compile(r"INSERT\s+INTO\s+takeoff_rows\s*\((.*?)\)\s*VALUES", re.S | re.I)


def _production_modules():
    return sorted(REPO.glob("pb_*.py"))


def _sample_row():
    row = {name: f"v:{name}" for name in contract.COMMERCIAL_PROVENANCE_FIELDS}
    row.update({"quantity": 12.5, "net_qty": 12.5, "item": 3, "coats": 2, "coverage_m2_per_litre": 12,
                "productivity_m2_per_hour": 8, "rate_per_unit": 0.0, "unit": "m²", "row_role": "",
                "confidence": "Derived", "workspace_id": 1})
    return row


class ContractDefinitionTests(unittest.TestCase):
    def test_layouts_are_built_from_the_same_ordered_groups(self):
        self.assertEqual(len(contract.EDITABLE_FIELDS), 17)
        self.assertEqual([len(f) for f in contract.LAYOUTS.values()], [21, 26, 30])
        core = contract.CORE_FIELDS
        self.assertEqual(core[0], "workspace_id")
        self.assertEqual(core[1:18], contract.EDITABLE_FIELDS)
        self.assertEqual(core[18:], ("row_role", "created_at", "updated_at"))
        for fields in contract.LAYOUTS.values():
            self.assertEqual(fields[:19], core[:19])
            self.assertEqual(fields[-2:], contract.AUDIT_FIELDS)
            self.assertEqual(len(set(fields)), len(fields))

    def test_app_editable_columns_come_from_the_contract(self):
        import pb_planreader_3d_app as app

        self.assertEqual(tuple(app.TAKEOFF_COLUMNS), contract.EDITABLE_FIELDS)
        self.assertIsInstance(app.TAKEOFF_COLUMNS, list)
        self.assertEqual(tuple(app.UNIT_OPTIONS), contract.TAKEOFF_UNITS)
        self.assertIsInstance(app.UNIT_OPTIONS, list)

    def test_live_schema_has_every_contract_column(self):
        import pb_planreader_3d_app as app

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp, \
                patch.object(app, "DB_PATH", Path(tmp) / "planreader.db"):
            app.init_local_db()
            columns = {row["name"] for row in app.lquery("PRAGMA table_info(takeoff_rows)")}
        self.assertTrue(set(contract.COMMERCIAL_PROVENANCE_FIELDS) <= columns)

    def test_auto_geometry_uses_the_contract(self):
        import pb_auto_geometry_v1219 as auto

        self.assertIs(auto.TAKEOFF_ROW_FIELDS, contract.CORE_FIELDS)
        self.assertEqual(auto._TAKEOFF_INSERT, contract.insert_sql(contract.CORE_FIELDS))
        self.assertIs(auto.TakeoffRowContractError, contract.TakeoffRowContractError)


class ContractApiTests(unittest.TestCase):
    def test_serialise_and_reconstruct_round_trip(self):
        row = _sample_row()
        for fields in contract.LAYOUTS.values():
            values = contract.values_from_mapping(row, fields)
            self.assertEqual(len(values), len(fields))
            self.assertEqual(contract.mapping_from_values(values, fields), {k: row[k] for k in fields})

    def test_insert_sql_binds_every_field(self):
        for fields in contract.LAYOUTS.values():
            sql = contract.insert_sql(fields)
            self.assertEqual(sql.count("?"), len(fields))
            self.assertEqual(contract.layout_of(_INSERT_RE.search(sql).group(1).split(",")), contract.layout_of(fields))

    def test_drifted_layouts_are_rejected(self):
        reordered = list(contract.CORE_FIELDS)
        reordered[6], reordered[7] = reordered[7], reordered[6]
        for bad in (reordered, contract.CORE_FIELDS[:13], contract.CORE_FIELDS + ("extra",)):
            self.assertIsNone(contract.layout_of(bad))
            with self.assertRaises(contract.TakeoffRowContractError):
                contract.insert_sql(bad)

    def test_malformed_rows_fail_explicitly(self):
        legacy = tuple(range(13))
        with self.assertRaises(contract.TakeoffRowContractError) as caught:
            contract.validate_values(legacy, contract.CORE_FIELDS, index=4, source="legacy producer")
        message = str(caught.exception)
        for part in ("row 4", "13 values", "expected 21", "legacy producer", "workspace_id"):
            self.assertIn(part, message)
        with self.assertRaises(contract.TakeoffRowContractError):
            contract.validate_values({"section": "x"}, contract.CORE_FIELDS)
        partial = _sample_row()
        del partial["unit"]
        with self.assertRaises(contract.TakeoffRowContractError) as missing:
            contract.values_from_mapping(partial, contract.CORE_FIELDS)
        self.assertIn("unit", str(missing.exception))


class ProducerDriftTests(unittest.TestCase):
    def test_every_literal_insert_uses_a_canonical_layout(self):
        seen = 0
        for path in _production_modules():
            text = path.read_text(encoding="utf-8-sig")
            for match in _INSERT_RE.finditer(text):
                if "{" in match.group(1):  # generated from the contract, e.g. insert_sql()
                    continue
                seen += 1
                columns = [c.strip() for c in match.group(1).replace("\n", " ").split(",") if c.strip()]
                line = text[:match.start()].count("\n") + 1
                self.assertIsNotNone(contract.layout_of(columns), f"{path.name}:{line} drifted: {columns}")
        # Sanity floor that the scan still finds the literal statements; writers
        # moved onto the contract's generated SQL (insert_sql/save_schedule) drop out.
        self.assertGreaterEqual(seen, 15)

    def test_inline_insert_tuples_match_their_statement(self):
        import pb_planreader_3d_app as app

        checked = 0
        for path in _production_modules():
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for func in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
                for call in [n for n in ast.walk(func) if isinstance(n, ast.Call) and len(n.args) >= 2]:
                    sql = call.args[0]
                    if not (isinstance(sql, ast.Constant) and isinstance(sql.value, str)
                            and _INSERT_RE.search(sql.value)):
                        continue
                    arg = call.args[1]
                    if not isinstance(arg, ast.Tuple):
                        continue  # builder-fed batch writes: covered by the builder test below
                    width = _tuple_width(arg, func, len(app.TAKEOFF_COLUMNS))
                    self.assertIsNotNone(width, f"{path.name}:{call.lineno} tuple width cannot be verified")
                    self.assertEqual(width, sql.value.count("?"), f"{path.name}:{call.lineno}")
                    checked += 1
        self.assertGreaterEqual(checked, 10)

    def test_positional_builders_match_their_layout(self):
        import pb_auto_geometry_v1219 as auto
        import pb_full_reconstruction_v141 as reconstruction
        import pb_no_ai_takeoff_v1216 as no_ai
        import pb_performance_v1215 as performance
        import pb_premier_takeoff_v1225 as premier

        app = SimpleNamespace(now_stamp=lambda: "stamp")
        row = _sample_row()
        auto_row = auto._takeoff_row(
            workspace_id=1, section="s", element="e", location="l", substrate="x", quantity=1.0,
            status="Measured", source_page="p", source_reference=f"{auto.SOURCE_PREFIX} · r", confidence="c", notes="n",
        )
        cases = [
            ("auto_geometry._takeoff_row", auto_row, contract.CORE_FIELDS, auto._TAKEOFF_INSERT),
            ("no_ai._takeoff_values", no_ai._takeoff_values(1, dict(row), "stamp"), contract.COMMERCIAL_FIELDS,
             no_ai._TAKEOFF_INSERT_SQL),
            ("no_ai._takeoff_values_with_provenance", no_ai._takeoff_values_with_provenance(1, dict(row), "stamp"),
             contract.COMMERCIAL_PROVENANCE_FIELDS, no_ai._TAKEOFF_INSERT_WITH_PROVENANCE_SQL),
            ("performance._takeoff_values", performance._takeoff_values(1, dict(row), "stamp"),
             contract.COMMERCIAL_FIELDS, performance._TAKEOFF_INSERT_SQL),
            ("premier._takeoff_values", premier._takeoff_values(app, 1, dict(row)), contract.CORE_FIELDS, None),
            ("full_reconstruction._values", reconstruction._values(app, 1, dict(row)), contract.CORE_FIELDS, None),
        ]
        for name, values, fields, sql in cases:
            with self.subTest(name):
                self.assertEqual(len(values), len(fields))
                named = contract.mapping_from_values(values, fields)
                self.assertEqual(named["workspace_id"], 1)
                self.assertEqual(named["created_at"], named["updated_at"])
                if sql is not None:
                    self.assertEqual(contract.layout_of(_INSERT_RE.search(sql).group(1).split(",")),
                                     contract.layout_of(fields))


class ReplacerPrefixTests(unittest.TestCase):
    def test_full_reconstruction_deletes_the_prefix_its_rows_carry(self):
        import pb_full_reconstruction_v141 as reconstruction
        import pb_unified_building_v139 as unified

        rows = unified.takeoff_rows([{"side": "North", "wall_ref": "W1", "substrate": "Render", "net_m2": 10.0}])
        self.assertTrue(rows[0]["source_reference"].startswith(reconstruction.SOURCE_PREFIX))


def _tuple_width(node: ast.Tuple, func: ast.AST, editable_count: int):
    """Width of a tuple literal, resolving the starred patterns used by the app."""
    width = 0
    for element in node.elts:
        if not isinstance(element, ast.Starred):
            width += 1
            continue
        if not isinstance(element.value, ast.Name):
            return None
        resolved = _resolve_star(element.value.id, func, editable_count)
        if resolved is None:
            return None
        width += resolved
    return width


def _resolve_star(name: str, func: ast.AST, editable_count: int):
    for node in ast.walk(func):
        # values = [row.get(col, "") for col in TAKEOFF_COLUMNS]
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            value = node.value
            if isinstance(value, ast.ListComp) and len(value.generators) == 1:
                source = value.generators[0].iter
                if isinstance(source, ast.Name) and source.id == "TAKEOFF_COLUMNS":
                    return editable_count
        # for seed in seeds: ... where seeds is a list of equal-width tuple literals
        if isinstance(node, ast.For) and isinstance(node.target, ast.Name) and node.target.id == name \
                and isinstance(node.iter, ast.Name):
            for assign in ast.walk(func):
                if isinstance(assign, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == node.iter.id for t in assign.targets
                ) and isinstance(assign.value, (ast.List, ast.Tuple)):
                    widths = {len(e.elts) for e in assign.value.elts if isinstance(e, ast.Tuple)}
                    if len(widths) == 1 and all(isinstance(e, ast.Tuple) for e in assign.value.elts):
                        return widths.pop()
    return None


if __name__ == "__main__":
    unittest.main()
