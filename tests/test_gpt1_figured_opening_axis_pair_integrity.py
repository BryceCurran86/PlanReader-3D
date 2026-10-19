"""Source-neutral regression for original figured-pair and canonical axis receipts.

The live diagnostic no longer exposes a value-only axis helper. Its current
authority gate also requires distinct original producer width/height receipts.
These tests deliberately do not publish a FIRM quantity or V2 score.
"""
import pytest

from tools.diag_gptmax_lot16_host_frame_gpt1_handoff import (
    _source_owned_axes_agree_with_figured_pair,
)


def _canonical(width_m=0.9, height_m=2.1):
    return {
        "width_m": width_m,
        "height_m": height_m,
        "width_record_id": "original-width-receipt",
        "height_record_id": "original-height-receipt",
        "evidence_ids": ["original-width-receipt", "original-height-receipt"],
        "geometry_complete": True,
    }


def _evidence(pair=(900.0, 2100.0)):
    return {"dimension_values_mm": pair}


@pytest.mark.parametrize("width_m,height_m,pair,expected", [
    (0.9, 2.1, (900.0, 2100.0), True),
    (2.1, 0.9, (900.0, 2100.0), True),
    (0.9, 2.1, [2100.0, 900.0], True),
    # Equal area never substitutes for independently matching axes.
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
def test_figured_pair_requires_actual_canonical_axis_values(
    width_m, height_m, pair, expected,
):
    assert _source_owned_axes_agree_with_figured_pair(
        _canonical(width_m, height_m), _evidence(pair)
    ) is expected


def test_source_dimension_list_is_not_mutated():
    pair = [2100.0, 900.0]
    assert _source_owned_axes_agree_with_figured_pair(
        _canonical(), _evidence(pair)
    )
    assert pair == [2100.0, 900.0]


def test_finite_rounding_accepted_but_nonfinite_axis_rejected():
    assert _source_owned_axes_agree_with_figured_pair(
        _canonical(), _evidence((900.0000001, 2100.0))
    )
    assert not _source_owned_axes_agree_with_figured_pair(
        _canonical(float("inf"), 2.1), _evidence()
    )


@pytest.mark.parametrize("mutation", [
    {"width_record_id": ""},
    {"height_record_id": "original-width-receipt"},
    {"evidence_ids": ["original-width-receipt"]},
    {"evidence_ids": ["original-height-receipt"]},
    {"evidence_ids": ["forged-width", "forged-height"]},
    {"geometry_complete": False},
])
def test_unproven_independent_axis_receipts_fail_closed(mutation):
    canonical = _canonical()
    canonical.update(mutation)
    assert not _source_owned_axes_agree_with_figured_pair(
        canonical, _evidence()
    )


def test_figured_label_axis_order_cannot_contradict_canonical_receipts():
    canonical = _canonical()
    # A printed unordered pair is compatible with independent canonical axes.
    assert _source_owned_axes_agree_with_figured_pair(
        canonical, _evidence((2100.0, 900.0))
    )
    # A separate explicit ordered label assertion must match exactly.
    assert not _source_owned_axes_agree_with_figured_pair(
        canonical,
        {"dimension_values_mm": [900.0, 2100.0],
         "width_mm": 2100.0, "height_mm": 900.0},
    )
    assert _source_owned_axes_agree_with_figured_pair(
        canonical,
        {"dimension_values_mm": [2100.0, 900.0],
         "width_mm": 900.0, "height_mm": 2100.0},
    )
    assert not _source_owned_axes_agree_with_figured_pair(
        canonical,
        {"dimension_values_mm": [900.0, 2100.0], "width_mm": 900.0},
    )
