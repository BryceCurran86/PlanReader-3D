"""A safety-stopped original source is UNPROVEN, not a completed empty takeoff."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from tools import run_source_closed_project_handoff as handoff


@pytest.mark.parametrize("codes,blocked", [
    (("live_physical_net_wall_integration_unavailable",
      "physical_wall_candidate_scope_complexity_exceeded"), True),
    (("physical_wall_candidate_scope_complexity_exceeded",), True),
    (("live-authority-unavailable",), False),
    (("physical_wall_candidate_scope_complexity_exceeded_other",), False),
    (("physical_wall_candidate_scope_complexity_exceeded ",), False),
    ((None,1), False),
    ([], False),
    (None, False),
])
def test_source_safety_cap_reason_is_precise_and_cannot_be_guessed(codes,blocked):
    assert handoff._source_complexity_blocked(codes) is blocked


@pytest.mark.parametrize("codes,expected", [
    (("live_physical_net_wall_integration_unavailable",
      "physical_wall_candidate_scope_complexity_exceeded"), "source_complexity_blocked"),
    (("room_face_not_source_supported",), "no_sealable_quantities"),
])
def test_original_source_run_status_retains_unsealed_incomplete_vs_empty(
    codes, expected, tmp_path, monkeypatch,
):
    pdf=tmp_path/"original.pdf"
    pdf.write_bytes(b"source-bytes-not-benchmark-truth")
    monkeypatch.setattr(handoff,"_source_page_scopes",lambda *args: ((0,1),(),2))
    claim=SimpleNamespace(
        status=SimpleNamespace(value="abstained"),
        reason_codes=codes,
        canonical_walls=(),canonical_openings=(),canonical_rooms=(),
        canonical_floors=(),canonical_spaces=(),
        room_area_quantity_evidence=(),floor_finish_quantity_evidence=(),
        opening_quantity_evidence=(),opening_count_quantity_evidence=(),
    )
    monkeypatch.setattr(handoff,"collect_live_physical_net_wall_claim",lambda *a,**k: claim)
    monkeypatch.setattr(handoff,"publish_live_floor_area_quantities",lambda *a: ())
    monkeypatch.setattr(handoff,"collect_live_ceiling_lining_claims",lambda *a,**k: SimpleNamespace())
    monkeypatch.setattr(handoff,"publish_live_ceiling_area_quantities",lambda *a: ())
    out=tmp_path/"output"
    summary=handoff.generate_project_handoff(
        pdf_path=pdf,project_id="source-test",workspace_id=1,
        output_dir=out,family_group="surfaces",
    )
    assert summary["status"]==expected
    assert summary["claim_reason_codes"]==list(codes)
    assert summary["combined_run_file"] is None
    assert summary["combined_run_id"] is None
    assert summary["combined_quantity_count"]==0
    assert all(count == 0 for count in summary["family_counts"].values())
    assert not list(out.glob("*.sealed.json"))
    assert not list((out/"family_runs").glob("*.sealed.json"))
    assert not summary["frozen_v2_reconciliation_complete"]
    assert not summary["benchmark_score_granted"]
    saved=json.loads((out/"production_summary.json").read_text())
    assert saved["status"]==expected
    assert saved["claim_reason_codes"]==list(codes)
