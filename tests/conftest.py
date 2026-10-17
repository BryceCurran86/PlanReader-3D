"""Shared test fixtures for PB PlanReader tests.

Provides reusable database shims, fake bridges, and helper functions
that are currently duplicated across 18+ test files.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest


# These three historical Phase 5 tests encode the now-rejected assumption that
# an unregistered/missing "Ground" storey implicitly proves global elevation
# Z=0. Phase 5M intentionally removes that assumption. Strict xfail is used so
# the suite will fail if the unsafe legacy behaviour ever returns. Replacement
# positive/negative roof-Z coverage lives in test_phase5m_roof_closure.py.
_PHASE5M_SUPERSEDED_UNSAFE_ROOF_TESTS = {
    "test_section_14_legacy_27m_roof_z_fencing",
    "test_phase5j_roof_form_and_objective_z_proof",
    "test_phase5k_roof_z_reproduction_verification",
}

# This historical regression expected a calibrated floor carrying only weak
# sheet text such as "Ground Floor" to be discarded completely. The final
# contract retains valid metric XY under the unresolved/review storey while
# withholding takeoff authority. A strict xfail makes the suite fail if the old
# drop-on-unknown-storey behaviour returns. Replacement coverage lives in
# test_phase5m_unresolved_floor_retention.py.
_PHASE5M_SUPERSEDED_FLOOR_DROP_TESTS = {
    "test_free_form_page_level_is_not_floor_storey_authority",
}


# Real original-source tests execute only in the authorised owner's workspace.
# All entries below have an observed direct dependency on the original private
# Maryborough PDF. Keep the synthetic source-negative tests OUT of this list.
# Do not upload the original PDF to make hosted GitHub CI green.
_OWNER_ONLY_MARYBOROUGH_TESTS = frozenset({
    "tests/test_gpt2_a120_multipath_frame_whatif_shadow.py::test_source_original_a120_candidates_preserve_both_false_and_real_frames",
    "tests/test_gpt2_a120_opposed_source_wall_ink.py::test_original_a120_black_native_top_double_wall_is_exact_contiguous_source",
    "tests/test_gpt2_a120_opposed_source_wall_ink.py::test_original_a120_left_continuous_double_wall_has_four_independent_segments",
    "tests/test_gpt2_a120_opposed_source_wall_ink.py::test_original_bottom_window_gaps_are_not_cleared_by_other_wall_segments",
    "tests/test_gpt2_native_a503_stepped_partition_shadow.py::test_original_a503_m_amb_f_amb_divider_retains_multiple_competing_faces",
    "tests/test_gpt2_native_compound_sheet_labels.py::test_native_production_source_p24_to_p27_all_own_sheet_numbers",
    "tests/test_gpt2_native_compound_sheet_labels.py::test_source_page_bytes_are_not_rewritten_by_title_reader",
    "tests/test_gpt2_native_multipath_cad_grid_source_shadow.py::test_original_a120_true_multipath_cad_schedule_component_survives",
    "tests/test_gpt2_native_named_plan_caption_shadow.py::test_real_original_carries_all_four_named_amendities_source_local_plans",
    "tests/test_gpt2_original_crosssheet_native_ink_registration.py::test_original_p7_p11_many_source_ink_witnesses_and_competing_transforms",
    "tests/test_gpt2_original_ft2_ft3_sameblock_schedule_source.py::test_original_ft2_ft3_have_same_native_source_block_floor_rows_and_real_marks",
    "tests/test_gpt2_original_ft2_ft3_sameblock_schedule_source.py::test_original_ft2_schedule_manufacturer_subtype_size_same_native_block",
    "tests/test_gpt2_original_ft2_ft3_sameblock_schedule_source.py::test_original_ft3_schedule_separate_dura_grey_600_square_from_ft2",
    "tests/test_gpt2_original_ft2_ft3_sameblock_schedule_source.py::test_wall_tile_wt1_original_printed_800x400_not_a_floor_material",
    "tests/test_gpt2_original_rotated_text_first_gate_delta_shadow.py::test_six_original_ft3_native_marks_and_schedule_keep_competing_text_gates",
    "tests/test_gpt2_original_rotated_text_first_gate_delta_shadow.py::test_wrong_source_sha_and_native_addresses_never_alias_a_word",
    "tests/test_gpt2_original_window_elevation_title_lineage.py::test_original_p7_to_a601_p29_six_codes_four_true_elevation_titles",
    "tests/test_gpt2_original_window_elevation_title_lineage.py::test_original_three_codes_one_group_does_not_imply_three_frame_widths",
    "tests/test_gpt2_pdf_rotated_native_clip_parity_shadow.py::test_negative_mismatched_source_and_malformed_pages_abstain",
    "tests/test_gpt2_pdf_rotated_native_clip_parity_shadow.py::test_original_six_rotated_maryborough_pages_with_real_clip_stacks",
    "tests/test_gpt2_pwd_native_figure_wall_witness_chain.py::test_original_a502_pwd_3570_and_2200_have_unclosed_witness_extensions",
    "tests/test_gpt2_semantic_frame_acceptance_shadow.py::test_original_source_a120_semantic_frame_vs_rotated_ceiling_band",
    "tests/test_gpt2_six_original_native_source_gates.py::test_1_original_ft3_five_plan_marks_plus_one_schedule",
    "tests/test_gpt2_six_original_native_source_gates.py::test_2_original_a120_grid_ipf1_cld3_schedule_vs_plan_candidates",
    "tests/test_gpt2_six_original_native_source_gates.py::test_3_original_food_pos_three_native_paths_one_geometrical_divider",
    "tests/test_gpt2_six_original_native_source_gates.py::test_4_original_freezer_inside_wall_not_external_shell",
    "tests/test_gpt2_six_original_native_source_gates.py::test_5_original_a501_figured_5044_spans_multiple_named_sections",
    "tests/test_gpt2_six_original_native_source_gates.py::test_6_pwd_same_label_p7_p26_is_not_physical_crosssheet_room_join",
    "tests/test_gpt2_source_connected_semantic_cell_shadow.py::test_original_a120_false_table_rectangles_do_not_form_shared_cell_lattice",
    "tests/test_gpt2_source_dimension_face_competitors_shadow.py::test_original_pwd_figure_axis_agrees_but_actual_witness_does_not_intersect",
    "tests/test_gpt2_source_native_dimension_stroke_shadow.py::test_original_a502_both_3570_and_2200_native_end_tick_source_pairs",
    "tests/test_gpt2_source_native_dimension_stroke_shadow.py::test_original_page_a502_figured_3570_2200_native_lineage_recovered",
    "tests/test_gpt2_source_viewport_coverage_shadow.py::test_original_maryborough_p9_preserves_missing_sales_grid_and_rivals",
    "tests/test_gpt2_symbol_font_source_code_shadow.py::test_exact_native_word_address_required_and_wrong_pdf_rejected",
    "tests/test_gpt2_symbol_font_source_code_shadow.py::test_missing_original_native_word_does_not_retarget_nearest",
    "tests/test_gpt2_symbol_font_source_code_shadow.py::test_wrong_page_produces_no_false_positive_source_font",
    "tests/test_gpt2_symbol_source_optin_native_word_integrity.py::test_default_classifier_unchanged_and_explicit_bool_required",
    "tests/test_gpt2_symbol_source_optin_native_word_integrity.py::test_non_true_type_missing_font_and_invalid_glyph_must_abstain",
})
_OWNER_MARYBOROUGH_PDF = (
    Path(__file__).resolve().parents[1]
    / "documents/sources/Arch_Combined_Maryborough_Service_Station.pdf"
)


def pytest_collection_modifyitems(items):
    # Explicitly skip ONLY the source-bound tests when private original bytes
    # are absent; all other public-runner tests, including original-absence
    # fail-closed regressions, remain mandatory.
    owner_source_absent = not _OWNER_MARYBOROUGH_PDF.is_file()
    for item in items:
        node = item.nodeid.split("::")
        key = node[0] + "::" + (node[1].split("[", 1)[0] if len(node)>1 else "")
        if owner_source_absent and key in _OWNER_ONLY_MARYBOROUGH_TESTS:
            item.add_marker(pytest.mark.skip(
                reason="Owner-only original Maryborough PDF not distributed in public GitHub CI; run on authorised source machine",
            ))
    for item in items:
    for item in items:
        if item.name in _PHASE5M_SUPERSEDED_UNSAFE_ROOF_TESTS:
            item.add_marker(pytest.mark.xfail(
                strict=True,
                reason=(
                    "Superseded by Phase 5M zero-made-up-data contract: a Ground label "
                    "without objective storey elevation cannot establish absolute roof Z"
                ),
            ))
        elif item.name in _PHASE5M_SUPERSEDED_FLOOR_DROP_TESTS:
            item.add_marker(pytest.mark.xfail(
                strict=True,
                reason=(
                    "Superseded by Phase 5M unresolved-storey contract: valid calibrated XY "
                    "is retained under the unresolved review level, never discarded merely "
                    "because free-form sheet text is not storey authority"
                ),
            ))


def make_temp_db() -> sqlite3.Connection:
    """Create an in-memory SQLite database with the PlanReader schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            jobhub_id INTEGER,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL,
            file_name TEXT,
            path TEXT,
            sha256 TEXT,
            page_count INTEGER DEFAULT 0,
            extracted_text TEXT,
            uploaded_at TEXT,
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            workspace_id INTEGER NOT NULL,
            page_no INTEGER,
            page_label TEXT,
            page_type TEXT,
            text_content TEXT,
            FOREIGN KEY(document_id) REFERENCES documents(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            workspace_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT,
            updated_at TEXT,
            UNIQUE(workspace_id, key)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS takeoff_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL,
            page_no INTEGER,
            drawing TEXT,
            section TEXT,
            element TEXT,
            unit TEXT,
            quantity REAL DEFAULT 0,
            scale TEXT,
            notes TEXT,
            status TEXT DEFAULT 'To measure',
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
        )
    """)
    conn.execute("INSERT INTO workspaces (id, name) VALUES (1, 'test')")
    conn.commit()
    return conn


def lquery(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    """Execute a query and return list of dicts (mimics app.lquery)."""
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def lexecute(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> None:
    """Execute a statement (mimics app.lexecute)."""
    conn.execute(sql, params)
    conn.commit()


class FakeBridge:
    """Fake JobHub bridge for testing without Postgres."""

    def __init__(self, tables: Optional[Dict[str, List[Dict]]] = None):
        self._tables = tables or {}
        self._calls: List[tuple] = []

    def table_names(self) -> List[str]:
        return list(self._tables.keys())

    def columns(self, table: str) -> List[str]:
        if table in self._tables and self._tables[table]:
            return list(self._tables[table][0].keys())
        return []

    def query(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        self._calls.append(("query", sql, params))
        # Simple in-memory fake: return empty for most queries
        return []

    def execute(self, sql: str, params: tuple = ()) -> None:
        self._calls.append(("execute", sql, params))


class FakeApp:
    """Minimal fake app object for testing module apply() functions."""

    def __init__(self):
        self.st = MagicMock()
        self.local_connect = make_temp_db
        self.now_stamp = lambda: "2026-01-01 00:00:00"
        self._applied: List[str] = []

    def __getattr__(self, name: str):
        # Allow dynamic attribute access for monkey-patched modules
        if name.startswith("_"):
            raise AttributeError(name)
        return MagicMock()
