"""Owner-approved door review export (layer B): default-off, unwired, review lineage only.

An owner-approved height is an ASSUMPTION. A door area built on it may become an estimator-review row ("To review", origin AI, all three commercial
gates closed) with exact lineage, exactly like the ceiling review path, and nothing more: never FIRM or CORROBORATED, never publishable, never priced.
Synthetic numbers only; no project width, height or area is used anywhere in this file.
"""
from __future__ import annotations

import pathlib
import re
from dataclasses import replace

import pytest

import pb_owner_approved_door_review_promotion as promo
from pb_door_height_owner_gate_shadow import owner_height_approval_id
from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType, MeasurementRecord
from pb_customer_output_verification import verify_sealed_customer_output
from pb_live_opening_area_quantity_publication import (
    _opening_quantity,
    publish_live_opening_area_quantities,
)
from pb_owner_approved_door_review_promotion import (
    OWNER_DOOR_REVIEW_QUANTITY_AUTHORITY,
    build_owner_approved_door_review_candidates,
    seal_owner_approved_door_review_run,
)
from pb_quantity_takeoff_adapter import existing_commercial_gate_results
from pb_source_closed_run_export import (
    SourceClosedRunConflictError,
    seal_source_closed_quantity,
    sealed_source_closed_run_from_dict,
)
from tests.test_live_opening_area_quantity_publication import SHA, _composition, _opening

BASIS = "owner_approved_second_axis"
LABEL_ID = "label-evidence-1"
WIDTH, HEIGHT = 800.0, 2000.0
STAMP = "2026-01-01T09:00:00+10:00"


def _approval(**overrides) -> MeasurementRecord:
    fields = dict(
        value=HEIGHT, unit="mm", source_type=MeasurementAuthorityType.USER_APPROVED.value, confidence=1.0,
        sheet="", page=3, scale="", geometry_ref="opening-1",
        authority_status=AuthorityStatus.USER_APPROVED.value, approved_by="Test Approver", approved_at=STAMP,
        metadata={"second_axis": "height", "single_figure_axis": "width", "source_sha256": SHA},
    )
    fields.update(overrides)
    return MeasurementRecord(**fields)


def _owner_opening(approval: MeasurementRecord | None = None, *, canonical_id: str = "opening-1",
                   width: float = WIDTH, height: float = HEIGHT, **overrides):
    approval = approval if approval is not None else _approval(geometry_ref=canonical_id, value=height)
    approval_id = owner_height_approval_id(approval)
    base = _opening(canonical_id=canonical_id, kind="door", area_m2=width * height / 1_000_000.0,
                    area_basis=BASIS, figured_area_record_id=LABEL_ID)
    fields = dict(
        owner_approved_second_axis_record_id=approval_id,
        owner_approved_width_mm=width,
        owner_approved_height_mm=height,
        evidence_ids=(*base.evidence_ids, approval_id),
    )
    fields.update(overrides)
    return replace(base, **fields)


def _build(openings, approvals=None, *, workspace_id=7, project_id="proj-1"):
    openings = tuple(openings)
    approvals = tuple(approvals if approvals is not None else (_approval(),))
    return build_owner_approved_door_review_candidates(
        _composition(*openings), approvals=approvals, workspace_id=workspace_id, project_id=project_id)


def _one():
    collection = _build([_owner_opening()])
    assert len(collection.candidates) == 1 and collection.withheld == ()
    return collection.candidates[0]


# ---------------------------------------------------------------- positive

