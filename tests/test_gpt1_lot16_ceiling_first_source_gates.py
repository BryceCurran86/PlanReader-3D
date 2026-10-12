"""Source-only Q02 ceiling first-failure diagnostics cannot authorize m²."""
from dataclasses import replace
from types import MappingProxyType

from tools.diag_lot16_room_face_scope import _ceiling_quantity_diagnostic
from tests.test_live_ceiling_lining_source_closed_export import (
    _canonical_ceiling, _claim, _quantity,
)


def _report(claim):
    return _ceiling_quantity_diagnostic(claim)


def test_source_owned_ceiling_quantity_exposes_actual_exporter_trace_only():
    result = _report(_claim(_quantity()))
    assert result["canonical_ceiling_count"] == 1
    assert result["source_ceiling_quantity_count"] == 1
    assert result["source_closed_trace_count"] == 1
    assert result["source_closed_trace_error_type"] is None
    row = result["per_ceiling"][0]
    assert row["first_missing_prerequisite"] == "ceiling_lining_source_trace_resolved"
    assert row["source_trace_quantity_ids"] == ["qty-ceiling-1"]
    assert row["area_m2_source_record"] == 9.05352


def test_missing_original_ceiling_is_unavailable_not_zero_area():
    empty = replace(
        _claim(_quantity()),
        canonical_ceilings=(), ceiling_lining_quantity_evidence=(),
    )
    result = _report(empty)
    assert result["canonical_ceiling_count"] == 0
    assert result["source_closed_trace_count"] == 0
    assert result["per_ceiling"] == []
    assert result["unresolved_universe_reason"] == "canonical_ceiling_unavailable"


def test_foreign_room_source_hash_blocks_before_metric_publication():
    quantity = _quantity()
    ceiling = replace(_canonical_ceiling(quantity), source_sha256="b" * 64)
    result = _report(_claim(quantity, canonical_ceiling=ceiling))
    assert result["source_closed_trace_count"] == 0
    assert result["per_ceiling"][0]["first_missing_prerequisite"] == (
        "physical_ceiling_room_source_ownership_unavailable"
    )


def test_figured_dimension_pair_is_mandatory_without_scale_guess():
    quantity = _quantity()
    ceiling = replace(
        _canonical_ceiling(quantity),
        figured_dimension_ids=("dim-h", "dim-h"),
    )
    result = _report(_claim(quantity, canonical_ceiling=ceiling))
    assert result["source_closed_trace_count"] == 0
    assert result["per_ceiling"][0]["first_missing_prerequisite"] == (
        "source_documented_ceiling_dimension_pair_unavailable"
    )


def test_unscaled_ceiling_area_never_becomes_zero_or_firm():
    quantity = _quantity()
    ceiling = replace(
        _canonical_ceiling(quantity),
        area_m2=float("nan"),
        metric_area_complete=False,
    )
    result = _report(_claim(quantity, canonical_ceiling=ceiling))
    assert result["source_closed_trace_count"] == 0
    assert result["per_ceiling"][0]["first_missing_prerequisite"] == (
        "firm_ceiling_metric_area_unavailable"
    )
    assert result["per_ceiling"][0]["area_m2_source_record"] is None


def test_missing_rcp_support_cannot_prove_finish_occurrence():
    quantity = _quantity()
    altered = replace(
        quantity,
        metadata={**quantity.metadata, "support_snapshot_id": ""},
    )
    result = _report(_claim(altered))
    assert result["source_closed_trace_count"] == 0
    assert result["per_ceiling"][0]["first_missing_prerequisite"] == (
        "authenticated_ceiling_rcp_support_unavailable"
    )


def test_duplicate_source_identity_even_with_abstain_is_disclosed_and_not_traced():
    quantity = _quantity()
    rejected = replace(quantity, abstained=True, value=None, status="provisional")
    claim = replace(
        _claim(quantity), ceiling_lining_quantity_evidence=(rejected, quantity),
    )
    result = _report(claim)
    assert result["source_closed_trace_count"] == 0
    assert result["source_closed_trace_error_type"] is not None
    assert result["duplicate_source_ceiling_quantity_ids"] == ["qty-ceiling-1"]
    assert result["per_ceiling"][0]["first_missing_prerequisite"] == (
        "ceiling_lining_quantity_evidence_unavailable_or_ambiguous"
    )


def test_missing_ceiling_material_occurrence_remains_unavailable():
    quantity = _quantity()
    altered = replace(
        quantity,
        metadata={**quantity.metadata, "finish_occurrence_record_id": None},
    )
    result = _report(_claim(altered))
    assert result["source_closed_trace_count"] == 1 or result["source_closed_trace_error_type"] is not None
    assert result["per_ceiling"][0]["first_missing_prerequisite"] == (
        "authenticated_ceiling_finish_occurrence_unavailable"
    )


def test_actual_immutable_original_quantity_metadata_keeps_source_trace():
    source = _quantity()
    immutable = replace(source, metadata=MappingProxyType(dict(source.metadata)))
    result = _report(_claim(immutable))
    assert result["source_closed_trace_count"] == 1
    assert result["per_ceiling"][0]["first_missing_prerequisite"] == (
        "ceiling_lining_source_trace_resolved"
    )


def test_malformed_observation_identity_is_not_an_implicit_ceiling_source():
    source = _quantity()
    malformed = replace(source, input_entity_ids=None)
    result = _report(_claim(malformed))
    assert result["source_closed_trace_count"] == 0
    assert result["per_ceiling"][0]["first_missing_prerequisite"] == (
        "ceiling_lining_quantity_evidence_unavailable_or_ambiguous"
    )
