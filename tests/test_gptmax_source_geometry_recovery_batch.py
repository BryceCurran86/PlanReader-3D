"""Synthetic original-source proofs for the source geometry recovery batch."""
from dataclasses import asdict, replace
from hashlib import sha256
from types import SimpleNamespace as Obj

import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_source_observation_authority import ObservationSelector
from pb_opening_label_dimension_authority import OpeningLabelDimensionProducer
from pb_nominal_opening_canonical_shadow import build_nominal_opening_canonical_shadow
from pb_raster_unchanged_band_segments import (
    UnchangedRasterBandSegment, band_segment_exactly_observed,
    band_segment_already_observed, OPENING_LOCAL_SOURCE_IDENTITY_VERSIONS,
)
from pb_physical_wall_candidate_authority import _is_opening_local_supplemental_segment
from test_raster_unchanged_band_segments import _pdf as raster_pdf
from test_opening_label_dimension_authority import _pdf, _ingest, _opening_selector


def source():
    p=SourceVisibilityProducer(producer_method="fork-test",producer_version="1")
    pub=p.ingest_native_pdf_bytes(document_id="original",source_bytes=raster_pdf(),
        source_locator="memory://original.pdf",page_ids=(1,))
    return p,pub


def test_fork_has_independent_store_and_retains_original_issuer():
    original,pub=source()
    fork,replayed=original.fork_native_source_shadow(pub.revision.revision_id,
        raster_paired_outer_faces_shadow=True,exact_g17_nomination_shadow=True)
    assert fork is not original and fork._producer._store is not original._producer._store
    assert replayed.revision.source_sha256==pub.revision.source_sha256
    assert replayed.coverage.decoded_pages==pub.coverage.decoded_pages
    assert replayed.revision.source_locator==pub.revision.source_locator
    fork.augment_with_raster_opening_primitives(replayed.revision.revision_id,page_ids=("1",))
    assert original.published_snapshot_for_revision(pub.revision.revision_id) is pub
    assert original._raster_opening_primitive_receipts=={}
    assert fork._raster_opening_primitive_receipts


@pytest.mark.parametrize("damage",["bytes","obsolete","new-revision"])
def test_fork_never_copies_stale_or_foreign_original_lineage(damage):
    original,pub=source()
    revision=pub.revision.revision_id
    if damage=="bytes":
        original._producer._store.source_bytes_by_revision[revision]=b"altered-original"
    else:
        fresh=original.ingest_native_pdf_bytes(document_id="original",
            source_bytes=_pdf(labels=()),source_locator="memory://changed.pdf",page_ids=(1,))
        if damage=="new-revision": revision=fresh.revision.revision_id
    with pytest.raises(ValueError):original.fork_native_source_shadow(revision)


@pytest.mark.parametrize("flag",[None,1,"true",[],{}])
def test_exact_nomination_is_never_a_truthy_implicit_source_policy(flag):
    with pytest.raises(ValueError):
        SourceVisibilityProducer(producer_method="t",producer_version="1",exact_g17_nomination_shadow=flag)


def segment(line):
    return UnchangedRasterBandSegment(line,line,"horizontal",(0,15,100,20))


def test_nearby_or_touching_coarse_render_never_suppresses_new_original_span():
    candidate=segment((0.,4.,10.,4.))
    touching=segment((.5,4.1,8.,4.1))
    assert band_segment_already_observed(candidate,(touching,),dpi=300,ordinary_dpi=144)
    assert not band_segment_exactly_observed(candidate,(touching,),dpi=300,ordinary_dpi=144)
    assert band_segment_exactly_observed(candidate,(candidate,),dpi=300,ordinary_dpi=144)
    assert not band_segment_exactly_observed(candidate,(segment((0.,4.,9.99,4.)),),dpi=300,ordinary_dpi=300)


@pytest.mark.parametrize("family",OPENING_LOCAL_SOURCE_IDENTITY_VERSIONS)
def test_registered_source_families_stay_out_of_canonical_page_and_viewport_w4(family):
    assert _is_opening_local_supplemental_segment({"id":f"raster_segment:im:{family}:full:0"})
    assert not _is_opening_local_supplemental_segment({"id":f"native:im:{family}:full:0"})