def test_one_owner_approved_door_becomes_one_review_candidate():
    candidate = _one()
    q = candidate.promoted_quantity
    assert q.family == "opening_area" and q.unit == "m2"
    assert q.value == pytest.approx(WIDTH * HEIGHT / 1_000_000.0)
    assert q.authority == OWNER_DOOR_REVIEW_QUANTITY_AUTHORITY
    assert "figured" in q.authority                                   # width is the printed figure; the height is not
    assert q.status == "review_required" and q.abstained is False and q.blocking_reasons == ()
    assert q.input_entity_ids == ("opening-1",)
    assert q.metadata["shadow_only"] is False and q.metadata["commercial_projection_allowed"] is True
    assert q.metadata["commercial_review_required"] is True
    assert q.metadata["owner_approved_door_review_promotion"] is True
    assert q.metadata["area_basis"] == BASIS and q.metadata["second_axis_basis"] == "user_approved"
    assert q.metadata["owner_approved_by"] == "Test Approver" and q.metadata["owner_approved_at"] == STAMP
    assert q.metadata["owner_approved_height_mm"] == HEIGHT and q.metadata["owner_approved_width_mm"] == WIDTH
    assert q.metadata["promotion_parent_quantity_id"] == candidate.shadow_quantity_id != q.quantity_id
    assert "owner_approved_second_axis_is_an_assumption" in q.reason_codes
    assert "estimator_review_required" in q.reason_codes
    assert q.metadata["owner_approved_second_axis_record_id"] in q.evidence_ids and LABEL_ID in q.evidence_ids


def test_the_row_is_an_unreviewed_ai_row_and_every_commercial_gate_stays_closed():
    row = _one().review_row
    assert row["origin"] == "AI" and row["quantity_status"] == "To review"
    assert row["quantity"] == pytest.approx(WIDTH * HEIGHT / 1_000_000.0) and row["unit"] == "m2"
    assert row["measurement_method"] == "figured_dimension" and row["figured_dimension_ids"] == [LABEL_ID]
    assert row["quantity_authority"] == OWNER_DOOR_REVIEW_QUANTITY_AUTHORITY
    gates = existing_commercial_gate_results(row)
    assert set(gates) == {"publishability", "pricing", "jobhub"} and not any(g[0] for g in gates.values())


def test_the_source_trace_is_exact():
    candidate = _one()
    trace, opening = candidate.source_trace, _owner_opening()
    assert (trace.workspace_id, trace.project_id) == (7, "proj-1")
    assert (trace.document_id, trace.source_sha256, trace.source_page) == (opening.document_id, SHA, opening.page_id)
    assert (trace.viewport_id, trace.revision_id, trace.current_revision_id) == (opening.viewport_id, "rev-1", "rev-1")
    assert trace.canonical_entity_ids == ("opening-1",)
    assert set(candidate.promoted_quantity.evidence_ids) <= set(trace.evidence_ids)
    assert candidate.measurement_authority.method == "figured_dimension"
    assert candidate.measurement_authority.figured_dimension_ids == (LABEL_ID,)


def test_seal_and_customer_verification_accept_the_review_lineage():
    candidate = _one()
    run = seal_owner_approved_door_review_run([candidate], project_id="proj-1")
    assert len(run.quantities) == 1
    sealed = run.quantities[0]
    assert sealed.lineage_ok is True and sealed.lineage_reason_codes == ()
    assert sealed.status == "review_required" and sealed.authority == OWNER_DOOR_REVIEW_QUANTITY_AUTHORITY
    assert verify_sealed_customer_output(run, [candidate.review_row]) is not None
    assert sealed_source_closed_run_from_dict(run.to_dict()).fingerprint == run.fingerprint


def test_customer_verification_rejects_a_row_that_disagrees_with_the_seal():
    candidate = _one()
    run = seal_owner_approved_door_review_run([candidate], project_id="proj-1")
    for tamper in ({"quantity": candidate.review_row["quantity"] + 0.5}, {"quantity_id": "other"}):
        with pytest.raises(Exception):
            verify_sealed_customer_output(run, [{**candidate.review_row, **tamper}])


# ------------------------------------------------- default path and look-alikes

def test_no_owner_basis_openings_means_nothing_is_built():
    collection = _build([_opening(canonical_id="w1", kind="window"), _opening(canonical_id="d1", kind="door")], approvals=())
    assert collection.candidates == () and collection.withheld == ()


