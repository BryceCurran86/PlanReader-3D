"""GPT1 shadow-only dependency integrity checks for gross wall-area publication.

The adversarial cases exercise current fail-closed rules, including the
reviewed FIRM-with-blockers correction merged in #2826.
No producer, source PDF, original quantity, signature or benchmark is changed.
See GPT1 #2017 wall-gross architecture preflight (2026-10-16).
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_wall_gross_area_quantity import build_gross_wall_area_quantity
from test_wall_gross_area_quantity import _ctx, _height, _length


def _publish(*, length=None, height=None):
    return build_gross_wall_area_quantity(
        wall_id="WALL-1",
        wall_length=length if length is not None else _length(),
        wall_height=height if height is not None else _height(),
        context=_ctx(),
    )


@pytest.mark.parametrize(
    ("which", "field", "value", "expected"),
    [
        ("length", "page_no", None, "wall_length_page_source_invalid"),
        ("length", "page_no", True, "wall_length_page_source_invalid"),
        ("height", "page_no", 1.0, "wall_height_page_source_invalid"),
        ("height", "page_no", 0, "wall_height_page_source_invalid"),
        ("length", "page_no", 2, "wall_length_page_mismatch"),
        ("height", "page_no", 2, "wall_height_page_mismatch"),
        ("length", "viewport_id", "VP-2", "wall_length_viewport_stale"),
        ("height", "viewport_id", "VP-2", "wall_height_viewport_stale"),
        ("length", "viewport_id", " VP-1", "wall_length_viewport_source_invalid"),
        ("height", "viewport_id", "VP-1 ", "wall_height_viewport_source_invalid"),
        ("length", "source_sha256", "b" * 64, "wall_length_source_sha_stale"),
        ("height", "source_sha256", "b" * 64, "wall_height_source_sha_stale"),
        ("length", "revision_id", "R2", "wall_length_revision_stale"),
        ("height", "revision_id", "R2", "wall_height_revision_stale"),
        ("length", "revision_id", "", "wall_length_provenance_incomplete"),
        ("height", "revision_id", "", "wall_height_provenance_incomplete"),
        ("length", "evidence_snapshot_id", "", "wall_length_evidence_snapshot_missing"),
        ("height", "evidence_snapshot_id", "", "wall_height_evidence_snapshot_missing"),
        ("length", "evidence_snapshot_id", "foreign", "wall_length_evidence_snapshot_stale"),
        ("height", "evidence_snapshot_id", "foreign", "wall_height_evidence_snapshot_stale"),
        ("length", "canonical_graph_snapshot_id", "", "wall_length_graph_snapshot_missing"),
        ("height", "canonical_graph_snapshot_id", "", "wall_height_graph_snapshot_missing"),
        ("length", "canonical_graph_snapshot_id", "foreign", "wall_length_graph_snapshot_stale"),
        ("height", "canonical_graph_snapshot_id", "foreign", "wall_height_graph_snapshot_stale"),
    ],
)
def test_source_scope_and_page_mutations_abstain(which, field, value, expected):
    baseline = _length() if which == "length" else _height()
    tampered = replace(baseline, metadata={**baseline.metadata, field: value})
    result = _publish(**{which: tampered})
    assert result.abstained is True
    assert result.value is None
    assert expected in result.blocking_reasons
    assert result.status == "blocked"
    # The upstream receipt remains unchanged; downstream never repairs source.
    assert type(baseline.metadata[field]) is not type(value) or baseline.metadata[field] != value


@pytest.mark.parametrize(
    ("which", "changes", "expected"),
    [
        ("length", {"unit": "mm"}, "invalid_wall_length_unit"),
        ("height", {"unit": "mm"}, "invalid_wall_height_unit"),
        ("length", {"authority": "model_derived"}, "wall_length_authority_not_trusted"),
        ("height", {"authority": MeasurementAuthorityType.PDF_SCALED.value}, "wall_height_authority_not_trusted"),
        ("length", {"semantic_key": "wall_length:WALL-OTHER"}, "wall_length_semantic_identity_mismatch"),
        ("height", {"semantic_key": "wall_height:WALL-OTHER"}, "wall_height_semantic_identity_mismatch"),
        ("length", {"input_entity_ids": ("WALL-OTHER",)}, "wall_length_identity_mismatch"),
        ("height", {"input_entity_ids": ("WALL-OTHER",)}, "wall_height_identity_mismatch"),
        ("length", {"evidence_ids": ("padded ",)}, "wall_length_source_receipts_invalid"),
        ("height", {"evidence_ids": (" padded",)}, "wall_height_source_receipts_invalid"),
        ("length", {"evidence_ids": ()}, "wall_length_source_receipts_invalid"),
        ("height", {"evidence_ids": ()}, "wall_height_source_receipts_invalid"),
        ("length", {"value": 0.0}, "wall_length_value_invalid"),
        ("height", {"value": 0.0}, "wall_height_value_invalid"),
        ("length", {"value": 1e-16}, "gross_wall_area_invalid"),
    ],
)
def test_dependency_identity_value_and_receipt_mutations_abstain(which, changes, expected):
    baseline = _length() if which == "length" else _height()
    changed = replace(baseline, **changes)
    result = _publish(**{which: changed})
    assert result.abstained
    assert result.value is None
    assert expected in result.blocking_reasons


def test_replayed_quantity_id_collision_never_claims_firm_area():
    length = _length()
    height = replace(_height(), quantity_id=length.quantity_id)
    result = _publish(length=length, height=height)
    assert result.abstained
    assert "wall_dimension_quantity_identity_collision" in result.blocking_reasons


def test_real_positive_contract_replays_with_unchanged_firm_fingerprint():
    first = _publish()
    second = _publish()
    assert first.to_dict() == second.to_dict()
    assert first.value == 12.0
    assert first.status == "firm"
    assert first.abstained is False
    assert len(first.metadata["dependency_fingerprints"]) == 2


@pytest.mark.parametrize("which", ("length", "height"))
def test_firm_upstream_with_explicit_blocking_reasons_must_not_publish_firm(which):
    parent = _length() if which == "length" else _height()
    # QuantityEvidence permits this contradictory imported/replayed state.
    # #2826 enforces this check: a numerically populated blocked parent is not firm.
    corrupted = replace(parent, blocking_reasons=("original_source_conflict",))
    result = _publish(**{which: corrupted})
    assert result.abstained
    assert result.value is None
    assert f"wall_{which}_source_blocked" in result.blocking_reasons
