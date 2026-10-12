"""GPT1 Q07: an abstained replay may not hide a disputed room source ID."""
from dataclasses import replace

import pytest

from pb_live_room_area_source_closed_export import (
    build_live_room_area_source_traces,
    seal_live_room_area_run,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_floor_area_quantity_publication_integrity import (
    _claim_with_canonical_room,
    _source_area,
)


def _traces(*quantities):
    return build_live_room_area_source_traces(
        _claim_with_canonical_room(*quantities),
        workspace_id=1, project_id="exact-source-room",
    )


@pytest.mark.parametrize("reverse", (False, True))
def test_nonfirm_duplicate_source_id_cannot_hide_under_firm_area(reverse):
    firm = _source_area()
    unresolved = replace(
        firm, value=None, abstained=True, status="provisional",
        blocking_reasons=("unresolved_source",),
    )
    pair = (unresolved, firm) if reverse else (firm, unresolved)
    with pytest.raises(SourceClosedRunConflictError, match="duplicate room-area"):
        _traces(*pair)
    with pytest.raises(SourceClosedRunConflictError, match="duplicate room-area"):
        seal_live_room_area_run(
            _claim_with_canonical_room(*pair),
            workspace_id=1, project_id="exact-source-room",
        )


def test_unrelated_distinct_source_id_abstention_is_not_zero_or_a_conflict():
    firm = _source_area()
    unsupported = replace(
        firm, quantity_id="other-unresolved-room-area",
        value=None, abstained=True, status="provisional",
        blocking_reasons=("room_area_unavailable",),
    )
    traces = _traces(firm, unsupported)
    assert tuple(traces) == (firm.quantity_id,)
    assert traces[firm.quantity_id].source_sha256 == "a" * 64


def test_two_abstained_receipts_cannot_reuse_one_source_identity():
    source = _source_area()
    unsupported = replace(
        source, value=None, abstained=True, status="provisional",
        blocking_reasons=("source_room_face_unavailable",),
    )
    with pytest.raises(SourceClosedRunConflictError, match="duplicate room-area"):
        _traces(unsupported, unsupported)


@pytest.mark.parametrize("wrong", ("", " original-source-area", "original-source-area ", True))
def test_invalid_unpublished_source_identity_cannot_be_filtered_away(wrong):
    source = _source_area()
    blocked = replace(
        source, value=None, abstained=True, status="provisional",
        blocking_reasons=("unavailable",),
    )
    # A constructor already blocks blank IDs. A deserialised/replayed object
    # can still carry a mutated original source ID at the sealing boundary;
    # exercise the exporter rather than failing fixture construction.
    object.__setattr__(blocked, "quantity_id", wrong)
    with pytest.raises(SourceClosedRunConflictError, match="invalid original room-area"):
        _traces(source, blocked)


def test_single_original_firm_area_still_source_closes():
    source = _source_area()
    traces = _traces(source)
    assert tuple(traces) == (source.quantity_id,)
