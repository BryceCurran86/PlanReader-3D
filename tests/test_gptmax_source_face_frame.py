"""Exact source faces, rather than aperture padding, define a wall band."""
from dataclasses import asdict, replace
from types import SimpleNamespace as Obj

import pytest
import fitz

import pb_opening_host_binding_authority as host
from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_opening_host_frame_authority import OpeningHostFrameProducer
from pb_source_observation_authority import ObservationSelector
from test_raster_connected_host_frame import _scope, _publish, _pdf
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_visibility_authority import SourceVisibilityProducer


def _fixture(*, expand=False, **kwargs):
    source=SourceVisibilityProducer(producer_method='source-face-frame-test',
        producer_version='1',raster_paired_outer_faces_shadow=True,
        exact_g17_nomination_shadow=True)
    payload=_pdf(**kwargs)
    if expand:
        doc=fitz.open(stream=payload,filetype='pdf')
        box=doc[0].mediabox
        doc[0].set_mediabox(fitz.Rect(0,0,box.width+70,box.height+90))
        payload=doc.tobytes();doc.close()
    pub=source.ingest_native_pdf_bytes(document_id='source-face-frame-test',
        source_bytes=payload,source_locator='memory://source-face-frame.pdf',
        page_ids=(1,))
    composition=compose_live_wall_opening_authority(source_visibility_producer=source,
        revision_id=pub.revision.revision_id,page_ids=('1',),
        include_unmeasured_ink_closed_flanks_shadow=True,
        source_fragment_roles_shadow=True)
    producer=OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=composition.physical_opening_authority,
        host_binding_authority=composition.opening_host_binding_authority,
        physical_wall_candidate_authority=composition.physical_wall_candidate_authority,
        supplemental_wall_candidate_authority=composition.supplemental_physical_wall_candidate_authority,
        source_fragment_roles_shadow=True)
    pub=source.published_snapshot_for_revision(composition.revision_id)
    bound=[]
    for trace in composition.opening_bindings:
        assert trace.status is Status.CORROBORATED
        selector=ObservationSelector(pub.revision.document_id,pub.revision.revision_id,
            pub.revision.source_sha256,pub.snapshot.snapshot_id,trace.representative_observation_id)
        opening=composition.physical_opening_authority.prove_existence(selector).existence_record
        binding_selector=composition.binding_selectors[trace.opening_identity_id]
        binding=composition.opening_host_binding_authority.resolve(binding_selector).record
        bound.append((selector,opening,binding_selector,binding))
    assert len(bound)==2
    return source,composition,producer,tuple(bound)


def contexts(producer, bound):
    scope = _scope(producer, bound)
    selector, opening, _, binding = bound[0]
    geometry = host._opening_geometry(producer._opening, opening)
    result = producer._scope_bindings(wall_scope=scope, selected_binding=binding,
        selected_geometry=geometry, selected_opening=opening)
    assert result and len(result) == 2
    return result


@pytest.mark.parametrize('kwargs', ({},dict(dx=35,dy=20),dict(rotation=1),
    dict(rotation=2),dict(scale=2),dict(unrelated=True),dict(expand=True)))
def test_exact_source_faces_survive_bbox_padding_order_and_transform(kwargs):
    _,_,producer,bound = _fixture(**kwargs)
    ctx = contexts(producer,bound)
    normal = ctx[0].geometry.normal
    baseline = producer._raster_component_source_faces(ctx, normal)
    assert baseline is not None and baseline[1] > baseline[0]
    padded = tuple(replace(c,geometry=replace(c.geometry,
        thickness=c.geometry.thickness + (0.2 if i else -0.2))) for i,c in enumerate(ctx))
    # The source G17 face/end observations and physical opening IDs remain
    # untouched. An inferred bbox thickness cannot rewrite their wall band.
    assert producer._raster_component_source_faces(padded,normal) == pytest.approx(baseline)
    assert producer._raster_component_source_faces(tuple(reversed(padded)),normal) == pytest.approx(baseline)
    assert producer._raster_component_source_faces(ctx,normal) == baseline


def test_shadow_frame_uses_reproved_wall_faces_and_preserves_original_authority():
    source,composition,producer,bound = _fixture()
    original_producer=OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=composition.physical_opening_authority,
        host_binding_authority=composition.opening_host_binding_authority,
        physical_wall_candidate_authority=composition.physical_wall_candidate_authority,
        supplemental_wall_candidate_authority=composition.supplemental_physical_wall_candidate_authority)
    original=tuple(asdict(r) for r in _publish(original_producer,bound))
    scope=asdict(_scope(producer,bound))
    current=source.published_snapshot_for_revision(composition.revision_id)
    results=_publish(producer,bound)
    assert all(r.status is Status.CORROBORATED for r in results)
    assert len({r.evidence.whole_wall_frame_id for r in results}) == 1
    faces=producer._raster_component_source_faces(contexts(producer,bound),
        results[0].evidence.normal_unit)
    assert all(r.evidence.wall_thickness_pt == pytest.approx(faces[1]-faces[0]) for r in results)
    assert asdict(_scope(producer,bound)) == scope
    assert source.published_snapshot_for_revision(composition.revision_id) is current
    assert tuple(asdict(r) for r in _publish(original_producer,bound)) == original



