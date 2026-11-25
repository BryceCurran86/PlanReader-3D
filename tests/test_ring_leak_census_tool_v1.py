"""P4a: the read-only ring-leak census tool (spies on both ring builders, a replay of the canonical preview, and the command line).

Synthetic only; no private source. The tool replays a real builder under throwaway spies, rebuilds what the builder did from what the spies
saw, and asks ``pb_ring_leak_census.census_report`` for the counts-only census. Two replication checks (the unresolved collinear count and the
ring count recomputed from the captured barrier must equal the builder's own) guard every ring figure. The tool changes no ring, closure, gate
or builder: the builders' results, the preview's summary and its PNG are identical with and without it, and every spy is removed afterwards.
"""
from __future__ import annotations

import copy
import hashlib
import json
import random
import sys
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest
from shapely.geometry import Polygon, box

import pb_layered_wall_doorway_room_ring_shadow as layered
import pb_new_source_trace_preview as canonical
import pb_next_wall_ring_preview as preview
import pb_ring_leak_census as census
from tools import diag_ring_leak_census as tool

SHA = "ab" * 32
BLACK = (0.0, 0.0, 0.0)
REPO_ROOT = Path(__file__).resolve().parents[1]
BUILDERS = ("layered", "preview")


# ------------------------------------------------------------------------------------------------ scenes (filled wall rows)

def _wall(x0, y0, x1, y1, layer="A-WALL"):
    return {"layer": layer, "fill": BLACK, "color": None, "items": [("re", fitz.Rect(x0, y0, x1, y1))]}


def _stroke(a, b, width=0.5):
    return {"layer": "", "fill": None, "color": BLACK, "width": width, "items": [("l", fitz.Point(*a), fitz.Point(*b))]}


def _arc_rows(hinge, radius):
    """A native quarter-circle door swing about ``hinge``: the closed leaf runs from the hinge along -y, the open leaf along +x."""
    hx, hy = hinge
    k = 0.5522847498 * radius
    p1, p4 = fitz.Point(hx, hy - radius), fitz.Point(hx + radius, hy)
    p2, p3 = fitz.Point(hx + k, hy - radius), fitz.Point(hx + radius, hy - k)
    return [
        {"layer": "", "fill": None, "color": BLACK, "width": 0.5, "items": [("c", p1, p2, p3, p4)]},
        {"layer": "", "fill": None, "color": BLACK, "width": 0.5, "items": [("l", fitz.Point(hx, hy), p4)]},
    ]


def _room(gap=(150.0, 180.0), *, x0=100.0, y0=100.0, w=200.0, h=140.0, t=6.0, twin=False, arc=False, extra=(), right_gap=True):
    """A closed 200 x 140 room of 6 pt filled walls whose right wall is cut by a doorway (a gap along y), plus optional twin bands over the
    same doorway (one aperture, two raw gaps), a native door swing and extra rows."""
    x1, y1 = x0 + w, y0 + h
    rows = [_wall(x0, y0, x1, y0 + t), _wall(x0, y1 - t, x1, y1), _wall(x0, y0, x0 + t, y1)]
    bands = [(x1 - t, x1)] + ([(x1 - t + 1.5, x1 - 1.5)] if twin else [])
    for b0, b1 in bands:
        if right_gap:
            rows.append(_wall(b0, y0, b1, gap[0]))
            rows.append(_wall(b0, gap[1], b1, y1))
        else:
            rows.append(_wall(b0, y0, b1, y1))
    if arc:
        rows.extend(_arc_rows((x1 - t / 2, gap[1]), gap[1] - gap[0]))
    rows.extend(extra)
    return rows


TICKS = [_stroke((294.0, 160.0), (300.0, 160.0)), _stroke((294.0, 170.0), (300.0, 170.0))]
STUB = [_wall(180.0, 106.0, 186.0, 200.0)]
CELL = [_wall(150, 150, 171, 156), _wall(150, 165, 171, 171), _wall(150, 150, 156, 171), _wall(165, 150, 171, 171)]     # a 9 x 9 enclosed cell


def _capture(builder, rows, **kw):
    if builder == "layered":
        return tool.capture_layered_builder(rows, source_sha256=SHA, page_index=0, **kw)
    return tool.capture_preview_builder_rows(rows, source_sha256=SHA, page_index=0, **kw)


def _report(builder, rows, **kw):
    capture, result = _capture(builder, rows)
    assert capture is not None
    return census.census_report(capture, **kw), result


# ------------------------------------------------------------------------------------------------ spies

SPY_NAMES = {
    "layered": ("_collect_strips", "_gaps", "_swing_arcs", "_place_swings", "_closed_union", "_lining_face_wall_strips", "_source_unresolved_gap_witnesses"),
    "preview": ("_collect_strips", "_gaps", "_swing_arcs", "_place_swings", "_closed_union"),
}
MODULES = {"layered": (layered, census.BUILDER_LAYERED), "preview": (preview, census.BUILDER_PREVIEW_FORK)}


@pytest.mark.parametrize("builder", BUILDERS)
def test_spies_install_and_every_original_is_restored_even_when_the_builder_raises(builder):
    module, family = MODULES[builder]
    originals = {name: getattr(module, name) for name in SPY_NAMES[builder]}
    with tool.BuilderSpies(family):
        for name, original in originals.items():
            assert getattr(module, name) is not original, name
    assert all(getattr(module, name) is original for name, original in originals.items())
    with pytest.raises(RuntimeError, match="boom"):
        with tool.BuilderSpies(family):
            raise RuntimeError("boom")
    assert all(getattr(module, name) is original for name, original in originals.items())
    assert not tool._ACTIVE_FAMILIES


@pytest.mark.parametrize("builder", BUILDERS)
def test_a_second_spy_on_the_same_module_is_refused_and_the_first_still_restores(builder):
    module, family = MODULES[builder]
    originals = {name: getattr(module, name) for name in SPY_NAMES[builder]}
    with tool.BuilderSpies(family):
        with pytest.raises(tool.CensusContractError, match="already installed"):
            with tool.BuilderSpies(family):
                pass
    assert all(getattr(module, name) is original for name, original in originals.items()) and not tool._ACTIVE_FAMILIES


def test_both_families_can_be_spied_at_once_because_they_are_different_modules():
    with tool.BuilderSpies(census.BUILDER_LAYERED), tool.BuilderSpies(census.BUILDER_PREVIEW_FORK):
        assert tool._ACTIVE_FAMILIES == {census.BUILDER_LAYERED, census.BUILDER_PREVIEW_FORK}
    assert not tool._ACTIVE_FAMILIES


def test_an_unknown_family_is_refused():
    with pytest.raises(ValueError):
        tool.BuilderSpies("neither")


@pytest.mark.parametrize("builder", BUILDERS)
def test_spies_record_only_while_building(builder):
    module, family = MODULES[builder]
    with tool.BuilderSpies(family) as spies:
        module._collect_strips([])
        module._closed_union([])
        assert "rows" not in spies.state and spies.state["union_calls"] == []
        with spies.building():
            module._collect_strips([])
            module._closed_union([])
        assert spies.state["rows"] == [] and len(spies.state["union_calls"]) == 1
    module._collect_strips([])                                           # the restored original still works


@pytest.mark.parametrize("builder,name", [
    ("layered", "_place_swings"), ("preview", "_place_swings"), ("layered", "_gaps"), ("preview", "_closed_union"), ("layered", "_swing_arcs"),
    ("layered", "_lining_face_wall_strips"), ("layered", "_source_unresolved_gap_witnesses"),
])
def test_a_spied_function_that_changes_its_leading_parameters_is_refused_loudly(builder, name, monkeypatch):
    module, family = MODULES[builder]
    original = getattr(module, name)

    def drifted(first_renamed, *args, **kwargs):
        return original(first_renamed, *args, **kwargs)

    monkeypatch.setattr(module, name, drifted)
    with pytest.raises(tool.CensusContractError, match=name):
        tool.BuilderSpies(family).__enter__()
    assert getattr(module, name) is drifted and not tool._ACTIVE_FAMILIES    # nothing was installed


@pytest.mark.parametrize("builder,name", [("preview", "_gaps"), ("layered", "_lining_face_wall_strips"), ("layered", "_polygon_parts"), ("preview", "NOISE_PT")])
def test_a_missing_function_or_constant_is_refused_loudly(builder, name, monkeypatch):
    module, family = MODULES[builder]
    monkeypatch.delattr(module, name)
    with pytest.raises(tool.CensusContractError, match=name):
        tool.BuilderSpies(family).__enter__()
    assert not tool._ACTIVE_FAMILIES


def test_the_preview_family_does_not_need_the_layered_only_functions(monkeypatch):
    assert not hasattr(preview, "_lining_face_wall_strips") and not hasattr(preview, "_source_unresolved_gap_witnesses")
    tool.check_spy_contract(census.BUILDER_PREVIEW_FORK)
    tool.check_spy_contract(census.BUILDER_LAYERED)


