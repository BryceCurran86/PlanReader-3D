"""Whole-wall raster frames through real sealed source and host producers."""
from dataclasses import asdict, replace
from types import SimpleNamespace

import cv2
import fitz
import numpy as np
import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_opening_area_quantity_publication import publish_live_opening_area_quantities
from pb_opening_host_frame_authority import OpeningHostFrameProducer
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from test_raster_door_swing_g17_contract import _png


def _pdf(*, remote=False, unrelated=False, text_overlay=False, dx=0, dy=0, rotation=0, scale=1):
    image = np.full((440, 1400), 255, np.uint8)
    for lo, hi in ((230, 440), (600, 800), (960, 1160)):
        cv2.rectangle(image, (lo + dx, 150 + dy), (hi + dx, 164 + dy), 0, -1)
    for x in (440, 800):
        cv2.line(image, (x + dx, 164 + dy), (x + dx, 324 + dy), 0, 1)
        cv2.ellipse(image, (x + dx, 164 + dy), (160, 160), 0, 0, 90, 0, 1)
    if unrelated:
        cv2.rectangle(image, (30, 30), (110, 42), 0, -1)
    image = np.ascontiguousarray(np.rot90(image, rotation))
    doc = fitz.open()
    width, height = (180, 320) if rotation % 2 else (320, 180)
    page = doc.new_page(width=width * scale, height=height * scale)
    page.insert_image(page.rect, stream=_png(image), keep_proportion=False)
    if remote:
        # A separate retained source wall fragment, aligned but unconnected.
        # The ordinary W4 producer owns this native segment independently of
        # the raster opening chain; no DISTINCT relation has been proved.
        page.draw_line((10., 64.25), (30., 64.25), width=.5)
    if text_overlay:
        page.insert_text((10.,78.),'90',fontsize=20.)
    data = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return data


def _fixture(data=None, **kwargs):
    source = SourceVisibilityProducer(producer_method='connected-raster-frame-test', producer_version='1')
    published = source.ingest_native_pdf_bytes(document_id='connected-raster-frame-test',
        source_bytes=_pdf(**kwargs) if data is None else data,
        source_locator='memory://connected-raster-frame-test.pdf', page_ids=('1',))
    composition = compose_live_wall_opening_authority(source_visibility_producer=source,
        revision_id=published.revision.revision_id, page_ids=('1',))
    published = source.published_snapshot_for_revision(published.revision.revision_id)
    producer = OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=composition.physical_opening_authority,
        host_binding_authority=composition.opening_host_binding_authority,
        physical_wall_candidate_authority=composition.physical_wall_candidate_authority)
    bound = []
    for trace in composition.opening_bindings:
        assert trace.status is Status.CORROBORATED
        selector = ObservationSelector(document_id=published.revision.document_id,
            revision_id=published.revision.revision_id, source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id, observation_id=trace.representative_observation_id)
        opening = composition.physical_opening_authority.prove_existence(selector).existence_record
        binding_selector = composition.binding_selectors[trace.opening_identity_id]
        binding = composition.opening_host_binding_authority.resolve(binding_selector).record
        assert len(binding.member_wall_candidate_ids) == 2
        bound.append((selector, opening, binding_selector, binding))
    assert len(bound) == 2
    return source, composition, producer, tuple(bound)


def _publish(producer, bound):
    return tuple(producer.publish(opening_selector=s, host_binding_selector=b)
        for s, _o, b, _r in bound)


def _scope(producer, bound):
    binding = bound[0][3]
    return producer._walls.resolve_scope(PhysicalWallCandidateSelector(
        document_id=binding.document_id, revision_id=binding.revision_id,
        source_sha256=binding.source_sha256, snapshot_id=binding.snapshot_id,
        page_id=binding.page_id, decision_scope_id=binding.decision_scope_id))


