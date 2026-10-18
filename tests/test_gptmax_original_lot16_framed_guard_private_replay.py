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


def test_original_g17_frames_survive_all_pages_four_job_entrypoint(tmp_path):
    """The owner's 10GB four-job path must not silently seal only two of eight.

    The all-page source snapshot may legitimately use different host-binding
    receipts/fingerprints from the page-3 issuer. Compare stable source
    *physical opening* identities, quantity IDs and values, not cross-scope
    fingerprints, and NEVER copy the archived rows into a new producer output.
    """
    raw = os.environ.get("PLANREADER_LOT16_ORIGINAL_PDF")
    if not raw:
        pytest.skip("private original not provisioned; source-neutral tests run")
    from tools.run_gpt3_lot16_original_sealed_score_input import _verify_original_source
    from tools.run_source_closed_project_handoff import generate_project_handoff
    import json

    source = Path(raw)
    _verify_original_source(source, _PROTECTED.parents[3] /
        "benchmarks/frozen_holdout/full_plan_v2/projects/"
        "au_qld_lot16_power/source_manifest.json")

    out = tmp_path / "all_pages"
    summary = generate_project_handoff(
        pdf_path=source,
        project_id="au_qld_lot16_power",
        workspace_id=1,
        output_dir=out,
        family_group="all",
    )
    assert summary["status"] == "sealed"
    assert summary["family_counts"]["opening_area"] == 8
    assert summary["customer_rows_verified"] is False  # Not a customer publisher.

    historical = json.loads((_PROTECTED / "source_sealed_run.json").read_text())
    all_page = json.loads((out / "au_qld_lot16_power.json").read_text())
    assert all_page["source_sha256s"] == historical["source_sha256s"]
    def stable(rows):
        return {
            q["quantity_id"]: (
                q["semantic_key"],
                q["value"],
                q["unit"],
                tuple(q["object_identity_refs"]),
            )
            for q in rows
        }
    assert stable(all_page["quantities"]) == stable(historical["quantities"])