def test_the_open_gap_reason_and_the_veto_exist_in_both_builders():
    assert census.REASON_OPEN_GAP == layered.REASON_OPEN_GAP == preview.REASON_OPEN_GAP
    assert tool._touch_function(layered) is layered._unresolved_collinear_gap_breaches_outer_ring
    assert tool._touch_function(preview) is preview._original_two_end_gap_veto


@pytest.mark.parametrize("module", [layered, preview])
@pytest.mark.parametrize("length,closes", [(9.9, False), (10.0, True), (75.0, True), (140.0, True), (140.1, False)])
def test_the_bucket_edges_are_the_builders_face_identity_band(module, length, closes):
    """``_stroke_closed`` accepts a stroke 0.3 pt short of both ends only on an opening-sized gap (10 to 140 pt), and the census buckets are
    exactly that band."""
    lo = 150.0
    gap = module._Gap(False, (294.0, 300.0), lo, lo + length, (), (), True)
    rows = [_stroke((294.0, lo + 0.3), (294.0, lo + length - 0.3))]
    assert (module._stroke_closed(rows, gap, all_ink=True) is not None) is closes
    assert (census.length_bucket(length) == census.BUCKET_OPENING) is closes


# ------------------------------------------------------------------------------------------------ the capture on real builders

@pytest.mark.parametrize("builder", BUILDERS)
def test_a_closed_room_has_one_ring_and_no_unclosed_gap(builder):
    report, result = _report(builder, _room(right_gap=False))
    assert report["replication"]["exact"] is True and report["counts"]["rings"] == 1 and report["counts"]["raw_gaps"] == 0
    assert report["unclosed_gaps"]["count"] == 0 and report["unblocking_power"]["single_closure"]["gaps_adding_a_ring"] == 0
    assert len(result.rings) == 1


@pytest.mark.parametrize("builder", BUILDERS)
def test_an_empty_doorway_leaks_and_one_closure_would_add_the_room_as_a_ring(builder):
    report, result = _report(builder, _room())
    assert report["replication"]["exact"] is True and report["counts"]["rings"] == 0 and len(result.rings) == 0
    assert report["unclosed_gaps"]["by_orientation_and_class"] == {"collinear|empty": 1}
    assert report["unclosed_gaps"]["unresolved_collinear_by_bucket"] == {"10to140": 1} and report["unclosed_gaps"]["touching_no_ring"] == 1
    unblock = report["unblocking_power"]
    assert unblock["rings_now"] == 0 and unblock["if_all_unresolved_collinear_closed"] == 1
    assert unblock["single_closure"]["gaps_adding_a_ring"] == 1 and unblock["single_closure"]["adding_with_door_evidence"] == 0
    assert report["apertures"]["ring_adding_gaps"] == 1 and report["apertures"]["groups"] == 1


@pytest.mark.parametrize("builder", BUILDERS)
def test_strokes_across_the_doorway_are_perpendicular_strokes_and_still_do_not_close_it(builder):
    report, _ = _report(builder, _room(extra=TICKS))
    assert report["unclosed_gaps"]["by_orientation_and_class"] == {"collinear|perpendicular_strokes": 1} and report["counts"]["rings"] == 0
    assert report["replication"]["exact"] is True


@pytest.mark.parametrize("builder", BUILDERS)
def test_a_stub_that_stops_short_of_a_wall_is_a_non_collinear_leak_the_builder_never_reports(builder):
    report, result = _report(builder, _room(right_gap=False, extra=STUB))
    assert result.unresolved_gap_count == 0                                   # the builder's own count says nothing is wrong
    assert report["counts"]["raw_gaps_non_collinear"] == 1 and report["unclosed_gaps"]["non_collinear"] == 1 and report["unclosed_gaps"]["collinear"] == 0
    assert report["unclosed_gaps"]["by_orientation_and_class"] == {"non_collinear|empty": 1}
    assert report["counts"]["rings"] == 1 and report["unblocking_power"]["single_closure"]["gaps_adding_a_ring"] == 1       # closing it splits the room in two
    assert report["unblocking_power"]["single_closure"]["adding_by_orientation_and_class"] == {"non_collinear|empty": 1}
    assert report["replication"]["exact"] is True


@pytest.mark.parametrize("builder", BUILDERS)
def test_a_seam_under_the_opening_floor_is_bucketed_short(builder):
    report, _ = _report(builder, _room(gap=(150.0, 156.0)))
    assert report["unclosed_gaps"]["unresolved_collinear_by_bucket"] == {"lt10": 1} and report["unblocking_power"]["single_closure"]["adding_by_bucket"] == {"lt10": 1}


@pytest.mark.parametrize("builder", BUILDERS)
def test_one_aperture_drawn_as_twin_bands_is_two_raw_gaps_and_one_group(builder):
    report, _ = _report(builder, _room(twin=True))
    apertures = report["apertures"]
    assert apertures["raw_gaps"] == 2 and apertures["groups"] == 1 and apertures["groups_with_two_or_more_gaps"] == 1 and apertures["gaps_in_such_groups"] == 2
    assert apertures["largest_group"] == 2 and apertures["ring_adding_gaps"] == 2 and apertures["ring_adding_distinct_groups"] == 1
    assert apertures["ring_adding_gaps_in_multi_gap_groups"] == 2 and report["unclosed_gaps"]["by_orientation_and_class"] == {"collinear|empty": 2}


@pytest.mark.parametrize("builder", BUILDERS)
def test_a_native_door_swing_over_twin_gaps_is_ambiguous_and_the_census_says_why(builder):
    report, result = _report(builder, _room(twin=True, arc=True))
    assert result.ambiguous_swing_count == 1 and report["counts"]["closed"] == 0
    assert report["unclosed_gaps"]["by_orientation_and_class"] == {"collinear|native_arc_swing_not_placed": 2}
    arcs = report["native_arcs"]
    assert arcs["found"] == 1 and arcs["builder_ambiguous"] == 1 and arcs["builder_unplaced"] == 0 and arcs["rejected_by_finder"] == 0
    assert arcs["per_arc_candidate_gaps"] == {"several_candidate_gaps": 1} and arcs["several_candidate_shape"] == {"all_pairs_overlap_one_aperture": 1}
    assert arcs["several_candidate_kinds"] == {"collinear+collinear": 1}
    assert report["unblocking_power"]["single_closure"]["adding_with_door_evidence"] == 2


@pytest.mark.parametrize("builder", BUILDERS)
def test_a_native_door_swing_over_one_gap_is_placed_and_closes_it(builder):
    report, result = _report(builder, _room(arc=True))
    assert report["counts"]["closed"] == 1 and report["unclosed_gaps"]["count"] == 0 and report["counts"]["rings"] == 1
    assert report["native_arcs"]["per_arc_candidate_gaps"] == {"one_candidate_gap": 1} and report["native_arcs"]["builder_unplaced"] == 0


@pytest.mark.parametrize("builder", BUILDERS)
def test_the_ring_rule_of_each_builder_is_the_one_the_census_models(builder):
    """A 9 x 9 enclosed cell is a ring under the preview's half-thickness inset and a cavity sliver under the layered builder's full inset
    and six-thickness extent test; the replication check holds for both because the census models each rule."""
    report, result = _report(builder, _room(right_gap=False, extra=CELL))
    assert report["replication"]["exact"] is True and report["replication"]["rings"]["recomputed"] == len(result.rings)
    assert len(result.rings) == (1 if builder == "layered" else 2)


@pytest.mark.parametrize("builder", BUILDERS)
def test_the_census_figures_equal_the_builders_own_result_fields(builder):
    for rows in (_room(), _room(right_gap=False, extra=STUB), _room(twin=True, arc=True), _room(arc=True), _room(right_gap=False)):
        report, result = _report(builder, rows)
        counts = report["counts"]
        assert counts["strips"] == result.wall_strip_count and counts["raw_gaps_builder"] == result.wall_gap_count == counts["raw_gaps"]
        assert counts["closed"] == len(result.closures) and counts["rings"] == len(result.rings)
        assert report["replication"]["unresolved_collinear"]["builder"] == result.unresolved_gap_count
        assert counts["rings_by_status_and_reason"] == dict(sorted(
            {f"{r.status.value}|{'+'.join(r.reason_codes)}": sum(1 for q in result.rings if (q.status, q.reason_codes) == (r.status, r.reason_codes)) for r in result.rings}.items()))
        assert report["builder_status"] == result.status.value and report["builder_reason_codes"] == list(result.reason_codes)


def _ring_ids(result):
    return [r.record_id for r in result.rings], [c.closure_id for c in result.closures], result.status, result.reason_codes


@pytest.mark.parametrize("builder", BUILDERS)
def test_the_spies_change_nothing_the_builder_returns(builder):
    for rows in (_room(), _room(right_gap=False, extra=STUB), _room(twin=True, arc=True)):
        clean = (layered.build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0, dark_painted_wall_source=True) if builder == "layered"
                 else preview.build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0, **tool.CANONICAL_PREVIEW_FLAGS))
        _, spied = _capture(builder, rows)
        assert _ring_ids(spied) == _ring_ids(clean)
        for field in ("wall_strip_count", "wall_gap_count", "unresolved_gap_count", "unplaced_swing_count", "ambiguous_swing_count", "sliver_region_count"):
            assert getattr(spied, field) == getattr(clean, field), field


