"""W3 source-parent span is evidence, not a reason to override ambiguity."""
from copy import deepcopy
import math

from pb_g17_w3_original_parent_span_shadow import (
    _positive_original_interval_contains_child,
    audit_g17_w3_short_arm_source_parents,
)


def source(raw, geometry, paint=True):
    return dict(source_primitive_id=raw, observation_id='observation-'+raw,
                geometry=geometry,
                source_paint=dict(original_solid_and_unchanged=paint))


def graph(child, parents=('original-a',), *, suspect='child'):
    return dict(
        w2_edges=[dict(edge_id=suspect, geometry=child, source_primitive_ids=list(parents))],
        w3_junctions=[dict(node_id='node',junction_type='ambiguous',status='abstained',
                           reason_codes=['short_isolated_arm_present','suspect_edge_id:'+suspect],
                           position_pt=[child[2], child[3]])],
    )


def report(child=(0.,0.,0.,1.), origin=(0.,-9.,0.,1.), *,
           positive=True, extra=None):
    g=graph(child, parents=('original-a','original-b') if extra else ('original-a',))
    return dict(source_sha256='sha',snapshot_id='snapshot',
                source_primitive_dispositions=[source('original-a',origin,positive)] +
                    ([source('original-b',extra[0],extra[1])] if extra else []),
                default_w2_w3_w4=g,exact_coordinate_w2_w3_w4=g)


def outcome(data):
    return audit_g17_w3_short_arm_source_parents(data)[
        'candidate_only_short_child_original_parent_results']['default_w2_w3_w4'][0]


def test_child_of_long_original_source_keeps_junction_abstained():
    data=report();before=deepcopy(data)
    row=outcome(data)
    assert row['any_full_painted_original_parent_longer_than_child']
    assert row['W3_junction_status']=='abstained'
    assert row['source_parents'][0]['original_source_length_pt']==10.
    assert row['W2_child_length_pt']==1.
    assert not row['W4_union_granted'] and not row['physical_opening_host_granted']
    assert data==before


def test_original_paint_negative_cannot_be_presented_as_source_positive():
    row=outcome(report(positive=False))
    assert row['source_parents'][0]['genuinely_longer_original_parent']
    assert not row['any_full_painted_original_parent_longer_than_child']


def test_opposing_parent_is_visible_not_borrowed_from_positive_parent():
    row=outcome(report(extra=((0.,-9.,0.,-.5),True)))
    assert len(row['source_parents'])==2
    assert row['source_parents'][0]['child_interval_originally_contained']
    assert not row['source_parents'][1]['child_interval_originally_contained']
    assert row['any_full_painted_original_parent_longer_than_child']
    assert all(not p['structural_wall_role_granted'] for p in row['source_parents'])


def test_short_original_source_remains_short_and_non_authoritative():
    row=outcome(report(origin=(0.,0.,0.,1.)))
    assert not row['any_full_painted_original_parent_longer_than_child']


def test_displaced_parents_and_endpoint_only_contact_cannot_cover_child():
    for parent in ((.48,-9.,.48,1.),(0.,-9.,0.,0.)):
        assert not _positive_original_interval_contains_child(parent,(0.,0.,0.,1.))


def test_rotated_source_contains_exact_child_without_nearness():
    theta=math.radians(27.)
    def tr(x,y):return (100.+math.cos(theta)*x-math.sin(theta)*y,
                        50.+math.sin(theta)*x+math.cos(theta)*y)
    a,b,c=tr(0.,-9.),tr(0.,0.),tr(0.,1.)
    row=outcome(report(child=(*b,*c),origin=(*a,*c)))
    assert row['any_full_painted_original_parent_longer_than_child']


def test_untrusted_or_missing_source_is_not_positive():
    data=report()
    data['source_primitive_dispositions']=[]
    row=outcome(data)
    assert not row['any_full_painted_original_parent_longer_than_child']
    assert row['source_parents'][0]['source_observation_id'] is None


def test_no_metric_or_host_grant_even_if_every_original_parent_is_valid():
    d=audit_g17_w3_short_arm_source_parents(report())
    for key in ('physical_wall_equivalence_granted','opening_host_granted',
                'opening_count_granted','metric_quantity_granted',
                'source_authentication_reperformed'):
        assert not d[key]


def test_non_short_arm_junction_not_relabelled_or_selected():
    d=report()
    d['default_w2_w3_w4']['w3_junctions'][0]['reason_codes']=['near_junction_review']
    rows=audit_g17_w3_short_arm_source_parents(d)[
        'candidate_only_short_child_original_parent_results']['default_w2_w3_w4']
    assert rows==[]