def test_corroborated_areas_are_never_promoted_and_stay_publishable_on_their_own_path():
    q = _opening_quantity(_opening(canonical_id="d1", kind="door"))
    assert q is not None and q.status == "corroborated"
    assert _build([_opening(canonical_id="d1", kind="door")]).candidates == ()


def test_a_window_with_owner_fields_publishes_nothing_so_nothing_is_promoted():
    assert _opening_quantity(_owner_opening(opening_kind="window")) is None
    assert _build([_owner_opening(opening_kind="window")]).candidates == ()


def test_a_two_figure_or_otherwise_based_door_is_not_touched():
    other = replace(_opening(canonical_id="opening-1", kind="door"), area_basis="authenticated_frame_schedule")
    assert _build([other]).candidates == ()


# ------------------------------------------------------- approval verification

@pytest.mark.parametrize("overrides,reason", [
    ({"page": 4}, "owner_approval_invalid"),
    ({"unit": "m"}, "owner_approval_invalid"),
    ({"source_type": MeasurementAuthorityType.PDF_SCALED.value}, "owner_approval_invalid"),
    ({"authority_status": AuthorityStatus.FIRM.value}, "owner_approval_invalid"),
    ({"approved_by": ""}, "owner_approval_invalid"),
    ({"approved_by": None}, "owner_approval_invalid"),
    ({"approved_at": "2026-01-01T09:00:00"}, "owner_approval_invalid"),
    ({"approved_at": "not a date"}, "owner_approval_invalid"),
    ({"metadata": {"second_axis": "width", "single_figure_axis": "width", "source_sha256": SHA}}, "owner_approval_invalid"),
    ({"metadata": {"second_axis": "height", "single_figure_axis": "height", "source_sha256": SHA}}, "owner_approval_invalid"),
    ({"metadata": {"second_axis": "height", "single_figure_axis": "width", "source_sha256": "b" * 64}}, "owner_approval_invalid"),
    ({"value": -5.0}, "owner_approval_invalid"),
])
def test_an_invalid_approval_withholds_the_candidate_with_a_typed_reason(overrides, reason):
    approval = _approval(**overrides)
    collection = _build([_owner_opening(approval)], approvals=[approval])
    assert collection.candidates == ()
    assert [(w.canonical_opening_id, w.reason_code) for w in collection.withheld] == [("opening-1", reason)]


def test_an_approval_for_another_opening_cannot_be_used():
    foreign = _approval(geometry_ref="opening-2")
    opening = _owner_opening(_approval())                         # canonical object retains the id of the REAL approval
    collection = _build([opening], approvals=[foreign])
    assert collection.candidates == ()
    assert [w.reason_code for w in collection.withheld] == ["owner_approval_absent"]


def test_an_approval_that_is_not_the_one_the_opening_retains_cannot_be_used():
    other_height = _approval(value=HEIGHT + 100.0)
    collection = _build([_owner_opening()], approvals=[other_height])
    assert collection.candidates == () and [w.reason_code for w in collection.withheld] == ["owner_approval_absent"]


def test_two_conflicting_approvals_for_one_opening_withhold_it():
    a, b = _approval(), _approval(value=HEIGHT + 100.0)
    collection = _build([_owner_opening(a)], approvals=[a, b])
    assert collection.candidates == () and [w.reason_code for w in collection.withheld] == ["owner_approval_conflict"]


def test_the_same_approval_supplied_twice_is_one_approval():
    a = _approval()
    assert len(_build([_owner_opening(a)], approvals=[a, replace(a)]).candidates) == 1


def test_the_canonical_height_must_equal_the_approved_height():
    a = _approval()
    lie = _owner_opening(a, owner_approved_height_mm=HEIGHT + 50.0, area_m2=WIDTH * (HEIGHT + 50.0) / 1_000_000.0)
    collection = _build([lie], approvals=[a])
    assert collection.candidates == ()
    assert [w.reason_code for w in collection.withheld] == ["owner_approved_height_mismatch"]


