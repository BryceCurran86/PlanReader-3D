"""Owner-original acceptance; a missing PDF is explicitly NOT verification."""
import hashlib
import json
import os
from pathlib import Path

import pytest

from tools.run_gpt3_lot16_original_sealed_score_input import run_original_lot16_sealed_handoff


def test_original_source_appends_one_area_and_preserves_all_eight_signed_customer_bodies(tmp_path):
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
