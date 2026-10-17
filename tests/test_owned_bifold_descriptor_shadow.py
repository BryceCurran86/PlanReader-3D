"""A source descriptor experiment cannot bypass physical/text/host authority."""
from copy import deepcopy

import fitz
import pytest

from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_label_dimension_authority import OpeningLabelDimensionProducer
from pb_opening_label_semantic_authority import OpeningLabelSemanticProducer
from pb_source_plan_opening_callout import classify_compact_source_opening_text
from tests.test_opening_label_semantic_authority import _ingest, _opening_selector


def semantic(source,selector,enabled):
    return OpeningLabelSemanticProducer.from_source_visibility_producer(source,
        bifold_descriptor_shadow=enabled).publish_scope(selector)


def measured(source,selector,enabled):
    return OpeningLabelDimensionProducer.from_source_visibility_producer(source,
        bifold_descriptor_shadow=enabled).publish_scope(selector)


def source_pdf(label,*,scale=1.,quarter_turn=False,offset=(0.,0.),reverse=False,remote=False,second=None):
    doc=fitz.open();page=doc.new_page(width=800.,height=800.)
    def point(x,y):
        if quarter_turn:x,y=y,-x
        return fitz.Point(scale*x+offset[0],scale*y+offset[1])
    lines=[((20.,100.),(100.,100.)),((140.,100.),(220.,100.)),
        ((20.,110.),(100.,110.)),((140.,110.),(220.,110.)),
        ((100.,100.),(100.,110.)),((140.,100.),(140.,110.))]
    for a,b in reversed(lines) if reverse else lines:
        page.draw_line(point(*a),point(*b),width=scale)
    page.insert_text(point(105.,125.),label,fontsize=7.*scale,rotate=90 if quarter_turn else 0)
    if second:page.insert_text(point(105.,130.),second,fontsize=7.*scale,rotate=90 if quarter_turn else 0)
    if remote:
        page.insert_text(fitz.Point(500.,500.),'Unrelated source content',fontsize=8.)
        page.insert_text(fitz.Point(500.,540.),'2436 BIFOLD',fontsize=8.)
        page.draw_line(fitz.Point(500.,600.),fitz.Point(650.,600.),width=1.)
    payload=doc.tobytes(garbage=4,deflate=True);doc.close();return payload


@pytest.mark.parametrize('label',['2118 BIFOLD','2436 BIFOLD','2130 bifold'])
def test_valid_compact_descriptor_is_explicitly_shadow_only(label):
    assert classify_compact_source_opening_text(label)==(None,False)
    assert classify_compact_source_opening_text(label,bifold_descriptor_shadow=False)==(None,False)
    assert classify_compact_source_opening_text(label,bifold_descriptor_shadow=True)==('door',False)


@pytest.mark.parametrize('label',['BIFOLD','2118','870 BIFOLD','1218 BIFOLD',
    '0000 BIFOLD','2160 UNKNOWN','2110 SQ. SET OPENING','2118 2124 BIFOLD','2118 BIFOLDING'])
def test_unknown_untyped_invalid_and_void_labels_remain_unavailable(label):
    assert classify_compact_source_opening_text(label,bifold_descriptor_shadow=True)==(None,False)


@pytest.mark.parametrize('label',['2118 BIFOLD WINDOW','2118 SGW BIFOLD'])
def test_explicit_conflicting_window_descriptor_is_not_elected(label):
    assert classify_compact_source_opening_text(label,bifold_descriptor_shadow=True)==(None,True)
    source,pub=_ingest(source_pdf(label));selector=_opening_selector(source,pub)
    assert semantic(source,selector,True).status is EvidenceResolutionStatus.CONFLICT
    assert measured(source,selector,True).evidence is None


@pytest.mark.parametrize('scale,turn,offset,reverse,remote',[
    (1.,False,(0.,0.),False,False),(.5,False,(80.,40.),True,True),
    (2.,False,(30.,50.),True,False),(1.,True,(50.,350.),False,True)])
def test_original_text_and_physical_gap_ownership_survive_transforms_and_unrelated_content(scale,turn,offset,reverse,remote):
    source,pub=_ingest(source_pdf('2436 BIFOLD',scale=scale,quarter_turn=turn,
        offset=offset,reverse=reverse,remote=remote));selector=_opening_selector(source,pub)
    observations=deepcopy(source._producer._store.observations)
    assert semantic(source,selector,False).status is EvidenceResolutionStatus.ABSTAINED
    assert measured(source,selector,False).evidence is None
    s=semantic(source,selector,True);m=measured(source,selector,True)
    assert s.status is m.status is EvidenceResolutionStatus.CORROBORATED
    assert s.evidence.semantic_kind=='door'
    assert m.evidence.dimension_values_mm==(2400.,3600.)
    assert m.evidence.area_m2==pytest.approx(8.64)
    # Order-invariant figured area does not fabricate axis-specific authority.
    assert not m.evidence.axis_order_resolved
    assert set(s.evidence.source_text_observation_ids)<=set(m.evidence.source_text_observation_ids)
    assert source._producer._store.observations==observations
    assert source.published_snapshot_for_revision(pub.revision.revision_id)==pub
    assert semantic(source,selector,True)==s and measured(source,selector,True)==m


def test_competing_sizes_abstain_instead_of_choosing_the_first_or_nearest():
    source,pub=_ingest(source_pdf('2436 BIFOLD',second='2118 BIFOLD'))
    result=measured(source,_opening_selector(source,pub),True)
    assert result.status is EvidenceResolutionStatus.CONFLICT and result.evidence is None


def test_source_text_elsewhere_on_page_cannot_be_borrowed():
    source,pub=_ingest(source_pdf('UNKNOWN',remote=True))
    selector=_opening_selector(source,pub)
    assert semantic(source,selector,True).evidence is None
    assert measured(source,selector,True).evidence is None


def test_source_without_physical_aperture_cannot_gain_measurement_from_a_descriptor():
    doc=fitz.open();page=doc.new_page(width=400.,height=300.)
    page.insert_text(fitz.Point(100.,100.),'2436 BIFOLD',fontsize=8.)
    payload=doc.tobytes();doc.close()
    source,pub=_ingest(payload)
    from pb_source_observation_authority import ObservationSelector
    selector=ObservationSelector(document_id=pub.revision.document_id,revision_id=pub.revision.revision_id,
        source_sha256=pub.revision.source_sha256,snapshot_id=pub.snapshot.snapshot_id,
        observation_id=pub.text_observation_ids[0])
    assert semantic(source,selector,True).evidence is None
    assert measured(source,selector,True).evidence is None


@pytest.mark.parametrize('bad',[1,0,None,'true',[]])
def test_shadow_flag_is_never_inferred(bad):
    with pytest.raises(ValueError,match='explicit boolean'):
        classify_compact_source_opening_text('2118 BIFOLD',bifold_descriptor_shadow=bad)
    source,pub=_ingest(source_pdf('2118 BIFOLD'))
    for factory in (OpeningLabelSemanticProducer.from_source_visibility_producer,
                    OpeningLabelDimensionProducer.from_source_visibility_producer):
        with pytest.raises(ValueError,match='explicit boolean'):
            factory(source,bifold_descriptor_shadow=bad)
    with pytest.raises(ValueError,match='explicit boolean'):
        compose_live_physical_opening_voids(source_visibility_producer=source,
            wall_opening_composition=None,bifold_descriptor_shadow=bad)
