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

# C1/C5 deliberately make public wall-length FIRM unavailable until the
# canonical physical-wall and viewport/scale enumerators expose independently
# content-addressed upstream snapshot payloads.  These historical tests predate
# that trust boundary and either require public FIRM/value output or require a
# deeper downstream blocker that is now intentionally pre-empted by the
# upstream completeness gate.
#
# Keep their original assertions intact as strict xfails.  This is not a skip
# or production bypass: an unexpected pass is XPASS(strict) and fails CI.  The
# markers must be removed once a real upstream snapshot producer is wired so
# the original publication assertions execute again.  New C1/C4/C5 commitment
# attacks are NOT listed here and must pass normally.
_COMPLETENESS_UPSTREAM_SNAPSHOT_PRODUCER_REQUIRED = frozenset(
    {
        # tests/test_completeness_authority_attacks.py
        "tests/test_completeness_authority_attacks.py::test_authentic_singleton_baseline_can_reach_firm",
        "tests/test_completeness_authority_attacks.py::test_c1_hidden_same_viewport_scale_competitor_cannot_leave_firm",
        "tests/test_completeness_authority_attacks.py::test_c1_omitted_admitted_scale_candidate_blocks",
        "tests/test_completeness_authority_attacks.py::test_c1_explicit_evidenced_scale_exclusion_allows_remaining_proven_scale",
        "tests/test_completeness_authority_attacks.py::test_c1_conflict_monotonicity_never_strengthens_authority",
        "tests/test_completeness_authority_attacks.py::test_c5_explicit_evidenced_exclusion_allows_unrelated_admitted_wall",
        "tests/test_completeness_authority_attacks.py::test_c5_candidate_outside_local_viewport_does_not_poison_local_scope",
        "tests/test_completeness_authority_attacks.py::test_c5_conflict_addition_monotonicity_never_strengthens",
        # tests/test_wall_length_authority_remediation_v3.py
        "tests/test_wall_length_authority_remediation_v3.py::TestBlockerRegressions::test_blocker1_page_viewports_path_derives_instead_of_trusting_caller_bindings",
        "tests/test_wall_length_authority_remediation_v3.py::TestBlockerRegressions::test_blocker6_direct_single_wall_call_requires_a_real_equivalence_argument",
        "tests/test_wall_length_authority_remediation_v3.py::TestBlockerRegressions::test_blocker7_generic_figured_dimension_alone_publishes_firm",
        "tests/test_wall_length_authority_remediation_v3.py::TestAuthorityMonotonicity::test_adding_competing_eligible_scale_cannot_preserve_firm",
        "tests/test_wall_length_authority_remediation_v3.py::TestAuthorityMonotonicity::test_removing_current_snapshot_proof_cannot_preserve_firm",
        "tests/test_wall_length_authority_remediation_v3.py::TestAuthorityMonotonicity::test_adding_same_id_changed_atom_cannot_preserve_firm",
        "tests/test_wall_length_authority_remediation_v3.py::TestAuthorityMonotonicity::test_adding_ambiguous_physical_competitor_cannot_preserve_firm",
        "tests/test_wall_length_authority_remediation_v3.py::TestAuthorityMonotonicity::test_direct_single_wall_path_cannot_bypass_publication_gate",
        "tests/test_wall_length_authority_remediation_v3.py::TestAuthorityMonotonicity::test_adding_generic_figured_dimension_cannot_create_firm",
        "tests/test_wall_length_authority_remediation_v3.py::TestAuthorityMonotonicity::test_duplicate_identical_evidence_does_not_strengthen",
        # tests/test_wall_length_quantity.py
        "tests/test_wall_length_quantity.py::test_scaled_wall_length_emits_firm_quantity",
        "tests/test_wall_length_quantity.py::test_translation_is_metamorphically_invariant",
        "tests/test_wall_length_quantity.py::test_rotation_is_metamorphically_invariant",
        "tests/test_wall_length_quantity.py::test_figured_dimension_is_authoritative_when_scale_absent",
        "tests/test_wall_length_quantity.py::test_stale_scale_causes_abstention_not_old_length_reuse",
        "tests/test_wall_length_quantity.py::test_reversed_and_rechunked_walls_cannot_publish_two_physical_quantities",
        "tests/test_wall_length_quantity.py::test_paired_face_and_centerline_cannot_both_publish",
        "tests/test_wall_length_quantity.py::test_same_path_different_duplicated_native_ids_cannot_publish_twice",
        "tests/test_wall_length_quantity.py::test_rechunk_equivalent_geometry_keeps_one_physical_quantity_count",
        # tests/test_wall_linear_authority_bridge.py
        "tests/test_wall_linear_authority_bridge.py::test_trusted_wall_and_firm_scale_publish_linear_quantity",
        "tests/test_wall_linear_authority_bridge.py::test_reverse_and_rechunk_keep_length",
        "tests/test_wall_linear_authority_bridge.py::test_thickness_change_alone_does_not_alter_length",
        "tests/test_wall_linear_authority_bridge.py::test_height_or_stored_length_alone_does_not_alter_length",
        "tests/test_wall_linear_authority_bridge.py::test_shuffled_batch_is_deterministic",
        "tests/test_wall_linear_authority_bridge.py::test_scale_from_another_page_cannot_leak",
        "tests/test_wall_linear_authority_bridge.py::test_unbound_scale_cannot_leak_across_viewports_on_same_page",
        "tests/test_wall_linear_authority_bridge.py::test_provisional_thickness_does_not_block_length_and_is_not_invented",
        "tests/test_wall_linear_authority_bridge.py::test_adding_conflict_cannot_leave_firm_length",
        "tests/test_wall_linear_authority_bridge.py::test_firm_path_reconciles_complete_binding_set_not_caller_preferred",
    }
)


def pytest_collection_modifyitems(items):
    completeness_marker = pytest.mark.xfail(
        strict=True,
        reason=(
            "requires real content-addressed canonical graph/viewport snapshot "
            "producer; public wall-length authority intentionally fails closed"
        ),
    )
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
        if item.nodeid in _COMPLETENESS_UPSTREAM_SNAPSHOT_PRODUCER_REQUIRED:
            item.add_marker(completeness_marker)


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