@pytest.mark.parametrize("builder", BUILDERS)
def test_the_builders_never_mutate_the_rows_and_neither_does_the_census(builder):
    rows = _room(twin=True, arc=True, extra=TICKS)
    before = copy.deepcopy(rows)
    report, _ = _report(builder, rows, per_gap=True)
    assert rows == before and report["replication"]["exact"] is True


@pytest.mark.parametrize("builder", BUILDERS)
def test_a_page_with_no_wall_ink_returns_no_capture_and_the_builders_own_reason(builder):
    capture, result = _capture(builder, [_stroke((10.0, 10.0), (200.0, 10.0))])
    assert capture is None and result.status.value == "abstained"
    capture, result = _capture(builder, [])
    assert capture is None


def test_a_page_over_the_structural_cap_returns_no_capture_and_the_builders_own_reason(monkeypatch):
    monkeypatch.setattr(layered, "structural_native_primitive_count", lambda rows: 20_001)
    capture, result = tool.capture_layered_builder(_room(), source_sha256=SHA, page_index=0)
    assert capture is None and result.status.value == "abstained" and result.reason_codes == (layered.REASON_UNLABELLED_SOURCE_PRIMITIVE_CAP,)
    assert not tool._ACTIVE_FAMILIES


# ------------------------------------------------------------------------------------------------ invariances

def _moved(rows, *, dx=0.0, dy=0.0, scale=1.0, swap=False):
    def pt(p):
        x, y = p.x * scale + dx, p.y * scale + dy
        return fitz.Point(y, x) if swap else fitz.Point(x, y)

    out = []
    for row in rows:
        items = []
        for item in row["items"]:
            if item[0] == "re":
                r = item[1]
                a, b = pt(fitz.Point(r.x0, r.y0)), pt(fitz.Point(r.x1, r.y1))
                items.append(("re", fitz.Rect(min(a.x, b.x), min(a.y, b.y), max(a.x, b.x), max(a.y, b.y))))
            else:
                items.append((item[0], *[pt(p) for p in item[1:]]))
        out.append({**row, "items": items})
    return out


def _signature(report):
    u = report["unblocking_power"]
    return (
        report["counts"]["strips"], report["counts"]["raw_gaps"], report["counts"]["closed"], report["counts"]["rings"],
        report["unclosed_gaps"]["by_class"], report["unclosed_gaps"]["unresolved_collinear_by_bucket"],
        u["if_all_unresolved_collinear_closed"], u["single_closure"]["gaps_adding_a_ring"], report["apertures"]["groups"],
    )


@pytest.mark.parametrize("builder", BUILDERS)
@pytest.mark.parametrize("scene", ["empty", "ticks", "stub", "twin"])
@pytest.mark.parametrize("transform", [{"dx": 37.5, "dy": -21.25}, {"swap": True}, {"scale": 1.5}, {"dx": -40.0, "dy": 60.0, "swap": True}])
def test_the_census_survives_translation_axis_swap_and_scale(builder, scene, transform):
    rows = {"empty": _room(), "ticks": _room(extra=TICKS), "stub": _room(right_gap=False, extra=STUB), "twin": _room(twin=True)}[scene]
    base, _ = _report(builder, rows)
    moved, _ = _report(builder, _moved(rows, **transform))
    assert moved["replication"]["exact"] is True and _signature(moved) == _signature(base)


@pytest.mark.parametrize("builder", BUILDERS)
def test_row_order_does_not_change_the_counts(builder):
    rows = _room(twin=True, arc=True, extra=TICKS)
    base, _ = _report(builder, rows)
    for seed in range(4):
        shuffled = rows[:]
        random.Random(seed).shuffle(shuffled)
        again, _ = _report(builder, shuffled)
        assert again["replication"]["exact"] is True and _signature(again) == _signature(base)


@pytest.mark.parametrize("builder", BUILDERS)
def test_unrelated_content_far_from_the_doorway_leaves_its_census_alone(builder):
    base, _ = _report(builder, _room())
    far = [_stroke((900.0, 900.0), (900.0, 960.0)), _stroke((905.0, 905.0), (960.0, 905.0))]
    more, _ = _report(builder, _room(extra=far))
    assert more["replication"]["exact"] is True and more["unclosed_gaps"] == base["unclosed_gaps"] and more["counts"]["rings"] == base["counts"]["rings"]
    second_room = _room() + _room(right_gap=False, x0=500.0, y0=400.0)                     # offset on both axes: no wall band lines up with the first room's
    both, _ = _report(builder, second_room)
    assert both["replication"]["exact"] is True and both["unclosed_gaps"]["by_orientation_and_class"] == {"collinear|empty": 1}
    assert both["counts"]["rings"] == base["counts"]["rings"] + 1


@pytest.mark.parametrize("builder", BUILDERS)
def test_the_report_replays_exactly_and_is_plain_json(builder):
    capture, _ = _capture(builder, _room(twin=True, arc=True))
    first, second = census.census_report(capture, per_gap=True), census.census_report(capture, per_gap=True)
    assert first == second and json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert json.loads(json.dumps(first)) == first


# ------------------------------------------------------------------------------------------------ the replication guard

def test_a_wrong_ring_model_fails_the_replication_check_and_withholds_the_ring_figures(monkeypatch):
    monkeypatch.setitem(tool._FAMILIES[census.BUILDER_LAYERED], "ring_rule", census.RingRule(sliver_inset_factor=0.05, min_extent_factor=None))
    capture, result = tool.capture_layered_builder(_room(right_gap=False, extra=CELL), source_sha256=SHA, page_index=0)
    report = census.census_report(capture)
    assert len(result.rings) == 1 and report["replication"]["rings"] == {"recomputed": 2, "builder": 1, "match": False} and report["replication"]["exact"] is False
    assert report["unblocking_power"] is None and report["unblocking_power_withheld"] == "ring_count_replication_not_exact"
    assert report["unclosed_gaps"]["count"] == 8                               # classification does not depend on the ring model


# ------------------------------------------------------------------------------------------------ the canonical preview path