@pytest.mark.parametrize("height", [1.0, 50_000.0])
def test_an_approved_height_outside_the_opening_bounds_is_withheld(height):
    approval = _approval(value=height)
    opening = _owner_opening(approval, height=height)
    collection = _build([opening], approvals=[approval])
    assert collection.candidates == ()
    assert [w.reason_code for w in collection.withheld] == ["approved_height_outside_opening_bounds"]


def test_an_owner_basis_opening_that_publishes_no_quantity_is_withheld_with_its_reason():
    collection = _build([_owner_opening(opening_kind="window")])
    assert collection.candidates == ()
    assert [(w.canonical_opening_id, w.reason_code) for w in collection.withheld] == [
        ("opening-1", "owner_basis_quantity_not_published")]


def test_missing_approvals_withhold_with_a_typed_reason_and_never_fall_back_to_a_default():
    collection = _build([_owner_opening()], approvals=())
    assert collection.candidates == () and [w.reason_code for w in collection.withheld] == ["owner_approval_absent"]


# ---------------------------------------------------------- invariance and purity

def test_result_is_independent_of_input_order_and_repeatable():
    a1, a2 = _approval(geometry_ref="d1"), _approval(geometry_ref="d2")
    o1, o2 = _owner_opening(a1, canonical_id="d1"), _owner_opening(a2, canonical_id="d2")
    first = _build([o1, o2], approvals=[a1, a2])
    second = _build([o2, o1], approvals=[a2, a1])
    again = _build([o1, o2], approvals=[a1, a2])
    ids = lambda c: [x.promoted_quantity.quantity_id for x in c.candidates]  # noqa: E731
    assert ids(first) == ids(second) == ids(again) == sorted(ids(first)) and len(ids(first)) == 2
    assert [x.review_row for x in first.candidates] == [x.review_row for x in second.candidates]


def test_unrelated_openings_in_the_composition_do_not_change_a_candidate():
    alone = _one()
    crowded = _build([_owner_opening(), _opening(canonical_id="w1", kind="window"),
                      _opening(canonical_id="d9", kind="door")]).candidates
    assert [c.promoted_quantity for c in crowded] == [alone.promoted_quantity]
    assert [c.review_row for c in crowded] == [alone.review_row]


def test_inputs_are_not_mutated():
    approval, opening = _approval(), _owner_opening()
    composition = _composition(opening)
    before = (opening.to_dict(), repr(approval), publish_live_opening_area_quantities(composition))
    build_owner_approved_door_review_candidates(composition, approvals=(approval,), workspace_id=7, project_id="proj-1")
    assert (opening.to_dict(), repr(approval), publish_live_opening_area_quantities(composition)) == before


def test_the_quantity_id_depends_on_the_approval_and_the_workspace_does_not_leak_into_it():
    a = _one().promoted_quantity.quantity_id
    other = _approval(approved_by="Someone Else")
    b = _build([_owner_opening(other)], approvals=[other]).candidates[0].promoted_quantity.quantity_id
    c = _build([_owner_opening()], workspace_id=99).candidates[0].promoted_quantity.quantity_id
    assert a != b and a == c


# ----------------------------------------------------------- argument validation

@pytest.mark.parametrize("workspace_id", [True, 1.5, "7", "7a", None])
def test_workspace_id_must_be_a_real_int(workspace_id):
    with pytest.raises(TypeError, match="workspace_id"):
        _build([_owner_opening()], workspace_id=workspace_id)


@pytest.mark.parametrize("workspace_id", [0, -1])
def test_workspace_id_must_be_positive(workspace_id):
    with pytest.raises(ValueError, match="workspace_id"):
        _build([_owner_opening()], workspace_id=workspace_id)


@pytest.mark.parametrize("project_id", [None, 5, b"proj"])
def test_project_id_must_be_a_string(project_id):
    with pytest.raises(TypeError, match="project_id"):
        _build([_owner_opening()], project_id=project_id)


