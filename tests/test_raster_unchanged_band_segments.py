from dataclasses import replace
from io import BytesIO

import cv2
import fitz
import numpy as np
import pytest
from PIL import Image

import pb_raster_unchanged_band_segments as capture
from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
from test_raster_source_visibility_v1 import _selector


def _png(image):
    ok, encoded = cv2.imencode('.png', image)
    assert ok
    return encoded.tobytes()


def _images():
    source = np.full((160, 240, 3), 255, dtype=np.uint8)
    source[70:80, 30:210] = 0
    return source, source.copy()


def test_changed_native_paint_is_a_cut_and_terminal_source_run_survives():
    source, full = _images()
    full[70:80, 35:40] = (0, 0, 255)
    before = (source.copy(), full.copy())
    result = capture.detect_unchanged_terminal_band_segments(_png(source), _png(full), dpi=144)
    assert len(result) == 1
    assert result[0].geometry_pt == (20.0, 37.25, 104.5, 37.25)
    assert result[0].pixel_support_bounds == (40, 70, 209, 79)
    assert np.array_equal(source, before[0]) and np.array_equal(full, before[1])
    assert result == capture.detect_unchanged_terminal_band_segments(_png(source), _png(full), dpi=144)


@pytest.mark.parametrize('change', ['white_overlay', 'changed_core', 'changed_center', 'same_gray_other_rgb'])
def test_changed_pixels_never_bridge_or_keep_interior_runs(change):
    source, full = _images()
    full[70:80, 30:40] = 255
    full[70:80, 200:210] = 255
    if change == 'white_overlay': full[70:80, 110:120] = 255
    elif change == 'changed_core': full[72:73, 110:120] = (0, 0, 100)
    elif change == 'changed_center': full[74:76, 110:120] = (0, 0, 100)
    else: full[70:80, 110:120] = (1, 0, 0)
    assert capture.detect_unchanged_terminal_band_segments(_png(source), _png(full), dpi=144) == ()


