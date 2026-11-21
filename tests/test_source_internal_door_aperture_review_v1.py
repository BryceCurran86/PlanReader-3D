"""Review-only binding of source-native internal door apertures to canonical opening records.

Synthetic geometry and stand-in detector receipts only. The module must retain every
representative, choose none, write no kind/host/area, and never carry authority.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import random
import re
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

import pb_source_internal_door_aperture_review as mod
from pb_original_window_canonical_representative_review import (
    _geometry_in_original_aperture,
)
from pb_source_internal_door_aperture_review import (
    CONTAINMENT_TOLERANCE_PT,
    InternalDoorApertureEntry,
    review_internal_door_apertures,
)
from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel
from tests.test_live_opening_area_quantity_publication import _opening
from tests.test_source_internal_door_completeness_shadow import _source_native_door
from tests.test_source_native_cavity_slider_jamb_shadow import _scene as _cavity_scene

SHA = "a" * 64  # the digest tests/test_live_opening_area_quantity_publication._opening carries
BOX = (100.0, 100.0, 130.0, 104.0)  # a stand-in hinged aperture box
FLAGS = (
    "physical_opening_authenticated", "kind_authorized", "host_authorized",
    "measurement_authorized", "customer_quantity_authorized", "frozen_benchmark_scored",
)


def _rec(name, geom, *, kind=None, wall=False, receipt=False, area=None, basis=None, **extra):
    return replace(
        _opening(canonical_id=name, kind=kind, area_m2=area, area_basis=basis),
        source_geometries=(tuple(float(v) for v in geom),),
        host_wall_id=("wall-" + name) if wall else None,
        host_binding_record_id=("bind-" + name) if receipt else None,
        host_frame_record_id=None,
        **extra,
    )


def _inside(name, x=110.0, **kw):
    return _rec(name, (x, 102.0, x + 5.0, 102.0), **kw)


def _stub(monkeypatch, *, hinged=(), sliders=()):
    marks, barriers, found = [], [], []
    for i, box in enumerate(hinged):
        marks.append(SimpleNamespace(
            kind="native_swing_arc_leaf", status="HOSTED_TOPOLOGY_ONLY",
            native_path_ids=(100 + i, 200 + i, 300 + i, 400 + i, 500 + i),
            source_word_index=None, label_width_mm=None,
        ))
        barriers.append(SimpleNamespace(swing_arc_path_id=100 + i, bounds_pdf_pts=box))
    for j, (interval, band, horizontal) in enumerate(sliders):
        marks.append(SimpleNamespace(
            kind="native_cavity_slider_callout", status="HOSTED_TOPOLOGY_ONLY",
            native_path_ids=(700 + j,), source_word_index=900 + j, label_width_mm=None,
        ))
        found.append(SimpleNamespace(
            cs_word_index=900 + j, clear_interval_pdf_pts=interval,
            band_pdf_pts=band, horizontal=horizontal,
        ))
    monkeypatch.setattr(mod, "inspect_source_internal_door_completeness",
                        lambda *a, **k: SimpleNamespace(marks=tuple(marks)))
    monkeypatch.setattr(mod, "detect_source_internal_swing_room_barriers", lambda *a, **k: tuple(barriers))
    monkeypatch.setattr(mod, "match_source_native_cavity_sliders", lambda *a, **k: tuple(found))


def _run(records, *, sha=SHA, page_index=2):
    return review_internal_door_apertures((), (), records, page_index=page_index, expected_source_sha256=sha)


# ---------------------------------------------------------------- positives

def test_every_contained_record_is_retained_and_none_is_chosen(monkeypatch):
    _stub(monkeypatch, hinged=[BOX])
    records = [_inside("c", 112), _inside("a", 104), _inside("b", 108)]
    entry = _run(records).entries[0]
    assert entry.state == mod.STATE_MULTIPLE
    assert entry.representative_ids == ("a", "b", "c")  # sorted ids, not nearest/first/smallest
    assert entry.first_open_gate == mod.GATE_KIND
    assert entry.printed_width_mm is None
    assert all(getattr(entry, flag) is False for flag in FLAGS)


def test_single_and_empty_apertures_are_reported_not_invented(monkeypatch):
    _stub(monkeypatch, hinged=[BOX, (200.0, 100.0, 230.0, 104.0)])
    entries = _run([_inside("only")]).entries
    states = sorted(e.state for e in entries)
    assert states == sorted([mod.STATE_SINGLE, mod.STATE_NO_REPRESENTATIVE])
    empty = next(e for e in entries if e.state == mod.STATE_NO_REPRESENTATIVE)
    assert empty.representative_ids == () and empty.first_open_gate == mod.GATE_NO_REPRESENTATIVE


def test_cavity_slider_box_is_clear_interval_by_band_in_both_orientations(monkeypatch):
    _stub(monkeypatch, sliders=[((40.0, 63.0), (100.0, 103.0), True), ((300.0, 340.0), (50.0, 53.0), False)])
    horizontal_hit = _rec("h", (45, 101.5, 60, 101.5))
    vertical_hit = _rec("v", (51.5, 310, 51.5, 330))
    swapped_miss = _rec("miss", (310, 51.5, 330, 51.5))
    entries = {e.native_path_ids: e for e in _run([horizontal_hit, vertical_hit, swapped_miss]).entries}
    assert entries[(700,)].representative_ids == ("h",)
    assert entries[(701,)].representative_ids == ("v",)


# ---------------------------------------------------------------- look-alike negatives

def test_records_outside_the_tolerance_or_spilling_out_are_not_bound(monkeypatch):
    _stub(monkeypatch, hinged=[BOX])
    edge = CONTAINMENT_TOLERANCE_PT
    just_in = _rec("in", (100 - edge, 100, 100 - edge, 104))
    just_out = _rec("out", (100 - edge - 0.5, 100, 100 - edge - 0.5, 104))
    spill = _rec("spill", (110, 102, 400, 102))  # runs far beyond the box
    far = _rec("far", (500, 500, 505, 500))
    entry = _run([just_in, just_out, spill, far]).entries[0]
    assert entry.representative_ids == ("in",)


def test_record_with_a_geometry_outside_is_not_a_representative(monkeypatch):
    _stub(monkeypatch, hinged=[BOX])
    record = replace(_inside("two"), source_geometries=((110.0, 102.0, 115.0, 102.0), (900.0, 900.0, 905.0, 900.0)))
    assert _run([record]).entries[0].representative_ids == ()


@pytest.mark.parametrize("bad", [(), (float("nan"), 1.0, 2.0, 1.0), (1.0, 2.0, 3.0), ("a", "b", "c", "d")])
def test_malformed_geometry_never_binds(monkeypatch, bad):
    _stub(monkeypatch, hinged=[BOX])
    record = replace(_inside("bad"), source_geometries=(bad,) if bad else ())
    assert _run([record]).entries[0].representative_ids == ()


# ---------------------------------------------------------------- ambiguity and conflict

def test_a_record_inside_two_apertures_is_a_shared_conflict_for_both(monkeypatch):
    near = (131.0, 100.0, 160.0, 104.0)  # within the margin of BOX on its right edge
    _stub(monkeypatch, hinged=[BOX, near])
    between = _rec("between", (130.4, 102.0, 130.8, 102.0))
    review = _run([between, _inside("solo", 104)])
    assert review.records_shared_by_apertures == 1
    assert review.records_bound_to_an_aperture == 1
    for entry in review.entries:
        assert entry.shared_representative_ids == ("between",)
    left = next(e for e in review.entries if e.aperture_bounds_pdf_pts == BOX)
    right = next(e for e in review.entries if e.aperture_bounds_pdf_pts == near)
    assert left.state == mod.STATE_SHARED and left.representative_ids == ("solo",)
    assert right.state == mod.STATE_SHARED and right.first_open_gate == mod.GATE_SHARED


def test_a_window_kind_on_a_door_aperture_is_a_retained_conflict_not_a_decision(monkeypatch):
    _stub(monkeypatch, hinged=[BOX])
    entry = _run([_inside("w", 104, kind="window"), _inside("d", 112, kind="door")]).entries[0]
    assert entry.first_open_gate == mod.GATE_KIND_CONFLICT
    assert entry.kinds_on_representatives == ("door", "window")
    assert set(entry.representative_ids) == {"w", "d"}


def test_gate_order_is_kind_host_receipt_area_basis_then_issuer(monkeypatch):
    _stub(monkeypatch, hinged=[BOX])
    chain = [
        ({}, mod.GATE_KIND),
        ({"kind": "door"}, mod.GATE_HOST_WALL),
        ({"kind": "door", "wall": True}, mod.GATE_HOST_RECEIPT),
        ({"kind": "door", "wall": True, "receipt": True}, mod.GATE_AREA),
        ({"kind": "door", "wall": True, "receipt": True, "area": 1.5}, mod.GATE_BASIS),
        ({"kind": "door", "wall": True, "receipt": True, "area": 1.5, "basis": "figured_opening_label"}, mod.GATE_ISSUER),
    ]
    for fields, gate in chain:
        entry = _run([_inside("x", **fields)]).entries[0]
        assert entry.first_open_gate == gate
        assert all(getattr(entry, flag) is False for flag in FLAGS)
    # a non-positive or non-finite area is not an area
    for bad in (0.0, -1.0, float("nan"), float("inf")):
        entry = _run([_inside("x", kind="door", wall=True, receipt=True, area=bad)]).entries[0]
        assert entry.first_open_gate == mod.GATE_AREA


def test_a_symbol_without_a_unique_detector_box_is_reported_not_dropped(monkeypatch):
    _stub(monkeypatch, hinged=[BOX])
    marks = (
        SimpleNamespace(kind="native_swing_arc_leaf", status="NEEDS_HOST", native_path_ids=(9, 10),
                        source_word_index=None, label_width_mm=None),
        SimpleNamespace(kind="native_cavity_slider_callout", status="NEEDS_JAMB_WITNESS", native_path_ids=(),
                        source_word_index=12, label_width_mm=870),
    )
    monkeypatch.setattr(mod, "inspect_source_internal_door_completeness", lambda *a, **k: SimpleNamespace(marks=marks))
    entries = _run([_inside("x")]).entries
    assert [e.state for e in entries] == [mod.STATE_NO_APERTURE_BOX, mod.STATE_NO_APERTURE_BOX]
    assert all(e.first_open_gate == mod.GATE_NO_APERTURE_BOX and e.representative_ids == () for e in entries)
    assert {e.printed_width_mm for e in entries} == {None, 870}


def test_competing_detector_receipts_for_one_symbol_leave_it_without_a_box(monkeypatch):
    _stub(monkeypatch, hinged=[BOX], sliders=[((40.0, 63.0), (100.0, 103.0), True)])
    dup_barrier = SimpleNamespace(swing_arc_path_id=100, bounds_pdf_pts=(500.0, 500.0, 530.0, 504.0))
    dup_slider = SimpleNamespace(cs_word_index=900, clear_interval_pdf_pts=(900.0, 930.0),
                                 band_pdf_pts=(10.0, 13.0), horizontal=True)
    barriers = (SimpleNamespace(swing_arc_path_id=100, bounds_pdf_pts=BOX), dup_barrier)
    found = (SimpleNamespace(cs_word_index=900, clear_interval_pdf_pts=(40.0, 63.0),
                             band_pdf_pts=(100.0, 103.0), horizontal=True), dup_slider)
    monkeypatch.setattr(mod, "detect_source_internal_swing_room_barriers", lambda *a, **k: barriers)
    monkeypatch.setattr(mod, "match_source_native_cavity_sliders", lambda *a, **k: found)
    entries = _run([_inside("x", 104), _rec("y", (45, 101.5, 60, 101.5))]).entries
    assert [e.state for e in entries] == [mod.STATE_NO_APERTURE_BOX] * 2
    assert all(e.representative_ids == () for e in entries)


def test_entries_are_sorted_by_symbol_then_box_not_by_detector_order(monkeypatch):
    boxes = [(300.0, 100.0, 330.0, 104.0), (100.0, 100.0, 130.0, 104.0), (200.0, 100.0, 230.0, 104.0)]
    _stub(monkeypatch, hinged=boxes, sliders=[((40.0, 63.0), (100.0, 103.0), True)])
    entries = _run([]).entries
    assert [e.symbol_kind for e in entries] == ["cavity_slider"] + ["hinged_swing"] * 3
    assert [e.aperture_bounds_pdf_pts[0] for e in entries if e.symbol_kind == "hinged_swing"] == [100.0, 200.0, 300.0]


def test_kind_values_are_normalised_like_the_issuer_audit_and_counts_are_exact(monkeypatch):
    _stub(monkeypatch, hinged=[BOX])
    records = [
        _inside("a", 104, kind=" Door ", wall=True, receipt=True, area=1.5, basis="figured_opening_label"),
        _inside("b", 112, kind="DOOR", wall=True),
        _inside("c", 120, kind="skylight"),
        _inside("d", 124),
    ]
    entry = _run(records).entries[0]
    assert entry.kinds_on_representatives == ("door",)
    assert entry.representatives_with_door_kind == 2
    assert entry.representatives_with_host_wall == 2
    assert entry.representatives_with_host_receipt == 1
    assert entry.representatives_with_positive_area == 1
    assert entry.representatives_with_area_basis == 1
    assert entry.first_open_gate == mod.GATE_ISSUER


# ---------------------------------------------------------------- scope and refusals

def test_foreign_sha_page_records_are_excluded_and_counted(monkeypatch):
    _stub(monkeypatch, hinged=[BOX])
    good = _inside("good")
    foreign_sha = replace(_inside("sha", 104), source_sha256="b" * 64)
    wrong_page = replace(_inside("pg", 108), page_id="4")
    review = _run([good, foreign_sha, wrong_page])
    assert review.in_scope_record_count == 1 and review.out_of_scope_record_count == 2
    assert review.entries[0].representative_ids == ("good",)


def test_mixed_revision_or_snapshot_in_one_page_abstains(monkeypatch):
    _stub(monkeypatch, hinged=[BOX])
    for field in ("revision_id", "snapshot_id", "document_id"):
        mixed = [_inside("a", 104), replace(_inside("b", 108), **{field: "other"})]
        review = _run(mixed)
        assert review.status == mod.INTERNAL_DOOR_APERTURE_REVIEW_ABSTAINED
        assert review.reason_codes == (mod.REASON_MIXED_SCOPE,) and review.entries == ()


@pytest.mark.parametrize("bad_sha", ["", "A" * 64, "a" * 63, None, 5])
def test_the_full_lowercase_source_digest_is_required(monkeypatch, bad_sha):
    _stub(monkeypatch, hinged=[BOX])
    with pytest.raises(ValueError, match="full_original_source_sha256_required"):
        _run([_inside("x")], sha=bad_sha)


@pytest.mark.parametrize("bad_page", [-1, True, 2.0, "2"])
def test_page_index_must_be_a_real_non_negative_int(monkeypatch, bad_page):
    _stub(monkeypatch, hinged=[BOX])
    with pytest.raises(ValueError, match="page_index_must_be_a_non_negative_int"):
        _run([_inside("x")], page_index=bad_page)


def test_duplicate_or_foreign_objects_are_refused(monkeypatch):
    _stub(monkeypatch, hinged=[BOX])
    with pytest.raises(ValueError, match="duplicate_or_untrusted_canonical_opening"):
        _run([_inside("same", 104), _inside("same", 108)])
    with pytest.raises(ValueError, match="duplicate_or_untrusted_canonical_opening"):
        _run([object()])
    with pytest.raises(ValueError, match="duplicate_or_untrusted_canonical_opening"):
        _run([replace(_inside("x"), canonical_opening_id="")])


# ---------------------------------------------------------------- metamorphic and invariance

def _transform(point, kind):
    x, y = point
    return {
        "translate": (x + 123.5, y - 40.25),
        "rotate90": (-y, x),
        "mirror": (-x, y),
        "scale3": (x * 3.0, y * 3.0),
    }[kind]


def _box_after(box, kind):
    corners = [_transform(p, kind) for p in ((box[0], box[1]), (box[2], box[3]))]
    return (min(c[0] for c in corners), min(c[1] for c in corners),
            max(c[0] for c in corners), max(c[1] for c in corners))


def _geom_after(geom, kind):
    a, b = _transform((geom[0], geom[1]), kind), _transform((geom[2], geom[3]), kind)
    return (a[0], a[1], b[0], b[1])


@pytest.mark.parametrize("kind", ["translate", "rotate90", "mirror", "scale3"])
def test_decisions_survive_translation_rotation_mirror_and_scale(monkeypatch, kind):
    # margins are far from the tolerance, so the decision (not a number) is what must be invariant
    geoms = {"in1": (104, 101, 106, 101), "in2": (120, 103, 126, 103), "out": (160, 100, 165, 100)}
    records = [_rec(n, g) for n, g in geoms.items()]
    _stub(monkeypatch, hinged=[BOX])
    base = _run(records).entries[0]
    moved = [replace(r, source_geometries=(_geom_after(r.source_geometries[0], kind),)) for r in records]
    _stub(monkeypatch, hinged=[_box_after(BOX, kind)])
    after = _run(moved).entries[0]
    assert (after.representative_ids, after.state, after.first_open_gate) == (
        base.representative_ids, base.state, base.first_open_gate)
    assert base.representative_ids == ("in1", "in2")


def test_record_order_unrelated_content_and_viewport_expansion_do_not_change_entries(monkeypatch):
    _stub(monkeypatch, hinged=[BOX, (200.0, 100.0, 230.0, 104.0)])
    records = [_inside("a", 104, kind="door"), _inside("b", 112), _rec("far", (205, 102, 210, 102))]
    base = _run(records).entries
    shuffled = records[:]
    random.Random(7).shuffle(shuffled)
    assert _run(shuffled).entries == base
    rng = random.Random(11)
    noise = [_rec(f"noise{i}", (1000 + rng.random() * 500, 900 + rng.random() * 500,
                                1010 + rng.random() * 500, 900 + rng.random() * 500)) for i in range(40)]
    assert _run(records + noise).entries == base


def test_replay_is_deterministic_and_ids_depend_on_source_and_symbol(monkeypatch):
    _stub(monkeypatch, hinged=[BOX])
    records = [_inside("a", 104), _inside("b", 112)]
    first, second = _run(records), _run(records)
    assert first == second and first.to_dict() == second.to_dict()
    assert re.fullmatch(r"internal_door_aperture_[0-9a-f]{32}", first.entries[0].entry_id)
    other_page = review_internal_door_apertures((), (), records, page_index=3, expected_source_sha256=SHA)
    assert other_page.entries[0].entry_id != first.entries[0].entry_id


def test_inputs_are_never_mutated(monkeypatch):
    _stub(monkeypatch, hinged=[BOX])
    records = [_inside("a", 104), _inside("b", 112)]
    drawings, words = [{"rect": (1, 2, 3, 4)}], [(0, 0, 1, 1, "720", 0, 0, 0)]
    before = (copy.deepcopy(drawings), copy.deepcopy(words), copy.deepcopy(records))
    review_internal_door_apertures(drawings, words, records, page_index=2, expected_source_sha256=SHA)
    assert (drawings, words, records) == before


# ---------------------------------------------------------------- authority and hygiene

def test_an_entry_can_never_carry_authority():
    base = {
        "entry_id": "x", "symbol_kind": "hinged_swing", "mark_status": "HOSTED_TOPOLOGY_ONLY",
        "aperture_bounds_pdf_pts": None, "native_path_ids": (), "printed_width_mm": None,
        "representative_ids": (), "shared_representative_ids": (),
        "state": "NO_CANONICAL_REPRESENTATIVE", "kinds_on_representatives": (),
        "representatives_with_door_kind": 0, "representatives_with_host_wall": 0,
        "representatives_with_host_receipt": 0, "representatives_with_positive_area": 0,
        "representatives_with_area_basis": 0, "first_open_gate": "no_canonical_representative",
    }
    InternalDoorApertureEntry(**base)
    for flag in FLAGS:
        for value in (True, 1, "yes"):
            with pytest.raises(ValueError, match="cannot_carry_authority"):
                InternalDoorApertureEntry(**{**base, flag: value})


def test_serialised_review_states_every_flag_false_and_public_summary_has_counts_only(monkeypatch):
    _stub(monkeypatch, hinged=[BOX])
    review = _run([_inside("secret-id", 104), _inside("other-id", 112)])
    for payload in (review.to_dict(), review.to_public_summary(), review.entries[0].to_dict()):
        assert all(payload[flag] is False for flag in FLAGS)
    summary = repr(review.to_public_summary())
    assert "secret-id" not in summary and "native_path_ids" not in summary and "bounds" not in summary
    assert review.to_public_summary()["representatives_per_aperture"] == [2]


def test_no_production_module_imports_the_review():
    root = Path(__file__).resolve().parents[1]
    offenders = []
    for path in root.glob("*.py"):
        if path.name == "pb_source_internal_door_aperture_review.py":
            continue
        if "pb_source_internal_door_aperture_review" in path.read_text(encoding="utf-8", errors="ignore"):
            offenders.append(path.name)
    assert offenders == []


def test_module_source_has_no_project_sha_page_or_width_literal():
    text = (Path(mod.__file__)).read_text(encoding="utf-8")
    code = "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith("#")
    )
    tree = ast.parse(code)
    strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    numbers = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and type(n.value) in (int, float)]
    blob = " ".join(strings).lower()
    for banned in ("laurel", "lot16", "maryborough", "q5446", "acacia", "014e9f68"):
        assert banned not in blob
    assert not [s for s in strings if re.fullmatch(r"[0-9a-f]{40,64}", s)]
    assert not {720, 870, 1200, 2100, 2400} & {n for n in numbers if type(n) is int}


def test_containment_rule_matches_the_merged_window_review_for_single_segment_records():
    rng = random.Random(5)
    for _ in range(400):
        box = (rng.uniform(0, 50), rng.uniform(0, 50), 0.0, 0.0)
        box = (box[0], box[1], box[0] + rng.uniform(1, 40), box[1] + rng.uniform(1, 40))
        geom = tuple(rng.uniform(-5, 95) for _ in range(4))
        assert mod._record_inside((geom,), box) == _geometry_in_original_aperture((geom,), box)


# ---------------------------------------------------------------- real detectors on synthetic drawings

def test_real_hinged_detector_box_binds_a_contained_record_end_to_end():
    drawings = _source_native_door()
    inside = _rec("inside", (98.5, 22.0, 98.5, 44.0))
    outside = _rec("outside", (140.0, 22.0, 140.0, 44.0))
    review = review_internal_door_apertures(
        tuple(drawings), (), (inside, outside), page_index=2, expected_source_sha256=SHA)
    assert len(review.entries) == 1
    entry = review.entries[0]
    assert entry.symbol_kind == "hinged_swing" and entry.aperture_bounds_pdf_pts == (97.8, 18.8, 99.8, 46.2)
    assert entry.representative_ids == ("inside",) and entry.state == mod.STATE_SINGLE


def _with_fitz_points(drawings):
    """The cavity-slider scene uses plain tuples; the swing inventory reads fitz points and rects."""
    converted = []
    for row in drawings:
        row = dict(row)
        row["rect"] = fitz.Rect(*row["rect"]) if row.get("rect") is not None else None
        row["items"] = tuple(
            (item[0], *(fitz.Point(*p) for p in item[1:])) for item in row.get("items", ())
        )
        converted.append(row)
    return converted


def test_real_cavity_slider_detector_box_binds_a_contained_record_end_to_end():
    drawings, words = _cavity_scene()
    drawings = _with_fitz_points(drawings)
    inside = _rec("inside", (45.0, 101.5, 60.0, 101.5))
    review = review_internal_door_apertures(
        tuple(drawings), tuple(words), (inside,), page_index=2, expected_source_sha256=SHA)
    assert [e.symbol_kind for e in review.entries] == ["cavity_slider"]
    assert review.entries[0].printed_width_mm == 720
    assert review.entries[0].representative_ids == ("inside",)


def test_a_page_with_no_door_symbol_yields_an_empty_review_not_an_invented_one():
    review = review_internal_door_apertures((), (), (_inside("x"),), page_index=2, expected_source_sha256=SHA)
    assert review.status == mod.INTERNAL_DOOR_APERTURE_REVIEW_STATUS and review.entries == ()
    assert review.in_scope_record_count == 1 and review.records_bound_to_an_aperture == 0


# ---------------------------------------------------------------- original source (skipped without the private PDF)

def test_original_3laurel_page_3_door_apertures_are_listed_without_records():
    original = require_original_3laurel()
    raw = original.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ORIGINAL_SHA256
    with fitz.open(stream=raw, filetype="pdf") as document:
        drawings, words = tuple(document[2].get_drawings()), tuple(document[2].get_text("words"))
    review = review_internal_door_apertures((drawings)[:], words, (), page_index=2, expected_source_sha256=ORIGINAL_SHA256)
    summary = review.to_public_summary()
    assert summary["symbol_counts"] == {"cavity_slider": 6, "hinged_swing": 8}
    assert summary["state_counts"] == {mod.STATE_NO_REPRESENTATIVE: 14}
    assert all(entry.aperture_bounds_pdf_pts is not None for entry in review.entries)
    assert all(getattr(entry, flag) is False for entry in review.entries for flag in FLAGS)
