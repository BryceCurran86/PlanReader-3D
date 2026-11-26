"""Default-off wiring: proven doorway chords become topology-only closures in the canonical preview's room tracer.

Synthetic only; no private source. ``pb_next_wall_ring_preview.build_layered_wall_doorway_room_rings`` takes the topology-only chord
receipts of ``pb_source_owned_doorway_chord_preview_shadow`` as ``source_owned_doorway_chords``: each chord in view closes its door
interval across its wall band unless the tracer already closed that doorway, and the collinear gaps it fills stop vetoing a ring.
``source_native_trace_preview(..., source_owned_doorway_chord_closures=True)`` supplies them and says which were applied. With the
switch off nothing changes. Nothing here is a wall, an opening, a quantity or a score.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from types import SimpleNamespace

import fitz
import pytest

import pb_new_source_trace_preview as canonical
import pb_next_wall_ring_preview as tracer
from tools import run_canonical_source_native_preview as runner

SHA = "ab" * 32
BLACK = (0.0, 0.0, 0.0)
KEY = "source_owned_doorway_chord_closures"
FLAGS = ("source_physical_door_host_authenticated", "metric_area_issued", "commercial_publishable")


def _bar(x0, y0, x1, y1):
    return {"layer": "", "fill": BLACK, "color": None, "width": 0.0, "items": [("re", fitz.Rect(x0, y0, x1, y1), 1)]}


def _line(a, b, width=0.5):
    return {"layer": "", "fill": None, "color": BLACK, "width": width, "items": [("l", fitz.Point(*a), fitz.Point(*b))]}


def _room(*, dx=0.0, doorway=(160.0, 190.0)):
    """A 200 x 150 room of 6 pt filled walls with one doorway cut out of the bottom wall and nothing else drawn in it."""
    lo, hi = doorway
    return [
        _bar(100 + dx, 100, 300 + dx, 106),
        _bar(100 + dx, 106, 106 + dx, 250),
        _bar(294 + dx, 106, 300 + dx, 250),
        _bar(106 + dx, 244, lo + dx, 250),
        _bar(hi + dx, 244, 294 + dx, 250),
    ]


def _chord(lo=160.0, hi=190.0, band=(244.0, 250.0), horizontal=True, **overrides):
    chord = {
        "horizontal": horizontal,
        "wall_band_pdf_pts": [band[0], band[1]],
        "door_interval_pdf_pts": [lo, hi],
        "source_swing_native_path_indices": [90, 91],
        "source_threshold_path_indices": [],
        "source_wall_end_left_path_indices": [3],
        "source_wall_end_right_path_indices": [4],
        "source_jamb_left_path_indices": [],
        "source_jamb_right_path_indices": [],
        "candidate_topology_doorway_closure": True,
        "source_physical_door_host_authenticated": False,
        "metric_area_issued": False,
        "commercial_publishable": False,
        "applied_to_preview_topology": False,
    }
    chord.update(overrides)
    return chord


def _trace(rows, **kw):
    kw.setdefault("source_sha256", SHA)
    kw.setdefault("page_index", 0)
    kw.setdefault("stroke_pair_wall_faces", True)  # the mode the canonical preview runs the tracer in
    return tracer.build_layered_wall_doorway_room_rings(rows, **kw)


def _candidates(result):
    return [r for r in result.rings if r.status.value == "candidate"]


def _chord_closures(result):
    return [c for c in result.closures if c.kind == tracer.KIND_SOURCE_OWNED_CHORD]


def test_without_chords_the_open_doorway_leaves_no_closed_room():
    result = _trace(_room())
    assert not _candidates(result) and not result.closures


def test_a_chord_closes_the_doorway_and_the_room_ring_uses_it():
    result = _trace(_room(), source_owned_doorway_chords=[_chord()])
    (closure,) = _chord_closures(result)
    assert closure.horizontal is True and closure.gap_interval == (160.0, 190.0) and closure.band == (244.0, 250.0)
    assert closure.native_path_indices == (90, 91) and closure.wall_path_indices == (3, 4)
    (ring,) = _candidates(result)
    assert closure.closure_id in ring.bounding_closure_ids and ring.closure_edge_count >= 1
    assert result.status.value == "candidate" and result.unresolved_gap_count == 0


def test_chords_are_never_added_to_a_doorway_the_tracer_already_closed():
    rows = [*_room(), _line((160.0, 244.0), (190.0, 244.0))]  # a drawn threshold the tracer closes by itself
    alone = _trace(rows)
    assert alone.closures and not _chord_closures(alone) and _candidates(alone)
    with_chord = _trace(rows, source_owned_doorway_chords=[_chord()])
    assert [c.closure_id for c in with_chord.closures] == [c.closure_id for c in alone.closures]
    assert [r.record_id for r in with_chord.rings] == [r.record_id for r in alone.rings]


def test_a_chord_elsewhere_changes_no_ring():
    base = _trace(_room())
    far = _trace(_room(), source_owned_doorway_chords=[_chord(lo=600.0, hi=630.0)])
    assert [r.record_id for r in far.rings] == [r.record_id for r in base.rings]
    assert len(_chord_closures(far)) == 1  # it is recorded, but bounds nothing
    assert far.unresolved_gap_count == base.unresolved_gap_count


def test_a_chord_covering_only_part_of_a_gap_leaves_that_gap_unresolved():
    partial = _trace(_room(), source_owned_doorway_chords=[_chord(lo=160.0, hi=172.0)])
    assert not _candidates(partial) and partial.unresolved_gap_count == _trace(_room()).unresolved_gap_count


@pytest.mark.parametrize("bad", [
    {"candidate_topology_doorway_closure": False}, {"source_physical_door_host_authenticated": True},
    {"metric_area_issued": True}, {"commercial_publishable": True}, {"commercial_publishable": None},
])
def test_a_chord_that_is_not_topology_only_is_rejected(bad):
    with pytest.raises(ValueError, match="source_owned_doorway_chord_must_be_topology_only"):
        _trace(_room(), source_owned_doorway_chords=[_chord(**bad)])


@pytest.mark.parametrize("bad", [
    {"horizontal": 1}, {"wall_band_pdf_pts": [250.0, 244.0]}, {"door_interval_pdf_pts": [190.0, 160.0]},
    {"door_interval_pdf_pts": [160.0]}, {"wall_band_pdf_pts": [244.0, float("nan")]},
])
def test_a_malformed_chord_is_rejected(bad):
    with pytest.raises(ValueError, match="source_owned_doorway_chord_geometry_invalid"):
        _trace(_room(), source_owned_doorway_chords=[_chord(**bad)])


def test_chord_order_and_replay_do_not_matter_and_nothing_is_mutated():
    rows = _room()
    chords = [_chord(), _chord(lo=600.0, hi=630.0)]
    before_rows, before_chords = copy.deepcopy(rows), copy.deepcopy(chords)
    first = _trace(rows, source_owned_doorway_chords=chords)
    second = _trace(rows, source_owned_doorway_chords=list(reversed(chords)))
    assert [r.record_id for r in first.rings] == [r.record_id for r in second.rings]
    assert [c.closure_id for c in first.closures] == [c.closure_id for c in second.closures]
    assert rows == before_rows and chords == before_chords


def test_overlapping_chords_are_all_kept_whatever_their_order_and_a_repeated_one_counts_once():
    face = _chord(band=(244.0, 245.2), source_swing_native_path_indices=[92])
    chords = [_chord(), face, _chord()]
    first = _trace(_room(), source_owned_doorway_chords=chords)
    second = _trace(_room(), source_owned_doorway_chords=list(reversed(chords)))
    assert len(_chord_closures(first)) == 2 and len(_candidates(first)) == 1
    assert [r.record_id for r in first.rings] == [r.record_id for r in second.rings]
    assert [c.closure_id for c in first.closures] == [c.closure_id for c in second.closures]


def test_translation_moves_the_closed_room_with_its_chord():
    moved = _trace(_room(dx=37.5), source_owned_doorway_chords=[_chord(lo=197.5, hi=227.5)])
    (ring,) = _candidates(moved)
    assert ring.bbox_pdf_pts == pytest.approx((143.5, 106.0, 331.5, 244.0), abs=0.05)


def test_a_chord_outside_the_requested_viewport_is_not_applied():
    view = (80.0, 80.0, 320.0, 270.0)
    inside = _trace(_room(), source_owned_doorway_chords=[_chord()], viewport_pdf_pts=view)
    assert len(_chord_closures(inside)) == 1 and _candidates(inside)
    outside = _trace(_room(), source_owned_doorway_chords=[_chord(lo=600.0, hi=630.0)], viewport_pdf_pts=view)
    assert not _chord_closures(outside)


def test_the_tiled_run_hands_the_chords_to_each_tile_and_keeps_one_closure(monkeypatch):
    far = [_line((600.0 + i, 600.0), (600.0 + i, 640.0)) for i in range(40)]
    rows = [*_room(), *far]
    monkeypatch.setattr(tracer, "_PRIMITIVE_CAP", 45)  # both viewports together exceed it; each one alone does not
    views = ((80.0, 80.0, 320.0, 270.0), (590.0, 590.0, 660.0, 660.0))
    result = _trace(rows, source_owned_doorway_chords=[_chord()], viewport_pdf_pts=views)
    assert len(_chord_closures(result)) == 1 and len(_candidates(result)) == 1


# ------------------------------------------------------------------------------------------------ the preview and the runner

def _write_scene_pdf(path, rows):
    doc = fitz.open()
    page = doc.new_page(width=800, height=400)
    for row in rows:
        shape = page.new_shape()
        for item in row["items"]:
            if item[0] == "l":
                shape.draw_line(item[1], item[2])
            else:
                shape.draw_rect(item[1])
        shape.finish(fill=row["fill"], color=row["color"], width=row["width"] or 0.0)
        shape.commit()
    doc.save(path)
    doc.close()
    return path


def _digest(summary):
    return {k: v for k, v in summary.items() if k != KEY}


@pytest.fixture(scope="module")
def scene_pdf(tmp_path_factory):
    return _write_scene_pdf(tmp_path_factory.mktemp("chord_closures") / "scene.pdf", _room())


def test_with_the_switch_off_there_is_no_new_key(scene_pdf):
    summary, _png = canonical.source_native_trace_preview(scene_pdf, 0)
    assert KEY not in summary


def test_the_switch_passes_the_channels_chords_to_the_tracer_and_marks_the_applied_ones(scene_pdf, monkeypatch):
    seen = {}
    real = canonical.build_layered_wall_doorway_room_rings

    def spy(*args, **kwargs):
        seen["chords"] = kwargs["source_owned_doorway_chords"]
        return real(*args, **kwargs)

    block = {"chords": [_chord(), _chord(lo=600.0, hi=630.0, band=(10.0, 16.0))], "chord_count": 2}
    monkeypatch.setattr(canonical, "build_layered_wall_doorway_room_rings", spy)
    monkeypatch.setattr(canonical, "_source_owned_doorway_chord_shadow_block", lambda rows, **kw: copy.deepcopy(block))
    off, off_png = canonical.source_native_trace_preview(scene_pdf, 0)
    assert seen["chords"] == ()
    on, on_png = canonical.source_native_trace_preview(scene_pdf, 0, source_owned_doorway_chord_closures=True)
    assert len(seen["chords"]) == 2
    assert on[KEY]["applied_count"] == 2 and on[KEY]["applied_to_preview_topology"] is True
    assert on[KEY]["preview_rings_and_closures_unchanged"] is False
    assert all(c["applied_to_preview_topology"] for c in on[KEY]["chords"])
    assert on["temporary_opening_closures"] == off["temporary_opening_closures"] + 2
    assert on_png != off_png


def test_with_no_chords_the_switch_changes_only_its_own_key(scene_pdf, monkeypatch):
    monkeypatch.setattr(canonical, "_source_owned_doorway_chord_shadow_block", lambda rows, **kw: {"chords": [], "chord_count": 0})
    off, off_png = canonical.source_native_trace_preview(scene_pdf, 0)
    on, on_png = canonical.source_native_trace_preview(scene_pdf, 0, source_owned_doorway_chord_closures=True)
    assert on_png == off_png and _digest(on) == off
    assert on[KEY]["applied_count"] == 0 and on[KEY]["preview_rings_and_closures_unchanged"] is True


@pytest.mark.parametrize("bad", [1, 0, None, "yes"])
def test_the_switch_must_be_a_real_boolean(bad):
    with pytest.raises(ValueError, match="new_trace_source_owned_doorway_chord_closures_must_be_bool"):
        canonical.source_native_trace_preview("missing.pdf", 0, source_owned_doorway_chord_closures=bad)


def test_the_read_only_channel_and_the_closures_cannot_be_combined(scene_pdf):
    with pytest.raises(ValueError, match="new_trace_doorway_chord_shadow_and_closures_are_exclusive"):
        canonical.source_native_trace_preview(
            scene_pdf, 0, source_owned_doorway_chord_shadow=True, source_owned_doorway_chord_closures=True,
        )


def _good_block(sha, page_index, *, applied=True):
    return {
        "source_sha256": sha, "page_index": page_index, "chord_count": 1, "applied_count": int(applied),
        "applied_to_preview_topology": applied, "preview_rings_and_closures_unchanged": not applied,
        "quantity_authorized": False, "commercial_publishable": False,
        "chords": [_chord(applied_to_preview_topology=applied)],
    }


def test_the_runner_accepts_an_honest_closure_block():
    sha = hashlib.sha256(b"x").hexdigest()
    for applied in (True, False):
        runner.validate_doorway_chord_closures(_good_block(sha, 0, applied=applied), expected_source_sha256=sha, expected_page_index=0)


@pytest.mark.parametrize("mutate", [
    lambda b: b.update(source_sha256="0" * 64), lambda b: b.update(page_index=1), lambda b: b.update(quantity_authorized=True),
    lambda b: b.update(commercial_publishable=True), lambda b: b.update(applied_count=0), lambda b: b.update(chords=None),
    lambda b: b["chords"][0].update(metric_area_issued=True),
    lambda b: b["chords"][0].update(source_physical_door_host_authenticated=True),
])
def test_the_runner_fails_closed_on_a_wrong_or_authority_claiming_closure_block(mutate):
    sha = hashlib.sha256(b"x").hexdigest()
    block = _good_block(sha, 0)
    mutate(block)
    with pytest.raises(runner.WrongTraceRoute):
        runner.validate_doorway_chord_closures(block, expected_source_sha256=sha, expected_page_index=0)


def _runner_summary(sha, page_index, block):
    return {
        "source_sha256": sha, "page_index": page_index, "producer": runner.EXPECTED_PRODUCER,
        "legacy_envelope_used": False, "legacy_fallback_allowed": False, "quantity_authorized": False,
        "commercial_publishable": False,
        "stage_order": ("attempt_source_native_exterior_wall_trace_first", "trace_source_native_internal_wall_candidates"),
        "external_wall_trace_status": "CANDIDATE",
        "external_wall_trace_reason": "source_closed_painted_wall_ring_needs_exterior_role_authentication",
        "external_wall_native_source_paths": [10, 11], KEY: block,
    }


def test_the_runner_asks_for_closures_and_records_the_validated_block(tmp_path, monkeypatch):
    pdf = tmp_path / "original.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    head = "b" * 40
    monkeypatch.setattr(runner, "_git_head", lambda _repo: head)
    seen = {}

    def stub(path, page_index, **kwargs):
        seen.update(kwargs)
        return _runner_summary(sha, page_index, _good_block(sha, page_index)), runner.PNG_SIGNATURE

    monkeypatch.setitem(sys.modules, "pb_new_source_trace_preview", SimpleNamespace(source_native_trace_preview=stub))
    kwargs = {"page_index": 0, "expected_source_sha256": sha, "expected_head_sha": head, "repo_root": tmp_path}
    receipt = json.loads(runner.run_preview(pdf, out_dir=tmp_path / "one", doorway_chord_closures=True, **kwargs)
                         .read_text(encoding="utf-8"))
    assert seen == {"source_owned_doorway_chord_closures": True}
    assert receipt["doorway_chord_closures_requested"] is True and receipt["full_preview_summary"][KEY]["applied_count"] == 1
    with pytest.raises(runner.WrongTraceRoute, match="exclusive"):
        runner.run_preview(pdf, out_dir=tmp_path / "two", doorway_chord_closures=True, doorway_chord_shadow=True, **kwargs)
    with pytest.raises(runner.WrongTraceRoute, match="doorway_chord_closures_must_be_bool"):
        runner.run_preview(pdf, out_dir=tmp_path / "three", doorway_chord_closures=1, **kwargs)
    assert not (tmp_path / "two").exists() and not (tmp_path / "three").exists()


@pytest.mark.parametrize("argv_extra,expected", [([], False), (["--with-doorway-chord-closures"], True)])
def test_the_command_line_option_reaches_run_preview(tmp_path, monkeypatch, argv_extra, expected):
    seen = {}

    def fake_run_preview(pdf, **kwargs):
        seen.update(kwargs)
        return tmp_path / "receipt.json"

    monkeypatch.setattr(runner, "run_preview", fake_run_preview)
    argv = ["--pdf", str(tmp_path / "x.pdf"), "--page-index", "2", "--source-sha256", "a" * 64, "--expected-head-sha", "b" * 40,
            "--out-dir", str(tmp_path / "out"), "--purpose", "preview", *argv_extra]
    assert runner.main(argv) == 0
    assert seen["doorway_chord_closures"] is expected and seen["doorway_chord_shadow"] is False
