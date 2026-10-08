"""Exact annotation opposition does not become measurement authority."""
from copy import deepcopy
from dataclasses import replace

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_native_dimension_cap_evidence import collect_native_dimension_cap_evidence
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _geometry():
    segments = {}
    selected = []
    words = []
    for index, x in enumerate((80., 200.)):
        prefix = str(index)
        segments[prefix+'line'] = (x, 50., x, 55.)
        selected.append(prefix+'line')
        for endpoint, y in enumerate((50., 55.)):
            for sign in (-1, 1):
                name = f'{prefix}cap{endpoint}_{sign}'
                segments[name] = (x, y, x+15*sign, y)
                if sign == (-1 if index == 0 else 1):
                    selected.append(name)
                segments[f'{prefix}tick{endpoint}_{sign}'] = (x, y, x+3*sign, y+3*sign)
        words.append(dict(id='text'+prefix, text='123', bbox=(x+3, 49., x+11, 56.), axis=(0., 1.)))
    return segments, words, selected


def _collect(segments, words, selected):
    return collect_native_dimension_cap_evidence(segments=segments, words=words,
        selected_ids=selected, document_id='source', page_id='1', revision_id='revision',
        source_sha256='hash', snapshot_id='snapshot')


def test_full_component_has_only_candidate_opposition_and_no_measurement():
    args = _geometry()
    before = deepcopy(args)
    result = _collect(*args)
    assert len(result) == 2
    assert all(a.status is Status.CANDIDATE and a.kind == 'dimension_annotation' for a in result)
    assert all(a.normalized_value is None and a.unit is None for a in result)
    assert all(a.metadata['polarity'] == 'opposing' for a in result)
    assert args == before
    assert _collect(dict(reversed(tuple(args[0].items()))), list(reversed(args[1])), list(reversed(args[2]))) == result


@pytest.mark.parametrize('defect', ['no_text','non_numeric','text_direction','text_remote',
    'one_end_tick','one_side_tick','one_cap','opposite_caps','physical_support','missing_selected',
    'non_finite_text_direction'])
def test_look_alike_or_partial_annotation_cannot_cover_opening(defect):
    segments, words, selected = _geometry()
    if defect == 'no_text': words = []
    elif defect == 'non_numeric': words[0]['text'] = 'W01'
    elif defect == 'text_direction': words[0]['axis'] = (1., 0.)
    elif defect == 'non_finite_text_direction': words[0]['axis'] = (float('nan'), 1.)
    elif defect == 'text_remote': words[0]['bbox'] = (400., 49., 408., 56.)
    elif defect == 'one_end_tick': del segments['0tick0_-1']; del segments['0tick0_1']
    elif defect == 'one_side_tick': del segments['0tick0_-1']
    elif defect == 'one_cap':
        del segments['0cap0_-1']; del segments['0cap0_1']; selected.remove('0cap0_-1')
    elif defect == 'opposite_caps':
        del segments['0cap0_1']; del segments['0cap1_-1']; selected.remove('0cap1_-1')
    elif defect == 'physical_support': segments['wall'] = (80., 20., 200., 20.); selected.append('wall')
    elif defect == 'missing_selected': selected.append('unpublished')
    assert _collect(segments, words, selected) == ()


@pytest.mark.parametrize('scale,rotation,dx,dy', [(1,0,400,-120),(1,1,0,0),(2,1,-50,20),(.5,0,3,9)])
@pytest.mark.parametrize('overhang,isolated', [(0., False), (2.5, False), (2.5, True)])
def test_source_geometry_transform_preserves_role(scale,rotation,dx,dy,overhang,isolated):
    segments, words, selected = _geometry()
    for prefix, x in (('0', 80.), ('1', 200.)):
        segments[prefix+'line'] = (x, 50.-overhang, x, 55.+overhang)
    if isolated:
        selected = ('0cap0_-1',)
    def point(p):
        x,y=p
        if rotation: x,y=-y,x
        return x*scale+dx,y*scale+dy
    segments={k:(*point(v[:2]),*point(v[2:])) for k,v in segments.items()}
    for word in words:
        x0,y0,x1,y1=word['bbox']
        points=[point(p) for p in ((x0,y0),(x1,y0),(x0,y1),(x1,y1))]
        word['bbox']=(min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points))
        word['axis']=(-1.,0.) if rotation else (0.,1.)
    assert len(_collect(segments,words,selected)) == (1 if isolated else 2)


