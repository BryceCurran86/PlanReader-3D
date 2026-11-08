"""Real family seal/customer integration; no benchmark or original PDFs."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from pb_combine_source_closed_runs import load_verified_sealed_run
from pb_customer_output_verification import verify_sealed_customer_output
from pb_live_floor_area_customer_projection import project_live_floor_area_customer_rows
from pb_live_floor_finish_customer_projection import project_live_floor_finish_customer_rows
from tests.test_gpt1_floor_original_room_ring_source_seal import _claim as floor_claim
from tests.test_live_floor_finish_area_source_closed_export import _claim as finish_claim
from tests.test_live_ceiling_lining_source_closed_export import (
    _claim as ceiling_claim, _quantity as ceiling_quantity,
)
from tests.test_live_ceiling_area_quantity_publication import _result as legacy_ceiling_result
from tests.test_gpt1_source_closed_opening_metric_axis_claim_handoff import _claim as axis_claim
from tests.test_live_opening_area_quantity_publication import _composition
from tests.test_gpt1_live_original_opening_metric_axes import _figured_with_explicit_axes
from tools import run_source_closed_project_handoff as handoff


def _run(tmp_path, monkeypatch, claim, *, family="all"):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"synthetic source scope -- not an original PDF")
    monkeypatch.setattr(handoff, "_source_page_scopes", lambda *_: ((0,), (), 1))
    monkeypatch.setattr(handoff, "_sha256", lambda *_: "a" * 64)
    monkeypatch.setattr(handoff, "collect_live_physical_net_wall_claim", lambda *_a, **_k: claim)
    monkeypatch.setattr(handoff, "collect_live_ceiling_lining_claims", lambda *_a, **_k: replace(legacy_ceiling_result(), canonical_ceilings=(), quantity_evidence=(), claims=()))
    monkeypatch.setattr(handoff, "publish_live_ceiling_area_quantities", lambda *_: ())
    return handoff.generate_project_handoff(
        pdf_path=source, project_id="project-1", workspace_id=1,
        output_dir=tmp_path / "out", family_group=family,
    )


def _mixed_claim():
    finish = finish_claim()
    ceiling = ceiling_claim(ceiling_quantity())
    return replace(
        finish, canonical_rooms=(
            replace(floor_claim().canonical_rooms[0], physical_room_id="finish-physical-room"),
            *ceiling.canonical_rooms,
        ),
        canonical_ceilings=ceiling.canonical_ceilings,
        ceiling_lining_quantity_evidence=ceiling.ceiling_lining_quantity_evidence,
    )


@pytest.mark.parametrize("kind", ("floor", "mixed"))
def test_all_mode_exports_exact_existing_family_customer_union(tmp_path, monkeypatch, kind):
    claim = replace(floor_claim(), floor_finish_quantity_evidence=()) if kind == "floor" else _mixed_claim()
    summary = _run(tmp_path, monkeypatch, claim)
    assert summary["status"] == "sealed"
    assert summary["customer_rows_verified"] is True
    assert summary["full_project_customer_first_gate"] == "PROJECT_VERIFIED"
    sealed = load_verified_sealed_run(Path(summary["combined_run_file"]))
    rows = json.loads(Path(summary["customer_rows_file"]).read_text())
    verified = verify_sealed_customer_output(sealed, rows)
    assert len(rows) == len(sealed.quantities) == (1 if kind == "floor" else 2)
    assert set(verified.verified_quantity_ids) == {q.quantity_id for q in sealed.quantities}
    assert summary["verified_customer_row_count"] == len(rows)
    assert summary["benchmark_score_granted"] is False


@pytest.mark.parametrize("corruption", ("missing", "duplicate", "foreign", "value", "manual_extra"))
def test_invalid_floor_projection_preserves_source_seal_without_customer_claim(
    tmp_path, monkeypatch, corruption,
):
    claim = replace(floor_claim(), floor_finish_quantity_evidence=())
    original = project_live_floor_area_customer_rows(claim, workspace_id=1, project_id="project-1")
    row = dict(original[0])
    if corruption == "missing":
        rows = ()
    elif corruption == "duplicate":
        rows = (row, row)
    elif corruption == "manual_extra":
        rows = (row, {"element": "manual extra"})
    else:
        row["quantity_id" if corruption == "foreign" else "quantity"] = "foreign" if corruption == "foreign" else 999
        rows = (row,)
    monkeypatch.setattr(handoff, "project_live_floor_area_customer_rows", lambda *_a, **_k: rows)
    summary = _run(tmp_path, monkeypatch, claim)
    assert summary["status"] == "sealed"
    assert summary["customer_rows_verified"] is False
    assert summary["customer_rows_file"] is None
    assert summary["verified_customer_row_count"] == 0
    assert summary["full_project_customer_first_gate"] != "PROJECT_VERIFIED"
    assert summary["claim_reason_codes"] == list(claim.reason_codes)
    assert not (tmp_path / "out" / "verified_customer_rows.json").exists()
    assert load_verified_sealed_run(Path(summary["combined_run_file"])).quantities


def test_failed_finish_family_is_not_retried_as_full_project_approval(tmp_path, monkeypatch):
    claim = _mixed_claim()
    rows = project_live_floor_finish_customer_rows(claim, workspace_id=1, project_id="project-1")
    monkeypatch.setattr(handoff, "project_live_floor_finish_customer_rows", lambda *_a, **_k: (rows[0], rows[0]))
    summary = _run(tmp_path, monkeypatch, claim)
    assert summary["customer_rows_verified"] is False
    assert summary["floor_finish_customer_rows_verified"] is False
    assert summary["ceiling_customer_rows_verified"] is True
    assert summary["full_project_customer_first_gate"] == "FLOOR_FINISH_CUSTOMER_UNVERIFIED"


def test_surface_only_family_receipts_stay_distinct_from_whole_project(tmp_path, monkeypatch):
    summary = _run(tmp_path, monkeypatch, _mixed_claim(), family="surfaces")
    assert summary["floor_finish_customer_rows_verified"] is True
    assert summary["ceiling_customer_rows_verified"] is True
    assert summary["customer_rows_verified"] is False
    assert summary["customer_rows_file"] is None


def test_source_only_axis_pair_is_preserved_without_customer_permission(tmp_path, monkeypatch):
    claim = axis_claim(_composition(_figured_with_explicit_axes()))
    summary = _run(tmp_path, monkeypatch, claim)
    assert summary["status"] == "sealed"
    assert summary["family_counts"]["opening_width"] == 1
    assert summary["family_counts"]["opening_height"] == 1
    assert summary["customer_rows_verified"] is False
    assert summary["full_project_customer_first_gate"] == "FULL_PROJECT_FAMILY_SCOPE"
    assert summary["customer_rows_file"] is None
    run = load_verified_sealed_run(Path(summary["family_run_files"]["opening_metric_axes"]))
    assert len(run.quantities) == 2
    assert all(q.metadata["commercial_projection_allowed"] is False for q in claim.opening_dimension_quantity_evidence)
