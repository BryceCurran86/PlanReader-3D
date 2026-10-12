"""Original location export cannot bless missing or foreign text ancestry."""
from dataclasses import asdict, replace
from types import SimpleNamespace

import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_pdf_text_integrity_authority import PdfTextIntegrityReceipt
from tools.diag_gptmax_source_authority_stages import _opening_identity_text_receipts


def _fixture():
    receipt = PdfTextIntegrityReceipt(
        receipt_id='text-receipt', parent_observation_id='text-1',
        document_id='doc', revision_id='rev', source_sha256='a'*64,
        page_id='3', source_partition_id='native-page-3', raw_text='0912 SGW',
        geometry=(10., 20., 30., 28.), trusted=True,
        decode_status='verified', visibility_status='visible', reason_codes=(),
    )
    published = SimpleNamespace(
        revision=SimpleNamespace(document_id='doc',revision_id='rev',source_sha256='a'*64),
        snapshot=SimpleNamespace(snapshot_id='snapshot'), text_observation_ids=('text-1',),
    )
    result = SimpleNamespace(status=Status.CORROBORATED, trusted_text='0912 SGW', receipt=receipt)
    seen = []
    def resolve(selector):
        seen.append(selector)
        return result
    source = SimpleNamespace(
        text_integrity_authority=lambda: SimpleNamespace(resolve_text=resolve),
        published_snapshot_for_revision=lambda rev: published,
    )
    traces = [{'opening_identity_id':'physical-1','result':{
        'status':Status.CORROBORATED,'evidence':{
            'opening_record_id':'physical-1', 'evidence_id':'label-1',
            'source_text_observation_ids':['text-1'],'page_id':'3',
        },
    }}]
    return source,published,traces,result,seen


def test_owned_receipt_is_detached_exact_location_not_a_quantity_or_binding():
    source,published,traces,result,seen = _fixture()
    original = asdict(result.receipt)
    rows = _opening_identity_text_receipts(source,published,traces)
    assert rows[0]['label_bbox_pdf_pt'] == [10.,20.,30.,28.]
    assert rows[0]['figured_label_evidence_id'] == 'label-1'
    assert rows[0]['source_text_integrity_receipts'][0] == original
    assert seen[0].snapshot_id == 'snapshot'
    assert not {'benchmark_item_id','quantity','value','host_wall_id'} & rows[0].keys()
    rows[0]['source_text_integrity_receipts'][0]['geometry'] = (0.,0.,1.,1.)
    assert asdict(result.receipt) == original


@pytest.mark.parametrize('fault',[
    'untrusted','foreign_parent','foreign_page','foreign_sha','foreign_revision',
    'outside_universe','duplicate_text','wrong_opening','invalid_box','changed_snapshot',
])
def test_missing_or_foreign_location_evidence_rejects_export(fault):
    source,published,traces,result,_seen = _fixture()
    if fault == 'untrusted':
        result.status = Status.ABSTAINED
    elif fault == 'foreign_parent':
        result.receipt = replace(result.receipt,parent_observation_id='another')
    elif fault == 'foreign_page':
        result.receipt = replace(result.receipt,page_id='4')
    elif fault == 'foreign_sha':
        result.receipt = replace(result.receipt,source_sha256='b'*64)
    elif fault == 'foreign_revision':
        result.receipt = replace(result.receipt,revision_id='stale')
    elif fault == 'outside_universe':
        published.text_observation_ids = ()
    elif fault == 'duplicate_text':
        traces[0]['result']['evidence']['source_text_observation_ids'] *= 2
    elif fault == 'wrong_opening':
        traces[0]['result']['evidence']['opening_record_id'] = 'another'
    elif fault == 'invalid_box':
        result.receipt = replace(result.receipt,geometry=(10.,20.,float('nan'),28.))
    else:
        source.published_snapshot_for_revision = lambda rev: None
    with pytest.raises(ValueError):
        _opening_identity_text_receipts(source,published,traces)


def test_abstained_label_stays_unavailable_without_resolving_text():
    source,published,traces,_result,seen = _fixture()
    traces[0]['result'] = {'status':Status.ABSTAINED,'evidence':None}
    assert _opening_identity_text_receipts(source,published,traces) == []
    assert not seen
