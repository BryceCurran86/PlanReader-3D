"""Owner-approved second axis: canonical opening object and area-quantity issuer (default-off, review lineage only).

The approved height is an owner-supplied ASSUMPTION. A quantity built on it is a reviewable shadow row: it must carry its basis,
never reach the customer projection, and leave every existing basis and every default object byte-identical.
Synthetic numbers only; no project value is an oracle.
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from pb_live_opening_area_quantity_publication import (
    LIVE_OPENING_OWNER_APPROVED_SECOND_AXIS_AREA_QUANTITY_AUTHORITY,
    LIVE_OPENING_AREA_QUANTITY_RESOLVED,
    _opening_quantity,
    publish_live_opening_area_quantities,
)
from pb_live_opening_customer_projection import _eligible_area_quantities
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from tests.test_live_opening_area_quantity_publication import _composition, _opening

BASIS = "owner_approved_second_axis"
APPROVAL_ID = "owner-approval-1"
LABEL_ID = "label-evidence-1"


def _owner_opening(width: float = 810.0, height: float = 2050.0, **overrides):
    base = _opening(kind="door", area_m2=width * height / 1_000_000.0, area_basis=BASIS,
                    figured_area_record_id=LABEL_ID)
    fields = dict(
        owner_approved_second_axis_record_id=APPROVAL_ID,
        owner_approved_width_mm=width,
        owner_approved_height_mm=height,
        evidence_ids=(*base.evidence_ids, APPROVAL_ID),
    )
    fields.update(overrides)
    return replace(base, **fields)


def test_default_object_serialisation_is_unchanged_and_owner_keys_appear_only_when_set():
    assert not any(key.startswith("owner_approved") for key in _opening().to_dict())
    assert _opening().owner_approved_second_axis_record_id is None
    owner = _owner_opening().to_dict()
    assert owner["owner_approved_second_axis_record_id"] == APPROVAL_ID
    assert owner["owner_approved_width_mm"] == 810.0 and owner["owner_approved_height_mm"] == 2050.0


def test_positive_owner_approved_area_is_a_review_shadow_quantity():
    q = _opening_quantity(_owner_opening())
    assert q is not None
    assert q.family == "opening_area" and q.unit == "m2"
    assert q.value == pytest.approx(0.81 * 2.05)
    assert q.authority == LIVE_OPENING_OWNER_APPROVED_SECOND_AXIS_AREA_QUANTITY_AUTHORITY
    assert q.status == "review_required"
    assert q.abstained is False and q.blocking_reasons == ()
    assert q.metadata["area_basis"] == BASIS
    assert q.metadata["measurement_record_id"] == APPROVAL_ID
    assert q.metadata["second_axis_basis"] == "user_approved"
    assert q.metadata["owner_approved_width_mm"] == 810.0 and q.metadata["owner_approved_height_mm"] == 2050.0
    assert q.metadata["shadow_only"] is True
    assert q.metadata["commercial_projection_allowed"] is False
    assert LIVE_OPENING_AREA_QUANTITY_RESOLVED in q.reason_codes
    assert "owner_approved_second_axis_is_an_assumption" in q.reason_codes
    assert APPROVAL_ID in q.evidence_ids and LABEL_ID in q.evidence_ids


def test_it_never_reaches_the_customer_projection_by_default():
    q = _opening_quantity(_owner_opening())
    assert _eligible_area_quantities(SimpleNamespace(opening_quantity_evidence=(q,))) == ()


def test_existing_bases_are_unchanged():
    q = _opening_quantity(_opening())
    assert q is not None and q.status == "corroborated"
    assert q.metadata["commercial_projection_allowed"] is True
    assert "shadow_only" not in q.metadata and "second_axis_basis" not in q.metadata
    assert q.reason_codes == (LIVE_OPENING_AREA_QUANTITY_RESOLVED,)
    assert _eligible_area_quantities(SimpleNamespace(opening_quantity_evidence=(q,))) == (q,)


@pytest.mark.parametrize("overrides", [
    {"area_m2": 2.0},                                              # replayed area disagrees with the product
    {"area_m2": None},
    {"evidence_ids": ("opening-1", "source-observation-1", "host-binding-1", "host-frame-1", LABEL_ID)},  # approval not retained
    {"evidence_ids": ("opening-1", "source-observation-1", "host-binding-1", "host-frame-1", APPROVAL_ID)},  # label not retained
    {"figured_area_record_id": None},
    {"owner_approved_second_axis_record_id": None},
    {"owner_approved_second_axis_record_id": ""},
    {"owner_approved_second_axis_record_id": " owner-approval-1"},
    {"owner_approved_width_mm": None}, {"owner_approved_height_mm": None},
    {"owner_approved_width_mm": True}, {"owner_approved_height_mm": True},
    {"owner_approved_width_mm": -1.0}, {"owner_approved_height_mm": 0.0},
    {"owner_approved_width_mm": float("nan")},
    {"width_m": 0.81}, {"height_m": 2.05},                         # the approved axes must not masquerade as metric axes
    {"geometry_complete": True},
    {"opening_kind": "window"}, {"opening_kind": None},
    {"host_wall_id": None},
])
def test_any_inconsistent_or_unretained_input_publishes_nothing(overrides):
    assert _opening_quantity(_owner_opening(**overrides)) is None


def test_the_basis_cannot_ride_on_another_authority_basis_or_missing_basis():
    assert _opening_quantity(replace(_owner_opening(), area_basis="owner_approved_second_axis_x")) is None
    assert _opening_quantity(replace(_owner_opening(), area_basis=None)) is None


def test_publication_is_deterministic_and_does_not_mutate_the_input():
    opening = _owner_opening()
    before = opening.to_dict()
    composition = _composition(opening)
    first = publish_live_opening_area_quantities(composition)
    second = publish_live_opening_area_quantities(composition)
    assert first == second and len(first) == 1
    assert opening.to_dict() == before


def test_quantity_id_depends_on_the_approval_record():
    a = _opening_quantity(_owner_opening())
    other = _owner_opening(owner_approved_second_axis_record_id="owner-approval-2",
                           evidence_ids=("opening-1", "source-observation-1", "host-binding-1", "host-frame-1",
                                         LABEL_ID, "owner-approval-2"))
    b = _opening_quantity(other)
    assert a is not None and b is not None and a.quantity_id != b.quantity_id


def test_composition_rejects_malformed_approvals_before_doing_any_work():
    with pytest.raises(TypeError, match="owner_approved_second_axis"):
        compose_live_physical_opening_voids(
            source_visibility_producer=object(), wall_opening_composition=object(),
            owner_approved_second_axis=["not a record"])
    with pytest.raises(TypeError, match="owner_approved_second_axis"):
        compose_live_physical_opening_voids(
            source_visibility_producer=object(), wall_opening_composition=object(),
            owner_approved_second_axis="2100")
