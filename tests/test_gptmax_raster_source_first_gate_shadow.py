"""Source-raster gate receipts explain candidates without producing quantities.

The report is diagnostic only: existing source-positive opening objects and
their immutable original snapshot are not changed by recording gate reasons.
"""
from copy import deepcopy

import pytest

from tests.test_raster_paired_original_outer_faces_shadow import (
    _notched_source_pdf, _source_records,
)


@pytest.mark.parametrize("turns,scale", [
    (0, 1.0), (1, 1.0), (2, 1.0), (3, 1.0), (0, 0.5),
])
def test_raster_gate_ledger_is_complete_deterministic_and_nonpublishing(turns, scale):
    payload = _notched_source_pdf(turns, scale)
    source, published, physical = _source_records(payload, False)
    authority = source.physical_opening_authority()
    before = deepcopy(source._producer._store.observations)
    raw = authority._raster_gap_candidate_audit_cache
    ledger = authority._raster_gap_first_gate_shadow_cache
    assert raw
    assert set(ledger) == set(raw)
    for key, raw_rows in raw.items():
        assert key in ledger
        reasons = dict(ledger[key])
        raw_ids = {row[0] for row in raw_rows}
        assert set(reasons) == raw_ids
        for candidate_id, gates in ledger[key]:
            assert candidate_id in raw_ids
            assert isinstance(gates, tuple) and gates
            assert len(set(gates)) == len(gates)
            assert tuple(sorted(gates)) == gates
            assert all(type(g) is str and g for g in gates)
    # Running the same original source again cannot alter authority or output.
    source_again, pub_again, physical_again = _source_records(payload, False)
    assert published == pub_again
    assert physical == physical_again
    assert authority._raster_gap_first_gate_shadow_cache == (
        source_again.physical_opening_authority()._raster_gap_first_gate_shadow_cache
    )
    assert source._producer._store.observations == before


def test_failed_snapshot_clears_source_gate_review_together_with_raw_gap_cache():
    payload = _notched_source_pdf()
    source, published, _physical = _source_records(payload, False)
    authority = source.physical_opening_authority()
    assert authority._raster_gap_first_gate_shadow_cache
    snapshot_id = published.snapshot.snapshot_id
    authority._invalidate_snapshot_caches_after_failed_source_batch(snapshot_id)
    assert not any(key[3] == snapshot_id
                   for key in authority._raster_gap_first_gate_shadow_cache)
    assert not any(key[3] == snapshot_id
                   for key in authority._raster_gap_candidate_audit_cache)
