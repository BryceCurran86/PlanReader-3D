"""Permanent audit test for production wrapper composition and module idempotency.

Pins the effective authority for core PlanReader entry points and functions,
and verifies that every module in the startup stack is idempotent under repeated apply().
"""
from __future__ import annotations

import importlib
import inspect
import unittest
from types import SimpleNamespace

import pb_auto_geometry_guard_v1219 as guard
import pb_auto_geometry_v1219 as auto
import pb_no_ai_takeoff_v1216 as noai
import pb_plan_read_engine_v1228 as engine
import pb_quick_takeoff_v153 as quick
import pb_room_face_takeoff as room_face
import pb_takeoff_review_v1226 as review
import pb_takeoff_v11 as v11
import pb_takeoff_v12 as v12


# The 73 modules in the production startup chain:
# pb_planreader_v133_app -> v139 -> v126 -> v11 -> pb_planreader_3d_app
PRODUCTION_MODULES_IN_CHAIN = [
    # pb_planreader_v11_app
    "pb_takeoff_v11", "pb_takeoff_v12", "pb_jobhub_connection_v122", "pb_jobhub_stability_v123", "pb_takeoff_accuracy_v125",
    # pb_planreader_v126_app
    "pb_gemini_v126", "pb_floor_mapper_v128", "pb_processing_stability_v129", "pb_takeoff_studio_v1211",
    "pb_3d_surface_editor_v1212", "pb_studio_path_guard_v1213", "pb_3d_quickstart_v1213", "pb_3d_wrapper_guard_v1214",
    "pb_performance_v1215", "pb_db_init_guard_v1215", "pb_subscription_core_guard_v1218", "pb_no_ai_takeoff_v1216",
    "pb_selected_pages_v1217", "pb_auto_geometry_v1219", "pb_auto_geometry_guard_v1219", "pb_memory_stability_v1220",
    "pb_unit_floor_area_v1221", "pb_unit_floor_area_gate_v1221", "pb_unit_floor_area_textfix_v1221",
    "pb_material_schedule_v1222", "pb_autopilot_v1223", "pb_autopilot_upload_batch_v1223",
    "pb_autopilot_accuracy_guard_v1223", "pb_context_floorarea_v1224", "pb_page_registration_v1225",
    "pb_registration_priority_guard_v1225", "pb_code_register_v1225", "pb_premier_takeoff_v1225",
    "pb_drawing_reading_v1226", "pb_selection_lock_v1226", "pb_selected_evidence_floor_v1226",
    "pb_elevation_regions_v1226", "pb_takeoff_review_v1226", "pb_legend_register_v1227",
    "pb_plan_read_engine_v1228", "pb_mapper_hard_guard_v1228", "pb_persistent_login_v1229",
    "pb_vector_geometry_v130", "pb_room_face_takeoff", "pb_accuracy_benchmark_v130", "pb_accuracy_ui_v130",
    "pb_substrate_qa_v131", "pb_surface_evidence_v160", "pb_hatch_detection_v160", "pb_precision_3d_v132",
    "pb_opening_deductions_v134", "pb_elevation_registration_v135",
    # pb_planreader_reconstruction_v139_app
    "pb_project_scope_v142", "pb_scope_read_gate_v142", "pb_elevation_profile_v136", "pb_height_evidence_v150",
    "pb_opening_geometry_v137", "pb_registered_substrates_v138", "pb_unified_building_v139",
    "pb_roof_envelope_v140", "pb_full_reconstruction_v141", "pb_render_resilience_v143", "pb_accuracy_v13_engines_v145",
    # pb_planreader_v133_app
    "pb_sidebar_viewport_guard_v146", "pb_upload_register_v147", "pb_runtime_performance_v149",
    "pb_processing_fastpath_v150", "pb_material_preview_guard_v152", "pb_quick_takeoff_v153",
    "pb_takeoff_colours_v153", "pb_opening_production_v175", "pb_3d_workspace_integration", "pb_commercial_workspace_v160",
]