def test_exact_line_split_and_unrelated_content_do_not_change_coverage():
    segments,words,selected=_geometry()
    del segments['0line']; selected.remove('0line')
    segments.update(part1=(80.,50.,80.,52.),part2=(80.,52.,80.,55.),unrelated=(400.,200.,450.,200.))
    selected.extend(('part1','part2'))
    assert len(_collect(segments,words,selected)) == 2
    segments['part2']=(80.,52.1,80.,55.)
    assert _collect(segments,words,selected) == ()


def test_single_sided_witness_caps_still_require_both_terminated_endpoints():
    segments,words,selected=_geometry()
    for i in range(2):
        for endpoint in range(2):
            del segments[f'{i}cap{endpoint}_{1 if i==0 else -1}']
    assert len(_collect(segments,words,selected)) == 2


@pytest.mark.parametrize('overhang', [0., 2.5, 4.])
def test_isolated_witness_finds_complete_page_component_with_bounded_overhang(overhang):
    segments, words, _selected = _geometry()
    segments['0line'] = (80., 50.-overhang, 80., 55.+overhang)
    before = deepcopy((segments, words))
    result = _collect(segments, words, ('0cap0_-1',))
    assert len(result) == 1
    assert result[0].metadata['dimension_line_observation_ids'] == ('0line',)
    assert result[0].metadata['opening_support_observation_ids'] == ('0cap0_-1',)
    assert result[0].normalized_value is None and result[0].unit is None
    assert (segments, words) == before
    assert _collect(dict(reversed(tuple(segments.items()))), list(reversed(words)),
        ('0cap0_-1',)) == result


@pytest.mark.parametrize('defect', ['start_overhang', 'end_overhang', 'wrong_side',
    'one_tick_half', 'text_outside_terminators', 'native_physical_support'])
def test_isolated_witness_does_not_weaken_complete_topology(defect):
    segments, words, _selected = _geometry()
    selected = ['0cap0_-1']
    if defect == 'start_overhang': segments['0line'] = (80., 45., 80., 55.)
    elif defect == 'end_overhang': segments['0line'] = (80., 50., 80., 60.)
    elif defect == 'wrong_side':
        del segments['0cap1_-1']; del segments['0cap0_1']
    elif defect == 'one_tick_half': del segments['0tick1_-1']
    elif defect == 'text_outside_terminators':
        segments['0line'] = (80., 47., 80., 58.)
        words[0]['bbox'] = (83., 46., 91., 51.)
    elif defect == 'native_physical_support':
        segments['wall'] = (80., 20., 200., 20.); selected.append('wall')
    assert _collect(segments, words, selected) == ()


def test_unselected_axis_split_is_rejoined_without_bridging_a_gap():
    segments, words, _selected = _geometry()
    del segments['0line']
    segments.update(part1=(80., 47.5, 80., 52.), part2=(80., 52., 80., 57.5))
    result = _collect(segments, words, ('0cap0_-1',))
    assert len(result) == 1
    assert result[0].metadata['dimension_line_observation_ids'] == ('part1', 'part2')
    segments['part2'] = (80., 52.1, 80., 57.5)
    assert _collect(segments, words, ('0cap0_-1',)) == ()