@pytest.mark.parametrize("project_id", ["", "   ", " proj-1", "proj-1 "])
def test_project_id_must_be_nonblank_and_canonical(project_id):
    with pytest.raises(ValueError, match="project_id"):
        _build([_owner_opening()], project_id=project_id)


def _shadow_and_opening():
    opening = _owner_opening()
    (shadow,) = publish_live_opening_area_quantities(_composition(opening))
    return shadow, opening


def _direct(shadow, opening):
    return promo._candidate_or_reason(
        shadow=shadow, opening=opening, approvals=(_approval(),), workspace_id=7, project_id="proj-1")


def test_the_direct_path_accepts_the_untouched_shadow():
    shadow, opening = _shadow_and_opening()
    assert not isinstance(_direct(shadow, opening), str)


@pytest.mark.parametrize("mutate", [
    lambda q: replace(q, metadata={**q.metadata, "shadow_only": False}),
    lambda q: replace(q, metadata={**q.metadata, "commercial_projection_allowed": True}),
    lambda q: replace(q, status="corroborated"),
    lambda q: replace(q, authority="something_else"),
    lambda q: replace(q, metadata={**q.metadata, "area_basis": "figured_opening_label"}),
    lambda q: replace(q, metadata={**q.metadata, "second_axis_basis": "default"}),
    lambda q: replace(q, input_entity_ids=("someone-else",)),
])
def test_a_shadow_that_is_not_the_owner_basis_review_shadow_is_withheld(mutate):
    shadow, opening = _shadow_and_opening()
    assert _direct(mutate(shadow), opening) == "shadow_quantity_not_review_shadow"


def test_the_promoted_row_states_the_assumption_even_if_the_shadow_did_not():
    shadow, opening = _shadow_and_opening()
    candidate = _direct(replace(shadow, reason_codes=()), opening)
    assert not isinstance(candidate, str)
    assert "owner_approved_second_axis_is_an_assumption" in candidate.promoted_quantity.reason_codes


def test_argument_types_are_enforced():
    with pytest.raises(TypeError):
        build_owner_approved_door_review_candidates(object(), approvals=(), workspace_id=7, project_id="p")
    with pytest.raises(TypeError):
        build_owner_approved_door_review_candidates(_composition(), approvals="2000", workspace_id=7, project_id="p")
    with pytest.raises(TypeError):
        build_owner_approved_door_review_candidates(_composition(), approvals=("x",), workspace_id=7, project_id="p")


def test_a_gate_that_opens_is_a_hard_failure(monkeypatch):
    monkeypatch.setattr(promo, "existing_commercial_gate_results", lambda row: {"publishability": (True, "ok")})
    with pytest.raises(RuntimeError, match="gate"):
        _build([_owner_opening()])


# ----------------------------------------------------------------------- seal

def test_seal_accepts_only_promoted_candidates():
    with pytest.raises(TypeError):
        seal_owner_approved_door_review_run([object()], project_id="proj-1")
    with pytest.raises(SourceClosedRunConflictError):
        seal_owner_approved_door_review_run([], project_id="proj-1")


def test_seal_refuses_a_candidate_whose_quantity_no_longer_matches_its_promotion():
    candidate = _one()
    q = candidate.promoted_quantity
    for bad in (
        replace(q, status="corroborated"),
        replace(q, status="provisional"),
        replace(q, metadata={**q.metadata, "shadow_only": True}),
        replace(q, metadata={**q.metadata, "commercial_projection_allowed": False}),
        replace(q, metadata={**q.metadata, "owner_approved_door_review_promotion": False}),
        replace(q, family="wall_area"),
        replace(q, value=q.value + 1.0),
    ):
        with pytest.raises(SourceClosedRunConflictError):
            seal_owner_approved_door_review_run([replace(candidate, promoted_quantity=bad)], project_id="proj-1")


