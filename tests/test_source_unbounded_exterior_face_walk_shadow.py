"""Unbounded exterior-face walk: both dwellings, never the PARTY wall."""
from __future__ import annotations

from types import SimpleNamespace

from shapely.geometry import box

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_native_exterior_endpoint_authority_shadow import CONTACT_PT
from pb_source_unbounded_exterior_face_walk_shadow import (
    REASON_AMBIGUOUS,
    REASON_CYCLE,
    REASON_LEFTOVER,
    REASON_UNCLOSED,
    ROLE_EXCLUDED,
    ROLE_EXTERIOR_FACE,
    ROLE_INTERIOR_DIVIDER,
    walk_unbounded_exterior_face,
)


def _strip(source_id, bounds):
    return SimpleNamespace(
        polygon=box(*bounds),
        path_index=source_id,
        native_path_indices=lambda sid=source_id: (sid,),
    )


def _drawing(layer="Enclosure_WallExternal"):
    return {"layer": layer, "fill": (0.0, 0.0, 0.0)}


def _two_dwelling_bars(*, include_right=True, party_gap=0.0, extra=()):
    bars = [
        _strip(0, (20.0, 10.0, 22.0, 110.0)),
        _strip(1, (98.5, 10.0, 101.5, 110.0)),
        _strip(3, (20.0, 10.0, 222.0, 12.0)),
        _strip(4, (20.0, 108.0, 222.0, 110.0)),
    ]
    if include_right:
        bars.insert(2, _strip(2, (220.0, 10.0, 222.0, 110.0)))
    if party_gap:
        bars[1] = _strip(1, (98.5 + party_gap, 10.0, 101.5 + party_gap, 110.0))
    bars.extend(extra)
    return tuple(bars)


def _words(*, party=True, opposite=True, outdoor=False):
    result = [(45.0, 55.0, 65.0, 63.0, "LIVING", 12, 0, 0)]
    if opposite:
        result.append((142.0, 55.0, 164.0, 63.0, "MEDIA", 13, 0, 0))
    if party:
        result.extend([
            (70.0, 43.0, 91.0, 51.0, "PARTY", 5, 0, 0),
            (70.0, 53.0, 92.0, 61.0, "WALL", 5, 1, 0),
        ])
    if outdoor:
        result.append((230.0, 40.0, 250.0, 48.0, "ALFRESCO", 20, 0, 0))
    return tuple(result)


def _drawings_for(bars):
    n = max(bar.path_index for bar in bars) + 1
    rows = [_drawing() for _ in range(n)]
    return tuple(rows)


def test_shared_envelope_walk_excludes_party_and_does_not_bill():
    bars = _two_dwelling_bars()
    result = walk_unbounded_exterior_face(
        _drawings_for(bars), source_words=_words(), page_index=2, bars=bars,
    )
    roles = {tuple(row["native_path_ids"]): row["role"] for row in result["face_records"]}
    assert roles[(1,)] == ROLE_INTERIOR_DIVIDER
    assert roles[(0,)] == ROLE_EXTERIOR_FACE
    assert roles[(2,)] == ROLE_EXTERIOR_FACE
    assert 1 in result["interior_divider_path_ids"]
    exterior = {next(iter(ids)) for ids in result["exterior_path_id_sequence"]}
    assert 1 not in exterior
    assert {0, 2, 3, 4} <= exterior
    assert result["status"] == EvidenceResolutionStatus.CANDIDATE.value
    assert result["reason"] == REASON_CYCLE
    assert result["closed_shared_envelope_candidate"] is True
    assert result["measurement_authorized"] is False
    assert result["physical_wall_authenticated"] is False
    assert result["building_footprint_authenticated"] is False
    assert result["snap_join_applied"] is False
    assert result["convex_hull_applied"] is False
    assert result["official_frozen120_score_change"] == 0
    assert result["layer_name_is_not_outer_role"] is True


def test_unit_only_left_loop_is_not_the_building_and_right_gap_abstains():
    bars = _two_dwelling_bars(include_right=False)
    result = walk_unbounded_exterior_face(
        _drawings_for(bars), source_words=_words(), bars=bars,
    )
    assert result["status"] == EvidenceResolutionStatus.ABSTAINED.value
    assert result["closed_shared_envelope_candidate"] is False
    assert 1 in result["interior_divider_path_ids"]
    assert result["measurement_authorized"] is False
    assert result["reason"] in {REASON_UNCLOSED, REASON_AMBIGUOUS}


