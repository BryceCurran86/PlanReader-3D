"""Independent original 3Laurel wet/vinyl/wall-tile/ceiling customer combination.

This test never uploads the original PDF or modifies the 120 benchmark.
"""
from pathlib import Path

import pytest

from pb_customer_output_verification import verify_sealed_customer_output
from pb_three_laurel_22_finish_combined_customer import (
    SOURCE_SHA, issue_original_three_laurel_22_finish_customer_rows,
)
from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel


def test_original_four_finish_families_produce_22_retained_sealed_customer_rows():
    original = require_original_3laurel()
    assert SOURCE_SHA == ORIGINAL_SHA256
    output = issue_original_three_laurel_22_finish_customer_rows(original)
    assert output.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
    assert output.family_counts == (3, 4, 8, 7)
    assert len(output.customer_rows) == 22
    assert len(output.sealed_run.quantities) == 22
    assert len({r.quantity_id for r in output.sealed_run.quantities}) == 22
    assert set(output.sealed_run.source_sha256s) == {ORIGINAL_SHA256}
    check = verify_sealed_customer_output(
        output.sealed_run, output.customer_rows,
    )
    assert check.customer_row_count == 22
    assert all(
        row["quantity_status"] == "To review" for row in output.customer_rows
    )
    assert not output.all_rooms_physically_authenticated
    assert not output.frozen_benchmark_score_authorized


def test_no_source_or_modified_bytes_never_issue_finish_customer_rows(tmp_path):
    not_found = issue_original_three_laurel_22_finish_customer_rows(
        tmp_path / "missing.pdf",
    )
    assert not_found.status == "ABSTAIN"
    assert not_found.customer_rows == ()
    assert "original_source_path_unavailable" in not_found.reason_codes
    wrong = tmp_path / "unverified.pdf"
    wrong.write_bytes(b"synthetic, not an original plan")
    result = issue_original_three_laurel_22_finish_customer_rows(wrong)
    assert result.status == "ABSTAIN"
    assert result.sealed_run is None
    assert result.customer_rows == ()
    assert result.reason_codes == ("original_source_hash_mismatch",)


def test_symlink_and_invalid_workspace_fail_closed(tmp_path):
    target = tmp_path / "unverified.pdf"
    target.write_bytes(b"example")
    link = tmp_path / "link.pdf"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink unsupported")
    assert issue_original_three_laurel_22_finish_customer_rows(link).status == "ABSTAIN"
    assert issue_original_three_laurel_22_finish_customer_rows(
        target, workspace_id=0
    ).status == "ABSTAIN"
