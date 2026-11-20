"""Guard against ever reporting a raster/inside-face diagnostic as original PlanReader."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest

from scripts.check_canonical_trace_route import verify_route_contract
from tools.run_canonical_source_native_preview import (
    EXPECTED_PRODUCER, WrongTraceRoute, validate_canonical_preview, run_preview,
)

SHA = "a" * 64


def _summary():
    return {
        "source_sha256": SHA,
        "page_index": 2,
        "producer": EXPECTED_PRODUCER,
        "legacy_envelope_used": False,
        "legacy_fallback_allowed": False,
        "quantity_authorized": False,
        "commercial_publishable": False,
        "stage_order": ("attempt_source_native_exterior_wall_trace_first", "trace_source_native_internal_wall_candidates"),
        "external_wall_trace_status": "CANDIDATE",
        "external_wall_trace_reason": "source_closed_painted_wall_ring_needs_exterior_role_authentication",
        "external_wall_native_source_paths": [10, 11],
    }


def test_original_app_route_locked_in_required_ci():
    verify_route_contract(Path(__file__).resolve().parents[1])


def test_valid_original_preview_remains_noncommercial():
    result = validate_canonical_preview(_summary(), expected_source_sha256=SHA, expected_page_index=2)
    assert result["route_verified"] is True
    assert result["official_frozen120_scored"] is False
    assert result["measurement_authorized"] is False


@pytest.mark.parametrize("change,reason", [
    ({"producer": "pb_external_footprint_first_trace.trace_external_footprint_first"}, "wrong_trace_producer"),
    ({"producer": "pb_external_footprint_inside_face_runtime.run_inside_face_footprint_runtime_stage"}, "wrong_trace_producer"),
    ({"producer": None}, "wrong_trace_producer"),
    ({"legacy_envelope_used": True}, "legacy_trace"),
    ({"legacy_fallback_allowed": True}, "legacy_trace"),
    ({"quantity_authorized": True}, "preview_must_not"),
    ({"commercial_publishable": True}, "preview_must_not"),
    ({"stage_order": ["inside_face_dominant_wall_start_and_left_turn_walk"]}, "canonical_trace_stage"),
    ({"external_wall_trace_reason": None}, "native_wall_result_reason_missing"),
])
def test_wrong_route_or_authority_is_not_benchmark_proof(change, reason):
    summary = _summary()
    summary.update(change)
    if reason is None:
        # A missing reason is handled by the report as an explicit null, not a success claim.
        assert validate_canonical_preview(summary, expected_source_sha256=SHA, expected_page_index=2)
    else:
        with pytest.raises(WrongTraceRoute, match=reason):
            validate_canonical_preview(summary, expected_source_sha256=SHA, expected_page_index=2)


def test_wrong_page_or_original_pdf_is_rejected():
    with pytest.raises(WrongTraceRoute, match="source_sha_mismatch"):
        validate_canonical_preview(_summary(), expected_source_sha256="b" * 64, expected_page_index=2)
    with pytest.raises(WrongTraceRoute, match="page_index_mismatch"):
        validate_canonical_preview(_summary(), expected_source_sha256=SHA, expected_page_index=1)


def test_unavailable_or_wrong_checkout_fails_before_importing_trace(tmp_path):
    pdf = tmp_path / "original.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    source_hash = hashlib.sha256(pdf.read_bytes()).hexdigest()
    with pytest.raises(WrongTraceRoute, match="full_current_repository_checkout_required|wrong_code_revision"):
        run_preview(
            pdf, page_index=0, expected_source_sha256=source_hash,
            expected_head_sha="b" * 40, out_dir=tmp_path / "private",
            repo_root=tmp_path,
        )


def test_source_sha_and_producer_must_both_match():
    bad = copy.deepcopy(_summary())
    bad.pop("external_wall_native_source_paths")
    with pytest.raises(WrongTraceRoute, match="native_wall_source_path_lineage_missing"):
        validate_canonical_preview(bad, expected_source_sha256=SHA, expected_page_index=2)
