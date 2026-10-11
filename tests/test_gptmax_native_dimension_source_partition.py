"""Paint partitions remain behind the original text-integrity authority."""
from copy import deepcopy
from hashlib import sha256

import fitz
import pytest

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_source_visibility_authority import SourceVisibilityProducer
from scripts.gptmax_native_dimension_source_partition import _paint_partitions, source_partition_report


def _facts():
    chars = [dict(c=c, origin=(float(i), 1.), bbox=(float(i), 0., float(i + 1), 2.), synthetic=False)
        for i, c in enumerate('90450')]
    word = dict(id='owned-word', text='90450', bbox=(0., 0., 5., 2.), axis=(1., 0.),
        block_no=0, line_no=0, text_integrity_status='corroborated',
        text_integrity_reason_codes=('producer_owned_pdf_text_integrity_resolved',),
        receipt_trace_sequence_numbers=(0, 1))
    traces = [dict(seqno=n, type=0, opacity=1., dir=(1., 0.),
        bbox=(float(start), 0., float(end), 2.),
        chars=[(ord(c['c']), 1, c['origin'], c['bbox']) for c in chars[start:end]])
        for n, start, end in ((0, 0, 2), (1, 2, 5))]
    return dict(words=[word], raw_blocks=[dict(lines=[dict(spans=[dict(chars=chars)])])],
        traces=traces, paint_commands=[('fill-text', (0., 0., 2., 2.)), ('fill-text', (2., 0., 5., 2.))])


def test_exact_source_commands_require_full_receipt_ownership():
    facts = _facts(); before = deepcopy(facts)
    additions, receipts = _paint_partitions(**facts)
    assert [row['text'] for row in additions] == ['90', '450']
    assert {row['id'] for row in additions} == {'owned-word'}
    assert receipts[0]['text_integrity_authenticated'] is True
    assert receipts[0]['intervening_paint_commands'] == []
    assert facts == before
    assert _paint_partitions(**facts) == (additions, receipts)


@pytest.mark.parametrize('defect', ['untrusted', 'borrowed_trace', 'partial', 'overprint',
    'one_command', 'direction', 'invisible', 'opacity', 'text_mismatch', 'synthetic',
    'cross_word', 'glyph_origin', 'sequence_collision', 'nonfinite', 'non_numeric'])
def test_no_split_is_promoted_from_unproven_or_ambiguous_paint(defect):
    facts = _facts()
    if defect == 'untrusted':
        facts['words'][0].update(text_integrity_status='abstained', receipt_trace_sequence_numbers=())
    elif defect == 'borrowed_trace': facts['words'][0]['receipt_trace_sequence_numbers'] = (3, 4)
    elif defect == 'partial': facts['traces'][1]['chars'].pop()
    elif defect == 'overprint': facts['traces'].append(deepcopy(facts['traces'][0]))
    elif defect == 'one_command':
        facts['traces'][0]['chars'] += facts['traces'][1]['chars']; facts['traces'].pop()
    elif defect == 'direction': facts['traces'][1]['dir'] = (0., 1.)
    elif defect == 'invisible': facts['traces'][1]['type'] = 3
    elif defect == 'opacity': facts['traces'][1]['opacity'] = .5
    elif defect == 'text_mismatch': facts['words'][0]['text'] = '90460'
    elif defect == 'synthetic': facts['raw_blocks'][0]['lines'][0]['spans'][0]['chars'][0]['synthetic'] = True
    elif defect == 'cross_word': facts['traces'][1]['chars'].append((ord('9'), 1, (99., 1.), (99., 0., 100., 2.)))
    elif defect == 'glyph_origin':
        c = facts['traces'][1]['chars'][0]; facts['traces'][1]['chars'][0] = (c[0], c[1], (2.000001, 1.), c[3])
    elif defect == 'sequence_collision': facts['traces'][1]['seqno'] = 0
    elif defect == 'nonfinite': facts['traces'][1]['bbox'] = (0., 0., float('nan'), 2.)
    elif defect == 'non_numeric': facts['words'][0]['text'] = 'W90450'
    additions, receipts = _paint_partitions(**facts)
    assert additions == []
    assert not any(row['text_integrity_authenticated'] for row in receipts)


