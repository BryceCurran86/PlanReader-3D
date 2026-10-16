"""Source interval continuity cannot be inferred from a snapped appearance."""
from copy import deepcopy
from math import cos, sin, radians
from types import SimpleNamespace as N

from pb_g17_source_interval_coverage_shadow import audit_g17_original_source_interval_coverage


def f(name, coords, raw='source:a'):
    return N(edge_id=name, geometry=coords, source_primitive_ids=(raw,))


def w(name, *fragments):
    return N(wall_candidate_id=name, source_edge_fragments=fragments)


def evaluate(source, *walls):
    return audit_g17_original_source_interval_coverage([source], walls)


def test_complete_split_source_can_cover_one_candidate_without_grant():
    source=f('s',(0.,0.,10.,0.))
    walls=[w('A', f('0',(0.,0.,5.,0.)),f('1',(5.,0.,10.,0.)))]
    before=deepcopy((source,walls))
    r=evaluate(source,*walls)
    c=r['original_source_edges'][0]['competing_wall_candidates'][0]
    assert c['complete_original_interval_candidate']
    assert c['uncovered_original_intervals_pt']==()
    assert not any(r[k] for k in ('structural_wall_role_granted','physical_wall_equivalence_granted',
                                   'opening_host_granted','metric_quantity_granted',
                                   'original_source_authentication_performed'))
    assert (source,walls)==before


def test_small_actual_source_gap_is_not_bridged_by_w2_snap():
    r=evaluate(f('s',(0.,0.,10.,0.)),w('A',f('0',(0.,0.,4.9,0.)),
                                                  f('1',(5.1,0.,10.,0.))))
    e=r['original_source_edges'][0]
    assert e['first_blocker']=='source_owned_w4_interval_incomplete'
    assert e['competing_wall_candidates'][0]['uncovered_original_intervals_pt']==((4.9,5.1),)


def test_foreign_ancestry_matches_geometry_but_cannot_cover_original():
    r=evaluate(f('s',(0.,0.,10.,0.)),w('wrong',f('c',(0.,0.,10.,0.),'source:other')))
    row=r['original_source_edges'][0]
    c=row['competing_wall_candidates'][0]
    assert not c['complete_original_interval_candidate']
    assert c['geometric_only_foreign_source_overlaps']
    assert c['uncovered_original_intervals_pt']==((0.,10.),)
    assert row['first_blocker']=='source_owned_w4_interval_missing'


def test_near_parallel_snapped_stroke_does_not_cover_original():
    r=evaluate(f('s',(0.,0.,10.,0.)),w('near',f('c',(0.,0.48,10.,0.48))))
    assert not r['original_source_edges'][0]['competing_wall_candidates']


def test_alternatives_cannot_borrow_portions_or_collapse_colliding_ids():
    s=f('s',(0.,0.,10.,0.))
    walls=[w('same',f('left',(0.,0.,5.,0.))),w('same',f('right',(5.,0.,10.,0.)))]
    r=evaluate(s,*walls)
    assert r['competing_wall_candidate_address_collisions']==('same',)
    candidates=r['original_source_edges'][0]['competing_wall_candidates']
    assert len(candidates)==2
    assert not any(c['complete_original_interval_candidate'] for c in candidates)
    assert sorted(c['uncovered_original_intervals_pt'] for c in candidates)==[((0.,5.),),((5.,10.),)]


def test_rotation_translation_and_reversed_endpoints_preserve_proof():
    theta=radians(38.)
    def trans(x,y):return (100.+cos(theta)*x-sin(theta)*y,7.+sin(theta)*x+cos(theta)*y)
    a,b,c=trans(0,0),trans(5,0),trans(10,0)
    s=f('s',(*c,*a))
    r=evaluate(s,w('candidate',f('p',(*a,*b)),f('q',(*b,*c))))
    assert r['original_source_edges'][0]['competing_wall_candidates'][0]['complete_original_interval_candidate']


def test_invalid_source_never_grants_or_assumes_a_measurement():
    for g in ((0.,0.,0.,0.),(0.,0.,float('nan'),1.)):
        r=evaluate(f('bad',g),w('candidate',f('c',(0.,0.,10.,0.))))
        assert r['original_source_edges'][0]['first_blocker']=='original_source_interval_invalid_or_lineage_missing'
        assert not r['opening_host_granted']


def test_input_order_keeps_all_alternative_evidence():
    s=f('s',(0.,0.,10.,0.))
    walls=(w('B',f('b',(0.,0.,5.,0.))),w('A',f('a',(0.,0.,10.,0.))))
    a=evaluate(s,*walls)['original_source_edges'][0]['competing_wall_candidates']
    b=evaluate(s,*reversed(walls))['original_source_edges'][0]['competing_wall_candidates']
    assert a==b


def test_source_fragment_order_and_duplicate_edge_ids_keep_every_alternative():
    sources=[f('dup',(0.,0.,5.,0.)),f('dup',(5.,0.,10.,0.))]
    walls=[w('W',f('full',(0.,0.,10.,0.)))]
    a=audit_g17_original_source_interval_coverage(sources,walls)
    b=audit_g17_original_source_interval_coverage(tuple(reversed(sources)),walls)
    assert a==b and len(a['original_source_edges'])==2
    assert all(row['competing_wall_candidates'][0]['complete_original_interval_candidate']
               for row in a['original_source_edges'])