def _source(*, image=False, overhang=0.):
    segments,_words,selected=_geometry()
    for prefix, x in (('0', 80.), ('1', 200.)):
        segments[prefix+'line'] = (x, 50.-overhang, x, 55.+overhang)
    doc=fitz.open(); page=doc.new_page(width=320,height=200)
    if image:
        pixmap=fitz.Pixmap(fitz.csRGB,fitz.IRect(0,0,1,1),False);pixmap.clear_with(255)
        page.insert_image(fitz.Rect(10,10,20,20),stream=pixmap.tobytes('png'))
    for line in segments.values(): page.draw_line(line[:2],line[2:],width=.3)
    for x in (80.,200.): page.insert_text((x+7.,57.),'90',fontsize=8,rotate=90)
    data=doc.tobytes();doc.close()
    source=SourceVisibilityProducer(producer_method='dimension-cap-test',producer_version='1')
    published=source.ingest_native_pdf_bytes(document_id='dimension-cap-test',source_bytes=data,
        source_locator='memory://dimension-cap-test.pdf',page_ids=('1',))
    rows=source.authority().authenticated_visible_observations(published)
    by_geometry={tuple(r.geometry):i for i,r in rows}
    support=tuple(by_geometry[segments[i]] for i in selected)
    selector=ObservationSelector(document_id=published.revision.document_id,revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,snapshot_id=published.snapshot.snapshot_id,observation_id=support[0])
    return source,published,selector,support


def test_producer_authenticates_native_geometry_text_and_replay():
    source,_published,selector,support=_source()
    atoms=source.native_dimension_cap_evidence(selector,opening_support_ids=support)
    assert len(atoms)==2
    assert source.native_dimension_cap_evidence(selector,opening_support_ids=tuple(reversed(support)))==atoms
    with pytest.raises(RuntimeError):
        source.native_dimension_cap_evidence(replace(selector,source_sha256='wrong'),opening_support_ids=support)


def test_source_owned_isolated_witness_role_is_available_to_frame_consumers():
    source, published, selector, support = _source(overhang=2.5)
    rows = dict(source.authority().authenticated_visible_observations(published))
    witness = next(i for i in support if tuple(rows[i].geometry) == (80., 50., 65., 50.))
    primitive = rows[witness].source_primitive_ref.removeprefix('visible:segment:')
    physical = source.physical_opening_authority()
    atoms = physical.native_dimension_annotation_evidence(selector, source_primitive_ids=(primitive,))
    assert len(atoms) == 1 and atoms[0].status is Status.CANDIDATE
    assert atoms[0].metadata['opening_support_observation_ids'] == (witness,)
    assert atoms[0].normalized_value is None and atoms[0].unit is None
    assert physical.native_dimension_annotation_evidence(selector,
        source_primitive_ids=(primitive, 'raster_segment:foreign:1')) == ()
    assert physical.native_dimension_annotation_evidence(selector, source_primitive_ids=('unowned',)) == ()
    with pytest.raises(RuntimeError):
        physical.native_dimension_annotation_evidence(replace(selector, snapshot_id='stale'),
            source_primitive_ids=(primitive,))
    source._producer._store.source_bytes_by_revision[selector.revision_id] = b'damaged-source'
    with pytest.raises(RuntimeError):
        physical.native_dimension_annotation_evidence(selector, source_primitive_ids=(primitive,))


def test_unrelated_image_does_not_shift_native_text_direction_ownership():
    source,_published,selector,support=_source(image=True)
    assert len(source.native_dimension_cap_evidence(selector,opening_support_ids=support))==2


def test_live_g17_retains_hypothesis_with_opposition_without_claiming_nonexistence():
    source,_published,selector,support=_source(image=True)
    physical=source.physical_opening_authority()
    result=physical.prove_existence(selector)
    assert result.status is Status.ABSTAINED
    assert result.reason_codes == ('native_dimension_annotation_opposes_opening',)
    assert result.existence_record is None and result.proposition is None
    assert result.candidate is not None
    assert len(result.opposing_evidence_atoms)==2
    assert all(a.status is Status.CANDIDATE for a in result.opposing_evidence_atoms)
    assert result==physical.prove_existence(selector)
    closure=physical.assess_visible_candidate_closure(selector)
    assert closure.raw_candidate_count > 0 and not closure.candidate_universe_complete
    assert result.candidate.candidate_id in closure.unresolved_candidate_ids
    assert set(result.candidate.source_observation_ids) <= set(closure.unresolved_observation_ids)
    assert closure == physical.assess_visible_candidate_closure(selector)
    assert len(source.authority().authenticated_visible_observations(_published)) > len(support)


