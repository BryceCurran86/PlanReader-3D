"""Real source-root drawing scope, complete competitor retention and negatives."""
from copy import deepcopy
from dataclasses import replace

import fitz
import numpy as np
import pytest

from pb_g17_plan_wall_scope_shadow import _paint, build_g17_plan_wall_scope_shadow
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from tests.test_source_owned_physical_plan_view import _sheet, _source
from tests.test_raster_framed_opening_g17_contract import _png, _sheet as _raster_sheet


def _prepare(**options):
    scale = options.get("scale", 1.0)
    dx, dy = options.get("dx", 0.0), options.get("dy", 0.0)
    with fitz.open(stream=_sheet(**options), filetype="pdf") as pdf:
        # Keep raster paint clear of existing native room/title/figure words.
        pdf[0].insert_image(fitz.Rect(60*scale+dx, 260*scale+dy,
                                     340*scale+dx, 330*scale+dy),
                            stream=_png(_raster_sheet(frame_lines=2)),
                            keep_proportion=False)
        data = pdf.tobytes()
    source, published = _source(data)
    published = source.augment_with_raster_opening_primitives(
        published.revision.revision_id, page_ids=("1",))
    return source, published


def test_same_source_plan_and_original_300_scope_keep_all_paint_and_negatives(monkeypatch):
    source, pub = _prepare()
    before = deepcopy(source._producer._store.observations)
    receipts = deepcopy(source._raster_opening_primitive_receipts)
    def forbidden(*args, **kwargs):
        raise AssertionError("reader must never augment original snapshot")
    monkeypatch.setattr(source, "augment_with_raster_visible_segments", forbidden)
    monkeypatch.setattr(source, "augment_with_raster_opening_primitives", forbidden)
    report = build_g17_plan_wall_scope_shadow(source, revision_id=pub.revision.revision_id,
                                             page_id="1")
    assert report["source_viewport_ownership_id"]
    assert report["snapshot_id"] == pub.snapshot.snapshot_id
    assert report["status"] == "abstained"
    assert report["source_primitive_count"] == len(pub.raster_opening_primitive_observation_ids)
    assert len(report["source_primitive_dispositions"]) == report["source_primitive_count"]
    assert report["source_positive_graph_primitive_count"] > 0
    for name in ("default_w2_w3_w4", "exact_coordinate_w2_w3_w4"):
        graph = report[name]
        assert graph["w4_records"] and graph["w3_junctions"]
        assert all(p.startswith("raster_opening_primitive:")
                   for w in graph["w4_records"]
                   for p in w["physical_identity"]["source_primitive_ids"])
    assert not any(report[k] for k in ("scope_complete", "structural_wall_role_granted",
        "physical_wall_equivalence_granted", "host_granted", "metric_quantity_granted"))
    assert source.published_snapshot_for_revision(pub.revision.revision_id) == pub
    assert source._producer._store.observations == before
    assert source._raster_opening_primitive_receipts == receipts
    with pytest.raises(TypeError):
        PhysicalWallCandidateProducer.from_source_visibility_producer(report)


@pytest.mark.parametrize("options", [{}, {"dx":13.,"dy":29.}, {"scale":1.5},
    {"reverse":True}, {"split":True}, {"unrelated":True}, {"expanded":True}])
def test_source_transform_replay_preserves_candidate_only_contract(options):
    source, pub = _prepare(**options)
    a = build_g17_plan_wall_scope_shadow(source, revision_id=pub.revision.revision_id, page_id="1")
    b = build_g17_plan_wall_scope_shadow(source, revision_id=pub.revision.revision_id, page_id="1")
    assert a == b
    assert a["source_viewport_ownership_id"]
    assert a["source_positive_graph_primitive_count"] > 0
    assert a["host_granted"] is False and a["scope_complete"] is False


@pytest.mark.parametrize("options", [{"second":True}, {"second":True,"second_incomplete":True},
    {"hidden_role":True}, {"no_dimensions":True}])
