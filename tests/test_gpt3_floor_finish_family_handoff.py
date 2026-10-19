"""GPT3 source-positive floor-finish family customer receipt integration.

This exercises the real canonical-floor/finish seal and customer projector, not
benchmark identities, expected areas, inferred surface finishes or source PDFs.
"""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

from pb_combine_source_closed_runs import load_verified_sealed_run
from pb_customer_output_verification import verify_sealed_customer_output
from pb_live_floor_finish_customer_projection import (
    project_live_floor_finish_customer_rows,
)
import tools.run_source_closed_project_handoff as handoff
from test_live_floor_finish_area_source_closed_export import _claim


def _surface_handoff(tmp_path: Path, monkeypatch, *, claim=None):
    claim = _claim() if claim is None else claim
    # Source scope and SHA are inherited from the synthetic producer fixture.
    # Do not pretend the dummy PDF was a real authenticated original.
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"synthetic-not-an-original-construction-source")
    monkeypatch.setattr(handoff, "_source_page_scopes", lambda *_: ((0,), (), 1))
    monkeypatch.setattr(handoff, "_sha256", lambda *_: "a" * 64)
    monkeypatch.setattr(
        handoff, "collect_live_physical_net_wall_claim",
        lambda *_args, **_kwargs: claim,
    )
    monkeypatch.setattr(handoff, "publish_live_floor_area_quantities", lambda *_: ())
    monkeypatch.setattr(
        handoff, "collect_live_ceiling_lining_claims",
        lambda *_a, **_k: SimpleNamespace(
            canonical_ceilings=(), quantity_evidence=(),
        ),
    )
    monkeypatch.setattr(handoff, "publish_live_ceiling_area_quantities", lambda *_: ())
    result = handoff.generate_project_handoff(
        pdf_path=pdf, project_id="project-1", workspace_id=1,
        output_dir=tmp_path / "out", family_group="surfaces",
    )
    return result


def test_real_floor_finish_family_seal_has_distinct_verified_customer_receipt(
    tmp_path, monkeypatch,
):
    summary = _surface_handoff(tmp_path, monkeypatch)
    assert summary["status"] == "sealed"
    assert summary["family_counts"]["floor_finish_area"] == 1
    assert summary["floor_finish_customer_first_gate"] == "FAMILY_VERIFIED"
    assert summary["floor_finish_customer_rows_verified"] is True
    assert summary["floor_finish_customer_row_count"] == 1
    # A single finish family is NOT a verified complete project/customer run.
    assert summary["customer_rows_verified"] is False
    assert summary["benchmark_score_granted"] is False
    customer_path = Path(summary["floor_finish_customer_rows_file"])
    rows = json.loads(customer_path.read_text(encoding="utf-8"))
    run = load_verified_sealed_run(
        Path(summary["family_run_files"]["floor_finish_area"])
    )
    assert rows[0]["quantity_id"] == run.quantities[0].quantity_id
    assert rows[0]["quantity_family"] == "floor_finish_area"
    assert rows[0]["quantity_status"] == "To review"
    assert verify_sealed_customer_output(run, rows).verified_quantity_ids == (
        run.quantities[0].quantity_id,
    )


def test_duplicate_customer_rows_never_claim_verified_family(
    tmp_path, monkeypatch,
):
    claim = _claim()
    legitimate = project_live_floor_finish_customer_rows(
        claim, workspace_id=1, project_id="project-1",
    )
    monkeypatch.setattr(
        handoff, "project_live_floor_finish_customer_rows",
        lambda *_args, **_kwargs: (legitimate[0], legitimate[0]),
    )
    summary = _surface_handoff(tmp_path, monkeypatch, claim=claim)
    assert summary["status"] == "sealed"  # independent source seal preserved
    assert summary["floor_finish_customer_rows_verified"] is False
    assert summary["customer_rows_verified"] is False
    assert summary["floor_finish_customer_rows_file"] is None
    assert summary["floor_finish_customer_row_count"] == 0
    assert "FLOOR_FINISH_CUSTOMER_UNVERIFIED" in summary[
        "floor_finish_customer_first_gate"
    ]
    assert "floor_finish_customer_projection_unverified" in summary[
        "claim_reason_codes"
    ]
    assert Path(summary["family_run_files"]["floor_finish_area"]).is_file()
    assert not (tmp_path / "out" / "verified_floor_finish_customer_rows.json").exists()


def test_no_floor_finish_does_not_invent_customer_rows(tmp_path, monkeypatch):
    claim = replace(_claim(), floor_finish_quantity_evidence=())
    summary = _surface_handoff(tmp_path, monkeypatch, claim=claim)
    assert summary["floor_finish_customer_first_gate"] == "NO_SEALED_FLOOR_FINISH"
    assert summary["floor_finish_customer_rows_verified"] is False
    assert summary["floor_finish_customer_rows_file"] is None
    assert summary["floor_finish_customer_row_count"] == 0
    assert summary["family_counts"]["floor_finish_area"] == 0
