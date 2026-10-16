"""Additional source-only graph policies cannot reissue the published root."""
from copy import deepcopy
from dataclasses import replace

import pytest

import pb_g17_plan_wall_scope_shadow as module
from tests.test_g17_plan_wall_scope_shadow import _prepare


def test_actual_source_modes_retain_every_baseline_graph_and_original_receipt():
    source,pub=_prepare()
    baseline=module.build_g17_plan_wall_scope_shadow(source,revision_id=pub.revision.revision_id,page_id='1')
    observations=deepcopy(source._producer._store.observations)
    receipts=deepcopy(source._raster_opening_primitive_receipts)
    guarded=module.build_g17_plan_wall_scope_shadow(source,revision_id=pub.revision.revision_id,page_id='1',
        preserve_overlapping_spans_shadow=True,immutable_exact_endpoints_shadow=True)
    only_baseline={k:v for k,v in guarded.items() if k not in (
        'overlap_preserving_exact_w2_w3_w4','immutable_endpoint_exact_w2_w3_w4')}
    assert baseline==only_baseline
    for key in ('overlap_preserving_exact_w2_w3_w4','immutable_endpoint_exact_w2_w3_w4'):
        assert guarded[key]['w4_records']
        ordinary_ids={w['wall_candidate_id'] for w in baseline['exact_coordinate_w2_w3_w4']['w4_records']}
        assert not ordinary_ids & {w['wall_candidate_id'] for w in guarded[key]['w4_records']}
    assert source.published_snapshot_for_revision(pub.revision.revision_id)==pub
    assert source._producer._store.observations==observations
    assert source._raster_opening_primitive_receipts==receipts
    assert not any(guarded[k] for k in ('scope_complete','structural_wall_role_granted',
        'physical_wall_equivalence_granted','host_granted','metric_quantity_granted'))


def test_damage_during_new_graph_policy_is_still_rejected_by_original_exit_authentication(monkeypatch):
    source,pub=_prepare()
    graph=module._graph
    def damage(*args,**kwargs):
        result=graph(*args,**kwargs)
        if kwargs.get('immutable_exact_endpoints_shadow'):
            oid=pub.raster_opening_primitive_observation_ids[0]
            key=(pub.snapshot.snapshot_id,oid)
            source._raster_opening_primitive_receipts[key]=replace(
                source._raster_opening_primitive_receipts[key],render_sha256='foreign')
        return result
    monkeypatch.setattr(module,'_graph',damage)
    with pytest.raises(RuntimeError):
        module.build_g17_plan_wall_scope_shadow(source,revision_id=pub.revision.revision_id,page_id='1',
            preserve_overlapping_spans_shadow=True,immutable_exact_endpoints_shadow=True)


@pytest.mark.parametrize('field',['preserve_overlapping_spans_shadow','immutable_exact_endpoints_shadow'])
@pytest.mark.parametrize('bad',[1,None,'true'])
def test_source_policy_is_explicit_and_never_a_caller_owned_receipt(field,bad):
    source,pub=_prepare()
    with pytest.raises(ValueError,match='explicit boolean'):
        module.build_g17_plan_wall_scope_shadow(source,revision_id=pub.revision.revision_id,page_id='1',**{field:bad})
