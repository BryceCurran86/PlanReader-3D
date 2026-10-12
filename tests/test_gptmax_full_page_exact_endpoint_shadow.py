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


@pytest.mark.parametrize('foreign',[False,True])
def test_actual_rejected_constructor_keeps_owned_fragments_or_rejects_foreign(monkeypatch,foreign):
    import tools.diag_gptmax_full_foreground_run_source as diag
    from pb_wall_room_topology_contracts import WallCandidate, JunctionType
    from pb_geometry_takeoff_model import MeasurementAuthorityType
    from pb_migration_contracts import EvidenceResolutionStatus
    original=diag.assemble_wall_candidates
    calls=0
    def rejection(graph,*args,**kwargs):
        nonlocal calls
        calls+=1
        if calls!=2: return original(graph,*args,**kwargs)
        edge=graph['edges'][0]
        a=(edge['x1'],edge['y1']); b=(edge['x2'],edge['y2'])
        # Execute the real guard. No invented source line enters the reader.
        return WallCandidate(candidate_id='rejected-attempt',viewport_id='full-page-pixel-shadow',
            representation='single_line',centerline_pts=(a,b,a),
            face_a_segment_ids=('foreign' if foreign else edge['id'],),face_b_segment_ids=None,
            is_curved=False,curve_control_pts=None,thickness_m=None,
            thickness_authority=MeasurementAuthorityType.PROVISIONAL,length_m=None,
            end_node_ids=('same','same'),junction_types=(JunctionType.UNRESOLVED,JunctionType.UNRESOLVED),
            interior_exterior='unresolved',level_id=None,status=EvidenceResolutionStatus.CANDIDATE,
            confidence=0.,reason_codes=())
    monkeypatch.setattr(diag,'assemble_wall_candidates',rejection)
    if foreign:
        with pytest.raises(RuntimeError,match='unavailable original W3 fragments'): run(pdf())
    else:
        result=run(pdf())
        mode=result['indexed_exact_endpoint_full_page_shadow']
        assert mode['source_graph'] is None and mode['opening_rows'] is None
        assert mode['w4_assembly_status']=='abstained'
        receipt=mode['first_failure_receipt']
        assert receipt['actual_owned_w3_fragment_rows']
        assert receipt['only_first_assembly_failure_observed'] is True
        assert receipt['w4_candidate_universe_available'] is False
        assert receipt['physical_wall_authority'] is False
        assert receipt['host_publication_allowed'] is False
        assert result['default_production_state_unchanged'] is True


@pytest.mark.parametrize('message',['unrelated geometry failure','a wall candidate cannot start and end at the same node'])
def test_unexpected_or_unowned_failure_cannot_be_reported_as_authentic_abstention(monkeypatch,message):
    original=shadow._trace_sources
    def failure(records,**kwargs):
        if kwargs.get('exact_endpoint_index_shadow'): raise ValueError(message)
        return original(records,**kwargs)
    monkeypatch.setattr(shadow,'_trace_sources',failure)
    expected=RuntimeError if message.startswith('a wall') else ValueError
    with pytest.raises(expected): run(pdf())


def test_failed_w4_preserves_real_fragment_spans_without_known_candidate_membership(monkeypatch):
    import tools.diag_gptmax_full_foreground_run_source as diag
    from pb_wall_room_topology_contracts import WallCandidate, JunctionType
    from pb_geometry_takeoff_model import MeasurementAuthorityType
    from pb_migration_contracts import EvidenceResolutionStatus
    from test_gptmax_exact_endpoint_flank_shadow import record
    from test_gptmax_full_foreground_flank_stages import _fixture

    joined,original,required,_=_fixture()
    records=(record('original-pixel',[16.,20.,20.,20.]),*(
        record(f'tick-{i}',[16.+i/2,19.,16.+i/2,21.]) for i in range(1,8)))
    def rejection(graph,*args,**kwargs):
        edge=graph['edges'][0]
        a=(edge['x1'],edge['y1']); b=(edge['x2'],edge['y2'])
        return WallCandidate(candidate_id='rejected-attempt',viewport_id='full-page-pixel-shadow',
            representation='single_line',centerline_pts=(a,b,a),
            face_a_segment_ids=(edge['id'],),face_b_segment_ids=None,
            is_curved=False,curve_control_pts=None,thickness_m=None,
            thickness_authority=MeasurementAuthorityType.PROVISIONAL,length_m=None,
            end_node_ids=('same','same'),junction_types=(JunctionType.UNRESOLVED,JunctionType.UNRESOLVED),
            interior_exterior='unresolved',level_id=None,status=EvidenceResolutionStatus.CANDIDATE,
            confidence=0.,reason_codes=())
    monkeypatch.setattr(diag,'assemble_wall_candidates',rejection)
    with pytest.raises(ValueError) as caught:
        shadow._trace_sources(records,exact_endpoint_shadow=True,exact_endpoint_index_shadow=True)
    rows=shadow._source_spans_before_failed_w4(caught.value,joined,original,required,records)
    pixel=rows[0]['flanks'][0]['source_run_rows'][0]
    coverage=pixel['exact_source_span_coverage']
    assert coverage['complete_actual_w3_retained_source_span_coverage'] is True
    assert len(coverage['exact_owned_fragment_intervals'])==8
    assert pixel['single_fragment_contact_failure_with_complete_retained_source_span'] is True
    assert pixel['w4_membership_available'] is False
    assert all(e['experimental_w4_candidate_ids'] is None for e in pixel['actual_w2_edge_rows'])
    assert all('original-pixel' in e['source_observation_ids'] for e in pixel['actual_w2_edge_rows'])
    assert coverage['combined_graph_edge_created'] is False
    assert coverage['physical_wall_authority'] is False and pixel['host_publication_allowed'] is False
