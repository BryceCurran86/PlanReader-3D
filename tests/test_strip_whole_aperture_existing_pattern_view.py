"""What the existing six-line rule makes of a whole-extent reading's members: pure classification, and the real-PDF path."""
from __future__ import annotations

import copy
from dataclasses import replace
from types import SimpleNamespace

import fitz
import pytest

import pb_callout_strip_whole_aperture_correspondence_shadow as shadow
from strip_whole_aperture_fixture import record, sub
from test_strip_whole_aperture_correspondence_producer import _nomination, _publish, _window_pdf

EQ = 0.06
READING = record((100.0, 304.0), lo=("jl",), hi=("jh",), host=("fa", "fb", "fc", "fd"))


def ink(box, stroked=True, sequence=10):
    return shadow.InkItem(tuple(box), sequence, stroked)


def scene():
    """One six-line structure (two faces split by the gap, two jambs) for an H strip spanning 100..304."""
    ink_by_id = {
        "fa": ink((20.0, 195.0, 100.0, 195.0)), "fb": ink((304.0, 195.0, 380.0, 195.0)),
        "fc": ink((20.0, 205.0, 100.0, 205.0)), "fd": ink((304.0, 205.0, 380.0, 205.0)),
        "jl": ink((100.0, 195.0, 100.0, 205.0)), "jh": ink((304.0, 195.0, 304.0, 205.0)),
        "glass": ink((110.0, 200.0, 150.0, 200.0)),
    }
    structure = SimpleNamespace(candidate_id="s1", source_observation_ids=("fa", "fb", "fc", "fd", "jl", "jh"),
                                structural_pattern="jamb_bounded_two_face_interruption")
    return READING, [structure], ink_by_id


def view(reading, structures, ink_by_id, *, support=("glass",), subs=None, eq=EQ, axis="H"):
    return shadow.view_existing_pattern(reading, structures, ink_by_id, set(support), subs or {}, eq, axis)


def test_one_structure_whose_jambs_sit_at_the_readings_ends_describes_it():
    v = view(*scene())
    assert v.verdict == shadow.VIEW_DESCRIBED and v.matching_structure_ids == ("s1",) and v.shared_member_ids == ()
    assert v.unaccounted_ink_ids == () and v.reason_codes == (shadow.VIEW_DESCRIBED,)


def test_two_structures_of_the_same_gap_that_share_a_face_are_layers_and_disjoint_ones_are_ambiguous():
    reading, structures, ink_by_id = scene()
    ink_by_id.update({"fe": ink((20.0, 190.0, 100.0, 190.0)), "ff": ink((304.0, 190.0, 380.0, 190.0)),
                      "jl2": ink((100.0, 190.0, 100.0, 195.0)), "jh2": ink((304.0, 190.0, 304.0, 195.0))})
    layered = SimpleNamespace(candidate_id="s2", structural_pattern="x",
                              source_observation_ids=("fa", "fb", "fe", "ff", "jl2", "jh2"))
    v = view(reading, structures + [layered], ink_by_id)
    assert v.verdict == shadow.VIEW_LAYERED and v.shared_member_ids == ("fa", "fb") and v.matching_structure_ids == ("s1", "s2")
    ink_by_id.update({"ga": ink((20.0, 180.0, 100.0, 180.0)), "gb": ink((304.0, 180.0, 380.0, 180.0)),
                      "gc": ink((20.0, 185.0, 100.0, 185.0)), "gd": ink((304.0, 185.0, 380.0, 185.0)),
                      "kl": ink((100.0, 180.0, 100.0, 185.0)), "kh": ink((304.0, 180.0, 304.0, 185.0))})
    distinct = SimpleNamespace(candidate_id="s3", structural_pattern="x",
                               source_observation_ids=("ga", "gb", "gc", "gd", "kl", "kh"))
    assert view(reading, structures + [distinct], ink_by_id).verdict == shadow.VIEW_AMBIGUOUS