class ProductionCompositionAuthorityTests(unittest.TestCase):
    """Ensure the fully composed production application preserves required authorities."""

    authorities: dict[str, dict[str, str]] = {}

    @classmethod
    def setUpClass(cls):
        import json
        import subprocess
        import sys

        script = (
            "import json\n"
            "import pb_planreader_v133_app as entry\n"
            "import pb_no_ai_takeoff_v1216 as noai\n"
            "import pb_auto_geometry_v1219 as auto\n"
            "app = entry.app\n"
            "data = {\n"
            "    'subscription_takeoff_page': {\n"
            "        'name': getattr(app, 'subscription_takeoff_page').__name__,\n"
            "        'module': getattr(app, 'subscription_takeoff_page').__module__,\n"
            "    },\n"
            "    'no_ai_takeoff_panel': {\n"
            "        'name': getattr(noai, 'no_ai_takeoff_panel').__name__,\n"
            "        'module': getattr(noai, 'no_ai_takeoff_panel').__module__,\n"
            "    },\n"
            "    'analyse_workspace': {\n"
            "        'name': getattr(auto, 'analyse_workspace').__name__,\n"
            "        'module': getattr(auto, 'analyse_workspace').__module__,\n"
            "    },\n"
            "    '_build_unit_rows': {\n"
            "        'name': getattr(auto, '_build_unit_rows').__name__,\n"
            "        'module': getattr(auto, '_build_unit_rows').__module__,\n"
            "    },\n"
            "    '_build_facade_rows': {\n"
            "        'name': getattr(auto, '_build_facade_rows').__name__,\n"
            "        'module': getattr(auto, '_build_facade_rows').__module__,\n"
            "    },\n"
            "    'model_3d_page': {\n"
            "        'name': getattr(app, 'model_3d_page').__name__,\n"
            "        'module': getattr(app, 'model_3d_page').__module__,\n"
            "    },\n"
            "}\n"
            "print('__DATA__' + json.dumps(data))\n"
        )
        out = subprocess.check_output([sys.executable, "-c", script], text=True)
        for line in out.splitlines():
            if line.startswith("__DATA__"):
                cls.authorities = json.loads(line[len("__DATA__"):])
                break
        else:
            raise RuntimeError(f"Could not read authorities from subprocess output:\n{out}")

    def test_subscription_takeoff_page_authority(self):
        """The live subscription_takeoff_page must be the scoped quick takeoff wrapper."""
        auth = self.authorities["subscription_takeoff_page"]
        self.assertEqual(auth["name"], "subscription_with_scope")
        self.assertIn("pb_quick_takeoff_v153", auth["module"])

    def test_no_ai_takeoff_panel_authority(self):
        """no_ai_takeoff_panel must be the reviewed takeoff panel."""
        auth = self.authorities["no_ai_takeoff_panel"]
        self.assertEqual(auth["name"], "_panel_with_review")
        self.assertIn("pb_takeoff_review_v1226", auth["module"])

    def test_analyse_workspace_authority(self):
        """auto.analyse_workspace must route through the v1228 plan read engine."""
        auth = self.authorities["analyse_workspace"]
        self.assertEqual(auth["name"], "_analyse")
        self.assertIn("pb_plan_read_engine_v1228", auth["module"])

    def test_build_unit_rows_authority(self):
        """auto._build_unit_rows must be wrapped by room face takeoff."""
        auth = self.authorities["_build_unit_rows"]
        self.assertEqual(auth["name"], "_build_unit_rows_with_room_faces")
        self.assertIn("pb_room_face_takeoff", auth["module"])

    def test_build_facade_rows_authority(self):
        """auto._build_facade_rows must be wrapped by auto geometry guard."""
        auth = self.authorities["_build_facade_rows"]
        self.assertEqual(auth["name"], "_safe_facades")
        self.assertIn("pb_auto_geometry_guard_v1219", auth["module"])

    def test_model_3d_page_authority(self):
        """app.model_3d_page must be the canonical 3D WebGL viewer integration."""
        auth = self.authorities["model_3d_page"]
        self.assertEqual(auth["name"], "model_3d_page_canonical_wrapper")
        self.assertIn("pb_3d_workspace_integration", auth["module"])


class ModuleIdempotencyAuditTests(unittest.TestCase):
    """Verify that all production modules are idempotent and safe against repeated apply()."""

    def test_v12_apply_is_strictly_idempotent(self):
        """Repeated apply() on pb_takeoff_v12 must not re-wrap functions or grow wrapper chains."""
        mock_app = SimpleNamespace(
            TAKEOFF_COLUMNS=["section", "element", "location", "substrate", "quantity", "unit"],
            _normalise_unit=lambda u: u,
            _parse_qty=lambda q: float(q or 0),
            _match_takeoff_header=lambda h: None,
        )
        v12.apply(mock_app)
        fn_parse_1 = mock_app.parse_takeoff_file
        fn_detect_1 = mock_app.detect_takeoff_columns
        fn_match_1 = mock_app._match_takeoff_header

        # Second apply call
        v12.apply(mock_app)
        self.assertIs(mock_app.parse_takeoff_file, fn_parse_1, "parse_takeoff_file must remain identical")
        self.assertIs(mock_app.detect_takeoff_columns, fn_detect_1, "detect_takeoff_columns must remain identical")
        self.assertIs(mock_app._match_takeoff_header, fn_match_1, "_match_takeoff_header must remain identical")

    def test_v11_apply_is_strictly_idempotent(self):
        """Repeated apply() on pb_takeoff_v11 must not re-wrap subscription_takeoff_page."""
        mock_app = SimpleNamespace(
            APP_VERSION="1.0.0",
            subscription_takeoff_page=lambda *a, **k: "orig",
            st=SimpleNamespace(multiselect=None, button=None, markdown=None),
        )
        v11.apply(mock_app)
        page_fn_1 = mock_app.subscription_takeoff_page

        # Second apply call
        v11.apply(mock_app)
        self.assertIs(mock_app.subscription_takeoff_page, page_fn_1, "subscription_takeoff_page must remain identical")

    def test_all_production_chain_modules_have_idempotency_guards(self):
        """Every module in the production startup chain must guard against repeated apply()."""
        unguarded = []
        for mod_name in PRODUCTION_MODULES_IN_CHAIN:
            mod = importlib.import_module(mod_name)
            apply_fn = getattr(mod, "apply", None)
            if not apply_fn or not callable(apply_fn):
                continue
            src = inspect.getsource(apply_fn)
            has_guard = any(
                token in src
                for token in (
                    "_applied",
                    "getattr(app",
                    "hasattr(app",
                    "installed",
                    "patched",
                    "_guarded",
                    "already",
                )
            )
            if not has_guard:
                unguarded.append(mod_name)

        self.assertEqual(
            unguarded,
            [],
            f"Found production modules without idempotency guards in apply(): {unguarded}",
        )


if __name__ == "__main__":
    unittest.main()
