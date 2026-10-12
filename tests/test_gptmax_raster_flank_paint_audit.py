"""Paint comparisons retain source uncertainty and never promote a host."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256

import fitz
import numpy as np
import pytest

from pb_source_visibility_authority import SourceVisibilityProducer
from scripts.gptmax_raster_flank_paint_audit import (
    intersecting_paint_commands, original_flank_paint_report,
    original_paint_commands, pixel_paint_profile,
)


def _arrays():
    image = np.full((30, 40, 3), 255, dtype=np.uint8)
    image[10:16, 5:26] = 0
    return image, image.copy(), [5, 10, 25, 15]


def test_dark_overprint_preserves_mass_but_fails_exact_rgb_equality():
    image, full, box = _arrays()
    full[10:16, 12] = (120, 0, 0)
    before = image.copy(), full.copy(), box.copy()
    x = pixel_paint_profile(image, full, box, orientation="horizontal")
    for region in ("inset_core", "complete_centerline"):
        assert x[region]["source_mass_solid"] and x[region]["full_render_mass_solid"]
        assert not x[region]["rgb_equal"]
    assert x["inset_core"]["changed_rgb_pixel_count"] == 4
    assert x["complete_centerline"]["changed_rgb_pixel_count"] == 2
    assert x["changed_rgb_pixel_bbox_inclusive"] == [12, 10, 12, 15]
    assert not x["native_paint_role_authenticated"] and not x["host_publication_allowed"]
    assert np.array_equal(image, before[0]) and np.array_equal(full, before[1]) and box == before[2]
    assert x == pixel_paint_profile(image, full, box, orientation="horizontal")


def test_centerline_only_and_incomplete_endpoints_remain_negative_source_facts():
    image, full, box = _arrays()
    image[11, 9] = full[11, 9] = 255
    x = pixel_paint_profile(image, full, box, orientation="horizontal")
    assert not x["inset_core"]["source_mass_solid"]
    assert x["complete_centerline"]["source_mass_solid"]
    image[12:14, 5] = full[12:14, 5] = 255
    x = pixel_paint_profile(image, full, box, orientation="horizontal")
    assert not x["complete_centerline"]["source_mass_solid"]
    assert x["complete_centerline"]["rgb_equal"]


def test_centerline_endpoint_changes_are_not_hidden_by_inset_core():
    image, full, box = _arrays()
    full[12, 5] = (50, 50, 50)
    x = pixel_paint_profile(image, full, box, orientation="horizontal")
    assert x["inset_core"]["rgb_equal"]
    assert not x["complete_centerline"]["rgb_equal"]


@pytest.mark.parametrize("rotate,scale,pad", [(False, 1, 7), (True, 1, 0), (True, 2, 8), (False, 3, 0)])
def test_source_mass_and_paint_conflict_survive_pixel_transforms(rotate, scale, pad):
    image, full, box = _arrays()
    full[10:16, 12] = (120, 0, 0)
    if rotate:
        image, full = np.rot90(image), np.rot90(full)
        box = [box[1], 39-box[2], box[3], 39-box[0]]
    image, full = (np.repeat(np.repeat(a, scale, 0), scale, 1) for a in (image, full))
    box = [box[0]*scale, box[1]*scale, (box[2]+1)*scale-1, (box[3]+1)*scale-1]
    image, full = (np.pad(a, ((pad, pad), (pad, pad), (0, 0)), constant_values=255) for a in (image, full))
    box = [v+pad for v in box]
    x = pixel_paint_profile(image, full, box, orientation="vertical" if rotate else "horizontal")
    for region in ("inset_core", "complete_centerline"):
        assert x[region]["source_mass_solid"] and x[region]["full_render_mass_solid"]
        assert not x[region]["rgb_equal"]


def test_unrelated_content_and_expanded_page_do_not_change_local_receipt():
    image, full, box = _arrays()
    x = pixel_paint_profile(image, full, box, orientation="horizontal")
    full[0, 0] = 0
    image, full = (np.pad(a, ((0, 20), (0, 30), (0, 0)), constant_values=255) for a in (image, full))
    assert pixel_paint_profile(image, full, box, orientation="horizontal") == x


@pytest.mark.parametrize("box", [[-1, 10, 25, 15], [5, 10, 40, 15], [5, 10, 25, 11],
                                  [5., 10, 25, 15], [False, 10, 25, 15]])
def test_invalid_or_partial_pixel_queries_fail_closed(box):
    image, full, _ = _arrays()
    with pytest.raises(ValueError):
        pixel_paint_profile(image, full, box, orientation="horizontal")


def test_mismatched_or_non_rgb_arrays_fail_closed():
    image, full, box = _arrays()
    for bad in (full[:-1], full.astype(float), full[:, :, 0]):
        with pytest.raises(ValueError):
            pixel_paint_profile(image, bad, box, orientation="horizontal")


def _commands():
    return [{"seqno": i, "original_paint_kind": "stroke-path", "rendered_paint_bounds_pt": b,
             "literal_native_path": {"color": [1., 0., 0.]}}
            for i, b in enumerate(([0., 0., 10., 10.], [4., 4., 12., 12.], [30., 30., 40., 40.]))]


def test_all_competing_paint_bounds_retained_without_first_or_role_choice():
    commands = _commands()
    before = deepcopy(commands)
    x = intersecting_paint_commands(commands, [5., 5., 8., 8.])
    assert [r["seqno"] for r in x] == [0, 1]
    assert all(not r["paint_causality_proven"] and not r["native_paint_role_authenticated"] for r in x)
    assert x == intersecting_paint_commands(commands[::-1], [5., 5., 8., 8.])
    assert commands == before
    x[0]["literal_native_path"]["color"][0] = 99
    assert commands == before


def test_segment_split_retains_each_actual_paint_address_without_causal_election():
    commands = _commands()[:1]
    split = [dict(commands[0], rendered_paint_bounds_pt=[0., 0., 5., 10.]),
             dict(commands[0], seqno=1, rendered_paint_bounds_pt=[5., 0., 10., 10.])]
    query = [4., 4., 6., 6.]
    assert len(intersecting_paint_commands(commands, query)) == 1
    assert len(intersecting_paint_commands(split, query)) == 2
    assert all(not r["paint_causality_proven"] for r in intersecting_paint_commands(split, query))


@pytest.mark.parametrize("defect", ["duplicate", "nonfinite", "string", "overlimit"])
def test_invalid_or_over_limit_original_inventory_fails_closed(defect):
    commands = _commands()
    if defect == "duplicate": commands[1]["seqno"] = 0
    elif defect == "nonfinite": commands[0]["rendered_paint_bounds_pt"][0] = float("nan")
    elif defect == "string": commands[0]["seqno"] = "0"
    else: commands *= 7000
    with pytest.raises(ValueError):
        intersecting_paint_commands(commands, [5., 5., 8., 8.])


def test_original_renderer_bounds_retain_a_zero_width_stroked_path():
    with fitz.open() as pdf:
        page = pdf.new_page(width=100, height=100)
        page.draw_line((50, 10), (50, 90), color=(1, 0, 0), width=2)
        commands = original_paint_commands(page)
        row, = intersecting_paint_commands(commands, [49.5, 40., 49.9, 60.])
        assert row["original_paint_kind"] == "stroke-path"
        assert row["literal_native_path"]["rect"][0] == row["literal_native_path"]["rect"][2] == 50
        assert row["rendered_paint_bounds_pt"][0] < 49.5
        assert not row["paint_causality_proven"]


def _pdf():
    with fitz.open() as pdf:
        page = pdf.new_page(width=100, height=100)
        page.draw_line((50, 10), (50, 90), color=(1, 0, 0), width=2)
        return pdf.tobytes()


def test_fresh_source_replay_has_stable_parent_and_no_quantity_or_source_mutation():
    source = _pdf()
    x = original_flank_paint_report(source, page_id="1", expected_source_sha=sha256(source).hexdigest())
    assert x == original_flank_paint_report(source, page_id="1", expected_source_sha=sha256(source).hexdigest())
    assert x["original_pdf_reauthenticated"]
    assert x["rows"] == [] and x["original_paint_command_count"] == 1
    assert not x["host_publication_allowed"] and not x["metric_quantity_publication_allowed"]
    assert not x["source_universe_completeness_proven"]
    assert x["producer_snapshot_unchanged"]


def test_source_hash_mismatch_rejected_before_source_composition():
    with pytest.raises(ValueError, match="SHA mismatch"):
        original_flank_paint_report(_pdf(), page_id="1", expected_source_sha="foreign")


def test_foreign_full_render_parent_cannot_authenticate_the_comparison(monkeypatch):
    original = SourceVisibilityProducer.render_raster_opening_source_page
    def foreign(self, *args):
        png, parent, frame, dpi = original(self, *args)
        return png, replace(parent, snapshot_id="foreign"), frame, dpi
    monkeypatch.setattr(SourceVisibilityProducer, "render_raster_opening_source_page", foreign)
    source = _pdf()
    with pytest.raises(ValueError, match="frame/parent"):
        original_flank_paint_report(source, page_id="1", expected_source_sha=sha256(source).hexdigest())