def test_two_source_proven_openings_share_one_complete_raster_frame_and_no_quantity():
    source, composition, producer, bound = _fixture()
    before = asdict(_scope(producer, bound))
    results = _publish(producer, bound)
    assert all(r.status is Status.CORROBORATED for r in results)
    frames = tuple(r.evidence for r in results)
    assert len({r.whole_wall_frame_id for r in frames}) == 1
    assert len({r.origin_pt for r in frames}) == 1
    assert len(frames[0].whole_wall_candidate_ids) == 3
    assert all(0 < r.u0_pt < r.u1_pt < r.whole_wall_length_pt for r in frames)
    assert frames[0].u1_pt < frames[1].u0_pt or frames[1].u1_pt < frames[0].u0_pt
    assert _publish(producer, tuple(reversed(bound))) == tuple(reversed(results))
    assert asdict(_scope(producer, bound)) == before
    voids = compose_live_physical_opening_voids(source_visibility_producer=source,
        wall_opening_composition=composition)
    assert publish_live_opening_area_quantities(voids) == ()
    assert all(o.width_m is None and o.height_m is None for o in voids.canonical_openings)


@pytest.mark.parametrize('kwargs', [dict(dx=35, dy=20), dict(rotation=1), dict(scale=2),
    dict(unrelated=True)])
def test_transformed_and_unrelated_source_content_preserves_frame_proof(kwargs):
    _source, _composition, producer, bound = _fixture(**kwargs)
    results = _publish(producer, bound)
    assert all(r.status is Status.CORROBORATED for r in results)
    assert len({r.evidence.whole_wall_frame_id for r in results}) == 1
    assert _publish(producer, bound) == results


def test_source_owned_text_fragments_are_retained_as_opposition_on_complete_frame():
    source,composition,producer,bound=_fixture(text_overlay=True)
    before=asdict(_scope(producer,bound))
    results=_publish(producer,bound)
    assert all(r.status is Status.CORROBORATED for r in results)
    assert len({r.evidence.whole_wall_frame_id for r in results})==1
    assert all(r.evidence.annotation_exclusion_evidence_atoms for r in results)
    assert all(a.status is Status.CANDIDATE and a.metadata['all_source_primitives_covered']
        for r in results for a in r.evidence.annotation_exclusion_evidence_atoms)
    assert asdict(_scope(producer,bound))==before
    assert _publish(producer,bound)==results
    voids=compose_live_physical_opening_voids(source_visibility_producer=source,
        wall_opening_composition=composition)
    assert publish_live_opening_area_quantities(voids)==()


def test_text_role_does_not_hide_independent_native_wall_competitor():
    _source,_composition,producer,bound=_fixture(text_overlay=True,remote=True)
    assert all(r.status is Status.ABSTAINED for r in _publish(producer,bound))


def test_text_role_source_damage_keeps_frame_unproven_after_pixel_cache_hit():
    source,_composition,producer,bound=_fixture(text_overlay=True)
    source._text_integrity_receipts.clear()
    results=_publish(producer,bound)
    assert all(r.status is Status.ABSTAINED and r.evidence is None for r in results)
    assert all('opening_host_frame_annotation_source_integrity_unproven' in r.reason_codes for r in results)


def test_aligned_unproven_fragment_blocks_whole_wall_extent():
    _source, _composition, producer, bound = _fixture(remote=True)
    results = _publish(producer, bound)
    assert all(r.status is Status.ABSTAINED and r.evidence is None for r in results)
    assert all('opening_host_frame_aligned_fragment_distinctness_unproven' in r.reason_codes for r in results)


def test_incomplete_wall_scope_blocks_frame(monkeypatch):
    _source, _composition, producer, bound = _fixture()
    scope = _scope(producer, bound)
    monkeypatch.setattr(producer._walls, 'resolve_scope', lambda _s: replace(scope, scope_complete=False))
    result = _publish(producer, bound)[0]
    assert result.status is Status.ABSTAINED
    assert 'opening_host_frame_complete_wall_scope_unavailable' in result.reason_codes


def test_tampered_isolated_receipt_blocks_complete_scope_discovery(monkeypatch):
    _source, _composition, producer, bound = _fixture()
    visibility = producer._opening.source_visibility_authority()
    receipts = dict(visibility._raster_opening_primitive_receipts)
    selected = bound[0][0].observation_id
    key = next(k for k in receipts if k[0] == bound[0][0].snapshot_id and k[1] != selected)
    receipts[key] = replace(receipts[key], geometry=(0., 0., 1., 1.))
    monkeypatch.setattr(visibility, '_raster_opening_primitive_receipts', receipts)
    result = _publish(producer, bound)[0]
    assert result.status is Status.ABSTAINED
    assert 'opening_host_frame_raster_scope_integrity_unproven' in result.reason_codes


