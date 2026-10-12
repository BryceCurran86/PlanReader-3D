"""Lot16 diagnostic count does not coerce fake source metric receipts."""
import pytest

from tests.test_diag_lot16_metric_floor_count import _floor
from tools.diag_lot16_room_face_scope import _has_firm_metric_floor_receipt


def test_documented_metric_positive_retains_source_count():
    assert _has_firm_metric_floor_receipt(_floor(metric_area_m2=8.64))


@pytest.mark.parametrize("bad", [
    True, 7, "source-area-q1 ", " source-area-q1", "", None,
])
def test_untyped_or_padded_source_quantity_id_cannot_claim_metric_floor(bad):
    assert not _has_firm_metric_floor_receipt(_floor(metric_area_quantity_id=bad))


@pytest.mark.parametrize("bad", [
    True, 9, " face-1", "face-1 ", "", None,
])
def test_untyped_or_padded_physical_source_face_cannot_claim_metric_floor(bad):
    assert not _has_firm_metric_floor_receipt(_floor(source_room_face_record_id=bad))


@pytest.mark.parametrize("bad", [
    None, "", " ev-dim-h", ("ev-dim-h", "ev-dim-h"),
    ("ev-dim-h", True), (["nested"],), "ev-dim-h",
])
def test_broken_source_area_receipts_do_not_inflate_lot16_firm_floor_diagnostic(bad):
    assert not _has_firm_metric_floor_receipt(_floor(evidence_ids=bad))