@pytest.mark.parametrize('damage', ('missing','foreign_page','geometry','ambiguous_end'))
def test_missing_conflicting_or_competing_source_blocks_constant_band(monkeypatch,damage):
    _,_,producer,bound = _fixture()
    ctx = contexts(producer,bound)
    visibility = producer._opening.source_visibility_authority()
    resolve = visibility.resolve_raster_opening_primitive
    changed = [False]
    def corrupt(selector):
        result = resolve(selector)
        observation = result.observation
        if observation is None or changed[0]: return result
        if observation.observation_kind != 'raster_wall_band_face': return result
        changed[0] = True
        if damage == 'missing': return replace(result,status=Status.ABSTAINED,observation=None)
        if damage == 'foreign_page': observation=replace(observation,page_id='foreign')
        elif damage == 'geometry':
            g=observation.geometry
            observation=replace(observation,geometry=(g[0],g[1]+1,g[2],g[3]+1))
        else: observation=replace(observation,observation_kind='raster_wall_band_end')
        return replace(result,observation=observation)
    monkeypatch.setattr(visibility,'resolve_raster_opening_primitive',corrupt)
    assert producer._raster_component_source_faces(ctx,ctx[0].geometry.normal) is None
    assert changed[0]


def test_real_band_step_cannot_be_flattened_into_a_constant_wall(monkeypatch):
    _,_,producer,bound = _fixture()
    ctx = contexts(producer,bound)
    original = host._raster_source_band_flanks
    def stepped(support, geometry):
        flanks = original(support, geometry)
        # Geometry-only negative after source closure: one complete flank has
        # its own different band bounds, rather than a padded aperture bbox.
        if flanks is not None:
            lo,hi,nlo,nhi,edge = flanks['right']
            flanks = {**flanks, 'right': (lo,hi,nlo+0.2,nhi+0.2,edge)}
        return flanks
    monkeypatch.setattr(host,'_raster_source_band_flanks',stepped)
    assert producer._raster_component_source_faces(ctx,ctx[0].geometry.normal) is None


def test_unproven_aligned_fragment_still_blocks_source_face_frame():
    _,_,producer,bound = _fixture(remote=True)
    results = _publish(producer,bound)
    assert all(r.status is Status.ABSTAINED and r.evidence is None for r in results)
    assert all('opening_host_frame_aligned_fragment_distinctness_unproven' in r.reason_codes for r in results)


def test_source_face_frame_is_invariant_to_source_member_order_and_path_splitting(monkeypatch):
    _,_,producer,bound = _fixture()
    expected=_publish(producer,bound)
    assert all(r.status is Status.CORROBORATED for r in expected)
    scope=_scope(producer,bound)
    records=[]
    for record in reversed(scope.records):
        points=record.wall_candidate.centerline_pts
        split=[]
        for a,b in zip(points,points[1:]):
            split.extend((a,((a[0]+b[0])/2,(a[1]+b[1])/2)))
        split.append(points[-1])
        records.append(replace(record,wall_candidate=replace(record.wall_candidate,
            centerline_pts=tuple(split))))
    monkeypatch.setattr(producer._walls,'resolve_scope',
        lambda _: replace(scope,records=tuple(records)))
    assert _publish(producer,tuple(reversed(bound))) == tuple(reversed(expected))


def test_all_unknown_source_wall_pairs_remain_visible_in_sorted_replay(monkeypatch):
    _,_,producer,bound=_fixture(remote=True)
    scope=_scope(producer,bound)
    results=_publish(producer,bound)
    for result in results:
        pairs=tuple(r for r in result.reason_codes if r.startswith('opening_host_frame_unproven_wall_pair:'))
        assert pairs and pairs == tuple(sorted(pairs))
        assert result.status is Status.ABSTAINED and result.evidence is None
    monkeypatch.setattr(producer._walls,'resolve_scope',
        lambda _: replace(scope,records=tuple(reversed(scope.records))))
    assert _publish(producer,bound) == results


def test_distinct_source_offsets_are_not_elected_within_coordinate_tolerance(monkeypatch):
    _,_,producer,bound=_fixture()
    ctx=contexts(producer,bound)
    original=host._raster_source_band_flanks
    def nearby(support,geometry):
        flanks=original(support,geometry)
        if flanks is not None and geometry == ctx[1].geometry:
            flanks={role:(lo,hi,nlo+0.0000002,nhi+0.0000002,edge)
                for role,(lo,hi,nlo,nhi,edge) in flanks.items()}
        return flanks
    monkeypatch.setattr(host,'_raster_source_band_flanks',nearby)
    assert producer._raster_component_source_faces(ctx,ctx[0].geometry.normal) is None
    assert producer._raster_component_source_faces(tuple(reversed(ctx)),ctx[0].geometry.normal) is None
