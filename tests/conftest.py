"""Shared test fixtures for PB PlanReader tests.

Provides reusable database shims, fake bridges, and helper functions
that are currently duplicated across 18+ test files.
"""

from __future__ import annotations

import json
import os
import sqlite3
import types
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest


# Private construction customer PDFs must remain outside the repository.
# The public CI path MAY deliberately skip tests which cannot run without
# those privately provisioned source bytes. All synthetic/adversarial tests
# in the same files still run. Dedicated original-SHA workflows never enable
# this flag, and MUST fail if the original PDF is unavailable.
_MARYBOROUGH_ORIGINAL_NAME = "Arch_Combined_Maryborough_Service_Station.pdf"
_PRIVATE_SOURCE_PUBLIC_CI_POLICY = "skip_missing_in_public_ci"


def _public_ci_source_policy_enabled() -> bool:
    policy = os.environ.get("PLANREADER_PRIVATE_ORIGINAL_POLICY", "")
    if policy and policy != _PRIVATE_SOURCE_PUBLIC_CI_POLICY:
        raise pytest.UsageError("invalid_private_original_source_ci_policy")
    return (
        policy == _PRIVATE_SOURCE_PUBLIC_CI_POLICY
        and not (
            Path.cwd() / "documents" / "sources" / _MARYBOROUGH_ORIGINAL_NAME
        ).is_file()
    )


def _code_uses_original_source(
    function,
    *,
    max_depth: int = 4,
    _seen: Optional[set[int]] = None,
) -> bool:
    """Static, bounded source-dependency scan; never execute a test/helper.

    Check actual source-variable references, source filename literals and
    directly called module-local helpers. Do not skip synthetic tests just
    because their test *module* contains a private ORIGINAL/PDF constant.
    Ambiguous or unrecognized dependencies are NOT skipped, so CI fails
    visibly instead of hiding an unexpected original-source requirement.
    """
    if max_depth < 0:
        return False
    code = getattr(function, "__code__", None)
    if not isinstance(code, types.CodeType):
        return False
    seen = set() if _seen is None else _seen
    if id(code) in seen:
        return False
    seen.add(id(code))
    globals_map = getattr(function, "__globals__", {})
    for constant in code.co_consts:
        if isinstance(constant, str) and _MARYBOROUGH_ORIGINAL_NAME in constant:
            return True
        if isinstance(constant, types.CodeType):
            if any(
                isinstance(value, str) and _MARYBOROUGH_ORIGINAL_NAME in value
                for value in constant.co_consts
            ):
                return True
    for name in code.co_names:
        val = globals_map.get(name)
        if isinstance(val, Path) and val.name == _MARYBOROUGH_ORIGINAL_NAME:
            return True
    if max_depth == 0:
        return False
    for name in code.co_names:
        val = globals_map.get(name)
        if (
            callable(val)
            and getattr(val, "__module__", None)
            == getattr(function, "__module__", None)
            and _code_uses_original_source(
                val, max_depth=max_depth - 1, _seen=seen,
            )
        ):
            return True
    return False


def _test_requires_missing_original_pdf(item) -> bool:
    if _code_uses_original_source(getattr(item, "function", None)):
        return True
    info = getattr(item, "_fixtureinfo", None)
    named = getattr(info, "name2fixturedefs", {}) or {}
    for fixture_name in getattr(item, "fixturenames", ()):
        for definition in named.get(fixture_name, ()):
            if _code_uses_original_source(getattr(definition, "func", None)):
                return True
    return False


def pytest_report_header(config):
    if _public_ci_source_policy_enabled():
        return (
            "PRIVATE PDF ABSENT: public CI skips only tests whose source-byte "
            "dependency is proven; this is NOT an original-PDF test pass"
        )


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


def pytest_collection_modifyitems(items):
    if _public_ci_source_policy_enabled():
        for item in items:
            if _test_requires_missing_original_pdf(item):
                item.add_marker(pytest.mark.skip(
                    reason=(
                        "PRIVATE ORIGINAL SOURCE UNAVAILABLE in public CI: "
                        "not a passing original-source verification; "
                        "run this test with SHA-verified private source"
                    ),
                ))
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