@pytest.mark.parametrize('transform', ['translate', 'rotate', 'scale'])
def test_source_geometry_follows_render_transform(transform):
    source, full = _images()
    base = capture.detect_unchanged_terminal_band_segments(_png(source), _png(full), dpi=144)[0]
    if transform == 'translate':
        shifted = np.full((180, 260, 3), 255, dtype=np.uint8)
        shifted[10:170, 10:250] = source
        result = capture.detect_unchanged_terminal_band_segments(_png(shifted), _png(shifted), dpi=144)[0]
        assert result.geometry_pt == tuple(v + 5 for v in base.geometry_pt)
    elif transform == 'rotate':
        rotated = np.rot90(source).copy()
        result = capture.detect_unchanged_terminal_band_segments(_png(rotated), _png(rotated), dpi=144)[0]
        assert result.orientation == 'vertical'
        assert result.geometry_pt == (37.25, 15.0, 37.25, 104.5)
    else:
        scaled = cv2.resize(source, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
        result = capture.detect_unchanged_terminal_band_segments(_png(scaled), _png(scaled), dpi=288)[0]
        assert max(abs(a-b) for a,b in zip(result.geometry_pt,base.geometry_pt)) <= 72/288


def test_render_extents_and_existing_primitive_cap_fail_closed(monkeypatch):
    source, _ = _images()
    with pytest.raises(ValueError):
        capture.detect_unchanged_terminal_band_segments(_png(source), _png(source[:-1]), dpi=144)
    def bounded(*args, **kwargs):
        raise ValueError('raster opening primitive count exceeds safety bound')
    monkeypatch.setattr(capture, 'detect_raster_opening_source_primitives', bounded)
    with pytest.raises(ValueError, match='safety bound'):
        capture.detect_unchanged_terminal_band_segments(_png(source), _png(source), dpi=144)


def _pdf():
    source = np.full((360, 640, 3), 255, dtype=np.uint8)
    cv2.rectangle(source, (200, 150), (240, 164), (0,0,0), -1)
    cv2.rectangle(source, (400, 150), (610, 164), (0,0,0), -1)
    cv2.line(source, (248, 154), (392, 154), (0,0,0), 1)
    cv2.line(source, (248, 160), (392, 160), (0,0,0), 1)
    buf = BytesIO()
    Image.fromarray(source).save(buf, format='PNG')
    pdf = fitz.open()
    page = pdf.new_page(width=320, height=180)
    page.insert_image(page.rect, stream=buf.getvalue())
    page.draw_line((101, 70), (101, 85), color=(1,0,0), width=1)
    page.insert_text((145, 83), '1218 SGW', fontsize=4)
    result = pdf.tobytes()
    pdf.close()
    return result


@pytest.mark.parametrize('warm', [False, True])
@pytest.mark.parametrize('damage', ['full_hash', 'image_hash', 'dpi', 'pixel_geometry'])
def test_supplemental_visible_reader_reauthenticates_exact_render_registration(warm, damage):
    source = SourceVisibilityProducer(producer_method='terminal-test', producer_version='1')
    published = source.ingest_native_pdf_bytes(document_id='terminal-test', source_bytes=_pdf(),
                                              source_locator='memory://terminal-test.pdf')
    published = source.augment_with_raster_opening_primitives(published.revision.revision_id)
    published = source.augment_with_raster_visible_segments(published.revision.revision_id)
    authority = source.authority()
    rows = authority.authenticated_visible_observations(published)
    ids = [oid for oid, row in rows if capture.UNCHANGED_BAND_IDENTITY_VERSION in row.source_primitive_ref]
    assert ids
    oid = ids[0]
    key = (published.snapshot.snapshot_id, oid)
    selector = _selector(published, oid)
    if warm:
        assert authority.resolve_visible(selector).status is Status.CORROBORATED
    receipt = source._raster_visibility_receipts[key]
    if damage == 'full_hash': receipt = replace(receipt, visibility_render_sha256='0' * 64)
    elif damage == 'image_hash': receipt = replace(receipt, image_sha256='0' * 64)
    elif damage == 'dpi': receipt = replace(receipt, dpi=144)
    else: receipt = replace(receipt, pixel_geometry=(0.,0.,1.,1.))
    source._raster_visibility_receipts[key] = receipt
    assert authority.resolve_visible(selector).status in (Status.ABSTAINED, Status.CONFLICT)
    with pytest.raises(RuntimeError):
        authority.authenticated_visible_observations(published)


def test_actual_source_capture_closes_host_and_figured_area_without_default_count(monkeypatch):
    from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
    from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
    from pb_live_opening_area_quantity_publication import publish_live_opening_area_quantities

    source_bytes = _pdf()

    def collect():
        source = SourceVisibilityProducer(producer_method='terminal-test', producer_version='1')
        published = source.ingest_native_pdf_bytes(document_id='terminal-test', source_bytes=source_bytes,
                                                  source_locator='memory://terminal-test.pdf')
        composition = compose_live_wall_opening_authority(source_visibility_producer=source,
            revision_id=published.revision.revision_id, page_ids=('1',))
        current = source.published_snapshot_for_revision(published.revision.revision_id)
        assert current is not None
        wall_scope = composition.physical_wall_candidate_authority.resolve_scope(
            PhysicalWallCandidateSelector(
                document_id=current.revision.document_id,
                revision_id=current.revision.revision_id,
                source_sha256=current.revision.source_sha256,
                snapshot_id=current.snapshot.snapshot_id,
                page_id='1',
                decision_scope_id='wall-source:page-1',
            )
        )
        wall_signature = tuple(
            (
                record.wall_candidate_id,
                record.physical_identity.candidate_identity_id,
                tuple(record.physical_identity.source_primitive_ids),
                tuple(record.physical_identity.edge_ids),
                tuple(tuple(point) for point in record.wall_candidate.centerline_pts),
            )
            for record in wall_scope.records
        )
        voids = compose_live_physical_opening_voids(source_visibility_producer=source,
                                                   wall_opening_composition=composition)
        return composition, voids, publish_live_opening_area_quantities(voids), wall_signature

    with monkeypatch.context() as absent:
        absent.setattr('pb_source_visibility_authority.detect_unchanged_terminal_band_segments',
                       lambda *args, **kwargs: ())
        before, _voids, previous, baseline_walls = collect()
    assert before.opening_bindings[0].status is Status.ABSTAINED
    assert previous == ()
    composition, voids, quantities, candidate_walls = collect()
    assert candidate_walls == baseline_walls
    assert len(composition.opening_bindings) == 1
    binding = composition.opening_bindings[0]
    assert binding.status is Status.CORROBORATED
    assert binding.record_id and binding.host_wall_id
    assert len(binding.member_wall_candidate_ids) == 2
    assert 'raster_source_band_host_resolved' in binding.reason_codes
    assert len(quantities) == 1
    assert quantities[0].value == pytest.approx(2.16)
    assert quantities[0].abstained is False
    assert voids.canonical_openings[0].schedule_count_explicit is False
    assert voids.canonical_openings[0].schedule_declared_count is None


def test_registered_one_ended_g17_source_parent_reauthenticates_and_routes_only_to_supplemental_w4():
    from pb_source_visibility_authority import (
        _raster_segment_observation_id, _raster_segment_receipt_matches_parent,
    )
    from pb_physical_wall_candidate_authority import (
        _is_opening_local_supplemental_segment,
        RASTER_PDF_VISIBLE_SEGMENT,
    )
    assert capture.OPENING_LOCAL_SOURCE_IDENTITY_VERSIONS == frozenset((
        capture.UNCHANGED_BAND_IDENTITY_VERSION,
        capture.ORIGINAL_G17_ONE_END_SOURCE_IDENTITY_VERSION,
        capture.ORIGINAL_G17_JAMB_PARTIAL_IDENTITY_VERSION,
        capture.ORIGINAL_G17_EXACT_ONE_END_IDENTITY_VERSION,
        capture.ORIGINAL_G17_EXACT_PARTIAL_IDENTITY_VERSION,
    ))
    source = SourceVisibilityProducer(producer_method="original-one-ended-parent-test", producer_version="1")
    selected = source.ingest_native_pdf_bytes(document_id="one-ended-parent",
        source_bytes=_pdf(), source_locator="memory://source.pdf")
    selected = source.augment_with_raster_opening_primitives(selected.revision.revision_id)
    selected = source.augment_with_raster_visible_segments(selected.revision.revision_id)
    observed = source.authority().authenticated_visible_observations(selected)
    rows = [(oid, parent) for oid, parent in observed if
        capture.UNCHANGED_BAND_IDENTITY_VERSION in parent.source_primitive_ref]
    assert len(rows) >= 1
    oid, visible = rows[0]
    receipt = source._raster_visibility_receipts[(selected.snapshot.snapshot_id, oid)]
    from pb_source_observation_authority import ObservationSelector
    parent_proof = source._producer.authority().resolve(ObservationSelector(
        document_id=receipt.document_id, revision_id=receipt.revision_id,
        source_sha256=receipt.source_sha256,
        snapshot_id=selected.snapshot.snapshot_id,
        observation_id=receipt.parent_observation_id,
    ))
    assert parent_proof.status is Status.CORROBORATED
    parent = parent_proof.observation
    assert parent is not None
    assert visible.source_primitive_ref == f"visible:{parent.source_primitive_ref}"
    prefix, image_sha, version, full_sha, index = parent.source_primitive_ref.split(":")
    assert version == capture.UNCHANGED_BAND_IDENTITY_VERSION
    assert _raster_segment_receipt_matches_parent(receipt, parent)
    new_version = capture.ORIGINAL_G17_ONE_END_SOURCE_IDENTITY_VERSION
    new_ref = ":".join((prefix, image_sha, new_version, full_sha, index))
    new_id = _raster_segment_observation_id(
        document_id=receipt.document_id, revision_id=receipt.revision_id,
        page_id=receipt.page_id, partition_id=receipt.source_partition_id,
        image_sha256=receipt.image_sha256, identity_version=new_version,
        pixel_geometry=receipt.pixel_geometry, geometry=receipt.geometry,
        index=int(index), visibility_render_sha256=receipt.visibility_render_sha256,
    )
    reissued = replace(parent, observation_id=new_id, source_primitive_ref=new_ref)
    assert _raster_segment_receipt_matches_parent(receipt, reissued)
    row = {"source_kind": RASTER_PDF_VISIBLE_SEGMENT, "id": new_ref,
           "source_observation_id": new_id}
    assert _is_opening_local_supplemental_segment(row)
    assert not _is_opening_local_supplemental_segment({
        **row, "source_kind": "native_pdf_visible_segment"
    })
    # No reusing the historical observation ID or other issuer's receipt.
    assert not _raster_segment_receipt_matches_parent(receipt,
        replace(parent, source_primitive_ref=new_ref))
    assert not _raster_segment_receipt_matches_parent(receipt,
        replace(reissued, source_primitive_ref=new_ref.replace(full_sha, "f"*64)))
    assert not _raster_segment_receipt_matches_parent(receipt,
        replace(reissued, source_primitive_ref=new_ref.replace(new_version, "foreign_g17_v1")))
    assert not _raster_segment_receipt_matches_parent(
        replace(receipt, dpi=144), reissued)
