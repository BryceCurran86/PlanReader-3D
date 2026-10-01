"""Tests for pb_dpc_substructure_customer_bridge (AG-11).

Validates:
1. Canonical 21-field core takeoff_rows contract adherence.
2. Fail-closed behaviour: no hallucinated quantities when drawing lacks explicit witness callout.
3. Positive witness resolution: source-backed callout bridges to verified takeoff row.
4. Database publication: idempotent replace without row accumulation.
"""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import fitz
import pytest

from pb_dpc_substructure_authority import (
    DPCSubstructureRecord,
    SubstructureFamily,
)
from pb_dpc_substructure_customer_bridge import (
    SOURCE_PREFIX,
    publish_substructure_takeoff_rows,
    resolve_pdf_substructure_records,
    resolve_workspace_substructure_takeoff_rows,
    substructure_record_to_takeoff_row,
)
import pb_takeoff_row_contract as takeoff_contract


def _draw_witness_dim(
    page: fitz.Page,
    *,
    x: float,
    y0: float,
    y1: float,
    text: str,
    witness_main: bool = True,
    witness_outer: bool = True,
) -> None:
    page.draw_line((x, y0), (x, y1))
    if witness_main:
        page.draw_line((x - 18, y0), (x + 18, y0))
    if witness_outer:
        page.draw_line((x - 18, y1), (x + 18, y1))
    page.insert_text((x + 5, (y0 + y1) / 2.0), text, fontsize=10, rotate=90)


def _build_test_substructure_pdf(
    *,
    label: str = "DPC",
    length_text: str = "4250",
    include_dim: bool = True,
) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=640, height=460)
    fx0, fy0 = 30.0, 30.0
    fx1, fy1 = fx0 + 280.0, fy0 + 280.0
    width, height = fx1 - fx0, fy1 - fy0
    page.draw_rect(fitz.Rect(fx0, fy0, fx1, fy1))
    page.insert_text((fx0 + 0.10 * width, fy1 - 8.0), "GROUND FLOOR PLAN", fontsize=10)

    label_x = fx0 + 0.30 * width
    label_y = fy0 + 0.40 * height
    page.insert_text((label_x, label_y), label, fontsize=10)
    label_cx = label_x + fitz.get_text_length(label, fontsize=10) / 2.0
    label_cy = label_y - 3.5

    if include_dim:
        y1 = label_cy - 4.0
        y0 = y1 - 36.0
        _draw_witness_dim(page, x=label_cx, y0=y0, y1=y1, text=length_text)

    data = doc.tobytes()
    doc.close()
    return data


