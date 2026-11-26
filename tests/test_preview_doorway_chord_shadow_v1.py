"""P2c: a default-off shadow channel that reports source-owned doorway chords beside the canonical preview.

Synthetic only; no private source. The canonical preview does not run the layered module's ring builder: it calls a separate fork
that has no merged-face collector, no segmented-swing producer and no chord fields. ``source_owned_doorway_chord_shadow`` runs the
layered dark-painted builder on the rows the preview already scoped and reports its witnesses and chords as counts plus
topology-only receipts. ``source_native_trace_preview(..., source_owned_doorway_chord_shadow=True)`` adds that block as ONE summary
key and changes nothing else: the preview's rings, closures, strips, PNG and every other key are identical, and with the flag off
the whole output is byte-identical. Nothing here is a wall, an opening, a closure, a quantity or a score.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import random
import sys
from types import SimpleNamespace

import fitz
import pytest

import pb_layered_wall_doorway_room_ring_shadow as layered
import pb_new_source_trace_preview as canonical
import pb_source_owned_doorway_chord_preview_shadow as shadow
from pb_new_raster_source_wall_trace import RasterSourceSegmentTrace
from pb_new_typed_vector_ink_scope import scope_outlined_vector_lettering
from pb_source_owned_doorway_chord_preview_shadow import source_owned_doorway_chord_shadow
from tools import run_canonical_source_native_preview as runner

SHA = "ab" * 32
BLACK = (0.0, 0.0, 0.0)
KEY = "source_owned_doorway_chord_shadow"
AUTHORITY_FLAGS = ("source_physical_door_host_authenticated", "metric_area_issued", "commercial_publishable")


def _stroke(a, b, width=0.5):
    return {"layer": "", "fill": None, "color": BLACK, "width": width, "items": [("l", fitz.Point(*a), fitz.Point(*b))]}


def _scene(width=23.0, *, lo=100.0, y0=43.0, vertical=False, dx=0.0, dy=0.0, drop_jamb=False, dashed=False):
    """A wall with one doorway drawn the way the ring builder reads it: two faces each side, two jambs, the nine chord strokes of a
    quarter-circle swing about the hinge at ``hi`` and the radial leaf. A 23 pt doorway keeps its chord with or without the door-ink
    exclusion of P3b (its leaf and jamb are too short to merge into a wall strip), so these tests hold on either tree. With
    ``dashed`` the swing is replaced by a straight dashed line of the same number of strokes (a look-alike, not a swing)."""
    hi = lo + width

    def pt(along, across):
        x, y = (across, along) if vertical else (along, across)
        return (x + dx, y + dy)

    rows = []
    for across in (y0 - 3.0, y0 + 3.0):
        rows.append(_stroke(pt(lo - 100.0, across), pt(lo, across)))
        rows.append(_stroke(pt(hi, across), pt(hi + 148.0, across)))
    rows.append(_stroke(pt(lo, y0 - 3.0), pt(lo, y0 + 3.0)))
    if not drop_jamb:
        rows.append(_stroke(pt(hi, y0 - 3.0), pt(hi, y0 + 3.0)))
    if dashed:
        for k in range(9):
            rows.append(_stroke(pt(lo + 2.4 * k, y0 + 12.0), pt(lo + 2.4 * k + 2.0, y0 + 12.0)))
        return rows
    pts = [pt(hi - width * math.cos(math.radians(10 * k)), y0 + width * math.sin(math.radians(10 * k))) for k in range(10)]
    for a, b in zip(pts, pts[1:]):
        rows.append(_stroke(a, b))
    rows.append(_stroke(pt(hi, y0), pt(hi, y0 + width)))
    return rows


def _direct(rows, *, page_index=0, source_sha256=SHA):
    return layered.build_layered_wall_doorway_room_rings(
        rows, source_sha256=source_sha256, page_index=page_index, dark_painted_wall_source=True, door_jamb_returns=True,
    )


def _block(rows, **kw):
    kw.setdefault("source_sha256", SHA)
    kw.setdefault("page_index", 0)
    return source_owned_doorway_chord_shadow(rows, **kw)


# ------------------------------------------------------------------------------------------------ the pure function

@pytest.mark.parametrize("scene_kw", [
    {}, {"vertical": True}, {"dx": 37.5, "dy": -21.25}, {"width": 52.08}, {"width": 138.0, "vertical": True}, {"drop_jamb": True},
    {"dashed": True},
])
def test_the_block_reports_exactly_what_a_direct_layered_builder_call_returns(scene_kw):
    rows = _scene(**scene_kw)
    direct, block = _direct(rows), _block(rows)
    assert block["builder_status"] == direct.status.value and block["builder_reason_codes"] == list(direct.reason_codes)
    assert block["swing_witness_count"] == len(direct.source_segmented_swing_witnesses)
    assert block["chord_count"] == len(direct.source_owned_doorway_chords) == len(block["chords"])
    assert block["witnesses_without_chord_count"] == block["swing_witness_count"] - block["chord_count"]
    mapped = [(c["horizontal"], tuple(c["door_interval_pdf_pts"]), tuple(c["wall_band_pdf_pts"]), tuple(c["source_swing_native_path_indices"]))
              for c in block["chords"]]
    expected = sorted((c["horizontal"], tuple(c["door_interval_pdf_pts"]), tuple(c["wall_band_pdf_pts"]), tuple(c["source_swing_native_path_indices"]))
                      for c in direct.source_owned_doorway_chords)
    assert mapped == expected


def test_a_23_pt_doorway_gives_one_chord_and_every_authority_flag_stays_false():
    block = _block(_scene())
    assert block["swing_witness_count"] == 1 and block["chord_count"] == 1 and block["witnesses_without_chord_count"] == 0
    (chord,) = block["chords"]
    assert chord["horizontal"] is True and chord["door_interval_pdf_pts"] == pytest.approx([100.0, 123.0], abs=0.02)
    assert chord["candidate_topology_doorway_closure"] is True and chord["applied_to_preview_topology"] is False
    for flag in AUTHORITY_FLAGS:
        assert chord[flag] is False, flag
    assert block["applied_to_preview_topology"] is False and block["preview_rings_and_closures_unchanged"] is True
    assert block["quantity_authorized"] is False and block["commercial_publishable"] is False
    assert block["builder_called"] is True and block["source_sha256"] == SHA and block["page_index"] == 0
    assert chord["receipt_id"].startswith("source_owned_doorway_chord_shadow_") and len(chord["receipt_id"]) == len("source_owned_doorway_chord_shadow_") + 24


def test_receipt_ids_carry_the_source_page_and_door_and_replay_exactly():
    rows = _scene()
    first, second = _block(rows), _block(rows)
    assert first == second and json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    base = first["chords"][0]["receipt_id"]
    assert _block(rows, page_index=1)["chords"][0]["receipt_id"] != base
    assert _block(rows, source_sha256="cd" * 32)["chords"][0]["receipt_id"] != base
    assert _block(_scene(lo=400.0))["chords"][0]["receipt_id"] != base
    assert _block(_scene(vertical=True))["chords"][0]["receipt_id"] != base


def test_the_block_never_mutates_the_rows():
    rows = _scene()
    before = copy.deepcopy(rows)
    _block(rows)
    assert rows == before


def test_an_unsupported_door_is_a_counted_witness_without_a_chord():
    block = _block(_scene(drop_jamb=True))
    assert block["swing_witness_count"] == 1 and block["chord_count"] == 0 and block["witnesses_without_chord_count"] == 1
    assert block["chords"] == []


def test_a_dashed_straight_line_is_not_a_swing():
    block = _block(_scene(dashed=True))
    assert block["swing_witness_count"] == 0 and block["chord_count"] == 0


def test_no_wall_ink_and_the_structural_cap_abstain_with_the_builders_own_reason(monkeypatch):
    block = _block([])
    assert block["builder_status"] == "abstained" and block["builder_reason_codes"] == [layered.REASON_NO_WALL_INK]
    assert block["chord_count"] == 0 and block["builder_called"] is True
    monkeypatch.setattr(layered, "structural_native_primitive_count", lambda rows: 20_001)
    capped = _block(_scene())
    assert capped["builder_status"] == "abstained" and capped["builder_reason_codes"] == [layered.REASON_UNLABELLED_SOURCE_PRIMITIVE_CAP]
    assert capped["chord_count"] == 0 and capped["swing_witness_count"] == 0


def test_a_page_whose_native_vectors_are_not_architectural_never_reaches_the_builder(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("the layered builder must not run on a raster underlay page")

    monkeypatch.setattr(shadow, "_build_layered_rings", refuse)
    block = _block(_scene(), native_vector_rows_architectural=False)
    assert block["builder_called"] is False and block["builder_status"] == "abstained"
    assert block["builder_reason_codes"] == [shadow.REASON_NATIVE_VECTORS_NOT_ARCHITECTURAL]
    assert block["chord_count"] == 0 and block["swing_witness_count"] == 0 and block["chords"] == []
    assert block["applied_to_preview_topology"] is False and block["quantity_authorized"] is False


@pytest.mark.parametrize("kwargs,error", [
    ({"source_sha256": "short"}, "source_sha256"),
    ({"page_index": -1}, "page_index"),
    ({"viewport_pdf_pts": [(0.0, 0.0, 1.0)]}, "viewport_pdf_pts"),
])
def test_the_raster_path_validates_its_inputs_too(monkeypatch, kwargs, error):
    monkeypatch.setattr(shadow, "_build_layered_rings", lambda *a, **k: pytest.fail("the builder must not run"))
    with pytest.raises(ValueError, match=error):
        _block(_scene(), native_vector_rows_architectural=False, **kwargs)


@pytest.mark.parametrize("kwargs,error", [
    ({"source_sha256": "short"}, "source_sha256"),
    ({"source_sha256": "AB" * 32}, "source_sha256"),
    ({"page_index": -1}, "page_index"),
    ({"page_index": True}, "page_index"),
    ({"native_vector_rows_architectural": "yes"}, "native_vector_rows_architectural"),
])
def test_inputs_are_validated_before_anything_runs(kwargs, error):
    with pytest.raises(ValueError, match=error):
        _block(_scene(), **kwargs)


def test_translation_and_axis_swap_keep_the_chord_and_move_or_turn_it():
    base = _block(_scene())["chords"][0]
    moved = _block(_scene(dx=37.5, dy=-21.25))["chords"][0]
    turned = _block(_scene(vertical=True))["chords"][0]
    assert moved["horizontal"] is True and moved["door_interval_pdf_pts"] == pytest.approx([base["door_interval_pdf_pts"][0] + 37.5, base["door_interval_pdf_pts"][1] + 37.5], abs=0.02)
    assert turned["horizontal"] is False and turned["door_interval_pdf_pts"] == pytest.approx(base["door_interval_pdf_pts"], abs=0.02)


def test_unrelated_leading_rows_shift_the_indices_and_the_order_of_the_wall_rows_does_not_matter():
    plain = _block(_scene())["chords"][0]
    lead = [_stroke((5000.0, 5000.0), (5000.0, 5000.5))] * 25
    shifted = _block(lead + _scene())["chords"][0]
    assert shifted["door_interval_pdf_pts"] == plain["door_interval_pdf_pts"]
    assert shifted["source_swing_native_path_indices"] == [i + 25 for i in plain["source_swing_native_path_indices"]]
    rows = _scene()
    head, tail = rows[:6], rows[6:]
    for seed in range(5):
        permuted = list(head)
        random.Random(seed).shuffle(permuted)
        got = _block(permuted + tail)
        assert got["chord_count"] == 1 and got["chords"][0]["door_interval_pdf_pts"] == pytest.approx(plain["door_interval_pdf_pts"], abs=1e-6)


@pytest.mark.parametrize("viewports,inside", [
    (None, None),
    ([(0.0, 0.0, 400.0, 300.0)], True),
    ([(0.0, 0.0, 110.0, 300.0)], False),                                         # cuts through the doorway
    ([(0.0, 0.0, 50.0, 50.0), (80.0, 20.0, 400.0, 300.0)], True),               # the door lies inside the second box
    ([(0.0, 100.0, 400.0, 300.0)], False),                                        # the wall band is outside
])
def test_each_chord_says_whether_it_lies_inside_the_requested_viewport(viewports, inside):
    (chord,) = _block(_scene(), viewport_pdf_pts=viewports)["chords"]
    assert chord["inside_requested_viewport"] is inside


def test_viewport_boxes_are_normalised_validated_and_tested_on_their_edges():
    (chord,) = _block(_scene())["chords"]
    x0, y0, x1, y1 = chord["door_interval_pdf_pts"][0], chord["wall_band_pdf_pts"][0], chord["door_interval_pdf_pts"][1], chord["wall_band_pdf_pts"][1]
    exact = (x0, y0, x1, y1)
    assert _block(_scene(), viewport_pdf_pts=[exact])["chords"][0]["inside_requested_viewport"] is True       # an edge counts as inside
    for shrunk in ((x0 + 0.001, y0, x1, y1), (x0, y0 + 0.001, x1, y1), (x0, y0, x1 - 0.001, y1), (x0, y0, x1, y1 - 0.001)):
        assert _block(_scene(), viewport_pdf_pts=[shrunk])["chords"][0]["inside_requested_viewport"] is False
    reversed_box = (400.0, 300.0, 0.0, 0.0)                                                                    # corners given the other way round
    assert _block(_scene(), viewport_pdf_pts=[reversed_box])["chords"][0]["inside_requested_viewport"] is True
    assert _block(_scene(), viewport_pdf_pts=[])["chords"][0]["inside_requested_viewport"] is False
    assert _block(_scene(), viewport_pdf_pts=[reversed_box])["viewport_pdf_pts"] == [[0.0, 0.0, 400.0, 300.0]]
    for bad in ([(0.0, 0.0, float("nan"), 5.0)], [(0.0, 0.0, 5.0)], [(0.0, 0.0, 1.0, 2.0, 3.0)], [(0.0, 0.0, float("inf"), 5.0)]):
        with pytest.raises(ValueError, match="viewport_pdf_pts"):
            _block(_scene(), viewport_pdf_pts=bad)


def test_chords_are_ordered_by_their_interval_whatever_the_order_of_the_rows():
    reverse = _block(_scene(lo=400.0) + _scene(lo=100.0))["chords"]
    forward = _block(_scene(lo=100.0) + _scene(lo=400.0))["chords"]
    assert [c["door_interval_pdf_pts"] for c in reverse] == [c["door_interval_pdf_pts"] for c in forward]
    assert [c["door_interval_pdf_pts"][0] for c in forward] == pytest.approx([100.0, 400.0], abs=0.02)


def test_the_receipt_id_also_depends_on_the_wall_band_and_the_swing_path_ids():
    base = _block(_scene())["chords"][0]["receipt_id"]
    assert _block(_scene(y0=143.0))["chords"][0]["receipt_id"] != base                      # another wall line
    lead = [_stroke((5000.0, 5000.0), (5000.0, 5000.5))] * 7
    assert _block(lead + _scene())["chords"][0]["receipt_id"] != base                        # same door, other native path ids


def test_the_layered_builder_is_called_on_the_dark_painted_path_and_nothing_else_is_switched_on(monkeypatch):
    seen = {}
    real = shadow._build_layered_rings

    def spy(rows, **kwargs):
        seen.update(kwargs)
        return real(rows, **kwargs)

    monkeypatch.setattr(shadow, "_build_layered_rings", spy)
    _block(_scene(), page_index=3)
    assert seen == {"source_sha256": SHA, "page_index": 3, "dark_painted_wall_source": True, "door_jamb_returns": True}


@pytest.mark.parametrize("style", ["true", "missing", "none", "zero"])
@pytest.mark.parametrize("flag", AUTHORITY_FLAGS)
def test_an_upstream_chord_that_claims_or_omits_authority_makes_the_block_abstain_instead_of_echoing_it(monkeypatch, flag, style):
    claim = dict(_direct(_scene()).source_owned_doorway_chords[0])
    if style == "missing":
        del claim[flag]
    else:
        claim[flag] = {"true": True, "none": None, "zero": 0}[style]
    fake = SimpleNamespace(status=SimpleNamespace(value="candidate"), reason_codes=("fake",), source_segmented_swing_witnesses=(object(),),
                           source_owned_doorway_chords=(claim,))
    monkeypatch.setattr(shadow, "_build_layered_rings", lambda *a, **k: fake)
    block = _block(_scene())
    assert block["builder_status"] == "abstained" and block["builder_reason_codes"] == [shadow.REASON_UPSTREAM_CHORD_CLAIMS_AUTHORITY]
    assert block["chord_count"] == 0 and block["chords"] == [] and block["builder_called"] is True and block["swing_witness_count"] == 1


# ------------------------------------------------------------------------------------------------ the preview integration

def _write_scene_pdf(path, rows, *, width=800, height=400):
    document = fitz.open()
    page = document.new_page(width=width, height=height)
    for row in rows:
        a, b = row["items"][0][1], row["items"][0][2]
        shape = page.new_shape()
        shape.draw_line(a, b)
        shape.finish(color=BLACK, width=0.5, closePath=False)
        shape.commit()
    document.save(str(path))
    document.close()
    return path


@pytest.fixture(scope="module")
def scene_pdf(tmp_path_factory):
    return _write_scene_pdf(tmp_path_factory.mktemp("p2c") / "scene.pdf", _scene())


@pytest.fixture(scope="module")
def previews(scene_pdf):
    off, off_png = canonical.source_native_trace_preview(scene_pdf, 0)
    explicit, explicit_png = canonical.source_native_trace_preview(scene_pdf, 0, source_owned_doorway_chord_shadow=False)
    on, on_png = canonical.source_native_trace_preview(scene_pdf, 0, source_owned_doorway_chord_shadow=True)
    return SimpleNamespace(off=off, off_png=off_png, explicit=explicit, explicit_png=explicit_png, on=on, on_png=on_png)


def _digest(summary):
    return hashlib.sha256(json.dumps(summary, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def test_with_the_flag_off_the_summary_has_no_shadow_key_and_the_call_is_byte_identical(previews):
    assert KEY not in previews.off and KEY not in previews.explicit
    assert _digest(previews.off) == _digest(previews.explicit) and previews.off_png == previews.explicit_png


def test_with_the_flag_on_exactly_one_key_is_added_and_everything_else_is_identical(previews):
    assert KEY in previews.on and set(previews.on) - set(previews.off) == {KEY} and set(previews.off) <= set(previews.on)
    assert list(previews.on)[-1] == KEY                                           # appended after every existing key
    assert {k: v for k, v in previews.on.items() if k != KEY} == previews.off
    assert previews.on_png == previews.off_png                                    # the overlay is untouched
    for key in ("candidate_enclosed_regions", "temporary_opening_closures", "wall_strip_count", "wall_gap_count", "status", "reason_codes",
                "quantity_authorized", "commercial_publishable"):
        assert previews.on[key] == previews.off[key], key


def test_the_summary_block_equals_a_direct_call_on_the_rows_the_preview_scoped(scene_pdf, previews):
    with fitz.open(str(scene_pdf)) as document:
        page = document[0]
        scoped = scope_outlined_vector_lettering(page, page.get_drawings()).drawings
    sha = hashlib.sha256(scene_pdf.read_bytes()).hexdigest()
    expected = source_owned_doorway_chord_shadow(scoped, source_sha256=sha, page_index=0, viewport_pdf_pts=None, native_vector_rows_architectural=True)
    assert previews.on[KEY] == expected
    assert expected["chord_count"] == 1 and expected["swing_witness_count"] == 1 and expected["builder_called"] is True
    assert expected["source_sha256"] == previews.on["source_sha256"]


@pytest.mark.parametrize("bad", [1, 0, "True", None, 1.0])
def test_the_flag_must_be_a_real_boolean_and_is_checked_before_the_pdf_is_read(bad):
    with pytest.raises(ValueError, match="source_owned_doorway_chord_shadow_must_be_bool"):
        canonical.source_native_trace_preview("never_opened.pdf", 0, source_owned_doorway_chord_shadow=bad)


def test_the_block_reads_the_rows_after_the_preview_scoped_them_not_the_raw_page(scene_pdf, monkeypatch):
    with fitz.open(str(scene_pdf)) as document:
        raw = document[0].get_drawings()
    without_the_swing = [row for row in raw if not (len(row["items"]) == 1 and row["items"][0][0] == "l"
                                                   and math.dist((row["items"][0][1].x, row["items"][0][1].y), (row["items"][0][2].x, row["items"][0][2].y)) < 12.0
                                                   and row["items"][0][1].x > 100.0 and row["items"][0][1].y > 43.0)]
    assert len(without_the_swing) < len(raw)
    scope = SimpleNamespace(drawings=without_the_swing, applied=True, reason="test", original_paths=len(raw), discarded_simple_stroke_paths=0,
                            native_line_segments=0, kept_line_segments=0)
    monkeypatch.setattr(canonical, "scope_outlined_vector_lettering", lambda page, drawings: scope)
    summary, _png = canonical.source_native_trace_preview(scene_pdf, 0, source_owned_doorway_chord_shadow=True)
    assert summary[KEY]["swing_witness_count"] == 0 and summary[KEY]["chord_count"] == 0


def test_a_requested_viewport_is_recorded_and_flagged_on_each_chord(scene_pdf):
    inside, _ = canonical.source_native_trace_preview(scene_pdf, 0, viewport_pdf_pts=(0.0, 0.0, 800.0, 400.0), source_owned_doorway_chord_shadow=True)
    outside, _ = canonical.source_native_trace_preview(scene_pdf, 0, viewport_pdf_pts=(500.0, 0.0, 800.0, 400.0), source_owned_doorway_chord_shadow=True)
    assert inside[KEY]["viewport_pdf_pts"] == [[0.0, 0.0, 800.0, 400.0]] and inside[KEY]["chords"][0]["inside_requested_viewport"] is True
    assert outside[KEY]["chords"][0]["inside_requested_viewport"] is False


def test_a_raster_underlay_page_reports_an_abstained_block_and_the_builder_is_not_called(scene_pdf, monkeypatch):
    modality = SimpleNamespace(route="tiled_raster_underlay", reason="test", raster_unique_xrefs=(), to_dict=lambda: {"route": "tiled_raster_underlay"})
    monkeypatch.setattr(canonical, "classify_source_page_modality", lambda page, vector_path_count: modality)
    monkeypatch.setattr(canonical, "trace_source_raster_wall_lines",
                        lambda page, source_page_index, source_raster_xrefs: RasterSourceSegmentTrace("ABSTAINED", "test", source_page_index, 0.0))
    calls = []
    real = shadow._build_layered_rings
    monkeypatch.setattr(shadow, "_build_layered_rings", lambda *a, **k: calls.append(1) or real(*a, **k))
    summary, _png = canonical.source_native_trace_preview(scene_pdf, 0, source_owned_doorway_chord_shadow=True)
    assert calls == []
    assert summary[KEY]["builder_called"] is False and summary[KEY]["builder_reason_codes"] == [shadow.REASON_NATIVE_VECTORS_NOT_ARCHITECTURAL]


# ------------------------------------------------------------------------------------------------ the canonical runner

def _runner_summary(sha, page_index, *, block=None):
    summary = {
        "source_sha256": sha, "page_index": page_index, "producer": runner.EXPECTED_PRODUCER,
        "legacy_envelope_used": False, "legacy_fallback_allowed": False, "quantity_authorized": False, "commercial_publishable": False,
        "stage_order": ("attempt_source_native_exterior_wall_trace_first", "trace_source_native_internal_wall_candidates"),
        "external_wall_trace_status": "CANDIDATE", "external_wall_trace_reason": "source_closed_painted_wall_ring_needs_exterior_role_authentication",
        "external_wall_native_source_paths": [10, 11],
    }
    if block is not None:
        summary[KEY] = block
    return summary


def _good_block(sha, page_index):
    return {
        "source_sha256": sha, "page_index": page_index, "builder_called": True, "chord_count": 0, "swing_witness_count": 0, "chords": [],
        "applied_to_preview_topology": False, "preview_rings_and_closures_unchanged": True, "quantity_authorized": False, "commercial_publishable": False,
    }


@pytest.fixture()
def runner_env(tmp_path, monkeypatch):
    pdf = tmp_path / "original.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    head = "b" * 40
    monkeypatch.setattr(runner, "_git_head", lambda _repo: head)
    seen = {}

    def install(stub):
        monkeypatch.setitem(sys.modules, "pb_new_source_trace_preview", SimpleNamespace(source_native_trace_preview=stub))

    return SimpleNamespace(pdf=pdf, sha=sha, head=head, out=tmp_path / "private", seen=seen, install=install, repo=tmp_path)


def _run(env, **kw):
    return runner.run_preview(env.pdf, page_index=0, expected_source_sha256=env.sha, expected_head_sha=env.head, out_dir=env.out, repo_root=env.repo, **kw)


def test_the_default_runner_call_is_unchanged_and_never_passes_the_flag(runner_env):
    def stub(path, page_index):                                                   # exactly the two-argument shape the runner always used
        return _runner_summary(runner_env.sha, page_index), runner.PNG_SIGNATURE

    runner_env.install(stub)
    receipt_path = _run(runner_env)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert "doorway_chord_shadow_requested" not in receipt and KEY not in receipt["full_preview_summary"]


def test_the_runner_passes_the_flag_and_records_the_validated_block(runner_env):
    def stub(path, page_index, **kwargs):
        runner_env.seen.update(kwargs)
        return _runner_summary(runner_env.sha, page_index, block=_good_block(runner_env.sha, page_index)), runner.PNG_SIGNATURE

    runner_env.install(stub)
    receipt = json.loads(_run(runner_env, doorway_chord_shadow=True).read_text(encoding="utf-8"))
    assert runner_env.seen == {"source_owned_doorway_chord_shadow": True}
    assert receipt["doorway_chord_shadow_requested"] is True and receipt["full_preview_summary"][KEY]["chord_count"] == 0


@pytest.mark.parametrize("what,mutate", [
    ("missing", lambda block: None),
    ("applied to the topology", lambda block: {**block, "applied_to_preview_topology": True}),
    ("quantity authorised", lambda block: {**block, "quantity_authorized": True}),
    ("commercial", lambda block: {**block, "commercial_publishable": True}),
    ("rings said to change", lambda block: {**block, "preview_rings_and_closures_unchanged": False}),
    ("wrong source", lambda block: {**block, "source_sha256": "0" * 64}),
    ("wrong page", lambda block: {**block, "page_index": 3}),
])
def test_the_runner_fails_closed_on_a_missing_or_authority_claiming_block(runner_env, what, mutate):
    def stub(path, page_index, **kwargs):
        block = mutate(_good_block(runner_env.sha, page_index))
        return _runner_summary(runner_env.sha, page_index, block=block), runner.PNG_SIGNATURE

    runner_env.install(stub)
    with pytest.raises(runner.WrongTraceRoute, match="doorway_chord_shadow"):
        _run(runner_env, doorway_chord_shadow=True)
    assert not runner_env.out.exists(), what                                      # no receipt is written


@pytest.mark.parametrize("flag", ["source_physical_door_host_authenticated", "metric_area_issued", "commercial_publishable", "applied_to_preview_topology"])
def test_the_runner_rejects_a_chord_that_claims_any_one_flag(runner_env, flag):
    clean = {"source_physical_door_host_authenticated": False, "metric_area_issued": False, "commercial_publishable": False,
             "applied_to_preview_topology": False}

    def stub(path, page_index, **kwargs):
        block = {**_good_block(runner_env.sha, page_index), "chords": [dict(clean), {**clean, flag: True}]}
        return _runner_summary(runner_env.sha, page_index, block=block), runner.PNG_SIGNATURE

    runner_env.install(stub)
    with pytest.raises(runner.WrongTraceRoute, match="doorway_chord_shadow_chord_claims_authority"):
        _run(runner_env, doorway_chord_shadow=True)


@pytest.mark.parametrize("what,chords", [("not a list", None), ("not a mapping", ["a chord"]), ("a number", 7)])
def test_the_runner_rejects_a_malformed_chord_list(runner_env, what, chords):
    def stub(path, page_index, **kwargs):
        block = {**_good_block(runner_env.sha, page_index), "chords": chords}
        return _runner_summary(runner_env.sha, page_index, block=block), runner.PNG_SIGNATURE

    runner_env.install(stub)
    with pytest.raises(runner.WrongTraceRoute, match="doorway_chord_shadow"):
        _run(runner_env, doorway_chord_shadow=True)


def test_the_runner_accepts_chords_that_claim_nothing(runner_env):
    clean = {"source_physical_door_host_authenticated": False, "metric_area_issued": False, "commercial_publishable": False,
             "applied_to_preview_topology": False}

    def stub(path, page_index, **kwargs):
        block = {**_good_block(runner_env.sha, page_index), "chords": [dict(clean), dict(clean)]}
        return _runner_summary(runner_env.sha, page_index, block=block), runner.PNG_SIGNATURE

    runner_env.install(stub)
    assert json.loads(_run(runner_env, doorway_chord_shadow=True).read_text(encoding="utf-8"))["doorway_chord_shadow_requested"] is True


def test_the_runner_flag_must_be_a_real_boolean(runner_env):
    runner_env.install(lambda path, page_index, **kw: (_runner_summary(runner_env.sha, page_index), runner.PNG_SIGNATURE))
    with pytest.raises(runner.WrongTraceRoute, match="doorway_chord_shadow_must_be_bool"):
        _run(runner_env, doorway_chord_shadow=1)


@pytest.mark.parametrize("argv_extra,expected", [([], False), (["--with-doorway-chord-shadow"], True)])
def test_the_command_line_option_reaches_run_preview(tmp_path, monkeypatch, argv_extra, expected):
    seen = {}

    def fake_run_preview(pdf, **kwargs):
        seen.update(kwargs)
        return tmp_path / "receipt.json"

    monkeypatch.setattr(runner, "run_preview", fake_run_preview)
    argv = ["--pdf", str(tmp_path / "x.pdf"), "--page-index", "2", "--source-sha256", "a" * 64, "--expected-head-sha", "b" * 40,
            "--out-dir", str(tmp_path / "out"), "--purpose", "preview", *argv_extra]
    assert runner.main(argv) == 0
    assert seen["doorway_chord_shadow"] is expected and seen["page_index"] == 2


def test_the_canonical_route_guard_still_passes_and_the_default_signature_is_unchanged():
    from pathlib import Path
    from scripts.check_canonical_trace_route import verify_route_contract
    verify_route_contract(Path(__file__).resolve().parents[1])
    import inspect
    parameters = inspect.signature(canonical.source_native_trace_preview).parameters
    assert parameters["source_owned_doorway_chord_shadow"].default is False
    assert parameters["source_owned_doorway_chord_shadow"].kind is inspect.Parameter.KEYWORD_ONLY
