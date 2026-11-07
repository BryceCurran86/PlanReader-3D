"""Owner-approved second axis for a door with ONE printed figure: review-only shadow.

The approval is an owner-supplied assumption, never a measurement. These tests use synthetic numbers only; no project value is an oracle.
The function consumes sealed evidence records and no geometry, so translation / rotation / scale invariance is exercised in the promotion
step through the real pipeline, not here.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from itertools import permutations

import pytest

from pb_door_height_owner_gate_shadow import (
    assess_door_height_owner_gate_shadow,
    assess_owner_approved_door_area_shadow,
)
from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType, MeasurementRecord
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_label_dimension_authority import (
    OpeningLabelDimensionEvidence,
    OpeningLabelDimensionResult,
)
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, PhysicalOpeningExistenceRecord

SHA = "a" * 64
RECORD_ID = "physical_opening_existence_test_1"
OTHER_RECORD_ID = "physical_opening_existence_test_2"


def _existence(record_id: str = RECORD_ID) -> PhysicalOpeningExistenceRecord:
    return PhysicalOpeningExistenceRecord(
        record_id=record_id, source_observation_ids=("obs-1",), source_lineage_root_ids=("root-1",),
        document_id="doc-1", revision_id="rev-1", source_sha256=SHA, snapshot_id="snap-1", page_id="3",
        viewport_id="vp-1", semantic_class="opening", status=EvidenceResolutionStatus.CORROBORATED,
        proposition=PHYSICAL_OPENING_EXISTS, structural_pattern="raster_door_swing_wall_band_interruption",
        diagnostic_confidence=1.0, blocking_reasons=(), structural_reason_codes=(), producer_method="t",
        producer_version="1", producer_generation=1,
    )


def _label(values=(810.0,), kind="door", record_id=RECORD_ID, status=EvidenceResolutionStatus.CORROBORATED):
    evidence = OpeningLabelDimensionEvidence(
        evidence_id="label-ev-1", opening_record_id=record_id, page_id="3", viewport_id="vp-1",
        source_text_observation_ids=("t-1",), raw_text="810 CS", dimension_values_mm=tuple(values),
        semantic_kind=kind, area_m2=(values[0] * values[1] / 1e6 if len(values) == 2 else None),
    )
    return OpeningLabelDimensionResult(status=status, reason_codes=("opening_label_dimension_resolved",), evidence=evidence)


def _approval(value=2050.0, **overrides) -> MeasurementRecord:
    fields = dict(
        value=value, unit="mm", source_type=MeasurementAuthorityType.USER_APPROVED.value, confidence=1.0,
        sheet="A-03", page=3, scale="", geometry_ref=RECORD_ID,
        authority_status=AuthorityStatus.USER_APPROVED.value, approved_by="Test Owner",
        approved_at="2026-11-05T07:10:00+10:00",
        metadata={"second_axis": "height", "single_figure_axis": "width", "source_sha256": SHA},
    )
    fields.update(overrides)
    return MeasurementRecord(**fields)


def _assess(label=None, approvals=None, existence=None):
    return assess_owner_approved_door_area_shadow(
        existence_record=existence or _existence(),
        label_result=label or _label(),
        approvals=[_approval()] if approvals is None else approvals,
    )


def test_positive_single_figure_door_with_valid_approval_is_review_only():
    r = _assess()
    assert r["first_remaining_gate"] == "owner_approved_door_area_review_only"
    assert r["width_mm"] == 810.0 and r["height_mm"] == 2050.0
    assert r["area_m2"] == pytest.approx(0.81 * 2.05)
    assert r["second_axis_basis"] == "user_approved"
    assert r["measurement_published"] is False and r["shadow_only"] is True
    assert r["used_typical_door_height_convention"] is False
    assert r["approval_id"] and r["label_evidence_id"] == "label-ev-1" and r["approved_by"] == "Test Owner"


def test_two_figure_label_keeps_its_own_path_and_ignores_the_approval():
    r = _assess(label=_label(values=(1200.0, 1810.0), kind="window"))
    assert r["first_remaining_gate"] == "printed_second_axis_present"
    assert r["area_m2"] is None
    r = _assess(label=_label(values=(900.0, 2100.0), kind="door"))
    assert r["first_remaining_gate"] == "printed_second_axis_present" and r["area_m2"] is None


@pytest.mark.parametrize("kind", ["window", None, "stacker"])
def test_only_an_authenticated_door_may_use_the_approval(kind):
    r = _assess(label=_label(kind=kind))
    assert r["first_remaining_gate"] == "opening_kind_not_door_authenticated" and r["area_m2"] is None


def test_label_for_another_opening_is_not_used():
    r = _assess(label=_label(record_id=OTHER_RECORD_ID))
    assert r["first_remaining_gate"] == "label_not_bound_to_opening" and r["area_m2"] is None


@pytest.mark.parametrize("status", [EvidenceResolutionStatus.ABSTAINED, EvidenceResolutionStatus.CONFLICT])
def test_uncorroborated_label_never_carries_an_area(status):
    r = _assess(label=OpeningLabelDimensionResult(status=status, reason_codes=("x",), evidence=None))
    assert r["first_remaining_gate"] == "label_dimension_not_corroborated" and r["area_m2"] is None


def test_no_printed_figure_is_never_replaced_by_a_swing_or_default():
    r = _assess(label=_label(values=()))
    assert r["first_remaining_gate"] == "single_figure_not_available" and r["area_m2"] is None


def test_no_approval_for_this_opening_abstains():
    assert _assess(approvals=[])["first_remaining_gate"] == "owner_approval_absent"
    other = _approval(geometry_ref=OTHER_RECORD_ID)
    assert _assess(approvals=[other])["first_remaining_gate"] == "owner_approval_absent"


@pytest.mark.parametrize("overrides", [
    {"approved_by": ""}, {"approved_by": "   "}, {"approved_by": None},
    {"approved_at": None}, {"approved_at": "2026-11-05T07:10:00"}, {"approved_at": "not a date"},
    {"unit": "m"}, {"unit": "MM"},
    {"value": -1.0}, {"value": 0.0}, {"value": 100.0}, {"value": 9000.0},
    {"source_type": MeasurementAuthorityType.DOCUMENTED_DIMENSION.value},
    {"authority_status": AuthorityStatus.FIRM.value},
    {"page": 4},
    {"metadata": {"second_axis": "height", "single_figure_axis": "width", "source_sha256": "b" * 64}},
    {"metadata": {"second_axis": "width", "single_figure_axis": "width", "source_sha256": SHA}},
    {"metadata": {"second_axis": "height", "single_figure_axis": "height", "source_sha256": SHA}},
    {"metadata": {"second_axis": "height", "source_sha256": SHA}},
    {"metadata": {}},
])
def test_invalid_approval_never_grants_a_height(overrides):
    r = _assess(approvals=[_approval(**overrides)])
    assert r["first_remaining_gate"] in {"owner_approval_invalid", "approved_height_outside_opening_bounds"}
    assert r["area_m2"] is None and r["height_mm"] is None and r["measurement_published"] is False


def test_bool_value_is_not_a_height():
    r = _assess(approvals=[_approval(value=True)])
    assert r["first_remaining_gate"] == "owner_approval_invalid" and r["area_m2"] is None


def test_two_different_approvals_for_one_opening_conflict():
    r = _assess(approvals=[_approval(2050.0), _approval(2100.0)])
    assert r["first_remaining_gate"] == "owner_approval_conflict" and r["area_m2"] is None


def test_an_invalid_second_approval_for_the_same_opening_still_conflicts():
    r = _assess(approvals=[_approval(2050.0), _approval(2100.0, approved_by="")])
    assert r["first_remaining_gate"] == "owner_approval_conflict"


def test_identical_duplicate_approvals_collapse():
    r = _assess(approvals=[_approval(), _approval()])
    assert r["first_remaining_gate"] == "owner_approved_door_area_review_only"


def test_approval_order_does_not_change_the_result_or_id():
    items = [_approval(2050.0), _approval(2050.0, geometry_ref=OTHER_RECORD_ID), _approval(2050.0, approved_by="Other Person")]
    results = {repr(_assess(approvals=list(order))) for order in permutations(items)}
    assert len(results) == 1


def test_replay_is_deterministic_and_inputs_are_not_mutated():
    existence, label, approvals = _existence(), _label(), [_approval()]
    before = (asdict(existence), asdict(label), [asdict(a) for a in approvals])
    first = assess_owner_approved_door_area_shadow(existence_record=existence, label_result=label, approvals=approvals)
    second = assess_owner_approved_door_area_shadow(existence_record=existence, label_result=label, approvals=approvals)
    assert first == second
    assert before == (asdict(existence), asdict(label), [asdict(a) for a in approvals])
    assert first["approval_id"] == _assess()["approval_id"]


def test_approval_id_changes_with_the_approved_value():
    assert _assess(approvals=[_approval(2050.0)])["approval_id"] != _assess(approvals=[_approval(2060.0)])["approval_id"]


def test_wrong_types_raise_instead_of_guessing():
    with pytest.raises(TypeError):
        assess_owner_approved_door_area_shadow(existence_record=_existence(), label_result={"status": "x"}, approvals=[])
    with pytest.raises(TypeError):
        assess_owner_approved_door_area_shadow(existence_record=_existence(), label_result=_label(), approvals=[{"value": 2100}])
    with pytest.raises(TypeError):
        assess_owner_approved_door_area_shadow(existence_record=_existence(), label_result=_label(), approvals="2100")


def test_the_existing_gate_still_refuses_a_bare_typical_height():
    r = assess_door_height_owner_gate_shadow(physical_opening_id="o", owned_height_mm=2100.0)
    assert r["first_remaining_gate"] == "door_height_unproven_no_owned_atom"
    assert r["used_typical_door_height_convention"] is True


def test_deepcopy_of_inputs_gives_the_same_decision():
    assert _assess() == assess_owner_approved_door_area_shadow(
        existence_record=deepcopy(_existence()), label_result=deepcopy(_label()), approvals=deepcopy([_approval()]))