def test_seal_refuses_a_row_that_bypassed_review_or_is_commercially_authorised():
    candidate = _one()
    for bad_row in ({**candidate.review_row, "origin": "USER"}, {**candidate.review_row, "quantity_status": "Approved"},
                    {**candidate.review_row, "quantity_id": "x"}):
        with pytest.raises(SourceClosedRunConflictError):
            seal_owner_approved_door_review_run([replace(candidate, review_row=bad_row)], project_id="proj-1")


def test_seal_refuses_duplicates_and_a_project_mismatch():
    candidate = _one()
    with pytest.raises(SourceClosedRunConflictError, match="duplicate door review quantity id"):
        seal_owner_approved_door_review_run([candidate, candidate], project_id="proj-1")
    with pytest.raises(Exception):
        seal_owner_approved_door_review_run([candidate], project_id="another-project")


# ------------------------------- the lineage exemption is narrow (shared validator)

def _receipt_codes(q):
    return seal_source_closed_quantity(q, trace=_one().source_trace).lineage_reason_codes


def test_the_exemption_admits_exactly_the_door_review_receipt():
    q = _one().promoted_quantity
    assert _receipt_codes(q) == ()


@pytest.mark.parametrize("mutate", [
    lambda q: replace(q, status="provisional"),
    lambda q: replace(q, status="candidate"),
    lambda q: replace(q, family="wall_area"),
    lambda q: replace(q, metadata={**q.metadata, "owner_approved_door_review_promotion": False}),
    lambda q: replace(q, metadata={k: v for k, v in q.metadata.items() if k != "owner_approved_door_review_promotion"}),
    lambda q: replace(q, metadata={**q.metadata, "area_basis": "figured_opening_label"}),
    lambda q: replace(q, metadata={**q.metadata, "opening_kind": "window"}),
    lambda q: replace(q, metadata={**q.metadata, "second_axis_basis": "default"}),
    lambda q: replace(q, metadata={**q.metadata, "shadow_only": True}),
    lambda q: replace(q, metadata={**q.metadata, "owner_approved_second_axis_record_id": "not-retained"}),
    lambda q: replace(q, blocking_reasons=("blocked",)),
    lambda q: replace(q, reason_codes=(*q.reason_codes, "conflict")),
])
def test_anything_short_of_the_full_receipt_is_still_refused(mutate):
    codes = _receipt_codes(mutate(_one().promoted_quantity))
    assert codes, "an incomplete door review receipt must not keep lineage_ok"


def test_the_receipt_does_not_open_review_required_for_other_quantities():
    q = _one().promoted_quantity
    ceilingish = replace(q, family="ceiling_lining", metadata={k: v for k, v in q.metadata.items()
                                                                if k != "owner_approved_door_review_promotion"})
    assert "quantity_status_not_publishable" in _receipt_codes(ceilingish)


def test_a_corroborated_opening_still_seals_exactly_as_before():
    q = _opening_quantity(_opening(canonical_id="d1", kind="door"))
    assert q is not None
    sealed = seal_source_closed_quantity(q, trace=_one().source_trace)
    assert sealed.status == "corroborated"
    assert "quantity_status_not_publishable" not in sealed.lineage_reason_codes


# ------------------------------------------------------------- default-off proof

def test_only_the_handoff_library_imports_the_promotion_module():
    root = pathlib.Path(__file__).resolve().parent.parent
    pattern = re.compile(r"^\s*(from|import)\s+pb_owner_approved_door_review_promotion\b", re.M)
    offenders = [
        str(path.relative_to(root)) for path in list(root.glob("*.py")) + list((root / "tools").glob("*.py"))
        if path.name != "pb_owner_approved_door_review_promotion.py" and pattern.search(path.read_text(encoding="utf-8", errors="ignore"))
    ]
    assert offenders == ["pb_owner_door_review_handoff.py"]   # the default-off handoff library; no tool or production module imports it directly