def test_intervening_paint_is_reported_without_repairing_text_receipt():
    facts = _facts()
    facts['words'][0].update(text_integrity_status='abstained',
        text_integrity_reason_codes=('text_trace_unavailable',), receipt_trace_sequence_numbers=())
    facts['traces'][1]['seqno'] = 2
    facts['paint_commands'].insert(1, ('fill-path', (2., 0., 5., 2.)))
    additions, receipts = _paint_partitions(**facts)
    assert additions == []
    assert receipts[0]['intervening_paint_commands'] == [dict(seqno=1, kind='fill-path', bbox=(2., 0., 5., 2.))]
    assert receipts[0]['text_integrity_status'] == 'abstained'
    assert receipts[0]['text_integrity_reason_codes'] == ('text_trace_unavailable',)


@pytest.mark.parametrize('scale,rotate,dx,dy', [(1, False, 13, 25), (2, False, 0, 0),
    (1, True, 0, 0), (.5, True, 7, -9)])
def test_glyph_partition_ownership_is_transform_invariant(scale, rotate, dx, dy):
    facts = _facts()
    def point(p):
        x, y = (-p[1], p[0]) if rotate else p
        return (x * scale + dx, y * scale + dy)
    def box(b):
        points = [point((x, y)) for x in (b[0], b[2]) for y in (b[1], b[3])]
        return (min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points), max(p[1] for p in points))
    axis = (0., 1.) if rotate else (1., 0.)
    facts['words'][0].update(bbox=box(facts['words'][0]['bbox']), axis=axis)
    for char in facts['raw_blocks'][0]['lines'][0]['spans'][0]['chars']:
        char.update(origin=point(char['origin']), bbox=box(char['bbox']))
    for trace in facts['traces']:
        trace.update(dir=axis, bbox=box(trace['bbox']),
            chars=[(c[0], c[1], point(c[2]), box(c[3])) for c in trace['chars']])
    facts['paint_commands'] = [(kind, box(b)) for kind, b in facts['paint_commands']]
    additions, receipts = _paint_partitions(**facts)
    assert [row['text'] for row in additions] == ['90', '450']
    assert receipts[0]['text_integrity_authenticated'] is True


def test_order_unrelated_content_and_word_addresses_do_not_select_an_alternative():
    facts = _facts(); expected = _paint_partitions(**facts)
    facts['traces'].reverse()
    facts['traces'].append(dict(seqno=99, type=0, opacity=1., dir=(1., 0.),
        bbox=(100., 100., 105., 102.), chars=[(ord('9'), 1, (100., 101.), (100., 100., 101., 102.))]))
    facts['words'].append(dict(facts['words'][0], id='remote-word', bbox=(100., 100., 105., 102.)))
    assert _paint_partitions(**facts) == expected


