"""Independent source-ink and grid-quantization negatives, never host grants."""
from dataclasses import replace

import numpy as np
import pytest

from pb_g17_dual_dpi_source_correspondence_shadow import (
    _pixel_grid_candidate, _source_144_pixel_profile,
    g17_144_300_source_correspondence_shadow,
)
from pb_opening_local_g17_wall_shadow import build_opening_local_g17_wall_shadow
from tests.test_opening_local_g17_wall_shadow import address
from tests.test_raster_framed_opening_g17_contract import _prepare


def test_one_pixel_lattice_candidate_not_exact_or_nearest_ownership():
    # 0.5 pt is exactly one original 144-DPI pixel, not a fitted tolerance.
    g17 = (0., 0., 10., 0.)
    assert _pixel_grid_candidate(g17, (2., 0.5, 8., 0.5))
    assert _pixel_grid_candidate(g17, (8., 0.5, 2., 0.5))
    assert not _pixel_grid_candidate(g17, (2., 0.75, 8., 0.75))
    assert not _pixel_grid_candidate(g17, (9.6, 0., 10.2, 0.))
    assert not _pixel_grid_candidate(g17, (3., -5., 3., 5.))
    assert not _pixel_grid_candidate(g17, (0., 0., 0., 0.))
    assert not _pixel_grid_candidate(g17, (0., 0., float("nan"), 0.))


def test_original_144_complete_interior_ink_and_changed_overlay_negatives():
    image = np.full((25, 40, 3), 255, dtype=np.uint8)
    # Horizontal y=3.0 pt maps to 144-DPI row 6; 1..10pt maps to col 2..20.
    image[6, 2:21] = (15, 15, 15)
    full = image.copy()
    line = (1., 3., 10., 3.)
    ok = _source_144_pixel_profile(image, full, line)
    assert ok["status"] == "evaluated"
    assert ok["original_144_solid_and_unchanged"]
    assert ok["pixel_sample_count"] > 10
    full[6, 6] = (40, 40, 40)
    changed = _source_144_pixel_profile(image, full, line)
    assert not changed["original_144_solid_and_unchanged"]
    assert changed["unchanged_rgb_sample_count"] < changed["pixel_sample_count"]
    image[6, 7] = (255, 255, 255)
    faint = _source_144_pixel_profile(image, image, line)
    assert not faint["original_144_solid_and_unchanged"]
    assert faint["source_solid_sample_count"] < faint["pixel_sample_count"]
    assert _source_144_pixel_profile(image, full, (0., 0., 0.5, 0.))["status"] != "evaluated"
    assert _source_144_pixel_profile(image, full, (0., 0., 1., 1.))["status"] == "unsupported_geometry_or_render"


def test_original_144_vertical_projection_and_frame_loss_are_negative():
    image = np.full((42, 30, 3), 255, dtype=np.uint8)
    image[3:30, 8] = (0, 0, 0)
    p = _source_144_pixel_profile(image, image.copy(), (4., 1., 4., 15.))
    assert p["status"] == "evaluated" and p["original_144_solid_and_unchanged"]
    assert _source_144_pixel_profile(image, image, (4., 1., 4., 100.))["status"] != "evaluated"


def test_actual_source_producer_g17_can_only_create_nonpublishing_cross_dpi_evidence():
    source, published = _prepare(frame_lines=2)
    selector = address(source, published)
    shadow = build_opening_local_g17_wall_shadow(source, selector)
    before = source.published_snapshot_for_revision(selector.revision_id)
    r = g17_144_300_source_correspondence_shadow(
        source, before, page_id="1", opening_shadows=(shadow,),
        ordinary_w4_records=(),
    )
    assert source.published_snapshot_for_revision(selector.revision_id) == before
    assert len(r["openings"]) == 1
    assert r["original_144_render_dpi"] == 144
    assert r["original_g17_render_dpi"] == 300
    assert r["original_w4_candidates_examined"] == 0
    assert len(r["openings"][0]["flanks"]) == 2
    assert all(len(x["source_edges"]) == 3 for x in r["openings"][0]["flanks"])
    assert not any(r[x] for x in (
        "physical_wall_role_granted", "cross_source_equivalence_granted",
        "host_granted", "metric_quantity_granted", "complete_wall_universe_proven",
    ))
    assert not r["openings"][0]["host_granted"]


def test_foreign_source_claims_fail_without_ordinary_w4_fallback():
    source, published = _prepare(frame_lines=2)
    selector = address(source, published)
    shadow = build_opening_local_g17_wall_shadow(source, selector)
    with pytest.raises(TypeError):
        g17_144_300_source_correspondence_shadow(
            {}, published, page_id="1", opening_shadows=(shadow,),
            ordinary_w4_records=())
    wrong = replace(shadow, physical_opening_id="wrong", source_selector=replace(selector, source_sha256="foreign"))
    with pytest.raises(ValueError):
        g17_144_300_source_correspondence_shadow(
            source, published, page_id="1", opening_shadows=(wrong,),
            ordinary_w4_records=())
    with pytest.raises(ValueError):
        g17_144_300_source_correspondence_shadow(
            source, published, page_id="forged", opening_shadows=(shadow,),
            ordinary_w4_records=())
