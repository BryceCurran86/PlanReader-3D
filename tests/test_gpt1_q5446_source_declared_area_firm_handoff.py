"""SHA-authenticated original Q5446 scheduled architectural m² FIRM handoff.

Read-only source-owned counts. It must not issue 245.71/298.19 rollups
as another physical quantity or claim that a scheduled area is net tiling.
"""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import os

import pytest

from pb_gpt1_q5446_original_area_schedule_shadow import (
    ORIGINAL_LABEL_STROKE_PATHS,
    ORIGINAL_ROW_Y_BOUNDS,
    PRINTED_ORIGINAL_ROWS,
    SOURCE_SHA256,
    OriginalAreaScheduleCandidate,
)
from pb_gpt1_q5446_source_declared_area_firm_handoff import (
    Q5446_PROJECT_ID,
    _issued_row,
    issue_original_q5446_scheduled_area_handoff,
)


def _synthetic_verified_shape(key: str):
    """Test-private fabricated shape, NEVER a source-authenticated issuer."""
    i, original = next(
        (i, row) for i, row in enumerate(PRINTED_ORIGINAL_ROWS, 1)
        if row[0] == key
    )
    return OriginalAreaScheduleCandidate(
        original_row_id=f"q5446_source_p1_area_schedule_row_{i}_{key}",
        printed_label=original[1],
        printed_area_m2=original[2],
        is_rollup=original[3],
        original_page_index=0,
        table_row_number=i,
        original_source_sha256=SOURCE_SHA256,
        glyph_correspondence_authenticated=True,
        physical_surface_owner_authenticated=False,
        customer_projection_allowed=False,
        original_numeric_vector_path_ids=tuple(range(400 + i * 15, 406 + i * 15)),
        original_label_vector_path_ids=ORIGINAL_LABEL_STROKE_PATHS[i - 1],
        label_stroke_presence_verified=True,
    )


@pytest.mark.parametrize("value", [None, 0, -1, 1.0, True, "1"])
def test_invalid_workspace_does_not_issue_quantities_without_source(tmp_path, value):
    report = issue_original_q5446_scheduled_area_handoff(
        str(tmp_path / "private.pdf"), workspace_id=value,
    )
    assert report.status == "ABSTAIN"
    assert report.quantities == ()
    assert report.sealed_run is None


def test_foreign_or_missing_pdf_never_produces_firm_scheduled_area(tmp_path):
    missing = issue_original_q5446_scheduled_area_handoff(
        str(tmp_path / "missing.pdf"), workspace_id=1,
    )
    assert missing.status == "ABSTAIN" and missing.quantities == ()
    forged = tmp_path / "lookalike.pdf"
    forged.write_bytes(b"%PDF-1.7 fake")
    result = issue_original_q5446_scheduled_area_handoff(
        str(forged), workspace_id=1,
    )
    assert result.status == "ABSTAIN" and result.sealed_run is None


@pytest.mark.parametrize("key", [
    "ground_floor", "first_floor", "porch", "garage", "alfresco",
])
def test_synthetic_structural_fixture_has_source_scoped_not_customer_area(key):
    # This exercises only the internal issuer's schema in tests; the public
    # entrypoint above demands a real SHA-verified private PDF.
    q, trace = _issued_row(_synthetic_verified_shape(key), key=key, workspace_id=123)
    assert q.status == "firm"
    assert q.family == "architectural_scheduled_area"
    assert q.unit == "m2"
    assert Decimal(str(q.value)) == _synthetic_verified_shape(key).printed_area_m2
    assert q.metadata["commercial_projection_allowed"] is False
    assert q.metadata["quantity_handoff_only"] is True
    assert q.metadata["canonical_physical_floor_owner_authenticated"] is False
    assert q.input_entity_ids == (
        f"q5446_original_source_schedule_{_synthetic_verified_shape(key).original_row_id}",
    )
    assert trace.canonical_entity_ids == q.input_entity_ids
    assert q.metadata["shadow_only"] is False
    assert "not_net_wall_face_or_finish" in q.metadata["source_printed_area_semantics"]
    assert trace.project_id == Q5446_PROJECT_ID
    assert trace.evidence_ids == tuple(sorted(set(trace.evidence_ids)))
    assert set(q.evidence_ids) <= set(trace.evidence_ids)


@pytest.mark.parametrize("wrong_key", ["ground_floor", "first_floor", "porch", "garage", "alfresco"])
def test_rollup_cannot_be_reissued_as_an_independent_area(wrong_key):
    with pytest.raises(ValueError, match="source row"):
        _issued_row(
            _synthetic_verified_shape("subtotal"), key=wrong_key, workspace_id=1,
        )


def test_equal_value_does_not_authorize_a_rekeyed_original_source_row():
    row = _synthetic_verified_shape("garage")
    with pytest.raises(ValueError, match="source row"):
        _issued_row(replace(row, printed_label="First Floor"), key="garage", workspace_id=1)
    with pytest.raises(ValueError, match="source row"):
        _issued_row(replace(row, printed_area_m2=Decimal("36.41")), key="garage", workspace_id=1)
    with pytest.raises(ValueError, match="source row"):
        _issued_row(replace(row, table_row_number=1), key="garage", workspace_id=1)


def test_duplicate_or_missing_vector_sources_never_issue_quantity():
    row = _synthetic_verified_shape("ground_floor")
    with pytest.raises(ValueError, match="source vector-path"):
        _issued_row(
            replace(row, original_numeric_vector_path_ids=(404, 404)),
            key="ground_floor", workspace_id=1,
        )
    with pytest.raises(ValueError, match="source vector-path"):
        _issued_row(
            replace(row, original_numeric_vector_path_ids=()),
            key="ground_floor", workspace_id=1,
        )


def test_original_sha_positive_issues_five_firm_source_area_receipts_only():
    private = os.environ.get("PLANREADER_ORIGINAL_Q5446_STANDARD_PLANS")
    if not private:
        pytest.skip("PRIVATE ORIGINAL SOURCE UNAVAILABLE: no FIRM source-positive test in public CI")
    report = issue_original_q5446_scheduled_area_handoff(
        private, workspace_id=12,
    )
    assert report.status == "SOURCE_FIRM_HANDOFF_ONLY", report.reason_codes
    assert report.customer_projection_allowed is False
    assert len(report.quantities) == len(report.traces) == 5
    assert all(q.status == "firm" and not q.abstained for q in report.quantities)
    assert all(q.family == "architectural_scheduled_area" for q in report.quantities)
    assert all(
        q.metadata["canonical_physical_floor_owner_authenticated"] is False
        for q in report.quantities
    )
    assert set(Decimal(str(q.value)) for q in report.quantities) == {
        Decimal("123.89"), Decimal("121.81"), Decimal("4.08"),
        Decimal("36.40"), Decimal("12.00"),
    }
    assert report.sealed_run is not None
    assert len(report.sealed_run.quantities) == 5
    assert all(q.lineage_ok for q in report.sealed_run.quantities)
    assert all(q.source_sha256 == SOURCE_SHA256 for q in report.sealed_run.quantities)
    assert not any(
        q.value in {245.71, 298.19} for q in report.sealed_run.quantities
    )
    # Repeat replay: deterministic source-issued identifiers/complete digest.
    same = issue_original_q5446_scheduled_area_handoff(
        private, workspace_id=12,
    )
    assert same.sealed_run.fingerprint == report.sealed_run.fingerprint