def test_live_ordinary_wall_opening_survives_and_keeps_physical_identity():
    from test_g17_visible_opening_existence_v1 import _opening_pdf_bytes
    identities=[]
    data=_opening_pdf_bytes()
    for version in ('1','different-evidence-producer'):
        source=SourceVisibilityProducer(producer_method='ordinary-wall-test',producer_version=version)
        published=source.ingest_native_pdf_bytes(document_id='ordinary-wall-test',source_bytes=data,
            source_locator='memory://ordinary-wall.pdf',page_ids=('1',))
        selector=ObservationSelector(document_id=published.revision.document_id,revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,snapshot_id=published.snapshot.snapshot_id,
            observation_id=published.visible_observation_ids[0])
        result=source.physical_opening_authority().prove_existence(selector)
        assert result.status is Status.CORROBORATED and result.existence_record is not None
        assert result.opposing_evidence_atoms == ()
        identities.append(result.existence_record.record_id)
    assert identities[0]==identities[1]


@pytest.mark.parametrize('defect',['geometry','visibility_receipt','text_receipt','text_page','stale'])
@pytest.mark.parametrize('cache_hit', [False, True])
def test_damaged_source_cannot_supply_annotation_opposition(defect,cache_hit):
    source,published,selector,support=_source()
    if cache_hit:
        assert len(source.native_dimension_cap_evidence(selector,opening_support_ids=support)) == 2
    if defect=='geometry':
        key=(selector.snapshot_id,support[0]);record=source._producer._store.observations[key]
        source._producer._store.observations[key]=replace(record,geometry=(0.,0.,10.,0.))
    elif defect=='visibility_receipt':
        del source._visibility_receipts[(selector.snapshot_id,support[0])]
    elif defect=='text_receipt':
        source._text_integrity_receipts.clear()
    elif defect=='text_page':
        key=(selector.snapshot_id,published.text_observation_ids[0])
        record=source._producer._store.observations[key]
        source._producer._store.observations[key]=replace(record,page_id='2')
    elif defect=='stale':
        doc=fitz.open();doc.new_page();data=doc.tobytes();doc.close()
        source.ingest_native_pdf_bytes(document_id=selector.document_id,source_bytes=data,source_locator='memory://changed.pdf',page_ids=('1',))
    with pytest.raises(RuntimeError):
        source.native_dimension_cap_evidence(selector,opening_support_ids=support)


def test_compiled_page_cache_keeps_query_coverage_and_atom_metadata_independent():
    source, published, selector, support = _source(overhang=2.5)
    before = tuple(source.authority().authenticated_visible_observations(published))
    expected = source.native_dimension_cap_evidence(selector, opening_support_ids=support)
    changed = source.native_dimension_cap_evidence(selector, opening_support_ids=support)
    changed[0].metadata['source_observation_ids'] = ('forged',)
    assert source.native_dimension_cap_evidence(selector, opening_support_ids=support) == expected
    witness = next(i for i, r in before if tuple(r.geometry) == (80., 50., 65., 50.))
    query = replace(selector, observation_id=witness)
    isolated = source.native_dimension_cap_evidence(query, opening_support_ids=(witness,))
    assert len(isolated) == 1
    assert isolated[0].metadata['opening_support_observation_ids'] == (witness,)
    assert source.native_dimension_cap_evidence(selector, opening_support_ids=support) == expected
    assert tuple(source.authority().authenticated_visible_observations(published)) == before


def test_live_g17_does_not_treat_missing_text_receipt_as_absent_opposition():
    source,_published,selector,_support=_source()
    source._text_integrity_receipts.clear()
    physical=source.physical_opening_authority()
    result=physical.prove_existence(selector)
    assert result.status is Status.ABSTAINED
    assert result.reason_codes == ('opening_annotation_source_integrity_unproven',)
    assert result.existence_record is None
    closure=physical.assess_visible_candidate_closure(selector)
    assert not closure.candidate_universe_complete
    assert result.candidate.candidate_id in closure.unresolved_candidate_ids
