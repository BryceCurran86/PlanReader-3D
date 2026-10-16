"""Partitioned candidates remain inside the actual source-authentication seam."""
from copy import deepcopy
from dataclasses import replace

import pytest

import pb_g17_plan_wall_scope_shadow as module
from tests.test_g17_plan_wall_scope_shadow import _prepare


def report(source,pub,**extra):
    return module.build_g17_plan_wall_scope_shadow(source,revision_id=pub.revision.revision_id,page_id='1',
        preserve_overlapping_spans_shadow=True,immutable_exact_endpoints_shadow=True,**extra)


def test_original_source_retention_and_disjoint_scope_for_partition_only():
    source,pub=_prepare()
    before=report(source,pub)
    observations=deepcopy(source._producer._store.observations)
    receipts=deepcopy(source._raster_opening_primitive_receipts)
    new=report(source,pub,partition_exact_collinear_overlaps_shadow=True)
    graph=new.pop('partitioned_exact_w2_w3_w4')
    assert new==before
    assert graph['w4_records'] and not graph['w4_identity_unavailable']
    ids={w['wall_candidate_id'] for w in graph['w4_records']}
    for key in ('default_w2_w3_w4','exact_coordinate_w2_w3_w4',
                'overlap_preserving_exact_w2_w3_w4','immutable_endpoint_exact_w2_w3_w4'):
        assert not ids & {w['wall_candidate_id'] for w in before[key]['w4_records']}
    assert source._producer._store.observations==observations
    assert source._raster_opening_primitive_receipts==receipts
    assert source.published_snapshot_for_revision(pub.revision.revision_id)==pub
    assert not any(new[k] for k in ('scope_complete','structural_wall_role_granted',
        'physical_wall_equivalence_granted','host_granted','metric_quantity_granted'))


def test_mid_partition_source_damage_remains_rejected(monkeypatch):
    source,pub=_prepare();original=module._graph
    def damage(*args,**kwargs):
        out=original(*args,**kwargs)
        if kwargs.get('partition_exact_collinear_overlaps_shadow'):
            key=(pub.snapshot.snapshot_id,pub.raster_opening_primitive_observation_ids[0])
            source._raster_opening_primitive_receipts[key]=replace(
                source._raster_opening_primitive_receipts[key],render_sha256='damaged')
        return out
    monkeypatch.setattr(module,'_graph',damage)
    with pytest.raises(RuntimeError):report(source,pub,partition_exact_collinear_overlaps_shadow=True)


@pytest.mark.parametrize('bad',[1,None,'true'])
def test_no_implicit_partition_policy(bad):
    source,pub=_prepare()
    with pytest.raises(ValueError,match='explicit boolean'):
        report(source,pub,partition_exact_collinear_overlaps_shadow=bad)


def test_no_partition_without_source_incidence_guards():
    source,pub=_prepare()
    with pytest.raises(ValueError,match='requires exact'):
        module.build_g17_plan_wall_scope_shadow(source,revision_id=pub.revision.revision_id,page_id='1',
            partition_exact_collinear_overlaps_shadow=True)