@pytest.mark.parametrize("text,width,height,kind",[
    ("1218 SGW",1800.,1200.,"window"),("2127 STACKER",2700.,2100.,"door"),
])
def test_owned_hhww_axes_do_not_rewrite_the_old_figured_area_evidence(text,width,height,kind):
    p,pub=_ingest(_pdf(labels=((88.,124.,text),)),"axis-"+text)
    sel=_opening_selector(p,pub)
    producer=OpeningLabelDimensionProducer.from_source_visibility_producer(p)
    prior=producer.publish_scope(sel)
    assert prior.evidence is not None
    frozen=asdict(prior)
    shadow=producer.ordered_compact_axes_shadow(sel)
    assert shadow.evidence.width_mm==width and shadow.evidence.height_mm==height
    assert shadow.evidence.semantic_kind==kind and shadow.evidence.axis_order_resolved is True
    assert shadow.evidence.area_m2==prior.evidence.area_m2
    assert shadow.evidence.evidence_id!=prior.evidence.evidence_id
    assert asdict(producer.publish_scope(sel))==frozen
    obj=build_nominal_opening_canonical_shadow(p,sel)
    assert obj.width_m==width/1000 and obj.height_m==height/1000
    assert obj.wall_id is None and obj.sill_height_m is None and obj.offset_along_wall_m is None
    assert obj.takeoff_eligible is False and obj.deduction_authority is False
    assert obj.provenance.opening_instance_id==shadow.evidence.opening_record_id
    assert obj.metadata["rough_opening_geometry_resolved"] is False


@pytest.mark.parametrize("text",["900 - 1200 asw","870","2127 UNKNOWN"])
def test_unordered_pairs_single_axes_and_unknown_types_are_not_nominal_axis_authority(text):
    p,pub=_ingest(_pdf(labels=((88.,124.,text),)),"unresolved-"+text)
    sel=_opening_selector(p,pub)
    producer=OpeningLabelDimensionProducer.from_source_visibility_producer(p)
    assert producer.ordered_compact_axes_shadow(sel).status is not Status.CORROBORATED
    assert build_nominal_opening_canonical_shadow(p,sel) is None


def test_raster_viewport_scope_is_compiled_once_and_source_tamper_still_abstains(monkeypatch):
    import pb_physical_opening_viewport_scope_authority as viewport
    p,pub=source()
    pub=p.augment_with_raster_opening_primitives(pub.revision.revision_id,page_ids=("1",))
    physical=p.physical_opening_authority()
    sel=ObservationSelector(pub.revision.document_id,pub.revision.revision_id,
        pub.revision.source_sha256,pub.snapshot.snapshot_id,pub.raster_opening_primitive_observation_ids[0])
    resolved=p.authority().resolve_raster_opening_primitive(sel)
    records,failures=physical._raster_primitive_snapshot_records(resolved)
    assert not failures
    seed=records[0]
    records=tuple(r for r in records if r.page_id=="1")
    candidates=physical._raster_framed_candidates_for(seed,records)
    assert candidates
    real=viewport.classify_opening_candidate_viewport_scopes
    calls=[]
    def reader(**kwargs):calls.append(1);return real(**kwargs)
    monkeypatch.setattr(viewport,"classify_opening_candidate_viewport_scopes",reader)
    first=physical._viewport_scoped_raster_candidates_for(seed,records,candidates)
    assert first==physical._viewport_scoped_raster_candidates_for(seed,records,candidates)
    assert len(calls)==1
    physical._invalidate_snapshot_caches_after_failed_source_batch(pub.snapshot.snapshot_id)
    assert first==physical._viewport_scoped_raster_candidates_for(seed,records,candidates)
    assert len(calls)==2
    p._producer._store.source_bytes_by_revision[pub.revision.revision_id]=b"foreign"
    assert physical._viewport_scoped_raster_candidates_for(seed,records,candidates)==()


def test_local_aperture_frame_never_enters_the_positive_whole_wall_authority():
    from test_raster_connected_host_frame import _fixture
    from pb_opening_host_frame_authority import OpeningHostFrameSelector
    _source,composition,producer,bound=_fixture()
    sel,opening,binding_sel,binding=bound[0]
    result=producer.local_source_frame_shadow(opening_selector=sel,host_binding_selector=binding_sel)
    assert result.status is Status.CANDIDATE and result.evidence is not None
    assert result.evidence.whole_wall_length_pt is None
    assert result.evidence.u1_pt>result.evidence.u0_pt
    frame_sel=OpeningHostFrameSelector(binding.document_id,binding.revision_id,binding.source_sha256,
        binding.snapshot_id,binding.page_id,binding.decision_scope_id,binding.opening_identity_id)
    assert producer.authority().resolve(frame_sel).evidence is None