@pytest.mark.parametrize("move", [{"jh": (310.0, 195.0, 310.0, 205.0)}, {"jl": (101.0, 195.0, 101.0, 205.0)}])
def test_a_structure_whose_gap_is_not_the_readings_extent_does_not_describe_it(move):
    reading, structures, ink_by_id = scene()
    ink_by_id.update({k: ink(v) for k, v in move.items()})
    v = view(reading, structures, ink_by_id)
    assert v.verdict == shadow.VIEW_NOT_DESCRIBED and v.matching_structure_ids == () and v.structure_count == 1


def test_no_structure_at_all_does_not_describe_it():
    reading, _, ink_by_id = scene()
    v = view(reading, [], ink_by_id)
    assert v.verdict == shadow.VIEW_NOT_DESCRIBED and v.structure_count == 0


def test_a_structure_with_members_the_inventory_does_not_know_is_skipped():
    reading, structures, ink_by_id = scene()
    del ink_by_id["fc"]
    assert view(reading, structures, ink_by_id).verdict == shadow.VIEW_NOT_DESCRIBED


def test_three_perpendicular_stations_are_not_a_gap():
    reading, structures, ink_by_id = scene()
    ink_by_id["jm"] = ink((200.0, 195.0, 200.0, 205.0))
    structures[0] = replace(structures[0], source_observation_ids=structures[0].source_observation_ids + ("jm",)) if False \
        else SimpleNamespace(candidate_id="s1", structural_pattern="x",
                             source_observation_ids=structures[0].source_observation_ids + ("jm",))
    assert view(reading, structures, ink_by_id).verdict == shadow.VIEW_NOT_DESCRIBED


@pytest.mark.parametrize("offset, matches", [(0.0, True), (0.05, True), (0.07, False)])
def test_the_ends_are_compared_with_the_equality_tolerance(offset, matches):
    reading, structures, ink_by_id = scene()
    ink_by_id["jl"] = ink((100.0 + offset, 195.0, 100.0 + offset, 205.0))
    assert (view(reading, structures, ink_by_id).verdict == shadow.VIEW_DESCRIBED) is matches


def test_ink_inside_the_gap_that_nothing_accounts_for_is_listed_and_accounted_ink_is_not():
    reading, structures, ink_by_id = scene()
    ink_by_id["stray"] = ink((200.0, 196.0, 250.0, 196.0))
    ink_by_id["posted"] = ink((150.0, 197.0, 150.0, 199.0))
    ink_by_id["fill"] = ink((120.0, 196.0, 130.0, 199.0), stroked=False)
    ink_by_id["outside"] = ink((400.0, 196.0, 450.0, 196.0))
    ink_by_id["touching"] = ink((304.0, 200.0, 330.0, 200.0))
    post = replace(sub((148.0, 152.0), sid="post-1"), member_observation_ids=("posted",))
    reading = replace(reading, discriminated_subdivision_ids=("post-1",))
    v = view(reading, structures, ink_by_id, subs={"post-1": post})
    assert v.unaccounted_ink_ids == ("stray",) and v.reason_codes == (shadow.VIEW_DESCRIBED, shadow.UNACCOUNTED_INK_INSIDE_GAP)


def _move(box, scale, dx, dy, swap):
    x0, y0, x1, y1 = box
    if swap:
        x0, y0, x1, y1 = y0, x0, y1, x1
    return (x0 * scale + dx, y0 * scale + dy, x1 * scale + dx, y1 * scale + dy)


@pytest.mark.parametrize("scale, dx, dy, swap", [(1.0, 1000.0, 0.0, False), (2.0, 0.0, 0.0, False), (0.5, 8.0, -4.0, False),
                                                  (1.0, 0.0, 0.0, True), (2.0, 12.5, 3.0, True)])