def _all_keys(value):
    if isinstance(value, dict):
        for key, inner in value.items():
            yield str(key)
            yield from _all_keys(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from _all_keys(inner)


def _write_pdf(path, rows_or_segments):
    document = fitz.open()
    page = document.new_page(width=800, height=400)
    for a, b in rows_or_segments:
        shape = page.new_shape()
        shape.draw_line(fitz.Point(*a), fitz.Point(*b))
        shape.finish(color=BLACK, width=0.5, closePath=False)
        shape.commit()
    document.save(str(path))
    document.close()
    return path


def _stroke_room(gap=(150.0, 180.0), *, x0=100.0, y0=100.0, w=200.0, h=140.0, t=6.0):
    x1, y1 = x0 + w, y0 + h
    segments = [((x0, y), (x1, y)) for y in (y0, y0 + t, y1 - t, y1)] + [((x, y0), (x, y1)) for x in (x0, x0 + t)]
    for x in (x1 - t, x1):
        segments += [((x, y0), (x, gap[0])), ((x, gap[1]), (x, y1))]
    return segments


@pytest.fixture(scope="module")
def room_pdf(tmp_path_factory):
    return _write_pdf(tmp_path_factory.mktemp("p4a") / "room.pdf", _stroke_room())


def _digest(summary):
    return hashlib.sha256(json.dumps(summary, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def test_the_preview_capture_reproduces_the_previews_own_builder_run(room_pdf):
    capture, summary, entry_rows = tool.capture_preview_builder(room_pdf, 0)
    assert capture is not None and entry_rows is not None
    report = census.census_report(capture)
    assert report["replication"]["exact"] is True and report["counts"]["strips"] == summary["wall_strip_count"]
    assert report["counts"]["raw_gaps"] == summary["wall_gap_count"] and report["replication"]["unresolved_collinear"]["builder"] == summary["unresolved_wall_gap_count"]
    assert report["unclosed_gaps"]["by_orientation_and_class"] == {"collinear|empty": 1} and report["unblocking_power"]["single_closure"]["gaps_adding_a_ring"] == 1
    assert not tool._ACTIVE_FAMILIES


def test_the_preview_summary_and_png_are_byte_identical_with_and_without_the_census(room_pdf):
    clean_summary, clean_png = canonical.source_native_trace_preview(room_pdf, 0)
    _, spied_summary, _ = tool.capture_preview_builder(room_pdf, 0)
    after_summary, after_png = canonical.source_native_trace_preview(room_pdf, 0)
    assert _digest(spied_summary) == _digest(clean_summary) == _digest(after_summary) and after_png == clean_png


def test_the_mirrored_canonical_flags_are_the_ones_the_preview_really_passes(room_pdf, monkeypatch):
    seen = []
    real = canonical.build_layered_wall_doorway_room_rings

    def recorder(*args, **kwargs):
        seen.append(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(canonical, "build_layered_wall_doorway_room_rings", recorder)
    canonical.source_native_trace_preview(room_pdf, 0)
    assert seen and all(seen[0][name] is value for name, value in tool.CANONICAL_PREVIEW_FLAGS.items())


def test_run_census_covers_both_builders_and_the_two_row_sources_agree_on_a_plain_page(room_pdf):
    both = tool.run_census(room_pdf, 0, per_gap=True)
    assert set(both["builders"]) == {"preview_fork", "layered"} and both["page_index"] == 0 and len(both["source_sha256_prefix"]) == 16
    for name, block in both["builders"].items():
        assert block["census_available"] is True and block["replication"]["exact"] is True and block["unclosed_gaps"]["count"] == 1, name
        assert len(block["gap_records"]) == 1
    assert both["builders"]["preview_fork"]["source_modality_route"] == "native_vector"
    scoped = tool.run_census(room_pdf, 0, layered_rows="preview-scoped")
    assert scoped["builders"]["layered"]["counts"] == both["builders"]["layered"]["counts"]
    assert "raw get_drawings" in both["builders"]["layered"]["rows_source"] and "canonical preview" in scoped["builders"]["layered"]["rows_source"]
    only = tool.run_census(room_pdf, 0, builders=("layered",))
    assert set(only["builders"]) == {"layered"} and "gap_records" not in only["builders"]["layered"]


def test_run_census_validates_its_arguments(room_pdf):
    for kwargs in ({"builders": ()}, {"builders": ("other",)}, {"layered_rows": "everything"}, {"builders": ("layered",), "layered_rows": "preview-scoped"}):
        with pytest.raises(ValueError):
            tool.run_census(room_pdf, 0, **kwargs)
    for index in (-1, 1, 99):
        with pytest.raises(ValueError):
            tool.run_census(room_pdf, index)


def test_a_raster_underlay_page_skips_the_layered_builder_when_it_would_read_the_previews_rows(room_pdf, monkeypatch):
    real = tool.capture_preview_builder

    def raster(pdf, index):
        capture, summary, rows = real(pdf, index)
        return capture, {**summary, "source_modality": {"route": tool.RASTER_ROUTE}}, rows

    monkeypatch.setattr(tool, "capture_preview_builder", raster)
    page = tool.run_census(room_pdf, 0, layered_rows="preview-scoped")
    assert page["builders"]["layered"] == {"census_available": False, "skipped": "raster_underlay_page_native_vectors_are_not_architectural"}
    assert page["builders"]["preview_fork"]["source_modality_route"] == tool.RASTER_ROUTE
    assert tool.run_census(room_pdf, 0)["builders"]["layered"]["census_available"] is True        # raw rows: the room-face scope reads them regardless


def test_a_builder_that_stops_before_its_closure_loop_is_reported_with_its_own_status(tmp_path):
    path = _write_pdf(tmp_path / "blank.pdf", [((10.0, 10.0), (200.0, 10.0))])
    page = tool.run_census(path, 0, builders=("layered",))
    block = page["builders"]["layered"]
    assert block["census_available"] is False and block["builder_status"] == "abstained" and block["builder_reason_codes"]


def test_the_report_assembly_lists_every_page_and_every_replication_failure(room_pdf, monkeypatch):
    report = tool.build_report(room_pdf, [0], builders=("preview", "layered"))
    assert report["schema_version"] == census.SCHEMA_VERSION and report["tool"] == "tools/diag_ring_leak_census.py" and report["replication_failures"] == []
    assert [p["page_index"] for p in report["pages"]] == [0] and report["note"] == tool.NOTE
    monkeypatch.setitem(tool._FAMILIES[census.BUILDER_LAYERED], "ring_rule", census.RingRule(0.05, None))
    broken = tool.build_report(room_pdf, [0], builders=("layered",))
    assert broken["replication_failures"] in ([], [{"page_index": 0, "builder": "layered"}])


# ------------------------------------------------------------------------------------------------ the command line

def test_the_command_line_writes_a_counts_only_report_outside_the_repository(room_pdf, tmp_path, capsys):
    out = tmp_path / "census.json"
    assert tool.main(["--pdf", str(room_pdf), "--page-index", "0", "--json-out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "page 0 preview_fork:" in printed and "page 0 layered:" in printed and "replication exact" in printed and "{" not in printed
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["pages"][0]["builders"]["layered"]["replication"]["exact"] is True and report["replication_failures"] == []
    text = out.read_text(encoding="utf-8")
    keys = [key.lower() for key in _all_keys(report)]
    for key_part in ("bbox", "polygon", "coord", "pdf_pts", "words", "text", "name", "path"):
        assert not any(key_part in key for key in keys), key_part
    for coordinate in ("294.0", "300.0", "150.0", "180.0", "240.0", "106.0"):         # the scene's own coordinates never appear as values
        assert f": {coordinate}" not in text and f"[{coordinate}" not in text, coordinate


def test_the_command_line_refuses_to_write_inside_the_repository(room_pdf):
    inside = REPO_ROOT / "no_such_directory_for_the_census" / "census.json"          # if the guard failed, writing here would raise, never leave a file
    with pytest.raises(SystemExit) as caught:
        tool.main(["--pdf", str(room_pdf), "--page-index", "0", "--json-out", str(inside)])
    assert caught.value.code == 2 and not inside.parent.exists()
    assert tool._inside_repository(REPO_ROOT / "a" / "b.json") and tool._inside_repository(REPO_ROOT) and not tool._inside_repository(Path(sys.executable))


def test_the_command_line_prints_the_json_when_no_output_file_is_given(room_pdf, capsys):
    assert tool.main(["--pdf", str(room_pdf), "--page-index", "0", "--builder", "layered", "--per-gap"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert list(report["pages"][0]["builders"]) == ["layered"] and "gap_records" in report["pages"][0]["builders"]["layered"]


def test_the_command_line_exits_non_zero_when_a_replication_check_fails_unless_told_not_to(room_pdf, monkeypatch, capsys):
    monkeypatch.setitem(tool._FAMILIES[census.BUILDER_PREVIEW_FORK], "ring_rule", census.RingRule(0.05, None))
    real = tool.capture_preview_builder_rows
    del real
    original_census = census.census_report

    def inexact(capture, **kwargs):
        report = original_census(capture, **kwargs)
        report["replication"]["exact"] = False
        report["replication"]["rings"] = {"recomputed": 9, "builder": 0, "match": False}
        return report

    monkeypatch.setattr(census, "census_report", inexact)
    assert tool.main(["--pdf", str(room_pdf), "--page-index", "0", "--builder", "layered"]) == 2
    assert "replication check failed" in capsys.readouterr().out
    assert tool.main(["--pdf", str(room_pdf), "--page-index", "0", "--builder", "layered", "--allow-inexact"]) == 0


def test_the_layered_flags_and_row_source_reach_the_builders(room_pdf, tmp_path, monkeypatch):
    seen = []
    real = tool.capture_layered_builder

    def recorder(rows, **kwargs):
        seen.append(kwargs)
        return real(rows, **kwargs)

    monkeypatch.setattr(tool, "capture_layered_builder", recorder)
    out = tmp_path / "flags.json"
    assert tool.main(["--pdf", str(room_pdf), "--page-index", "0", "--builder", "layered", "--layered-sliding-leaf", "--layered-wall-end-strokes", "--json-out", str(out)]) == 0
    assert seen[-1]["sliding_leaf_frame_closure"] is True and seen[-1]["wall_end_stroke_closures"] is True and seen[-1]["page_index"] == 0
    assert json.loads(out.read_text(encoding="utf-8"))["pages"][0]["builders"]["layered"]["flags"] == {
        "dark_painted_wall_source": True, "sliding_leaf_frame_closure": True, "wall_end_stroke_closures": True}
    assert tool.main(["--pdf", str(room_pdf), "--page-index", "0", "--builder", "layered", "--json-out", str(out)]) == 0
    assert seen[-1]["sliding_leaf_frame_closure"] is False and seen[-1]["wall_end_stroke_closures"] is False
    assert tool.main(["--pdf", str(room_pdf), "--page-index", "0", "--layered-rows", "preview-scoped", "--json-out", str(out)]) == 0
    assert "canonical preview" in json.loads(out.read_text(encoding="utf-8"))["pages"][0]["builders"]["layered"]["rows_source"]


def test_no_unblocking_skips_the_ring_recomputations_without_calling_them_withheld(room_pdf, tmp_path):
    out = tmp_path / "fast.json"
    assert tool.main(["--pdf", str(room_pdf), "--page-index", "0", "--no-unblocking", "--json-out", str(out)]) == 0
    for block in json.loads(out.read_text(encoding="utf-8"))["pages"][0]["builders"].values():
        assert block["unblocking_power"] is None and block["unblocking_power_withheld"] is None and block["replication"]["exact"] is True


def test_the_command_line_needs_a_page_and_rejects_a_bad_one(room_pdf):
    with pytest.raises(SystemExit):
        tool.main(["--pdf", str(room_pdf)])
    with pytest.raises(SystemExit) as caught:
        tool.main(["--pdf", str(room_pdf), "--page-index", "7"])
    assert caught.value.code == 2


def test_the_summary_lines_name_the_page_the_builder_and_the_counts_only(room_pdf):
    lines = tool.summary_lines(tool.build_report(room_pdf, [0]))
    assert len(lines) == 2 and lines[0].startswith("page 0 preview_fork: strips ") and lines[1].startswith("page 0 layered: strips ")
    assert all("replication exact" in line and "ring-adding gaps 1 (new space 1)" in line and "apertures 1 of 1" in line for line in lines)


def test_every_spy_is_gone_after_a_full_run(room_pdf):
    before = {(m.__name__, n): getattr(m, n) for m in (layered, preview) for n in ("_collect_strips", "_gaps", "_swing_arcs", "_place_swings", "_closed_union")}
    tool.build_report(room_pdf, [0])
    assert all(getattr(m, n) is original for (m_name, n), original in before.items() for m in (layered, preview) if m.__name__ == m_name)
    assert not tool._ACTIVE_FAMILIES and canonical.build_layered_wall_doorway_room_rings is preview.build_layered_wall_doorway_room_rings


# ------------------------------------------------------------------------------------------------ spy internals

STUBS = {
    "_collect_strips": lambda drawings: ([], []),
    "_gaps": lambda strips, union, domain: [],
    "_swing_arcs": lambda drawings, **kw: ([], 0),
    "_place_swings": lambda arcs, gaps: ({}, 0, 0),
    "_closed_union": lambda polygons: "union",
    "_lining_face_wall_strips": lambda drawings, gaps, **kw: (["face"], []),
    "_source_unresolved_gap_witnesses": lambda unresolved, **kw: ((), 0),
}


def _stub_out(monkeypatch, module, names):
    for name in names:
        monkeypatch.setattr(module, name, STUBS[name])


@pytest.mark.parametrize("builder", BUILDERS)
def test_every_spy_keeps_the_first_call_made_while_building_and_ignores_the_rest(builder, monkeypatch):
    module, family = MODULES[builder]
    _stub_out(monkeypatch, module, SPY_NAMES[builder])
    rows_a, rows_b, arcs_a, gaps_a = ["a"], ["b"], [{"arc": "a"}], ["gap-a"]
    with tool.BuilderSpies(family) as spies:
        module._collect_strips(rows_a)
        module._swing_arcs(rows_a)
        module._gaps(["s0"], "u0", "d0")
        module._place_swings(arcs_a, gaps_a)
        module._closed_union(["p0"])
        assert spies.state == {"union_calls": []}                                     # nothing outside building()
        with spies.building():
            module._collect_strips(rows_a)
            module._collect_strips(rows_b)
            module._swing_arcs(rows_a)
            module._swing_arcs(rows_b)
            module._gaps(["s1"], "u1", "d1")
            module._gaps(["s2"], "u2", "d2")
            module._place_swings(arcs_a, gaps_a)
            module._place_swings([{"arc": "b"}], ["gap-b"])
            module._closed_union(["p1"])
            module._closed_union(["p2"])
        state = spies.state
        assert state["rows"] is rows_a and state["swing_rows"] is rows_a and state["arcs_rejected"] == 0 and state["strips"] == ["s1"]
        assert state["gaps_ref"] is gaps_a and state["arcs_ref"] is arcs_a and state["placed_ref"] == ({}, 0, 0)
        assert state["union_calls"] == [(["p1"], "union"), (["p2"], "union")]
        gaps_a.append("grown")
        assert state["gaps_ref"] == ["gap-a", "grown"]                                # a reference: the builder's later appends are seen
        module._collect_strips(rows_b)
        module._closed_union(["p3"])
        assert state["rows"] is rows_a and len(state["union_calls"]) == 2             # after building(): not recorded


def test_the_layered_only_spies_record_the_face_strips_and_the_unresolved_list_while_building(monkeypatch):
    _stub_out(monkeypatch, layered, SPY_NAMES["layered"])
    unresolved = ["gap"]
    with tool.BuilderSpies(census.BUILDER_LAYERED) as spies:
        layered._lining_face_wall_strips(["d"], ["g"])
        layered._source_unresolved_gap_witnesses(unresolved)
        assert "face_strips" not in spies.state and "unresolved_ref" not in spies.state
        with spies.building():
            assert layered._lining_face_wall_strips(["d"], ["g"]) == (["face"], [])
            assert layered._source_unresolved_gap_witnesses(unresolved) == ((), 0)
        assert spies.state["face_strips"] == ["face"] and spies.state["unresolved_ref"] is unresolved


def test_building_releases_its_flag_even_after_an_error():
    with tool.BuilderSpies(census.BUILDER_LAYERED) as spies:
        with pytest.raises(RuntimeError):
            with spies.building():
                assert spies._active is True
                raise RuntimeError("inside")
        assert spies._active is False
        layered._closed_union([])
        assert spies.state["union_calls"] == []


def test_the_entry_wrapper_records_the_first_call_marks_it_as_building_and_restores_the_owner():
    seen = []
    with tool.BuilderSpies(census.BUILDER_PREVIEW_FORK) as spies:
        def build(rows, **kwargs):
            seen.append(spies._active)
            return f"result-{len(rows)}"

        owner = SimpleNamespace(build=build)
        with spies.wrap_entry(owner, "build"):
            assert owner.build is not build
            assert owner.build([1], flag=True) == "result-1"
            assert owner.build([1, 2], flag=False) == "result-2"
        assert owner.build is build and seen == [True, True] and spies._active is False
        assert spies.result == "result-1" and spies.kwargs == {"flag": True} and spies.entry_rows == [1]
        with pytest.raises(RuntimeError):
            with spies.wrap_entry(owner, "build"):
                raise RuntimeError("boom")
        assert owner.build is build


def test_the_entry_wrapper_reads_the_rows_from_a_keyword_when_that_is_how_they_are_passed():
    with tool.BuilderSpies(census.BUILDER_PREVIEW_FORK) as spies:
        owner = SimpleNamespace(build=lambda drawings=None, **kw: "ok")
        with spies.wrap_entry(owner, "build"):
            owner.build(drawings=[7])
        assert spies.entry_rows == [7] and spies.result == "ok"


def test_a_failed_install_restores_everything_it_had_already_wrapped(monkeypatch):
    class Exploding(set):
        def add(self, item):
            raise RuntimeError("install failed")

    originals = {name: getattr(layered, name) for name in SPY_NAMES["layered"]}
    monkeypatch.setattr(tool, "_ACTIVE_FAMILIES", Exploding())
    with pytest.raises(RuntimeError, match="install failed"):
        tool.BuilderSpies(census.BUILDER_LAYERED).__enter__()
    assert all(getattr(layered, name) is original for name, original in originals.items())


def test_a_builder_module_without_an_unresolved_gap_veto_is_refused(monkeypatch):
    monkeypatch.setattr(tool, "_touch_function", lambda module: None)
    with pytest.raises(tool.CensusContractError, match="veto"):
        tool.check_spy_contract(census.BUILDER_LAYERED)


def test_the_veto_lookup_prefers_the_builders_own_name_over_the_alias():
    assert tool._touch_function(SimpleNamespace(_unresolved_collinear_gap_breaches_outer_ring="own", _original_two_end_gap_veto="alias")) == "own"
    assert tool._touch_function(SimpleNamespace(_original_two_end_gap_veto="alias")) == "alias"
    assert tool._touch_function(SimpleNamespace()) is None


# ------------------------------------------------------------------------------------------------ the capture from a fake builder run

def _fake_result(**over):
    ring = SimpleNamespace(status=SimpleNamespace(value="candidate"), reason_codes=("ring_ok",),
                           polygon_pdf_pts=((250.0, 100.0), (300.0, 100.0), (300.0, 130.0), (250.0, 130.0)))
    fields = dict(status=SimpleNamespace(value="candidate"), reason_codes=("builder_ok",),
                  closures=[SimpleNamespace(horizontal=False, band=(294.0, 300.0), gap_interval=(100.0, 130.0))],
                  wall_strip_count=5, wall_gap_count=3, unresolved_gap_count=1, unplaced_swing_count=3, ambiguous_swing_count=4, rings=[ring])
    fields.update(over)
    return SimpleNamespace(**fields)


def _fake_state(module, *, face=()):
    base = [box(0, 0, 10, 10), box(20, 0, 30, 10)]
    rect = box(10, 0, 20, 10)
    closed_gap = module._Gap(False, (294.0, 300.0), 100.0, 130.0, (1,), (2,), True)
    open_gap = module._Gap(True, (50.0, 56.0), 10.0, 40.0, (3,), (4,), False)
    long_gap = module._Gap(False, (394.0, 400.0), 0.0, 200.0, (5,), (6,), True)
    native_a = {"centre": (297.0, 100.0), "closed_tip": (297.0, 130.0)}
    native_long = {"centre": (397.0, 0.0), "closed_tip": (397.0, 200.0)}
    segmented = {"centre": (297.0, 102.0), "closed_tip": (297.0, 128.0), "source_segmented_polyline": True}
    state = {
        "rows": ["row"],
        "strips": [SimpleNamespace(x0=0, y0=0, x1=3, y1=10), SimpleNamespace(x0=0, y0=0, x1=6, y1=10), SimpleNamespace(x0=0, y0=0, x1=6, y1=12)],
        "union_calls": [(base, box(0, 0, 10, 10)), (base, box(0, 0, 30, 10)), ([box(500, 500, 501, 501)], box(500, 500, 501, 501)),
                        ([*base, rect], box(0, 0, 30, 10))],
        "gaps_ref": [closed_gap, open_gap, long_gap], "arcs_ref": [native_a, native_long, segmented], "placed_ref": ({1: {"arc": 9}}, 0, 0),
        "arcs_rejected": 7, "swing_rows": [],
    }
    if module is layered:
        state["unresolved_ref"] = [open_gap, long_gap]
    if face:
        state["face_strips"] = list(face)
    return state, SimpleNamespace(base=base, rect=rect, closed_gap=closed_gap, open_gap=open_gap, native_a=native_a, native_long=native_long, segmented=segmented)


def _fake_capture(builder, **kw):
    module, family = MODULES[builder]
    state, parts = _fake_state(module, **kw)
    spies = tool.BuilderSpies(family)
    spies.state.update(state)
    return spies.capture(result=_fake_result(), kwargs={"dark_painted_wall_source": True}), parts, state


def test_the_capture_needs_a_result_and_the_state_of_a_builder_that_reached_its_closure_loop():
    spies = tool.BuilderSpies(census.BUILDER_LAYERED)
    assert spies.capture(result=_fake_result()) is None                              # nothing recorded
    assert spies.capture() is None                                                   # no result either
    spies.state.update({"rows": [], "union_calls": [([], "u")]})
    assert spies.capture(result=_fake_result()) is None                              # no gap list: the builder never reached the loop
    spies.state["gaps_ref"] = []
    assert spies.capture(result=_fake_result()) is None                              # the layered builder also needs its unresolved list
    other = tool.BuilderSpies(census.BUILDER_PREVIEW_FORK)
    other.state.update({"rows": [], "union_calls": []})
    other.state["gaps_ref"] = []
    assert other.capture(result=_fake_result()) is None                              # no union call recorded


@pytest.mark.parametrize("builder", BUILDERS)
def test_the_capture_identifies_the_barrier_the_union_and_the_domain_from_the_recorded_union_calls(builder):
    capture, parts, state = _fake_capture(builder)
    assert capture.barrier is state["union_calls"][-1][1] and capture.barrier_inputs == (*parts.base, parts.rect)
    assert capture.domain.bounds == pytest.approx((-1.0, -1.0, 31.0, 11.0))         # the LATEST earlier call whose polygons prefix the barrier's
    assert capture.noise_pt == MODULES[builder][0].NOISE_PT


@pytest.mark.parametrize("builder", BUILDERS)
def test_the_median_strip_thickness_includes_the_face_strips_the_layered_builder_adds_later(builder):
    plain, _, _ = _fake_capture(builder)
    assert plain.median_thickness == 6.0                                             # strips 3, 6, 6: the median, not the minimum
    thin = [SimpleNamespace(x0=0, y0=0, x1=1, y1=10) for _ in range(4)]
    with_faces, _, _ = _fake_capture(builder, face=thin)
    assert with_faces.median_thickness == 1.0                                        # 1, 1, 1, 1, 3, 6, 6


def test_the_layered_capture_reads_closed_gaps_from_the_unresolved_list_and_its_own_ring_rule_and_closure_padding():
    capture, parts, _ = _fake_capture("layered")
    assert capture.closed == (True, False, False) and capture.ring_rule is census.LAYERED_RING_RULE and capture.builder == census.BUILDER_LAYERED
    assert capture.closure_rect(census.PlainGap(False, (294.0, 300.0), 150.0, 180.0, True)).bounds == pytest.approx((294.0, 148.8, 300.0, 181.2))
    assert capture.closure_rect(census.PlainGap(True, (294.0, 300.0), 150.0, 180.0, True)).bounds == pytest.approx((148.8, 294.0, 181.2, 300.0))


def test_the_preview_capture_reads_closed_gaps_from_the_builders_closure_intervals_and_closes_with_the_plain_rectangle():
    capture, parts, _ = _fake_capture("preview")
    assert capture.closed == (True, False, False) and capture.ring_rule is census.PREVIEW_RING_RULE and capture.builder == census.BUILDER_PREVIEW_FORK
    assert capture.closure_rect(census.PlainGap(False, (294.0, 300.0), 150.0, 180.0, True)).bounds == pytest.approx((294.0, 150.0, 300.0, 180.0))
    assert capture.closure_rect(census.PlainGap(True, (294.0, 300.0), 150.0, 180.0, True)).bounds == pytest.approx((150.0, 294.0, 180.0, 300.0))
    assert capture.door_witnesses == ()                                              # the preview reads witnesses from its swing rows, here empty


@pytest.mark.parametrize("builder", BUILDERS)
def test_the_capture_copies_the_builders_own_counts_and_rings(builder):
    capture, _, _ = _fake_capture(builder)
    assert (capture.builder_strip_count, capture.builder_gap_count, capture.builder_closure_count, capture.builder_unresolved_collinear) == (5, 3, 1, 1)
    assert capture.status == "candidate" and capture.reason_codes == ("builder_ok",) and len(capture.gaps) == 3 and capture.rows == ["row"]
    (ring,) = capture.builder_rings
    assert ring.status == "candidate" and ring.reason_codes == ("ring_ok",)
    assert ring.polygon.equals(Polygon([(250.0, 100.0), (300.0, 100.0), (300.0, 130.0), (250.0, 130.0)]))
    assert capture.arc_info.rejected_by_finder == 7 and capture.arc_info.builder_unplaced == 3 and capture.arc_info.builder_ambiguous == 4
    assert capture.arc_info.found == 2


def test_the_layered_capture_splits_native_arcs_from_segmented_witnesses_and_uses_the_builders_opening_filter():
    capture, parts, _ = _fake_capture("layered")
    assert capture.native_arcs == (parts.native_a, parts.native_long) and capture.door_witnesses == (parts.segmented,)
    assert capture.arc_info.candidate_gap_indices == ((0,), ())                      # the 200 pt gap is not an opening to the layered builder


def test_the_preview_capture_has_no_opening_filter_for_swing_candidates():
    capture, parts, _ = _fake_capture("preview")
    assert capture.native_arcs == (parts.native_a, parts.native_long)
    assert capture.arc_info.candidate_gap_indices == ((0,), (2,))


@pytest.mark.parametrize("builder", BUILDERS)
def test_the_ring_touch_is_the_builders_own_veto_not_its_negation(builder):
    capture, _, _ = _fake_capture(builder)
    assert capture.ring_touch(box(250, 100, 300, 130), 0) is True                    # both ends of the collinear gap lie on this ring's outer boundary
    assert capture.ring_touch(box(0, 0, 10, 10), 0) is False
    assert capture.ring_touch(box(250, 100, 300, 130), 1) is False                   # a non-collinear gap never vetoes a ring


# ------------------------------------------------------------------------------------------------ owner evidence

def _layered_owners(monkeypatch, *, swing=None, stroke=None, jamb=None, frame=None, sliding=None, dark=True, sliding_on=False, thickness=6.0):
    calls = []

    def make(name, value):
        def stub(*args, **kwargs):
            calls.append(name)
            return value
        return stub

    monkeypatch.setattr(layered, "_stroke_closed", make("stroke", stroke))
    monkeypatch.setattr(layered, "_jamb_cap_closed", make("jamb", jamb))
    monkeypatch.setattr(layered, "_frame_pair_closed", make("frame", frame))
    monkeypatch.setattr(layered, "_sliding_leaf_evidence", make("sliding", sliding))
    gap = layered._Gap(False, (294.0, 294.0 + thickness), 150.0, 180.0, (), (), True)
    evidence = tool.BuilderSpies(census.BUILDER_LAYERED)._owner_evidence(
        ["row"], [gap], {} if swing is None else {0: swing}, {"dark_painted_wall_source": dark, "sliding_leaf_frame_closure": sliding_on})
    return evidence(0), calls


def test_layered_owner_evidence_follows_the_closure_loop_one_function_at_a_time(monkeypatch):
    assert _layered_owners(monkeypatch, swing={"arc": 1}, stroke=(1,)) == (("swing",), [])                     # a swing: nothing else is searched
    assert _layered_owners(monkeypatch, stroke=(1,)) == (("stroke_or_jamb",), ["stroke"])
    assert _layered_owners(monkeypatch, jamb=(2,)) == (("stroke_or_jamb",), ["stroke", "jamb"])
    assert _layered_owners(monkeypatch, frame=(3,)) == (("stroke_or_jamb",), ["stroke", "jamb", "frame"])
    assert _layered_owners(monkeypatch, frame=(3,), sliding_on=True) == ((), ["stroke", "jamb", "sliding"])    # no frame pair beside a sliding-leaf run
    assert _layered_owners(monkeypatch, jamb=(2,), frame=(3,), dark=False) == ((), ["stroke"])                 # jambs and frames need the dark-painted source
    assert _layered_owners(monkeypatch, stroke=(1,), thickness=1.0) == ((), [])                                 # a wall thinner than a stroke pair is no host
    assert _layered_owners(monkeypatch, stroke=(1,), sliding=(4,), sliding_on=True) == (("stroke_or_jamb", "sliding"), ["stroke", "sliding"])
    assert _layered_owners(monkeypatch, stroke=(1,), sliding=(4,), sliding_on=False) == (("stroke_or_jamb",), ["stroke"])
    assert _layered_owners(monkeypatch, swing={"arc": 1}, sliding=(4,), sliding_on=True) == (("swing", "sliding"), ["sliding"])


def _preview_owners(monkeypatch, *, swing=None, stroke=None, jamb=None, sliding=None, cs_words=None, paired=None, pocket=None, panel=None,
                    all_ink=True, sliding_on=True, panel_on=True):
    calls = []

    def make(name, value):
        def stub(*args, **kwargs):
            calls.append(name)
            return value
        return stub

    for name, value in (("_stroke_closed", stroke), ("_jamb_cap_closed", jamb), ("_sliding_leaf_evidence", sliding), ("_cavity_slider_word_evidence", cs_words),
                        ("_paired_cavity_leaves", paired), ("_pocket_cavity_leaves", pocket), ("_panel_lift_word_evidence", panel)):
        monkeypatch.setattr(preview, name, make(name, value))
    gap = preview._Gap(False, (294.0, 300.0), 150.0, 180.0, (), (), True)
    kwargs = {"stroke_pair_wall_faces": all_ink, "sliding_leaf_frame_closure": sliding_on, "panel_lift_label_closure": panel_on, "source_words": ("w",)}
    evidence = tool.BuilderSpies(census.BUILDER_PREVIEW_FORK)._owner_evidence(["row"], [gap], {} if swing is None else {0: swing}, kwargs)
    return evidence(0), calls


def test_preview_owner_evidence_follows_the_closure_loop_one_function_at_a_time(monkeypatch):
    quiet = dict(sliding_on=False, panel_on=False)
    assert _preview_owners(monkeypatch, swing={"arc": 1}, stroke=(1,), **quiet) == (("swing",), [])
    assert _preview_owners(monkeypatch, stroke=(1,), **quiet) == (("stroke_or_jamb",), ["_stroke_closed"])
    assert _preview_owners(monkeypatch, jamb=(2,), **quiet) == (("stroke_or_jamb",), ["_stroke_closed", "_jamb_cap_closed"])
    assert _preview_owners(monkeypatch, jamb=(2,), all_ink=False, **quiet) == ((), ["_stroke_closed"])
    owners, calls = _preview_owners(monkeypatch, sliding=(3,), panel_on=False)
    assert owners == ("sliding",) and calls == ["_stroke_closed", "_jamb_cap_closed", "_sliding_leaf_evidence", "_cavity_slider_word_evidence",
                                                "_paired_cavity_leaves", "_pocket_cavity_leaves"]
    assert _preview_owners(monkeypatch, cs_words=("cs",), paired=(5,), panel_on=False)[0] == ("cavity",)
    assert _preview_owners(monkeypatch, cs_words=("cs",), pocket=(6,), panel_on=False)[0] == ("cavity",)                 # pocket leaves when no paired leaves
    assert _preview_owners(monkeypatch, cs_words=("cs",), panel_on=False)[0] == ()                                      # words without leaves are not a cavity slider
    assert _preview_owners(monkeypatch, paired=(5,), panel_on=False)[0] == ()                                           # leaves without words either
    assert _preview_owners(monkeypatch, panel=("lift",), sliding_on=False)[0] == ("panel",)
    assert _preview_owners(monkeypatch, panel=("lift",), panel_on=False, sliding_on=False)[0] == ()
    owners, calls = _preview_owners(monkeypatch, stroke=(1,), sliding=(3,), cs_words=("cs",), paired=(5,), panel=("lift",))
    assert owners == ("stroke_or_jamb", "sliding", "cavity", "panel")
    owners, calls = _preview_owners(monkeypatch, stroke=(1,), sliding_on=False, panel_on=False)
    assert "_sliding_leaf_evidence" not in calls and "_panel_lift_word_evidence" not in calls


# ------------------------------------------------------------------------------------------------ builder inputs and arc scenes

def _door_scene(width=23.0, lo=100.0, y0=43.0):
    """A wall with one doorway drawn the way the layered builder reads a segmented source door: faces, jambs, nine chord strokes, a leaf."""
    import math

    hi = lo + width
    rows = []
    for across in (y0 - 3.0, y0 + 3.0):
        rows.append(_stroke((lo - 100.0, across), (lo, across)))
        rows.append(_stroke((hi, across), (hi + 148.0, across)))
    rows.append(_stroke((lo, y0 - 3.0), (lo, y0 + 3.0)))
    rows.append(_stroke((hi, y0 - 3.0), (hi, y0 + 3.0)))
    pts = [(hi - width * math.cos(math.radians(10 * k)), y0 + width * math.sin(math.radians(10 * k))) for k in range(10)]
    rows.extend(_stroke(a, b) for a, b in zip(pts, pts[1:]))
    rows.append(_stroke((hi, y0), (hi, y0 + width)))
    return rows


@pytest.mark.parametrize("builder", BUILDERS)
def test_a_segmented_source_door_swing_is_a_door_witness_and_not_a_native_arc(builder):
    capture, _ = _capture(builder, _door_scene())
    assert len(capture.door_witnesses) == 1 and capture.native_arcs == () and capture.arc_info.found == 0


@pytest.mark.parametrize("builder,expected", [("layered", {"no_candidate_gap": 1}), ("preview", {"one_candidate_gap": 1})])
def test_the_layered_builder_only_places_a_swing_in_an_opening_sized_gap(builder, expected):
    report, _ = _report(builder, _room(gap=(120.0, 330.0), h=450.0, arc=True))      # a 210 pt interruption with a swing of that radius
    assert report["native_arcs"]["found"] == 1 and report["native_arcs"]["per_arc_candidate_gaps"] == expected


@pytest.mark.parametrize("builder", BUILDERS)
def test_a_curve_that_is_not_a_door_swing_is_counted_as_rejected_by_the_finder(builder):
    lopsided = {"layer": "", "fill": None, "color": BLACK, "width": 0.5, "items": [("c", fitz.Point(0, 0), fitz.Point(5, 0), fitz.Point(10, 5), fitz.Point(10, 20))]}
    report, _ = _report(builder, _room(extra=[lopsided]))
    assert report["native_arcs"]["found"] == 0 and report["native_arcs"]["rejected_by_finder"] == 1


def test_the_canonical_flags_are_the_literal_ones_and_the_callers_overrides_win(monkeypatch):
    literal = {"sliding_leaf_frame_closure": True, "panel_lift_label_closure": True, "source_native_cs_jamb_closure": False,
               "source_native_internal_swing_closure": False, "stroke_pair_wall_faces": True}
    assert tool.CANONICAL_PREVIEW_FLAGS == literal
    seen = {}
    real = preview.build_layered_wall_doorway_room_rings

    def recorder(rows, **kwargs):
        seen.clear()
        seen.update(kwargs)
        return real(rows, **kwargs)

    monkeypatch.setattr(preview, "build_layered_wall_doorway_room_rings", recorder)
    tool.capture_preview_builder_rows(_room(), source_sha256=SHA, page_index=3)
    assert {k: seen[k] for k in literal} == literal and seen["page_index"] == 3 and seen["source_sha256"] == SHA
    tool.capture_preview_builder_rows(_room(), source_sha256=SHA, page_index=0, stroke_pair_wall_faces=False, source_words=())
    assert seen["stroke_pair_wall_faces"] is False and seen["sliding_leaf_frame_closure"] is True and seen["source_words"] == ()


def test_the_layered_builder_runs_dark_painted_by_default_and_with_the_flags_it_is_given(monkeypatch):
    seen = {}
    real = layered.build_layered_wall_doorway_room_rings

    def recorder(rows, **kwargs):
        seen.clear()
        seen.update(kwargs)
        return real(rows, **kwargs)

    monkeypatch.setattr(layered, "build_layered_wall_doorway_room_rings", recorder)
    tool.capture_layered_builder(_room(), source_sha256=SHA, page_index=2)
    assert seen["dark_painted_wall_source"] is True and seen["sliding_leaf_frame_closure"] is False
    assert seen["wall_end_stroke_closures"] is False and seen["page_index"] == 2
    tool.capture_layered_builder(_room(), source_sha256=SHA, page_index=0, sliding_leaf_frame_closure=True, wall_end_stroke_closures=True)
    assert seen["sliding_leaf_frame_closure"] is True and seen["wall_end_stroke_closures"] is True


@pytest.mark.parametrize("builder", BUILDERS)
def test_the_capture_hands_placed_swings_to_the_owner_evidence(builder):
    capture, _, _ = _fake_capture(builder)
    assert capture.owner_evidence(1) == ("swing",)                                        # gap 1 holds a placed swing in the builder's own table


@pytest.mark.parametrize("builder", BUILDERS)
def test_what_the_census_closes_with_is_the_polygon_the_builder_closed_with(builder):
    """The builder's own closure rectangle is the last polygon of its barrier; the census's closing rectangle for the same gap is that polygon."""
    capture, result = _capture(builder, _room(arc=True))
    assert capture is not None and len(result.closures) == 1 and capture.closed == (True,)
    closed_polygon = capture.barrier_inputs[-1]
    assert capture.closure_rect(capture.gaps[0]).bounds == pytest.approx(closed_polygon.bounds)
    assert capture.closed_union(list(capture.barrier_inputs)).equals(capture.barrier)     # the barrier is exactly the union of those polygons


@pytest.mark.parametrize("builder", BUILDERS)
def test_closing_a_non_collinear_leak_counts_in_the_every_gap_upper_bound_but_not_in_the_collinear_set(builder):
    report, _ = _report(builder, _room(right_gap=False, extra=STUB))
    unblock = report["unblocking_power"]
    assert unblock["if_all_unresolved_collinear_closed"] == 1 and unblock["if_every_unclosed_raw_gap_closed_UPPER_BOUND_NOT_A_RULE"] == 2
    assert unblock["if_all_unclosed_of_one_class_closed"] == {"empty": 2} and unblock["if_all_opening_sized_unresolved_closed"] == 2


def test_a_later_page_of_a_document_is_censused_and_named_by_its_own_index(tmp_path):
    document = fitz.open()
    document.new_page(width=800, height=400)                                         # page 0: blank
    page = document.new_page(width=800, height=400)                                  # page 1: the room
    for a, b in _stroke_room():
        shape = page.new_shape()
        shape.draw_line(fitz.Point(*a), fitz.Point(*b))
        shape.finish(color=BLACK, width=0.5, closePath=False)
        shape.commit()
    path = tmp_path / "two_pages.pdf"
    document.save(str(path))
    document.close()
    census_of_room = tool.run_census(path, 1)
    assert census_of_room["page_index"] == 1
    assert all(block["census_available"] and block["unclosed_gaps"]["count"] == 1 for block in census_of_room["builders"].values())
    blank = tool.run_census(path, 0, builders=("layered",))
    assert blank["page_index"] == 0 and blank["builders"]["layered"]["census_available"] is False


def test_summary_lines_flag_an_inexact_replication_and_a_missing_census():
    counts = {"strips": 5, "raw_gaps": 3, "raw_gaps_collinear": 2, "closed": 1, "rings": 4}
    block = {"census_available": True, "counts": counts, "unclosed_gaps": {"count": 2, "collinear": 1}, "apertures": {"groups": 3, "raw_gaps": 3},
             "replication": {"exact": False}, "unblocking_power": None}
    report = {"pages": [{"page_index": 4, "builders": {"layered": block, "preview_fork": {"census_available": False, "builder_status": "abstained"}}}]}
    lines = tool.summary_lines(report)
    assert lines == [
        "page 4 layered: strips 5 raw gaps 3 (collinear 2) closed 1 | unclosed 2 (collinear 1) | rings 4 | replication NOT EXACT | ring-adding gaps n/a (new space n/a) | apertures 3 of 3",
        "page 4 preview_fork: no census (abstained)",
    ]
    skipped = {"pages": [{"page_index": 0, "builders": {"layered": {"census_available": False, "skipped": "raster"}}}]}
    assert tool.summary_lines(skipped) == ["page 0 layered: no census (raster)"]


class _CountingPage:
    def __init__(self, page, counter):
        self._page, self._counter = page, counter

    def get_drawings(self, *args, **kwargs):
        self._counter.append(1)
        return self._page.get_drawings(*args, **kwargs)


class _CountingDocument:
    def __init__(self, document, counter):
        self._document, self._counter = document, counter

    def __len__(self):
        return len(self._document)

    def __getitem__(self, index):
        return _CountingPage(self._document[index], self._counter)

    def close(self):
        self._document.close()


@pytest.mark.parametrize("builders,layered_rows,reads", [
    (("preview",), "raw", 0), (("layered",), "raw", 1), (("preview", "layered"), "raw", 1), (("preview", "layered"), "preview-scoped", 0),
])
def test_the_tool_reads_the_pages_raw_rows_only_when_the_layered_builder_needs_them(room_pdf, monkeypatch, builders, layered_rows, reads):
    counter = []
    real_open = fitz.open
    monkeypatch.setattr(tool, "fitz", SimpleNamespace(open=lambda *a, **k: _CountingDocument(real_open(*a, **k), counter)))
    tool.run_census(room_pdf, 0, builders=builders, layered_rows=layered_rows, unblocking=False)
    assert len(counter) == reads


def test_the_report_text_is_sorted_and_indented_so_two_runs_diff_cleanly(room_pdf, tmp_path, capsys):
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    assert tool.main(["--pdf", str(room_pdf), "--page-index", "0", "--json-out", str(first)]) == 0
    assert tool.main(["--pdf", str(room_pdf), "--page-index", "0", "--json-out", str(second)]) == 0
    capsys.readouterr()
    text = first.read_text(encoding="utf-8")
    assert text == json.dumps(json.loads(text), indent=1, sort_keys=True) + "\n" and text == second.read_text(encoding="utf-8")
    assert tool.main(["--pdf", str(room_pdf), "--page-index", "0"]) == 0
    printed = capsys.readouterr().out
    assert printed == text                                                           # stdout carries exactly the file's text


def _split_long_walls(rows):
    """Cut every long horizontal wall bar into two touching collinear bars: the same wall ink, one more strip per cut."""
    out = []
    for row in rows:
        item = row["items"][0] if row.get("items") else None
        if row.get("layer") == "A-WALL" and item and item[0] == "re" and item[1].width > 40 and item[1].width > item[1].height:
            r = item[1]
            mid = (r.x0 + r.x1) / 2
            out.append({**row, "items": [("re", fitz.Rect(r.x0, r.y0, mid, r.y1))]})
            out.append({**row, "items": [("re", fitz.Rect(mid, r.y0, r.x1, r.y1))]})
        else:
            out.append(row)
    return out


@pytest.mark.parametrize("builder", BUILDERS)
@pytest.mark.parametrize("scene", ["empty", "ticks", "stub", "twin"])
def test_splitting_a_wall_bar_into_touching_collinear_bars_leaves_the_census_alone(builder, scene):
    rows = {"empty": _room(), "ticks": _room(extra=TICKS), "stub": _room(right_gap=False, extra=STUB), "twin": _room(twin=True)}[scene]
    split = _split_long_walls(rows)
    assert len(split) > len(rows)
    base, _ = _report(builder, rows)
    again, _ = _report(builder, split)
    assert again["replication"]["exact"] is True and again["counts"]["strips"] > base["counts"]["strips"]
    assert _signature(again)[1:] == _signature(base)[1:]                              # everything but the strip count


@pytest.mark.parametrize("builder", BUILDERS)
def test_an_empty_doorway_encloses_new_space_and_a_partition_end_only_splits_the_room(builder):
    leak, _ = _report(builder, _room(), per_gap=True)
    assert leak["unblocking_power"]["single_closure"]["adding_by_effect"] == {"encloses_new_space": 1}
    assert leak["apertures"]["new_space_gaps"] == 1 and leak["gap_records"][0]["single_closure_effect"] == "encloses_new_space"
    split, _ = _report(builder, _room(right_gap=False, extra=STUB), per_gap=True)
    assert split["unblocking_power"]["single_closure"]["adding_by_effect"] == {"splits_an_enclosed_ring": 1}
    assert split["unblocking_power"]["single_closure"]["adding_by_orientation_and_effect"] == {"non_collinear|splits_an_enclosed_ring": 1}
    assert split["apertures"]["ring_adding_gaps"] == 1 and split["apertures"]["new_space_gaps"] == 0 and split["gap_records"][0]["single_closure_effect"] == "splits_an_enclosed_ring"


@pytest.mark.parametrize("builder", BUILDERS)
def test_twin_bands_over_one_leaking_doorway_are_two_new_space_gaps_in_one_group(builder):
    report, _ = _report(builder, _room(twin=True))
    apertures = report["apertures"]
    assert apertures["new_space_gaps"] == 2 and apertures["new_space_distinct_groups"] == 1 and apertures["ring_adding_gaps"] == 2


def test_the_summary_line_counts_ring_adding_gaps_and_how_many_enclose_new_space(room_pdf):
    lines = tool.summary_lines(tool.build_report(room_pdf, [0]))
    assert all("ring-adding gaps 1 (new space 1)" in line for line in lines)


def test_the_summary_line_reports_the_ring_adding_and_new_space_counts_and_the_aperture_figures_separately():
    counts = {"strips": 5, "raw_gaps": 5, "raw_gaps_collinear": 2, "closed": 1, "rings": 4}
    block = {"census_available": True, "counts": counts, "unclosed_gaps": {"count": 4, "collinear": 1}, "apertures": {"groups": 3, "raw_gaps": 5, "new_space_gaps": 2},
             "replication": {"exact": True}, "unblocking_power": {"single_closure": {"gaps_adding_a_ring": 4}}}
    (line,) = tool.summary_lines({"pages": [{"page_index": 9, "builders": {"layered": block}}]})
    assert line == ("page 9 layered: strips 5 raw gaps 5 (collinear 2) closed 1 | unclosed 4 (collinear 1) | rings 4 | replication exact | "
                    "ring-adding gaps 4 (new space 2) | apertures 3 of 5")
