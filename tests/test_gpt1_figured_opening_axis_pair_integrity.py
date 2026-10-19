"""Shadow-only regression: source-owned opening axes must match figured pair.

The helper under test requires distinct source-owned width/height record IDs.
An unordered figured pair is corroboration, never an axis-order issuer.
"""
import pytest

from tools.diag_gptmax_lot16_host_frame_gpt1_handoff import (
    _source_owned_axes_agree_with_figured_pair,
)


def _canonical(width_m=0.9, height_m=2.1):
    return {
        "width_record_id": "independent-source-width",
        "height_record_id": "independent-source-height",
        "geometry_complete": True,
        "evidence_ids": ["independent-source-width", "independent-source-height"],
        "width_m": width_m,
        "height_m": height_m,
    }


def _evidence(pair=(900.0, 2100.0)):
    return {"dimension_values_mm": pair}


@pytest.mark.parametrize("width_m,height_m,pair,expected", [
    (0.9, 2.1, (900.0, 2100.0), True),
    (2.1, 0.9, (900.0, 2100.0), True),
    (0.9, 2.1, [2100.0, 900.0], True),
    # Equal products are NOT source-authenticated equal dimensions.
    (0.7, 2.7, (900.0, 2100.0), False),
    (1.05, 1.8, (900.0, 2100.0), False),
    (0.9, 2.1, (900.0,), False),
    (0.9, 2.1, (900.0, 0.0), False),
    (0.9, 2.1, (900.0, float("nan")), False),
    (True, 2.1, (900.0, 2100.0), False),
    (0.9, 2.1, (True, 2100.0), False),
    (0.9, 2.1, "900x2100", False),
    (0.9, 2.1, None, False),
])
def test_figured_pair_corroborates_both_independent_axes_only(
    width_m, height_m, pair, expected,
):
    assert _source_owned_axes_agree_with_figured_pair(
        _canonical(width_m, height_m), _evidence(pair)
    ) is expected


def test_original_dimension_list_never_mutated():
    pair = [2100.0, 900.0]
    assert _source_owned_axes_agree_with_figured_pair(_canonical(), _evidence(pair))
    assert pair == [2100.0, 900.0]


def test_near_finite_rounding_passes_but_infinite_axis_fails():
    assert _source_owned_axes_agree_with_figured_pair(
        _canonical(), _evidence((900.0000001, 2100.0)))
    assert not _source_owned_axes_agree_with_figured_pair(
        _canonical(float("inf"), 2.1), _evidence())


@pytest.mark.parametrize("mutation", [
    {"width_record_id": ""},
    {"height_record_id": "independent-source-width"},
    {"geometry_complete": False},
    {"evidence_ids": ["independent-source-width"]},
    {"evidence_ids": ["independent-source-height"]},
    {"evidence_ids": []},
])
def test_figured_label_cannot_invent_missing_axis_source_authority(mutation):
    canonical = {**_canonical(), **mutation}
    assert not _source_owned_axes_agree_with_figured_pair(canonical, _evidence())


def test_explicit_original_axis_order_must_not_contradict_canonical_axes():
    assert _source_owned_axes_agree_with_figured_pair(
        _canonical(), {**_evidence(), "width_mm": 900, "height_mm": 2100})
    assert not _source_owned_axes_agree_with_figured_pair(
        _canonical(), {**_evidence(), "width_mm": 2100, "height_mm": 900})
    assert not _source_owned_axes_agree_with_figured_pair(
        _canonical(), {**_evidence(), "width_mm": 900})
