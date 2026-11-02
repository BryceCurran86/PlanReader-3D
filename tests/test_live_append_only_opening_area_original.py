"""Owner-original acceptance; a missing PDF is explicitly NOT verification."""
import hashlib
import json
import os
from pathlib import Path

import pytest

from tools.run_gpt3_lot16_original_sealed_score_input import run_original_lot16_sealed_handoff


def _original_pdf():
    root = Path(__file__).resolve().parents[1]
    configured = os.environ.get("PLANREADER_LOT16_ORIGINAL_PDF")
    pdf = (Path(configured) if configured else root / "documents/sources"
           / "1. Construction Plans - Lot 16 Power (REV E).pdf")
    if not pdf.is_file():
        if configured:
            pytest.fail("explicit owner-original PDF path is unavailable")
        pytest.skip("private original unavailable: source-positive acceptance NOT VERIFIED")
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == (
        "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
    )
    return pdf


def test_original_source_appends_one_area_and_preserves_all_eight_signed_customer_bodies(tmp_path):
    root = Path(__file__).resolve().parents[1]
    pdf = _original_pdf()
    # Produce and seal first. Archives are used only AFTER prediction, solely
    # for immutable historical retention, never as detector/measurement input.
    receipt = run_original_lot16_sealed_handoff(
        pdf, tmp_path / "production", recover_additional_opening_areas=True,
    )
    archived = root / "docs/engineering/lot16_original_signed_eight_row_20261015/production"
    before = json.loads((archived / "source_sealed_run.json").read_text())
    after = json.loads((tmp_path / "production/source_sealed_run.json").read_text())
    original_rows = json.loads((archived / "verified_customer_rows.json").read_text())
    rows = json.loads((tmp_path / "production/verified_customer_rows.json").read_text())
    indexed = {q["quantity_id"]: q for q in after["quantities"]}
    assert all(indexed[q["quantity_id"]] == q for q in before["quantities"])
    assert all(row in rows for row in original_rows)
    assert len(after["quantities"]) == len(before["quantities"]) + 1
    assert len(rows) == receipt["quantity_count"] == len(after["quantities"])
    assert receipt["signed_run_and_customer_parity"] is True
    assert receipt["benchmark_score_granted"] is False


def test_original_source_recovery_reaches_workspace_customer_output(monkeypatch):
    """The real workspace bridge must request recovery and consume its output."""
    from types import SimpleNamespace

    import pb_auto_geometry_v1219 as auto
    import pb_live_physical_net_wall_integration as live
    from pb_customer_output_verification import verify_sealed_customer_output
    from pb_live_opening_customer_projection import project_live_opening_customer_rows
    from pb_live_opening_source_closed_export import seal_live_opening_area_claim_run

    pdf = _original_pdf()
    received = []
    collect = live.collect_live_physical_net_wall_claim

    def collect_original(*args, **kwargs):
        assert kwargs["recover_supported_opening_areas"] is True
        assert not kwargs.get("recover_additional_opening_areas", False)
        claim = collect(*args, **kwargs)
        received.append(claim)
        return claim

    monkeypatch.setattr(live, "collect_live_physical_net_wall_claim", collect_original)
    # Ceiling extraction is independent of this opening-area customer path.
    monkeypatch.setattr(
        "pb_live_ceiling_lining_integration.collect_live_ceiling_lining_claims",
        lambda *args, **kwargs: SimpleNamespace(claims=()),
    )
    app = SimpleNamespace(lquery=lambda *_args, **_kwargs: [{"id": 1, "path": str(pdf)}])
    auto._try_physical_net_wall_rows(app, 1, [{
        "id": 1, "document_id": 1, "page_no": 3, "page_label": "p3",
        "page_type": "Other", "extracted_text": "", "selected": 1,
    }], [])
    assert len(received) == 1
    claim = received[0]

    # Historical archives are read only AFTER the original producer runs.
    root = Path(__file__).resolve().parents[1]
    archive = root / "docs/engineering/lot16_original_signed_eight_row_20261015/production"
    before = json.loads((archive / "source_sealed_run.json").read_text())
    historical_rows = json.loads((archive / "verified_customer_rows.json").read_text())
    sealed = seal_live_opening_area_claim_run(claim, workspace_id=1, project_id=before["project_id"])
    projected = project_live_opening_customer_rows(claim, workspace_id=1, project_id=before["project_id"])
    after = {q.quantity_id: q.to_dict() for q in sealed.quantities}
    assert all(after[q["quantity_id"]] == q for q in before["quantities"])
    assert all(row in projected for row in historical_rows)
    assert verify_sealed_customer_output(sealed, projected).valid_quantity_count == len(before["quantities"]) + 1
    previous_ids = {q["quantity_id"] for q in before["quantities"]}
    added = [q for q in claim.opening_quantity_evidence if q.quantity_id not in previous_ids]
    assert len(added) == 1
    # Pin the original physical case after production, not an expected BOQ value.
    assert added[0].input_entity_ids == (
        "physical_opening_existence_993560b2bdf85cdd668047edd7043f81",
    )
    opening = next(o for o in claim.canonical_openings
                   if o.canonical_opening_id == added[0].input_entity_ids[0])
    assert opening.host_binding_record_id in added[0].evidence_ids
    assert opening.figured_area_record_id == added[0].metadata["measurement_record_id"]

    workspace_rows = [dict(zip(auto.TAKEOFF_ROW_FIELDS, row))
                      for row in app._live_opening_takeoff_rows_by_workspace[1]]
    assert len(workspace_rows) == len(sealed.quantities)
    for quantity in claim.opening_quantity_evidence:
        matching = [row for row in workspace_rows if quantity.quantity_id in row["source_reference"]]
        assert len(matching) == 1
        assert matching[0]["quantity"] == quantity.value
        assert matching[0]["unit"] == "m²"
    assert not app._ag09_family_coverage_by_workspace[1]["family_gaps"].get("opening")