def _source(*, intervening=False, shift=0., scale=1., unrelated=False):
    doc = fitz.open(); page = doc.new_page(width=700, height=700)
    def point(p): return (p[0] * scale + shift, p[1] * scale + shift)
    for y in (100., 200.):
        page.draw_line(point((103., y)), point((106., y)))
        for x in (103., 106.):
            for sign in (-1, 1):
                page.draw_line(point((x, y)), point((x, y + 15 * sign)))
                page.draw_line(point((x, y)), point((x + 3 * sign, y + 3 * sign)))
        page.insert_text(point((100., y - 9)), '90', fontsize=8 * scale)
        if intervening:
            page.draw_rect(fitz.Rect(*point((109., y - 17)), *point((125., y - 8))),
                color=None, fill=(1., 1., 1.))
        page.insert_text(point((109., y - 9)), '450', fontsize=8 * scale)
    if unrelated:
        page.insert_text((400., 400.), '123', fontsize=8)
        page.draw_line((350., 350.), (400., 350.))
    data = doc.tobytes(); doc.close()
    digest = sha256(data).hexdigest()
    source = SourceVisibilityProducer(producer_method='live-physical-net-wall',
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION)
    published = source.ingest_native_pdf_bytes(document_id=f'live-source:{digest[:32]}',
        source_bytes=data, source_locator='memory://live-physical-net-wall-source.pdf', page_ids=('1',))
    geometry = (*point((103., 100.)), *point((103., 85.)))
    representative = next(i for i, r in source.authority().authenticated_visible_observations(published)
        if tuple(r.geometry) == geometry)
    return data, representative


@pytest.mark.parametrize('shift,scale,unrelated', [(0., 1., False), (20., 1., False),
    (0., 2., False), (10., .5, False), (0., 1., True)])
def test_fresh_source_partition_can_prove_shadow_role_without_changing_live(shift, scale, unrelated):
    data, representative = _source(shift=shift, scale=scale, unrelated=unrelated)
    result = source_partition_report(data, page_ids=('1',), representative_observation_ids=(representative,))
    row = result['candidate_audits'][0]
    assert row['original_uncovered_support_ids']
    assert row['partition_uncovered_support_ids'] == []
    assert row['complete_shadow_dimension_opposition'] is True
    assert row['original_live_state']['status'] == 'corroborated'
    assert row['live_state_unchanged'] is True
    assert result['source_sha256'] == sha256(data).hexdigest()
    assert result['source_reauthenticated'] is True
    assert all(atom['status'] == 'candidate' and atom['kind'] == 'dimension_annotation'
        and atom['normalized_value'] is None and atom['unit'] is None for atom in row['shadow_opposing_evidence_atoms'])
    for key in ('live_producer_changed', 'hypotheses_deletion_allowed', 'physical_nonexistence_proven',
        'host_publication_allowed', 'opening_count_publication_allowed', 'metric_quantity_publication_allowed'):
        assert result[key] is False
    assert source_partition_report(data, page_ids=('1',), representative_observation_ids=(representative,)) == result


def test_fresh_intervening_paint_cannot_bypass_text_integrity_negative():
    data, representative = _source(intervening=True)
    result = source_partition_report(data, page_ids=('1',), representative_observation_ids=(representative,))
    row = result['candidate_audits'][0]
    assert row['partition_uncovered_support_ids'] == row['original_uncovered_support_ids']
    assert row['complete_shadow_dimension_opposition'] is False
    assert row['shadow_opposing_evidence_atoms'] == []
    assert row['live_state_unchanged'] is True
    assert len(row['relevant_original_text_paint_partitions']) == 2
    for receipt in row['relevant_original_text_paint_partitions']:
        assert receipt['text_integrity_status'] == 'abstained'
        assert receipt['text_integrity_authenticated'] is False
        assert receipt['text_integrity_reason_codes'] == ('text_trace_unavailable',)
        assert len(receipt['intervening_paint_commands']) == 1


@pytest.mark.parametrize('defect', ['mutable', 'foreign', 'duplicate_page', 'duplicate_representative', 'absent_page'])
def test_public_audit_rejects_invalid_source_scope(defect):
    data, representative = _source()
    pages, representatives = ('1',), (representative,)
    if defect == 'mutable': data = bytearray(data)
    elif defect == 'foreign': representatives = ('source_observation_not_owned',)
    elif defect == 'duplicate_page': pages = ('1', '1')
    elif defect == 'duplicate_representative': representatives = (representative, representative)
    elif defect == 'absent_page': pages = ('2',)
    with pytest.raises((TypeError, ValueError)):
        source_partition_report(data, page_ids=pages, representative_observation_ids=representatives)
