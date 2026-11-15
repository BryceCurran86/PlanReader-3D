"""Original ROOM_AREA duplicate veto must never disclose source IDs in errors.

Synthetic source-backed fixtures test public exception boundaries only; they
cannot authorize an original PDF quantity, customer row or frozen score.
"""
from dataclasses import replace
import traceback

import pytest
import shapely.geometry

from pb_live_room_area_source_closed_export import _firm_room_area_quantities
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_gpt1_room_area_duplicate_original_physical_face import (
    _competing_room_claim,
    _trace,
    _seal,
    _customer,
)
from tests.test_live_room_area_source_closed_export import (
    live_claim,
    _second_original_figured_room,
)


QUANTITY_SECRET_A = "PRIVATE_SOURCE_QUANTITY_A_CANARY"
QUANTITY_SECRET_B = "PRIVATE_SOURCE_QUANTITY_B_CANARY"
FIGURE_SECRET_H = "PRIVATE_FIGURED_H_CANARY"
FIGURE_SECRET_V = "PRIVATE_FIGURED_V_CANARY"
GEOMETRY_SECRET = "PRIVATE_PDF_GEOMETRY_123.456_789.012_CANARY"


def _assert_public_error_safe(error, *secrets):
    public = "".join(traceback.format_exception(error))
    for secret in secrets:
        assert secret not in str(error)
        assert secret not in public
    assert error.__cause__ is None
    assert error.__context__ is None


def _private_quantity_ids(claim):
    ids = tuple(
        q.quantity_id for q in claim.room_area_quantity_evidence
        if q.family == "room_area" and q.abstained is False
    )
    assert len(ids) == 2
    remap = {ids[0]: QUANTITY_SECRET_A, ids[1]: QUANTITY_SECRET_B}
    return replace(
        claim,
        room_area_quantity_evidence=tuple(
            replace(q, quantity_id=remap.get(q.quantity_id, q.quantity_id))
            for q in claim.room_area_quantity_evidence
        ),
        canonical_floors=tuple(
            replace(
                floor,
                metric_area_quantity_id=remap.get(
                    floor.metric_area_quantity_id, floor.metric_area_quantity_id
                ),
            )
            for floor in claim.canonical_floors
        ),
    )


@pytest.mark.parametrize("consumer", (_trace, _seal, _customer))
def test_duplicate_physical_face_blocks_without_private_quantity_ids(
    live_claim, consumer,
):
    claim = _private_quantity_ids(
        _competing_room_claim(live_claim, variant="same")
    )
    with pytest.raises(
        SourceClosedRunConflictError, match="same physical PDF room face"
    ) as caught:
        consumer(claim)
    _assert_public_error_safe(caught.value, QUANTITY_SECRET_A, QUANTITY_SECRET_B)


def test_figured_receipt_pair_conflict_redacts_original_native_ids(live_claim):
    claim = _second_original_figured_room(live_claim, same_root=True)
    claim = replace(
        claim,
        room_area_quantity_evidence=tuple(
            replace(
                q,
                metadata={
                    **dict(q.metadata),
                    "figured_dimension_ids": (FIGURE_SECRET_H, FIGURE_SECRET_V),
                },
            )
            for q in claim.room_area_quantity_evidence
        ),
    )
    with pytest.raises(
        SourceClosedRunConflictError, match="one original figured pair"
    ) as caught:
        _firm_room_area_quantities(claim)
    _assert_public_error_safe(caught.value, FIGURE_SECRET_H, FIGURE_SECRET_V)


def test_shapely_exception_does_not_chain_private_geometry_into_public_error(
    live_claim, monkeypatch,
):
    original_polygon = shapely.geometry.Polygon
    calls = [0]

    def hostile_polygon(_points):
        calls[0] += 1
        if calls[0] > 1:
            raise ValueError(GEOMETRY_SECRET)
        return original_polygon(_points)

    # The first call proves the original floor's positive source ring;
    # only the later duplicate-face comparison is made to fail.
    monkeypatch.setattr(shapely.geometry, "Polygon", hostile_polygon)
    with pytest.raises(
        SourceClosedRunConflictError,
        match="original room-area source-face comparison failed closed",
    ) as caught:
        _trace(live_claim)
    _assert_public_error_safe(caught.value, GEOMETRY_SECRET)