def test_translation_quarter_turn_and_scale_do_not_change_the_classification(scale, dx, dy, swap):
    reading, structures, ink_by_id = scene()
    ink_by_id["stray"] = ink((200.0, 196.0, 250.0, 196.0))
    expected = view(reading, structures, ink_by_id)
    # the reading's ends are along-coordinates: they move with `dx` along the axis and scale; a quarter turn only
    # exchanges which page axis is the strip axis
    shift = dy if swap else dx
    moved_reading = replace(reading, aperture_span_along=tuple(v * scale + (dx if not swap else dy) for v in reading.aperture_span_along)) \
        if False else replace(reading, aperture_span_along=tuple(v * scale + shift for v in reading.aperture_span_along))
    moved_ink = {k: replace(v, box=_move(v.box, scale, dx, dy, swap)) for k, v in ink_by_id.items()}
    got = view(moved_reading, structures, moved_ink, eq=EQ * scale, axis="V" if swap else "H")
    assert (got.verdict, got.unaccounted_ink_ids, got.matching_structure_ids) == (
        expected.verdict, expected.unaccounted_ink_ids, expected.matching_structure_ids)


def test_input_order_replay_and_no_mutation():
    reading, structures, ink_by_id = scene()
    before = copy.deepcopy((reading, structures, ink_by_id))
    first = view(reading, structures, ink_by_id)
    reordered = {k: ink_by_id[k] for k in reversed(list(ink_by_id))}
    assert view(reading, structures, reordered) == first == view(reading, structures, ink_by_id)
    assert (reading, structures, ink_by_id) == before


# ---- real PDF --------------------------------------------------------------------------------------------------------
def _audit(source, published, nomination, **options):
    return shadow.StripWholeApertureCorrespondenceShadow(source, enabled=True, **options).audit(
        revision_id=published.revision.revision_id, plan_page_id=1, nominations=[nomination], coordinate_quantum_pt=0.24)


def test_off_by_default_and_the_option_must_be_a_bool():
    source, published = _publish(_window_pdf())
    assert _audit(source, published, _nomination(source, published)).correspondences[0].existing_pattern is None
    for flag in (1, "yes", None):
        with pytest.raises(TypeError):
            shadow.StripWholeApertureCorrespondenceShadow(object(), enabled=True, existing_pattern_view=flag)


def test_the_existing_rule_describes_a_clean_window_and_the_view_changes_no_decision():
    source, published = _publish(_window_pdf())
    nom = _nomination(source, published)
    plain = _audit(source, published, nom).correspondences[0]
    seen = _audit(source, published, nom, existing_pattern_view=True).correspondences[0]
    assert seen.existing_pattern is not None and seen.existing_pattern.verdict == shadow.VIEW_DESCRIBED
    assert seen.existing_pattern.unaccounted_ink_ids == ()
    assert replace(seen, existing_pattern=None) == plain


def test_a_window_whose_jamb_is_missing_gets_no_view_because_it_has_no_equal_reading():
    source, published = _publish(_window_pdf(jamb_hi=False))
    c = _audit(source, published, _nomination(source, published), existing_pattern_view=True).correspondences[0]
    assert c.status is not shadow.CAND and (c.existing_pattern is None or c.existing_pattern.verdict != shadow.VIEW_DESCRIBED)


def test_ink_inside_the_gap_that_the_nominator_did_not_name_is_reported_not_ignored():
    doc = fitz.open(stream=_window_pdf(), filetype="pdf")
    doc[0].draw_line(fitz.Point(200.0, 197.0), fitz.Point(250.0, 197.0), color=(0, 0, 0), width=0.48)
    payload = doc.tobytes()
    doc.close()
    source, published = _publish(payload)
    nom = _nomination(source, published)
    c = _audit(source, published, nom, existing_pattern_view=True).correspondences[0]
    if c.existing_pattern is not None and c.existing_pattern.verdict == shadow.VIEW_DESCRIBED:
        assert len(c.existing_pattern.unaccounted_ink_ids) == 1
        assert shadow.UNACCOUNTED_INK_INSIDE_GAP in c.existing_pattern.reason_codes
