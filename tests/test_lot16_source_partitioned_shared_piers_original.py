"""Genuine original source must reissue all nine retained customer bodies."""
import hashlib
import json
import os
from pathlib import Path

import pytest

from tools.run_gpt3_lot16_original_sealed_score_input import run_original_lot16_sealed_handoff


def test_original_partition_reproof_retains_ninth_and_all_historical_customer_bodies(tmp_path):
    configured_pdf = os.environ.get("PLANREADER_LOT16_ORIGINAL_PDF")
    configured_archive = os.environ.get("PLANREADER_LOT16_NINE_ARCHIVE_DIR")
    if not configured_pdf or not configured_archive:
        pytest.skip("private original and protected nine-row archive required: source acceptance NOT RUN")
    pdf = Path(configured_pdf)
    archive = Path(configured_archive)
    assert pdf.is_file() and archive.is_dir(), "configured private acceptance inputs unavailable"
    source_hash = hashlib.sha256(pdf.read_bytes()).hexdigest()
    output = tmp_path / "produced"
    receipt = run_original_lot16_sealed_handoff(
        pdf, output, recover_additional_opening_areas=True,
    )
    # Prediction, sealing and customer verification complete BEFORE any
    # historical body is read. The archive never enters a source producer.
    read = lambda path: json.loads(path.read_text(encoding="utf-8"))
    before = read(archive / "source_sealed_run.json")
    after = read(output / "source_sealed_run.json")
    old = {q["quantity_id"]: q for q in before["quantities"]
           if q["family"] == "opening_area" and not q["abstained"]}
    new = {q["quantity_id"]: q for q in after["quantities"]}
    old_rows = {row["quantity_id"]: row for row in read(archive / "verified_customer_rows.json")
                if row["quantity_id"] in old}
    new_rows = {row["quantity_id"]: row for row in read(output / "verified_customer_rows.json")}
    assert len(old) == len(new) == len(old_rows) == len(new_rows) == 9
    assert new == old
    assert new_rows == old_rows
    assert receipt["signed_run_and_customer_parity"] is True
    assert receipt["benchmark_score_granted"] is False
    assert set(after["source_sha256s"]) == {source_hash}
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == source_hash
