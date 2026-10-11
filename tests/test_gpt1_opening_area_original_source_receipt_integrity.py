"""Q04 source-measured opening area must not normalize forged original receipts."""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_live_opening_area_quantity_publication import _opening_quantity
from tests.test_live_opening_area_quantity_publication import _opening


@pytest.mark.parametrize("bad", [True, False, "2.172", 10 ** 400,
                                  float("nan"), float("inf")])
def test_opening_metric_cannot_publish_boolean_string_or_overflow(bad):
    assert _opening_quantity(replace(_opening(), area_m2=bad)) is None


@pytest.mark.parametrize("receipts", [
    ("figured-1", "figured-1", "host-binding-1", "host-frame-1"),
    ("figured-1", True, "host-binding-1", "host-frame-1"),
    ("figured-1", "  ", "host-binding-1", "host-frame-1"),
    ("figured-1", "host-binding-1", "host-frame-1", "host-frame-1"),
    ("figured-1", "host-binding-1", " host-frame-1"),
])
def test_opening_source_receipts_must_remain_original_typed_and_unique(receipts):
    assert _opening_quantity(replace(_opening(), evidence_ids=receipts)) is None


@pytest.mark.parametrize("field", [
    "canonical_opening_id", "physical_opening_id",
    "document_id", "revision_id", "snapshot_id", "page_id",
    "viewport_id", "host_wall_id", "representative_observation_id",
])
def test_opening_required_physical_source_identity_cannot_be_boolean(field):
    assert _opening_quantity(replace(_opening(), **{field: True})) is None


def test_source_owned_figured_opening_keeps_exact_original_2_172_m2():
    opening = _opening()
    quantity = _opening_quantity(opening)
    assert quantity is not None
    assert quantity.value == 2.172
    assert quantity.metadata["measurement_record_id"] == "figured-1"


def test_real_frame_host_remains_supported_without_optional_binding():
    opening = replace(
        _opening(),
        host_binding_record_id="",
    )
    quantity = _opening_quantity(opening)
    assert quantity is not None
    assert quantity.metadata["host_frame_record_id"] == "host-frame-1"



def _authenticated_schedule_frame():
    return replace(
        _opening(
            area_m2=2.16,
            area_basis="authenticated_frame_schedule",
            figured_area_record_id=None,
        ),
        schedule_binding_record_id="schedule-binding-1",
        schedule_declared_width_mm=1200,
        schedule_declared_height_mm=1800,
        schedule_row_dimension_basis="frame",
        schedule_row_basis_source="frame width",
        evidence_ids=(
            "opening-1", "source-observation-1", "schedule-binding-1",
            "schedule-row-1", "host-binding-1", "host-frame-1",
        ),
    )


def test_source_proven_outer_frame_dimensions_publish_exact_2_16_m2():
    quantity = _opening_quantity(_authenticated_schedule_frame())
    assert quantity is not None
    assert quantity.value == 2.16
    assert quantity.metadata["schedule_row_dimension_basis"] == "frame"


@pytest.mark.parametrize("bad", [2.17, 1.8, True, False, "2.16"])
def test_replayed_schedule_frame_area_must_agree_with_original_dimensions(bad):
    assert _opening_quantity(replace(_authenticated_schedule_frame(), area_m2=bad)) is None


@pytest.mark.parametrize("field,bad", [
    ("schedule_declared_width_mm", True),
    ("schedule_declared_width_mm", "1200"),
    ("schedule_declared_width_mm", 0),
    ("schedule_declared_height_mm", False),
    ("schedule_declared_height_mm", float("nan")),
    ("schedule_declared_height_mm", 10 ** 400),
])
def test_untyped_frame_source_dimensions_cannot_mint_opening_area(field, bad):
    opening = _authenticated_schedule_frame()
    from copy import copy
    altered = copy(opening)
    object.__setattr__(altered, field, bad)
    assert _opening_quantity(altered) is None



@pytest.mark.parametrize("fake_sha", ["f" * 63, "bad", "z" * 64, "f" * 65])
def test_opening_area_requires_full_original_source_hash(fake_sha):
    assert _opening_quantity(replace(_opening(), source_sha256=fake_sha)) is None


@pytest.mark.parametrize("altered_source", [
    (), ("foreign-source-observation",), ("source-observation-1", True),
    ("source-observation-1", "source-observation-1"),
    (" source-observation-1",),
])
def test_opening_area_requires_exact_producer_owned_source_observation_universe(altered_source):
    assert _opening_quantity(
        replace(_opening(), source_observation_ids=altered_source)
    ) is None


def test_opening_area_cannot_keep_host_and_figured_receipts_but_lose_physical_observation():
    opening = _opening()
    tampered = replace(
        opening,
        evidence_ids=tuple(
            value for value in opening.evidence_ids
            if value != opening.representative_observation_id
        ),
    )
    assert _opening_quantity(tampered) is None
    valid = _opening_quantity(opening)
    assert valid is not None and valid.value == 2.172


def _opening_final_source_claim():
    from tests.test_live_floor_finish_area_source_closed_export import _claim
    opening = _opening()
    quantity = _opening_quantity(opening)
    assert quantity is not None
    return replace(
        _claim(), canonical_openings=(opening,),
        opening_quantity_evidence=(quantity,),
    )


def test_real_producer_opening_area_claim_still_builds_one_source_closed_trace():
    from pb_live_opening_source_closed_export import (
        build_live_opening_area_claim_source_traces,
        seal_live_opening_area_claim_run,
    )

    claim = _opening_final_source_claim()
    qty = claim.opening_quantity_evidence[0]
    traces = build_live_opening_area_claim_source_traces(
        claim, workspace_id=1, project_id="source-opening-original",
    )
    assert set(traces) == {qty.quantity_id}
    sealed = seal_live_opening_area_claim_run(
        claim, workspace_id=1, project_id="source-opening-original",
    )
    assert len(sealed.quantities) == 1
    assert sealed.quantities[0].value == 2.172


@pytest.mark.parametrize("altered", [
    {"value": 3.1},
    {"value": 2.172001},
    {"authority": "copied_source"},
    {"status": "firm"},
    {"confidence": 0.7},
    {"formula": "replayed_m2_without_physical_source"},
    {"semantic_key": "window_area:foreign-opening"},
    {"metadata": {"source_sha256": "f" * 64}},
])
def test_replayed_opening_quantity_fails_final_seal_even_with_unchanged_id_and_receipts(altered):
    from pb_live_opening_source_closed_export import seal_live_opening_area_claim_run
    from pb_source_closed_run_export import SourceClosedRunConflictError

    claim = _opening_final_source_claim()
    genuine = claim.opening_quantity_evidence[0]
    if "metadata" in altered:
        altered = {
            "metadata": {**dict(genuine.metadata), **altered["metadata"]},
        }
    forged = replace(genuine, **altered)
    # This deliberately retains the original source evidence IDs and quantity
    # ID: only full producer replay can detect the changed value/semantic claim.
    assert forged.quantity_id == genuine.quantity_id
    assert forged.evidence_ids == genuine.evidence_ids
    with pytest.raises(SourceClosedRunConflictError, match="does not match current physical source"):
        seal_live_opening_area_claim_run(
            replace(claim, opening_quantity_evidence=(forged,)),
            workspace_id=1, project_id="source-opening-original",
        )