def test_order_and_segment_splitting_preserve_frame_identity(monkeypatch):
    _source, _composition, producer, bound = _fixture()
    expected = _publish(producer, bound)
    scope = _scope(producer, bound)
    records = []
    for record in reversed(scope.records):
        points = record.wall_candidate.centerline_pts
        split = []
        for a, b in zip(points, points[1:]):
            split.extend((a, ((a[0]+b[0])/2, (a[1]+b[1])/2)))
        split.append(points[-1])
        records.append(replace(record, wall_candidate=replace(record.wall_candidate, centerline_pts=tuple(split))))
    monkeypatch.setattr(producer._walls, 'resolve_scope', lambda _s: replace(scope, records=tuple(records)))
    assert _publish(producer, bound) == expected


def test_missing_receipts_cannot_hide_an_aligned_opening(monkeypatch):
    _source, _composition, producer, bound = _fixture()
    visibility = producer._opening.source_visibility_authority()
    hidden_ids = set(bound[1][1].source_observation_ids)
    receipts = {k: v for k, v in visibility._raster_opening_primitive_receipts.items() if k[1] not in hidden_ids}
    monkeypatch.setattr(visibility, '_raster_opening_primitive_receipts', receipts)
    assert hidden_ids <= visibility.raster_opening_primitive_observation_ids_for_snapshot(bound[0][0].snapshot_id)
    result = _publish(producer, bound)[0]
    assert result.status is Status.ABSTAINED
    assert 'opening_host_frame_raster_scope_integrity_unproven' in result.reason_codes


def test_raster_address_index_does_not_promote_or_leak_into_ordinary_visibility():
    source, _composition, _producer, bound = _fixture()
    visibility = source.authority()
    selector = bound[0][0]
    ids = visibility.raster_opening_primitive_observation_ids_for_snapshot(selector.snapshot_id)
    assert ids and selector.observation_id in ids
    assert not ids & visibility.visible_observation_ids_for_snapshot(selector.snapshot_id)
    assert visibility.raster_opening_primitive_observation_ids_for_snapshot('stale') == frozenset()
    assert visibility.resolve_raster_opening_primitive(replace(selector, source_sha256='0'*64)).status is Status.ABSTAINED


def test_wrong_source_membership_cannot_be_reissued_as_frame_edge():
    _source, _composition, producer, bound = _fixture()
    scope = _scope(producer, bound)
    _, opening, _, binding = bound[0]
    import pb_opening_host_binding_authority as host
    geometry = host._opening_geometry(producer._opening, opening)
    wrong = replace(binding, member_wall_candidate_ids=bound[1][3].member_wall_candidate_ids)
    assert producer._raster_binding_nodes(opening=opening, binding=wrong, geometry=geometry, wall_scope=scope) is None


@pytest.mark.parametrize('curved', [False, True])
def test_local_competing_fragment_cannot_be_hidden_by_averaging_a_bent_path(monkeypatch, curved):
    _source, _composition, producer, bound = _fixture()
    scope = _scope(producer, bound)
    record = scope.records[0]
    center = _publish(producer, bound)[0].evidence.origin_pt[1]
    extra = replace(record, wall_candidate_id='unproven-local-fragment',
        physical_identity=replace(record.physical_identity, source_primitive_ids=('unowned',)),
        wall_candidate=replace(record.wall_candidate, is_curved=curved,
            representation='curved' if curved else record.wall_candidate.representation,
            curve_control_pts=((10., center), (30., center), (30., center+100.)) if curved else None,
            centerline_pts=((10., center), (30., center), (30., center+100.))))
    monkeypatch.setattr(producer._walls, 'resolve_scope', lambda _s: replace(scope, records=(*scope.records, extra)))
    result = _publish(producer, bound)[0]
    assert result.status is Status.ABSTAINED
    assert 'opening_host_frame_aligned_fragment_distinctness_unproven' in result.reason_codes


@pytest.mark.parametrize('edges', [(('a', 'b'), ('b', 'c'), ('b', 'd')),
    (('a', 'b'), ('b', 'c'), ('c', 'a'))])
def test_branch_and_cycle_cannot_supply_a_whole_wall_path(edges):
    contexts = tuple(SimpleNamespace(left_node=((a,),), right_node=((b,),),
        binding=SimpleNamespace(record_id=str(i))) for i, (a, b) in enumerate(edges))
    assert OpeningHostFrameProducer._selected_component(contexts, contexts[0].binding) is None