def test_incomplete_competing_or_hidden_source_plan_cannot_elect_scope(options):
    source, pub = _prepare(**options)
    result = build_g17_plan_wall_scope_shadow(source, revision_id=pub.revision.revision_id, page_id="1")
    assert not result["source_viewport_ownership_id"]
    assert result["default_w2_w3_w4"] is None
    assert not result["host_granted"]


@pytest.mark.parametrize("damage", ["source_bytes", "parent", "receipt", "pixels", "render"])
def test_warmed_source_damage_cannot_reissue_candidate_plan(damage):
    source, pub = _prepare()
    first = build_g17_plan_wall_scope_shadow(source, revision_id=pub.revision.revision_id, page_id="1")
    assert first["source_viewport_ownership_id"]
    oid = pub.raster_opening_primitive_observation_ids[0]
    key = (pub.snapshot.snapshot_id, oid)
    store = source._producer._store
    if damage == "source_bytes":
        store.source_bytes_by_revision[pub.revision.revision_id] = b"changed original"
    elif damage == "parent":
        store.observations.pop((key[0], store.observations[key].derivation_parent_ids[0]))
    elif damage == "receipt":
        source._raster_opening_primitive_receipts.pop(key)
    else:
        fields = {"pixels":{"pixel_geometry":(1.,2.,3.,4.)},
                  "render":{"render_sha256":"foreign"}}[damage]
        source._raster_opening_primitive_receipts[key] = replace(
            source._raster_opening_primitive_receipts[key], **fields)
    with pytest.raises((ValueError, RuntimeError)):
        build_g17_plan_wall_scope_shadow(source, revision_id=pub.revision.revision_id, page_id="1")


@pytest.mark.parametrize("page", ["", "01", "0", "-1", "foreign", 1])
def test_page_address_is_canonical_source_selector(page):
    source, pub = _prepare()
    with pytest.raises(ValueError):
        build_g17_plan_wall_scope_shadow(source, revision_id=pub.revision.revision_id, page_id=page)


def test_foreign_producer_or_revision_is_rejected():
    source, pub = _prepare()
    with pytest.raises(TypeError):
        build_g17_plan_wall_scope_shadow({}, revision_id=pub.revision.revision_id, page_id="1")
    with pytest.raises(ValueError):
        build_g17_plan_wall_scope_shadow(source, revision_id="foreign", page_id="1")


def test_complete_original_paint_rejects_one_missing_or_changed_pixel():
    image = np.full((20,40,3),255,dtype=np.uint8)
    image[6,2:31] = 0
    pixels = (2.,6.,30.,6.)
    assert _paint(image,image.copy(),pixels)["original_solid_and_unchanged"]
    full = image.copy()
    full[6,15] = 30
    assert not _paint(image,full,pixels)["original_solid_and_unchanged"]
    image[6,15] = 255
    assert not _paint(image,image.copy(),pixels)["original_solid_and_unchanged"]
    # A genuine half-cell source centerline must prove BOTH original rows.
    image[6,2:31] = 0
    assert not _paint(image,image.copy(),(2.,6.5,30.,6.5))["original_solid_and_unchanged"]
    image[7,2:31] = 0
    assert _paint(image,image.copy(),(2.,6.5,30.,6.5))["original_solid_and_unchanged"]


def test_source_receipt_changed_during_graph_read_cannot_escape_exit_proof(monkeypatch):
    import pb_g17_plan_wall_scope_shadow as module
    source, pub = _prepare()
    original = module._graph
    def mutate(*args, **kwargs):
        result = original(*args, **kwargs)
        key = (pub.snapshot.snapshot_id,pub.raster_opening_primitive_observation_ids[0])
        source._raster_opening_primitive_receipts[key] = replace(
            source._raster_opening_primitive_receipts[key],render_sha256="changed during read")
        return result
    monkeypatch.setattr(module,"_graph",mutate)
    with pytest.raises(RuntimeError):
        build_g17_plan_wall_scope_shadow(source,revision_id=pub.revision.revision_id,page_id="1")