def test_external_layer_does_not_make_a_two_sided_wall_outer():
    bars = _two_dwelling_bars()
    drawings = tuple(_drawing("Enclosure_WallExternal") for _ in range(5))
    result = walk_unbounded_exterior_face(drawings, source_words=_words(), bars=bars)
    party = next(row for row in result["face_records"] if row["native_path_ids"] == [1])
    assert party["role"] == ROLE_INTERIOR_DIVIDER


def test_point425_gap_is_not_snapped_into_a_closed_envelope():
    bars = list(_two_dwelling_bars())
    # Split the top outer wall with a 0.425 pt unwitnessed gap.
    bars[3] = _strip(3, (20.0, 10.0, 120.0, 12.0))
    bars.append(_strip(5, (120.425, 10.0, 222.0, 12.0)))
    bars = tuple(bars)
    result = walk_unbounded_exterior_face(
        _drawings_for(bars), source_words=_words(), bars=bars,
    )
    assert result["snap_join_applied"] is False
    assert result["closed_shared_envelope_candidate"] is False
    assert result["status"] == EvidenceResolutionStatus.ABSTAINED.value
    assert 0.425 > CONTACT_PT


def test_isolated_post_and_alfresco_are_not_outer_walls():
    post = _strip(9, (240.0, 20.0, 244.0, 24.0))
    bars = _two_dwelling_bars(extra=(post,))
    words = _words(outdoor=True) + ((239.0, 20.5, 245.0, 23.5, "POST", 21, 0, 0),)
    drawings = _drawings_for(bars)
    result = walk_unbounded_exterior_face(drawings, source_words=words, bars=bars)
    post_row = next(row for row in result["face_records"] if row["native_path_ids"] == [9])
    assert post_row["role"] == ROLE_EXCLUDED
    assert 9 not in {ids[0] for ids in result["exterior_path_id_sequence"] if ids}


def test_unlabelled_interior_partition_is_not_walked_as_outer():
    bars = (
        _strip(0, (0.0, 0.0, 2.0, 40.0)),
        _strip(1, (38.0, 0.0, 40.0, 40.0)),
        _strip(2, (0.0, 0.0, 40.0, 2.0)),
        _strip(3, (0.0, 38.0, 40.0, 40.0)),
        _strip(4, (19.0, 2.0, 21.0, 38.0)),
    )
    result = walk_unbounded_exterior_face(_drawings_for(bars), source_words=(), bars=bars)
    roles = {tuple(row["native_path_ids"]): row["role"] for row in result["face_records"]}
    assert roles[(4,)] == ROLE_INTERIOR_DIVIDER
    assert result["closed_shared_envelope_candidate"] is True
    assert 4 not in {ids[0] for ids in result["exterior_path_id_sequence"]}


def test_l_shape_follows_reentrant_faces_not_a_hull():
    bars = (
        _strip(0, (0.0, 0.0, 2.0, 100.0)),
        _strip(1, (0.0, 98.0, 100.0, 100.0)),
        _strip(2, (98.0, 50.0, 100.0, 100.0)),
        _strip(3, (50.0, 50.0, 100.0, 52.0)),
        _strip(4, (50.0, 0.0, 52.0, 52.0)),
        _strip(5, (0.0, 0.0, 52.0, 2.0)),
    )
    result = walk_unbounded_exterior_face(_drawings_for(bars), bars=bars)
    exterior = {ids[0] for ids in result["exterior_path_id_sequence"]}
    assert {3, 4} <= exterior
    assert result["convex_hull_applied"] is False
    assert result["measurement_authorized"] is False


def test_two_disconnected_outer_rings_abstain():
    bars = (
        _strip(0, (0.0, 0.0, 2.0, 20.0)),
        _strip(1, (18.0, 0.0, 20.0, 20.0)),
        _strip(2, (0.0, 0.0, 20.0, 2.0)),
        _strip(3, (0.0, 18.0, 20.0, 20.0)),
        _strip(4, (80.0, 0.0, 82.0, 20.0)),
        _strip(5, (98.0, 0.0, 100.0, 20.0)),
        _strip(6, (80.0, 0.0, 100.0, 2.0)),
        _strip(7, (80.0, 18.0, 100.0, 20.0)),
    )
    result = walk_unbounded_exterior_face(_drawings_for(bars), bars=bars)
    assert result["status"] == EvidenceResolutionStatus.ABSTAINED.value
    assert result["reason"] in {REASON_AMBIGUOUS, REASON_LEFTOVER}
    assert result["closed_shared_envelope_candidate"] is False
    assert result["measurement_authorized"] is False


