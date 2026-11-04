"""Type-level figured frame evidence cannot launder a frame into installed quantity."""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_migration_contracts import EvidenceResolutionStatus, QuantityEvidence
from pb_source_elevation_frame_type_quantity import publish_nominal_elevation_frame_type_area
from test_opening_elevation_frame_area_authority import _authority, _elevation_pdf, _selector


def _record():
    published, authority = _authority(_elevation_pdf())
    result = authority.resolve(_selector(published,"W1"))
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    return result.record, authority


def test_original_source_neutral_figured_frame_reissues_type_only_evidence():
    record, authority = _record()
    evidence=publish_nominal_elevation_frame_type_area(record, authority=authority)
    assert type(evidence) is QuantityEvidence
    assert evidence.value == 7.2  # synthetic 3000 x 2400, not benchmark truth
    assert evidence.family == "opening_nominal_frame_type_area"
    assert evidence.status == "corroborated_type_only"
    assert evidence.unit == "m2"
    assert evidence.input_entity_ids == (record.record_id,)
    assert evidence.metadata["source_frame_area_record_id"] == record.record_id
    assert evidence.metadata["quantity_scope"] == "single_nominal_frame_type"
    assert evidence.metadata["installed_opening_count_granted"] is False
    assert evidence.metadata["physical_opening_identity_granted"] is False
    assert evidence.metadata["host_wall_binding_granted"] is False
    assert evidence.metadata["commercial_installed_quantity_granted"] is False
    assert evidence.metadata["customer_installed_takeoff_eligible"] is False
    assert all(x in evidence.evidence_ids for x in (
        record.mark_observation_id,*record.dimension_observation_ids,
        *record.title_observation_ids,*record.frame_geometry_ids,
    ))
    assert publish_nominal_elevation_frame_type_area(record, authority=authority) == evidence


@pytest.mark.parametrize("update",[
    {"area_m2":7.1},
    {"axis_x_mm":2000.0},
    {"source_sha256":"bad hash"},
    {"mark_observation_id":"source-word-missing"},
    {"source_observation_ids":()},
    {"source_observation_ids":("source-word-fake",)},
    {"dimension_observation_ids":("source-one","source-one")},
    {"dimension_observation_ids":("source-absent-one","source-absent-two")},
    {"frame_geometry_ids":()},
    {"title_observation_ids":()},
    {"dimension_line_ids":()},
    {"witness_line_ids":()},
    {"dimension_line_ids":("synthetic-fake-x","synthetic-fake-y")},
    {"witness_line_ids":("synthetic-fake-witness",)},
    {"frame_geometry_ids":("synthetic-fake-frame",)},
    {"frame_bbox":(0.0,0.0,1.0,1.0)},
    {"reason_codes":("unrelated_positive",)},
])
def test_replayed_or_damaged_frame_receipt_never_reissues_nominal_quantity(update):
    record, authority = _record()
    altered=replace(record,**update)
    assert publish_nominal_elevation_frame_type_area(altered, authority=authority) is None


def test_no_raw_caller_can_issue_nominal_type_without_sealed_record():
    record, authority = _record()
    with pytest.raises(TypeError,match="producer-owned"):
        publish_nominal_elevation_frame_type_area(object(), authority=authority)
    with pytest.raises(TypeError,match="producer-owned"):
        publish_nominal_elevation_frame_type_area(record, authority=object())


def test_original_producer_record_rejects_invalid_opening_kind_before_issuer():
    record, authority = _record()
    with pytest.raises(ValueError, match="opening_kind must be door or window"):
        replace(record, opening_kind="unknown")

def test_source_authority_must_resolve_exact_unmodified_receipt():
    record, authority = _record()
    assert publish_nominal_elevation_frame_type_area(record, authority=authority)
    # The producer seal survives replace(), but authority-owned receipts don't.
    for changed in (
        replace(record, dimension_line_ids=("forged-x", "forged-y")),
        replace(record, witness_line_ids=("forged-witness",)),
        replace(record, frame_bbox=(0.0, 0.0, 1.0, 1.0)),
    ):
        assert publish_nominal_elevation_frame_type_area(
            changed, authority=authority,
        ) is None
