"""Fresh original PDF bytes, unchanged production, no shadow promotion."""
from hashlib import sha256

import pytest

from scripts import gptmax_full_page_exact_endpoint_shadow as shadow
from test_gptmax_full_foreground_run_source import pdf


def run(data):
    return shadow.full_page_endpoint_source_report(data,page_id='1',
        expected_source_sha=sha256(data).hexdigest())


@pytest.mark.parametrize('data',[b'foreign','caller JSON',{},None])
def test_foreign_or_caller_authored_report_cannot_replace_original_bytes(data):
    with pytest.raises(ValueError,match='SHA'):
        shadow.full_page_endpoint_source_report(data,page_id='1',expected_source_sha='a'*64)


def test_fresh_pdf_full_page_controls_are_deterministic_and_nonpublishing():
    data=pdf()
    result=run(data)
    assert result==run(data)
    assert result['original_source_reauthenticated'] is True
    assert result['default_production_state_unchanged'] is True
    assert result['identical_full_page_source_inputs_for_both_modes'] is True
    assert result['full_source_input_primitive_count']<=result['source_primitive_safety_cap']==20000
    assert len(result['input_source_manifest_sha256'])==64
    for key in ('complete_full_page_legacy_zero_graph_equality_proven',
            'full_page_scope_is_authenticated_floor_plan_viewport','physical_wall_authority',
            'physical_equivalence_proven','source_parent_transfer_allowed',
            'structural_source_universe_complete','host_publication_allowed',
            'opening_count_publication_allowed','metric_quantity_publication_allowed'):
        assert result[key] is False
    assert result['benchmark_accuracy'] is None
    for mode in ('default_full_page_shadow','indexed_exact_endpoint_full_page_shadow'):
        graph=result[mode]['source_graph']
        assert graph['input_source_count']==result['full_source_input_primitive_count']
        assert graph['scope_authority'].startswith('full-page diagnostic only')
        assert graph['host_publication_allowed'] is False
        assert graph['physical_equivalence_proven'] is False


def test_changed_independent_production_receipt_rejects_whole_report(monkeypatch):
    original=shadow.original_raster_host_ancestry_census
    calls=0
    def changed(*args,**kwargs):
        nonlocal calls
        calls+=1
        result=original(*args,**kwargs)
        if calls==2: result['source_original_host_count']+=1
        return result
    monkeypatch.setattr(shadow,'original_raster_host_ancestry_census',changed)
    with pytest.raises(RuntimeError,match='production source state'):
        run(pdf())


def test_mutated_source_input_cannot_claim_unchanged_manifest(monkeypatch):
    original=shadow._trace_sources
    def changed(records,**kwargs):
        result=original(records,**kwargs)
        object.__setattr__(records[0],'raw_text','unauthenticated mutation')
        return result
    monkeypatch.setattr(shadow,'_trace_sources',changed)
    with pytest.raises(RuntimeError,match='source input records'):
        run(pdf())
