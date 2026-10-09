"""The source handoff exposes authority failures without quantity publication."""
import hashlib
import json

import pytest

from tools.diag_gptmax_source_authority_stages import source_stage_report
from test_raster_framed_opening_g17_contract import _pdf


@pytest.mark.parametrize('all_pages', [False, True])
def test_source_owned_handoff_keeps_identity_and_unknown_measurements(monkeypatch, all_pages):
    import pb_live_opening_area_quantity_publication as area
    import pb_live_opening_count_quantity_publication as count
    def forbidden(*args, **kwargs):
        raise AssertionError('diagnostics must not publish quantities')
    monkeypatch.setattr(area, 'publish_live_opening_area_quantities', forbidden)
    if hasattr(count, 'publish_live_opening_count_quantities'):
        monkeypatch.setattr(count, 'publish_live_opening_count_quantities', forbidden)
    data = _pdf(frame_lines=2)
    report = source_stage_report(data, page_ids=('1',), source_all_pages=all_pages)
    assert report['source_sha256'] == hashlib.sha256(data).hexdigest()
    assert report['primitive_safety_cap'] == 20_000
    assert report['all_source_pages_requested'] is all_pages
    ids = [row['opening_identity_id'] for row in report['opening_bindings']]
    assert len(ids) == len(set(ids)) == 1
    assert report['canonical_openings']
    assert all(row['source_sha256'] == report['source_sha256'] for row in report['canonical_openings'])
    assert all(row['width_m'] is None and row['height_m'] is None for row in report['canonical_openings'])
    assert all(row['schedule_declared_count'] is None for row in report['canonical_openings'])
    assert all(not row['geometry_complete'] for row in report['canonical_openings'])
    assert 'quantities' not in report and 'certified_opening_count' not in report
    assert report['opening_measurement_traces']
    assert {row['opening_identity_id'] for row in report['opening_figured_label_traces']} == set(ids)
    assert {row['opening_identity_id'] for row in report['opening_label_semantic_traces']} == set(ids)
    assert report['summary']['canonical_opening_area_records'] == 0
    assert source_stage_report(data, page_ids=('1',), source_all_pages=all_pages) == report
    json.dumps(report, default=lambda value: value.value)
