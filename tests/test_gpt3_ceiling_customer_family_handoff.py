"""End-to-end source-neutral ceiling-only customer parity; no V2 score claims."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from pb_combine_source_closed_runs import load_verified_sealed_run
from pb_customer_output_verification import verify_sealed_customer_output
from pb_live_ceiling_customer_projection import project_live_ceiling_customer_rows
import tools.run_source_closed_project_handoff as handoff
from test_live_ceiling_lining_source_closed_export import (
    _claim as _new_claim, _quantity as _new_quantity,
)
from test_live_ceiling_area_quantity_publication import _result as _legacy_result


def _run(tmp_path: Path, monkeypatch, *, claim, legacy=None):
    source = tmp_path / "synthetic.pdf"
    source.write_bytes(b"synthetic test -- NOT a source-authenticated PDF")
    monkeypatch.setattr(handoff, "_source_page_scopes", lambda *_: ((0,), (), 1))
    monkeypatch.setattr(handoff, "_sha256", lambda *_: "a" * 64)
    monkeypatch.setattr(
        handoff, "collect_live_physical_net_wall_claim",
        lambda *_a, **_k: claim,
    )
    monkeypatch.setattr(handoff, "publish_live_floor_area_quantities", lambda *_: ())
    monkeypatch.setattr(
        handoff, "collect_live_ceiling_lining_claims",
        lambda *_a, **_k: legacy if legacy is not None else replace(
            _legacy_result(), canonical_ceilings=(),
            quantity_evidence=(), claims=(),
        ),
    )
    if legacy is None:
        monkeypatch.setattr(handoff, "publish_live_ceiling_area_quantities", lambda *_: ())
    return handoff.generate_project_handoff(
        pdf_path=source, project_id="project-1", workspace_id=1,
        output_dir=tmp_path / "out", family_group="surfaces",
    )


def test_new_original_ceiling_seal_reaches_exact_family_customer_receipt(
    tmp_path, monkeypatch,
):
    summary = _run(tmp_path, monkeypatch, claim=_new_claim(_new_quantity()))
    assert summary["status"] == "sealed"
    assert summary["family_counts"]["ceiling_area"] == 1
    assert summary["ceiling_authority_path"] == "cross_view_room_area_plus_rcp_finish"
    assert summary["ceiling_customer_first_gate"] == "FAMILY_VERIFIED"
    assert summary["ceiling_customer_rows_verified"] is True
    assert summary["ceiling_customer_row_count"] == 1
    assert summary["customer_rows_verified"] is False
    assert summary["benchmark_score_granted"] is False
    run = load_verified_sealed_run(Path(summary["family_run_files"]["ceiling_area"]))
    rows = json.loads(Path(summary["ceiling_customer_rows_file"]).read_text())
    assert rows[0]["quantity_id"] == run.quantities[0].quantity_id
    assert rows[0]["quantity_family"] == "ceiling_lining"
    assert rows[0]["quantity_status"] == "To review"
    assert verify_sealed_customer_output(run, rows).verified_quantity_ids == (
        run.quantities[0].quantity_id,
    )


def test_legacy_source_positive_ceiling_reaches_own_verified_customer_path(
    tmp_path, monkeypatch,
):
    claim = _new_claim(_new_quantity())
    claim = replace(claim, ceiling_lining_quantity_evidence=(), canonical_ceilings=())
    summary = _run(tmp_path, monkeypatch, claim=claim, legacy=_legacy_result())
    assert summary["family_counts"]["ceiling_area"] == 1
    assert summary["ceiling_authority_path"] == "legacy_same_scope_ceiling_lining"
    assert summary["ceiling_customer_rows_verified"] is True
    assert summary["ceiling_customer_row_count"] == 1
    run = load_verified_sealed_run(Path(summary["family_run_files"]["ceiling_area"]))
    rows = json.loads(Path(summary["ceiling_customer_rows_file"]).read_text())
    assert verify_sealed_customer_output(run, rows).verified_quantity_ids == (
        run.quantities[0].quantity_id,
    )
    assert summary["customer_rows_verified"] is False


def test_duplicate_customer_projection_withholds_all_verified_ceiling_output(
    tmp_path, monkeypatch,
):
    claim = _new_claim(_new_quantity())
    source_rows = project_live_ceiling_customer_rows(
        claim, workspace_id=1, project_id="project-1",
    )
    monkeypatch.setattr(
        handoff, "project_live_ceiling_customer_rows",
        lambda *_a, **_k: (source_rows[0], source_rows[0]),
    )
    summary = _run(tmp_path, monkeypatch, claim=claim)
    assert summary["status"] == "sealed"
    assert summary["ceiling_customer_rows_verified"] is False
    assert summary["ceiling_customer_row_count"] == 0
    assert summary["ceiling_customer_rows_file"] is None
    assert "CEILING_CUSTOMER_UNVERIFIED" in summary["ceiling_customer_first_gate"]
    # Optional customer failure must not rewrite the original source gates.
    assert summary["claim_reason_codes"] == list(claim.reason_codes)
    assert Path(summary["family_run_files"]["ceiling_area"]).is_file()
    assert not (tmp_path / "out" / "verified_ceiling_customer_rows.json").exists()


def test_unsealed_ceiling_does_not_invent_customer_receipt(tmp_path, monkeypatch):
    claim = replace(
        _new_claim(_new_quantity()),
        ceiling_lining_quantity_evidence=(), canonical_ceilings=(),
    )
    summary = _run(tmp_path, monkeypatch, claim=claim)
    assert summary["family_counts"]["ceiling_area"] == 0
    assert summary["ceiling_customer_first_gate"] == "NO_SEALED_CEILING"
    assert summary["ceiling_customer_rows_verified"] is False
    assert summary["ceiling_customer_rows_file"] is None
    assert summary["ceiling_customer_row_count"] == 0
