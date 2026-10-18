"""Optional original-source parity gate for real raster G17 detector releases.

Public CI has no customer PDF and therefore runs synthetic G17 tests instead.
On an authorized owner machine set PLANREADER_LOT16_ORIGINAL_PDF to the
unmodified architectural original and run this test locally. No PDF content or
private path is committed or uploaded. This source-only test does not alter the
frozen V2 benchmark, source manifest, quantity fixture, or evaluator.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from tools.run_gpt3_lot16_original_sealed_score_input import (
    run_original_lot16_sealed_handoff,
)

_PROTECTED = (
    Path(__file__).resolve().parents[1]
    / "docs/engineering/lot16_original_signed_eight_row_20261015/production"
)


def test_original_g17_frames_preserve_existing_signed_and_customer_bytes(tmp_path):
    raw = os.environ.get("PLANREADER_LOT16_ORIGINAL_PDF")
    if not raw:
        pytest.skip("private original not provisioned; source-neutral tests must still run")
    source = Path(raw)
    if not source.is_file():
        pytest.fail("configured private original PDF does not exist")

    # The production-original entrypoint independently checks filename, SHA,
    # length, source ancestry and the source→quantity→customer bijection.
    receipt = run_original_lot16_sealed_handoff(source, tmp_path / "current")
    assert receipt["signed_run_and_customer_parity"] is True

    # Byte-wise source-positive fixture comparison is independent of frozen
    # benchmark gold. No updated issuer may silently rekey existing signatures.
    for name in ("source_sealed_run.json", "verified_customer_rows.json"):
        assert (tmp_path / "current" / name).read_bytes() == (
            _PROTECTED / name
        ).read_bytes(), f"original signed Lot16 source identity changed: {name}"
