"""Unpainted PDF path boundaries remain retained candidate opposition only."""
from dataclasses import asdict, replace

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _source(*, stroke=None, fill=(1, 1, 1), opacity=1, scale=1,
            dx=0, dy=0, rotation=0, unrelated=False):
    pdf = fitz.open()
    page = pdf.new_page(width=240*scale, height=240*scale)
    for y in (50, 70):
        page.draw_rect(fitz.Rect((80+dx)*scale, (y+dy)*scale,
                                (88+dx)*scale, (y+8+dy)*scale),
                       color=stroke, fill=fill, fill_opacity=opacity)
    if unrelated:
        page.draw_line((10*scale, 10*scale), (30*scale, 10*scale))
    page.set_rotation(rotation)
    data = pdf.tobytes()
    pdf.close()
    source = SourceVisibilityProducer(producer_method='paint-role-test', producer_version='1')
    published = source.ingest_native_pdf_bytes(document_id='paint-role-test',
        source_bytes=data, source_locator='memory://paint-role-test.pdf')
    rows = source.authority().authenticated_visible_observations(published)
    selected = tuple(i for i, r in rows if 'e' in r.source_primitive_ref.removeprefix('visible:segment:'))
    assert len(selected) == 8
    selector = ObservationSelector(document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id, observation_id=selected[0])
    return source, published, selector, selected


def test_exact_white_unstroked_rectangles_emit_only_candidate_opposition():
    source, published, selector, selected = _source()
    before = asdict(published)
    result = source.native_unstroked_fill_evidence(selector, support_observation_ids=selected)
    assert len(result) == 1
    atom = result[0]
    assert atom.kind == 'annotation_border' and atom.status is Status.CANDIDATE
    assert atom.metadata['polarity'] == 'opposing'
    assert atom.metadata['all_source_primitives_covered']
    assert set(atom.metadata['source_observation_ids']) == set(selected)
    assert atom.normalized_value is None and atom.unit is None
    assert source.native_unstroked_fill_evidence(selector,
        support_observation_ids=tuple(reversed(selected))) == result
    assert asdict(published) == before
    assert set(selected) <= set(source.authority().visible_observation_ids_for_snapshot(selector.snapshot_id))


@pytest.mark.parametrize('kwargs', [dict(stroke=(0,0,0)), dict(fill=(0,0,0)),
    dict(fill=(.99,1,1)), dict(fill=None), dict(opacity=.5)])
def test_stroked_colored_or_translucent_paths_do_not_prove_role(kwargs):
    source, _published, selector, selected = _source(**kwargs)
    assert source.native_unstroked_fill_evidence(selector, support_observation_ids=selected) == ()


@pytest.mark.parametrize('kwargs', [dict(dx=31,dy=20), dict(scale=2), dict(scale=.5),
    dict(rotation=90), dict(rotation=180), dict(rotation=270), dict(unrelated=True)])
def test_transforms_and_unrelated_content_preserve_role(kwargs):
    source, _published, selector, selected = _source(**kwargs)
    assert source.native_unstroked_fill_evidence(selector, support_observation_ids=selected)


def test_mixed_native_support_is_not_fully_explained():
    source, published, selector, selected = _source(unrelated=True)
    rows = source.authority().authenticated_visible_observations(published)
    line_id = next(i for i, r in rows if 'e' not in r.source_primitive_ref.removeprefix('visible:segment:'))
    assert source.native_unstroked_fill_evidence(selector,
        support_observation_ids=(*selected, line_id)) == ()


def test_g17_retains_unpainted_boundary_hypothesis_and_cannot_close_counts():
    source, _published, selector, selected = _source()
    physical = source.physical_opening_authority()
    results = tuple(physical.prove_existence(replace(selector, observation_id=i)) for i in selected)
    opposed = tuple(r for r in results if r.opposing_evidence_atoms)
    assert opposed
    assert all(r.status is Status.ABSTAINED and r.existence_record is None for r in opposed)
    assert all(r.candidate is not None and r.proposition is None for r in opposed)
    assert all(r.reason_codes == ('native_unstroked_fill_boundary_opposes_opening',) for r in opposed)
    assert not physical.assess_visible_candidate_closure(selector).candidate_universe_complete


@pytest.mark.parametrize('defect', ['geometry','missing_receipt','source_bytes'])
def test_geometry_receipt_and_source_hash_damage_fail_closed(defect):
    source, _published, selector, selected = _source()
    assert source.native_unstroked_fill_evidence(selector, support_observation_ids=selected)
    if defect == 'geometry':
        key = (selector.snapshot_id, selected[0])
        record = source._producer._store.observations[key]
        source._producer._store.observations[key] = replace(record, geometry=(0.,0.,1.,1.))
    elif defect == 'missing_receipt':
        del source._visibility_receipts[(selector.snapshot_id, selected[0])]
    else:
        source._producer._store.source_bytes_by_revision[selector.revision_id] = b'changed'
    with pytest.raises(RuntimeError):
        source.native_unstroked_fill_evidence(selector, support_observation_ids=selected)


def test_source_damage_cannot_be_hidden_by_a_cached_paint_page():
    source, _published, selector, selected = _source()
    assert source.native_unstroked_fill_evidence(selector, support_observation_ids=selected)
    key = (selector.snapshot_id, selected[-1])
    source._visibility_receipts[key] = 'foreign-parent'
    with pytest.raises(RuntimeError):
        source.native_unstroked_fill_evidence(selector, support_observation_ids=selected)


@pytest.mark.parametrize('field,value', [('revision_id','stale'), ('snapshot_id','stale'),
    ('source_sha256','0'*64), ('document_id','foreign')])
def test_stale_and_foreign_selectors_reject_role(field,value):
    source, _published, selector, selected = _source()
    with pytest.raises(RuntimeError):
        source.native_unstroked_fill_evidence(replace(selector, **{field:value}),
            support_observation_ids=selected)