class MockApp:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def local_connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self.local_connect()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER,
                file_name TEXT,
                path TEXT
            )
        """)
        cols = ", ".join(f"{col} TEXT" for col in takeoff_contract.CORE_FIELDS)
        conn.execute(f"CREATE TABLE IF NOT EXISTS takeoff_rows (id INTEGER PRIMARY KEY AUTOINCREMENT, {cols})")
        conn.commit()
        conn.close()

    def lquery(self, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        conn = self.local_connect()
        cur = conn.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def lexecute(self, sql: str, params: Sequence[Any] = ()) -> None:
        conn = self.local_connect()
        conn.execute(sql, params)
        conn.commit()
        conn.close()

    def now_stamp(self) -> str:
        return "2026-10-02T05:00:00Z"


def test_substructure_record_to_takeoff_row_contract():
    rec = DPCSubstructureRecord(
        record_id="rec-01",
        document_id="doc-01",
        revision_id="rev-01",
        source_sha256="abc123sha",
        snapshot_id="snap-01",
        page_id="1",
        viewport_id="",
        physical_run_id="run-dpc-01",
        family=SubstructureFamily.DPC_LENGTH,
        value=4.25,
        unit="m",
        dimension_chain_id="dim-chain-01",
        depth_dimension_chain_id=None,
        binding_status="source_bound",
    )
    row = substructure_record_to_takeoff_row(42, rec, now_stamp="2026-10-02T05:00:00Z")

    # Must have all 21 core fields
    vals = takeoff_contract.values_from_mapping(row, takeoff_contract.CORE_FIELDS)
    assert len(vals) == 21
    assert row["workspace_id"] == 42
    assert row["section"] == "Substructure"
    assert row["element"] == "Damp-proof course (DPC) run"
    assert row["quantity"] == 4.25
    assert row["unit"] == "lm"
    assert row["row_role"] == "dpc_substructure"
    assert row["source_page"] == "1"
    assert "dim-chain-01" in row["source_reference"]


def test_resolve_pdf_substructure_records_fail_closed():
    # Empty bytes fails closed
    assert resolve_pdf_substructure_records(b"") == []

    # PDF with generic text and rectangle but NO witness dimension fails closed
    pdf_bytes = _build_test_substructure_pdf(label="DPC", include_dim=False)
    records = resolve_pdf_substructure_records(pdf_bytes)
    assert records == []


def test_resolve_pdf_substructure_records_positive_witness():
    pdf_bytes = _build_test_substructure_pdf(label="DPC", length_text="4250", include_dim=True)
    records = resolve_pdf_substructure_records(pdf_bytes)
    assert len(records) >= 1
    dpc_rec = next(r for r in records if r.family == SubstructureFamily.DPC_LENGTH)
    assert dpc_rec.value == pytest.approx(4.25, rel=1e-2)
    assert dpc_rec.unit == "m"

    # Verify bridging to takeoff row maps unit 'm' -> 'lm'
    row = substructure_record_to_takeoff_row(1, dpc_rec)
    assert row["unit"] == "lm"
    assert row["quantity"] == 4.25


def test_publish_substructure_takeoff_rows_idempotent():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = str(Path(tmpdir) / "test.db")
        app = MockApp(db_file)
        pdf_path = str(Path(tmpdir) / "plan.pdf")

        pdf_bytes = _build_test_substructure_pdf(label="DPC", length_text="5600", include_dim=True)
        Path(pdf_path).write_bytes(pdf_bytes)

        app.lexecute(
            "INSERT INTO documents(workspace_id, file_name, path) VALUES(?,?,?)",
            (101, "plan.pdf", pdf_path),
        )

        # Initial publication
        count = publish_substructure_takeoff_rows(app, 101)
        assert count >= 1

        rows = app.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=?", (101,))
        assert len(rows) == count
        assert any(r["element"] == "Damp-proof course (DPC) run" and float(r["quantity"]) == 5.6 for r in rows)

        # Re-publication must replace previous rows cleanly (no accumulation)
        count2 = publish_substructure_takeoff_rows(app, 101)
        assert count2 == count
        rows2 = app.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=?", (101,))
        assert len(rows2) == count


def test_analyse_workspace_with_dpc_substructure():
    from test_auto_geometry_takeoff_row_contract import _workspace, _apply_production_chain
    import pb_auto_geometry_v1219 as auto

    with _workspace() as ws:
        pdf_bytes = _build_test_substructure_pdf(label="DPC", length_text="6400", include_dim=True)
        pdf_path = ws.root / "dpc_plan.pdf"
        pdf_path.write_bytes(pdf_bytes)
        ws.add_document(pdf_path)
        ws.add_page(1, "Floor Plan", "A101", "GROUND FLOOR PLAN DPC 6400")
        _apply_production_chain(ws.app)

        report = auto.analyse_workspace(ws.app, 1)
        assert "substructure_takeoff_rows" in report
        assert report["substructure_takeoff_rows"] >= 1

        rows = ws.app.lquery(
            "SELECT * FROM takeoff_rows WHERE workspace_id=1 AND source_reference LIKE ?",
            (SOURCE_PREFIX + "%",),
        )
        assert len(rows) == report["substructure_takeoff_rows"]
        assert any(r["element"] == "Damp-proof course (DPC) run" and float(r["quantity"]) == 6.4 for r in rows)