def test_translation_and_input_order_do_not_change_roles():
    bars = _two_dwelling_bars()
    words = _words()
    first = walk_unbounded_exterior_face(_drawings_for(bars), source_words=words, bars=bars)
    shifted = tuple(
        _strip(bar.path_index, tuple(v + 17.0 for v in bar.polygon.bounds))
        for bar in bars
    )
    shifted_words = tuple(
        (w[0] + 17.0, w[1] + 17.0, w[2] + 17.0, w[3] + 17.0, *w[4:])
        for w in words
    )
    second = walk_unbounded_exterior_face(
        _drawings_for(shifted), source_words=shifted_words, bars=shifted,
    )
    reversed_bars = tuple(reversed(bars))
    third = walk_unbounded_exterior_face(
        _drawings_for(bars), source_words=words, bars=reversed_bars,
    )
    assert first["interior_divider_path_ids"] == second["interior_divider_path_ids"] == third["interior_divider_path_ids"]
    assert first["status"] == second["status"] == third["status"]
    assert first["measurement_authorized"] is False


def test_drawings_are_not_mutated():
    bars = _two_dwelling_bars()
    drawings = [dict(row) for row in _drawings_for(bars)]
    snapshot = [dict(row) for row in drawings]
    walk_unbounded_exterior_face(drawings, source_words=_words(), bars=bars)
    assert drawings == snapshot


def test_window_topology_bridge_is_not_a_wall_and_does_not_bill():
    import fitz

    from pb_source_window_footprint_continuity import (
        detect_exterior_window_footprint_bridges,
    )

    def wall(bounds):
        return {
            "rect": fitz.Rect(*bounds),
            "layer": "Enclosure_WallExternal",
            "fill": (0.0, 0.0, 0.0),
            "items": (),
        }

    drawings = [
        wall((0.0, 0.0, 10.0, 2.0)),
        wall((20.0, 0.0, 30.0, 2.0)),
        {
            "rect": fitz.Rect(15.0, 4.0, 17.0, 4.5),
            "layer": "Enclosure_WallExternal",
            "fill": None,
            "items": (("l", fitz.Point(15.0, 4.0), fitz.Point(17.0, 4.5)),),
        },
        {
            "rect": fitz.Rect(15.0, 3.5, 17.0, 4.0),
            "layer": "Enclosure_WallExternal",
            "fill": None,
            "items": (("l", fitz.Point(15.0, 4.0), fitz.Point(17.0, 3.5)),),
        },
        wall((0.0, 0.0, 2.0, 30.0)),
        wall((28.0, 0.0, 30.0, 30.0)),
        wall((0.0, 28.0, 30.0, 30.0)),
    ]
    words = [(13.0, 9.0, 19.0, 13.0, "asw")]
    bridges = detect_exterior_window_footprint_bridges(drawings, words)
    assert len(bridges) == 1
    bars = (
        _strip(0, (0.0, 0.0, 10.0, 2.0)),
        _strip(1, (20.0, 0.0, 30.0, 2.0)),
        _strip(4, (0.0, 0.0, 2.0, 30.0)),
        _strip(5, (28.0, 0.0, 30.0, 30.0)),
        _strip(6, (0.0, 28.0, 30.0, 30.0)),
    )
    result = walk_unbounded_exterior_face(drawings, source_words=words, bars=bars)
    assert result["topology_continuity_pair_count"] >= 1
    assert result["measurement_authorized"] is False
    assert result["physical_wall_authenticated"] is False


def test_original_3laurel_p3_walks_outer_face_not_party_and_does_not_bill():
    import hashlib

    import fitz

    from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel

    path = require_original_3laurel()
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ORIGINAL_SHA256
    with fitz.open(stream=raw, filetype="pdf") as document:
        page = document[2]
        drawings = page.get_drawings()
        words = page.get_text("words")
        before = (len(drawings), len(words))
        result = walk_unbounded_exterior_face(drawings, source_words=words, page_index=2)
        after = (len(page.get_drawings()), len(page.get_text("words")))
    assert before == after
    assert result["measurement_authorized"] is False
    assert result["physical_wall_authenticated"] is False
    assert result["building_footprint_authenticated"] is False
    assert result["snap_join_applied"] is False
    assert result["convex_hull_applied"] is False
    assert result["official_frozen120_score_change"] == 0
    exterior = {path for ids in result["exterior_path_id_sequence"] for path in ids}
    interior = set(result["interior_divider_path_ids"])
    assert not exterior.intersection(interior)
    assert result["exterior_face_count"] >= 1
    assert result["closed_shared_envelope_candidate"] is False
    assert result["first_unclosed_exterior_endpoint"] is not None
    east = [
        row for row in result["face_records"]
        if row["role"] == ROLE_EXTERIOR_FACE and row["bounds_pdf_pts"][0] > 756.0
    ]
    assert east, "right-house/garage outer faces must stay on the unbounded walk"
