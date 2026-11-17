"""Negative control: candidate polygon equality cannot erase real outside walls."""
from types import SimpleNamespace

import pytest
from shapely.geometry import box

from pb_new_exterior_wall_preflight import (
    _independent_outside_nonwall_audit_complete as eligible,
)


OUTER = box(0, 0, 240, 120)


def _walk(**changes):
    props = {
        "status": "CANDIDATE",
        "source_outside_role_audit_applied": True,
        "other_source_wall_band_count": 0,
        "source_outside_band_count_before_role_audit": 3,
        "source_proven_nonwall_band_count": 3,
        "outer_wall_native_path_ids": (2, 3, 5, 8),
        "clockwise_pdf_pts": tuple(OUTER.exterior.coords),
    }
    props.update(changes)
    return SimpleNamespace(**props)


def test_complete_independent_source_negative_receipt_allows_candidate_only():
    assert eligible(_walk(), OUTER, outside_band_count=3, party_divider_count=1)


@pytest.mark.parametrize("changes", [
    {"status": "ABSTAINED"},
    {"source_outside_role_audit_applied": False},
    {"other_source_wall_band_count": 1},
    {"source_outside_band_count_before_role_audit": 2},
    {"source_proven_nonwall_band_count": 2},
    {"outer_wall_native_path_ids": (2, 3, 5)},
    {"clockwise_pdf_pts": tuple(box(1, 0, 240, 120).exterior.coords)},
    {"clockwise_pdf_pts": ()},
    {"clockwise_pdf_pts": ((0, 0), (1, 0), (2, 0))},
])
def test_missing_independent_witness_never_bypasses_original_wall_veto(changes):
    assert not eligible(_walk(**changes), OUTER,
                        outside_band_count=3, party_divider_count=1)


def test_party_wall_and_total_outside_count_must_agree():
    assert not eligible(_walk(), OUTER, outside_band_count=4, party_divider_count=1)
    assert not eligible(_walk(), OUTER, outside_band_count=3, party_divider_count=0)
    assert not eligible(None, OUTER, outside_band_count=3, party_divider_count=1)


def test_no_hull_or_measured_area_is_returned_from_security_gate():
    outcome = eligible(_walk(), OUTER, outside_band_count=3, party_divider_count=1)
    assert type(outcome) is bool
    assert outcome is True
