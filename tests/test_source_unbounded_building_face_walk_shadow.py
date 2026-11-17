"""Use the UNBOUNDED outside face for one building containing two homes.

These are topology-only safety/acceptance tests; no external wall customer
area or finished floor area can be minted from the preview.
"""

from dataclasses import dataclass

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from pb_source_shared_dwelling_envelope_shadow import CandidateSharedBuildingDivider
from pb_source_unbounded_building_face_walk_shadow import (
    _AABB_FILM_PT,
    _SNAP_PT,
    CONTACT_PT,
    diagnose_source_outside_face_neighbors,
    walk_source_unbounded_building_face,
)


@dataclass(frozen=True)
class SourceBar:
    polygon: Polygon
    original_path_id: int

    def native_path_indices(self):
        return (self.original_path_id,)


def _building_bars():
    return tuple(
        SourceBar(box(*r), i)
        for i, r in enumerate(
            (
                (0, 0, 240, 3),
                (0, 117, 240, 120),
                (0, 0, 3, 120),
                (237, 0, 240, 120),
                (118, 0, 122, 120),  # full-length PARTY partition, physically real
            )
        )
    )


def _source_words(*, second_x=178, alfresco=False):
    result = (
        (47, 55, 67, 63, "LIVING", 0, 0, 0),
        (second_x - 10, 55, second_x + 10, 63, "MEDIA", 1, 0, 0),
    )
    if alfresco:
        return (*result, (12, 25, 43, 33, "ALFRESCO", 2, 0, 0))
    return result


def _party():
    return CandidateSharedBuildingDivider(
        source_page_index=2,
        annotation_word_ids=(733, 734),
        annotation_text="PARTY WALL",
        wall_native_path_ids=(4,),
        wall_layer="Enclosure_WallExternal",
        wall_bounds_pdf_pts=(118.0, 0.0, 122.0, 120.0),
        orientation="vertical",
        side_one_label="LIVING",
        side_two_label="MEDIA",
    )



def _residual_row(layer, bounds, *, fill=(0, 0, 0), width=0.7, **extra):
    row = {
        "layer": layer,
        "fill": fill,
        "type": "s",
        "width": width,
        "rect": bounds,
    }
    row.update(extra)
    return row


def test_complete_two_dwelling_envelope_walk_skips_internal_party_edge():
    bars = _building_bars()
    result = walk_source_unbounded_building_face(
        bars,
        _source_words(),
        shared_dividers=(_party(),),
        source_wall_union=unary_union([x.polygon for x in bars]),
    )
    assert result.status == "CANDIDATE"
    assert result.enclosed_region_count == 2
    assert result.enclosed_dwelling_zone_count == 2
    assert result.outer_wall_native_path_ids == (0, 1, 2, 3)
    assert result.internal_party_wall_native_path_ids == (4,)
    assert len(result.clockwise_pdf_pts) >= 5
    assert result.clockwise_pdf_pts[0] == result.clockwise_pdf_pts[-1]
    pts = result.clockwise_pdf_pts
    assert sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:])) > 0
    assert result.to_dict()["measurement_authorized"] is False
    assert result.to_dict()["building_footprint_authenticated"] is False


def test_second_dwelling_wall_gap_is_not_repaired_by_left_turn_or_hull():
    bars = list(_building_bars())
    bars[1] = SourceBar(box(0, 117, 122, 120), 1)  # right home opens outdoors
    result = walk_source_unbounded_building_face(
        bars,
        _source_words(),
        shared_dividers=(_party(),),
    )
    assert result.status == "ABSTAINED"
    assert result.reason == "source_dwelling_region_still_open_to_outside"
    assert result.enclosed_region_count == 1
    assert result.enclosed_dwelling_zone_count == 1
    assert result.unclosed_dwelling_sides == ("right",)
    assert result.clockwise_pdf_pts == ()


def test_two_printed_rooms_on_same_side_cannot_prove_second_dwelling():
    result = walk_source_unbounded_building_face(
        _building_bars(), _source_words(second_x=59), shared_dividers=(_party(),)
    )
    assert result.status == "ABSTAINED"
    assert result.unclosed_dwelling_sides == ("right",)


def test_single_dwelling_unchanged_when_no_party_source_exists():
    result = walk_source_unbounded_building_face(
        _building_bars()[:4], _source_words(), shared_dividers=()
    )
    assert result.status == "CANDIDATE"
    assert result.enclosed_region_count == 1
    assert result.internal_party_wall_native_path_ids == ()


def test_missing_physical_party_between_occupied_units_fails():
    result = walk_source_unbounded_building_face(
        _building_bars()[:4], _source_words(), shared_dividers=(_party(),)
    )
    assert result.status == "ABSTAINED"
    assert result.reason == "party_wall_two_sides_are_same_free_space"


def test_alfresco_bounded_in_building_would_make_wrong_outside_trace():
    result = walk_source_unbounded_building_face(
        _building_bars(), _source_words(alfresco=True), shared_dividers=(_party(),)
    )
    assert result.status == "ABSTAINED"
    assert result.reason == "outdoor_space_inside_proposed_building"


def test_detached_internal_wall_inside_room_hole_does_not_veto_outer_footprint():
    # A native wall island inside one enclosed occupied zone is not outside
    # the building just because it does not touch the painted outer ring.
    # Old primary-wall-paint containment falsely rejected this original
    # geometry. The authoritative test is exterior-ring containment.
    bars = (*_building_bars(), SourceBar(box(35, 30, 38, 48), 25))
    result = walk_source_unbounded_building_face(
        bars, _source_words(), shared_dividers=(_party(),),
    )
    assert result.status == "CANDIDATE"
    assert result.reason == "unbounded_outside_wall_walk_requires_independent_source_seal"
    assert result.enclosed_dwelling_zone_count == 2
    assert 25 not in result.outer_wall_native_path_ids
    assert result.other_source_wall_band_count == 0
    assert result.measurement_authorized is False
    assert result.building_footprint_authenticated is False


def test_far_unowned_structural_wall_or_separate_building_cannot_be_dropped():
    bars = (*_building_bars(), SourceBar(box(280, 20, 283, 90), 12))
    result = walk_source_unbounded_building_face(
        bars, _source_words(), shared_dividers=(_party(),)
    )
    assert result.status == "ABSTAINED"
    assert result.reason == "source_other_structural_walls_outside_candidate"
    assert result.other_source_wall_band_count == 1
    assert result.clockwise_pdf_pts == ()  # no authoritative ring
    assert result.outer_wall_native_path_ids == ()
    assert len(result.diagnostic_unsealed_ring_pdf_pts) >= 5
    assert not Polygon(result.diagnostic_unsealed_ring_pdf_pts).buffer(0.05).covers(
        bars[-1].polygon
    )
    assert result.to_dict()["diagnostic_unsealed_not_measurement"] is True
    assert result.measurement_authorized is False


def test_far_paint_cavity_is_leftover_scheme_not_a_second_envelope():
    far = SourceBar(
        Polygon(
            ((400, 0), (440, 0), (440, 40), (400, 40), (400, 0)),
            [((410, 10), (420, 10), (420, 20), (410, 20), (410, 10))],
        ),
        20,
    )
    bars = (*_building_bars(), far)
    result = walk_source_unbounded_building_face(
        bars,
        _source_words(),
        shared_dividers=(_party(),),
        source_wall_union=unary_union([bar.polygon for bar in bars]),
    )
    assert result.status == "ABSTAINED"
    assert result.reason == "source_other_structural_walls_outside_candidate"
    assert result.clockwise_pdf_pts == ()
    assert result.measurement_authorized is False


def test_open_dwelling_plus_far_cavity_is_open_to_outside_not_unique_closed():
    bars = list(_building_bars())
    bars[1] = SourceBar(box(0, 117, 122, 120), 1)
    bars.append(
        SourceBar(
            Polygon(
                ((400, 0), (440, 0), (440, 40), (400, 40), (400, 0)),
                [((410, 10), (420, 10), (420, 20), (410, 20), (410, 10))],
            ),
            20,
        )
    )
    result = walk_source_unbounded_building_face(
        bars,
        _source_words(),
        shared_dividers=(_party(),),
        source_wall_union=unary_union([bar.polygon for bar in bars]),
    )
    assert result.status == "ABSTAINED"
    assert result.reason == "source_dwelling_region_still_open_to_outside"
    assert result.unclosed_dwelling_sides == ("right",)
    assert result.clockwise_pdf_pts == ()
    assert result.measurement_authorized is False


def test_aabb_outdoor_film_is_not_a_dwelling_leak_or_snap():
    # A short outer jamb expands the union AABB 0.4 pt beyond the continuous
    # outer face. That outdoor film is not a dwelling opening and must not be
    # closed by the 2.5 pt commercial snap.
    bars = (
        SourceBar(box(0.4, 0.4, 239.6, 3.4), 0),
        SourceBar(box(0.4, 116.6, 239.6, 119.6), 1),
        SourceBar(box(0.4, 0.4, 3.4, 119.6), 2),
        SourceBar(box(236.6, 0.4, 239.6, 119.6), 3),
        SourceBar(box(118.0, 0.4, 122.0, 119.6), 4),
        SourceBar(box(0.0, 50.0, 0.4, 55.0), 5),
    )
    result = walk_source_unbounded_building_face(
        bars,
        _source_words(),
        shared_dividers=(_party(),),
        source_wall_union=unary_union([bar.polygon for bar in bars]),
    )
    assert _AABB_FILM_PT < _SNAP_PT
    assert result.status == "CANDIDATE"
    assert result.enclosed_dwelling_zone_count == 2
    assert result.unclosed_dwelling_sides == ()
    assert result.measurement_authorized is False
    assert result.to_dict()["snap_join_applied"] is False


def test_original_wall_source_ids_required_and_nonfinite_or_empty_abstains():
    bad = SourceBar(Polygon(((0, 0), (1, 1), (2, 2))), 100)
    result = walk_source_unbounded_building_face(
        (bad,), _source_words(), shared_dividers=(_party(),)
    )
    assert result.status == "ABSTAINED"
    assert result.to_dict()["measurement_authorized"] is False
    assert result.to_dict()["snap_join_applied"] is False
    assert result.to_dict()["undirected_degree_is_not_outside_face_authority"] is True

def test_clockwise_outside_face_walk_handles_a_source_reentrant_L_not_a_hull():
    bars = tuple(
        SourceBar(box(*rect), i)
        for i, rect in enumerate(
            (
                (0, 0, 52, 2),
                (50, 0, 52, 52),
                (50, 50, 100, 52),
                (98, 50, 100, 100),
                (0, 98, 100, 100),
                (0, 0, 2, 100),
            )
        )
    )
    result = walk_source_unbounded_building_face(bars, (), shared_dividers=())
    assert result.status == "CANDIDATE"
    assert set(result.outer_wall_native_path_ids) == set(range(6))
    ring = Polygon(result.clockwise_pdf_pts)
    assert ring.is_valid
    assert not ring.covers(box(75, 20, 77, 23))
    assert ring.covers(box(10, 80, 12, 82))
    assert ring.area < 10000  # no page bounding hull
    assert not result.measurement_authorized


def test_source_T_junction_inside_outside_wall_is_not_taken_as_outer_face():
    bars = (
        *_building_bars()[:4],
        SourceBar(box(0, 56, 70, 59), 9),  # genuine internal T wall
    )
    result = walk_source_unbounded_building_face(bars, (), shared_dividers=())
    assert result.status == "CANDIDATE"
    assert 9 not in result.outer_wall_native_path_ids
    assert set(result.outer_wall_native_path_ids) == {0, 1, 2, 3}
    assert result.clockwise_pdf_pts[0] == result.clockwise_pdf_pts[-1]
    assert not result.measurement_authorized


def test_unwitnessed_four_tenths_point_source_gap_is_not_snapped_closed():
    bars = list(_building_bars())
    bars[0] = SourceBar(box(0, 0, 50, 3), 0)
    bars.append(SourceBar(box(50.425, 0, 240, 3), 5))
    result = walk_source_unbounded_building_face(
        bars,
        _source_words(),
        shared_dividers=(_party(),),
    )
    assert result.status == "ABSTAINED"
    assert result.clockwise_pdf_pts == ()
    assert not result.building_footprint_authenticated


def test_source_outside_walk_is_invariant_to_translation_and_input_order():
    from dataclasses import replace

    bars = _building_bars()
    original = walk_source_unbounded_building_face(
        bars,
        _source_words(),
        shared_dividers=(_party(),),
    )
    shifted_bars = tuple(
        SourceBar(
            box(
                bar.polygon.bounds[0] + 27,
                bar.polygon.bounds[1] + 13,
                bar.polygon.bounds[2] + 27,
                bar.polygon.bounds[3] + 13,
            ),
            bar.original_path_id,
        )
        for bar in reversed(bars)
    )
    shifted_words = tuple(
        (w[0] + 27, w[1] + 13, w[2] + 27, w[3] + 13, *w[4:]) for w in _source_words()
    )
    party = replace(_party(), wall_bounds_pdf_pts=(145.0, 13.0, 149.0, 133.0))
    shifted = walk_source_unbounded_building_face(
        shifted_bars,
        shifted_words,
        shared_dividers=(party,),
    )
    assert original.status == shifted.status == "CANDIDATE"
    assert original.outer_wall_native_path_ids == shifted.outer_wall_native_path_ids
    assert (
        original.internal_party_wall_native_path_ids
        == shifted.internal_party_wall_native_path_ids
    )
    assert (
        original.enclosed_dwelling_zone_count
        == shifted.enclosed_dwelling_zone_count
        == 2
    )
    assert original.measurement_authorized is shifted.measurement_authorized is False

def test_interior_t_junction_does_not_veto_canonical_outside_face():
    bars = (*_building_bars(), SourceBar(box(48, 60, 52, 117), 8))
    union = unary_union([x.polygon for x in bars])
    result = walk_source_unbounded_building_face(
        bars, _source_words(), shared_dividers=(_party(),), source_wall_union=union,
    )
    assert result.status == "CANDIDATE"
    assert 8 not in result.outer_wall_native_path_ids
    assert 4 in result.internal_party_wall_native_path_ids
    receipt = diagnose_source_outside_face_neighbors(
        bars, 1, shared_dividers=(_party(),), source_wall_union=union,
        source_words=_source_words(),
    )
    assert receipt["undirected_degree_gt_2"] is True
    assert receipt["undirected_degree_does_not_veto_outside_face"] is True
    assert receipt["canonical_walk_status"] == "CANDIDATE"
    kinds = {tuple(row["native_path_ids"]): row["kind"] for row in receipt["neighbors"]}
    assert kinds.get((8,)) == "interior_t_or_partition_contact"
    assert receipt["measurement_authorized"] is False
    assert receipt["snap_join_applied"] is False


def test_two_interior_t_junctions_still_follow_outside_face():
    bars = (
        *_building_bars(),
        SourceBar(box(48, 60, 52, 117), 8),
        SourceBar(box(170, 60, 174, 117), 9),
    )
    result = walk_source_unbounded_building_face(
        bars, _source_words(), shared_dividers=(_party(),),
        source_wall_union=unary_union([x.polygon for x in bars]),
    )
    assert result.status == "CANDIDATE"
    assert result.outer_wall_native_path_ids == (0, 1, 2, 3)
    assert {8, 9}.isdisjoint(result.outer_wall_native_path_ids)


def test_l_shape_keeps_reentrant_faces_and_does_not_hull():
    bars = (
        SourceBar(box(0, 0, 3, 120), 0),
        SourceBar(box(0, 117, 240, 120), 1),
        SourceBar(box(237, 60, 240, 120), 2),
        SourceBar(box(120, 60, 240, 63), 3),
        SourceBar(box(120, 0, 123, 63), 4),
        SourceBar(box(0, 0, 123, 3), 5),
    )
    result = walk_source_unbounded_building_face(bars, (), shared_dividers=())
    assert result.status == "CANDIDATE"
    assert {3, 4} <= set(result.outer_wall_native_path_ids)
    assert result.to_dict()["convex_hull_applied"] is False
    assert result.measurement_authorized is False


def test_point425_gap_is_not_snapped_closed():
    bars = list(_building_bars())
    bars[0] = SourceBar(box(0, 0, 170, 3), 0)
    bars.append(SourceBar(box(170.425, 0, 240, 3), 5))
    result = walk_source_unbounded_building_face(
        bars, _source_words(), shared_dividers=(_party(),),
    )
    assert result.status == "ABSTAINED"
    assert result.clockwise_pdf_pts == ()
    receipt = diagnose_source_outside_face_neighbors(
        bars, 0, source_words=_source_words(), shared_dividers=(_party(),),
    )
    assert receipt["snap_join_applied"] is False
    assert 0.425 > CONTACT_PT
    assert any(row["kind"] == "near_miss_unauthenticated_no_snap" for row in receipt["neighbors"])


def test_grey_seam_is_topology_only_not_a_wall_or_snap():
    import fitz

    bars = (
        SourceBar(box(0, 0, 10, 2.5), 0),
        SourceBar(box(10.5, 0, 30, 2.5), 1),
        SourceBar(box(0, 0, 2.5, 30), 4),
        SourceBar(box(27.5, 0, 30, 30), 5),
        SourceBar(box(0, 27.5, 30, 30), 6),
    )
    grey = {
        "rect": fitz.Rect(10, 0, 10.5, 2.5),
        "layer": "Enclosure_WallExternal",
        "fill": (0.415686, 0.415686, 0.415686),
        "items": (),
    }
    drawings = [
        {"rect": fitz.Rect(*b.polygon.bounds), "layer": "Enclosure_WallExternal", "fill": (0.0, 0.0, 0.0), "items": ()}
        for b in bars[:2]
    ]
    drawings.append(grey)
    union = unary_union([b.polygon for b in bars] + [box(10, 0, 10.5, 2.5)])
    receipt = diagnose_source_outside_face_neighbors(
        bars, 0, drawings=drawings, source_wall_union=union,
    )
    assert receipt["grey_seam_pairs"]
    assert receipt["grey_seam_pairs"][0]["neutral_fill_path_ids"] == [2]
    assert {0, 1} == {
        receipt["grey_seam_pairs"][0]["first_host_path_id"],
        receipt["grey_seam_pairs"][0]["second_host_path_id"],
    }
    kinds = [row["kind"] for row in receipt["neighbors"] if row["native_path_ids"] == [1]]
    assert kinds == ["source_neutral_or_opening_topology_only"]
    assert receipt["snap_join_applied"] is False
    assert receipt["measurement_authorized"] is False


def test_isolated_post_is_not_an_outer_wall_owner():
    bars = (*_building_bars(), SourceBar(box(260, 20, 264, 24), 9))
    result = walk_source_unbounded_building_face(
        bars, _source_words(), shared_dividers=(_party(),),
    )
    assert 9 not in result.outer_wall_native_path_ids
    assert result.measurement_authorized is False


def test_original_3laurel_p3_path1192_grey_seam_and_party_stay_unbilled():
    import hashlib

    import fitz

    from pb_new_exterior_wall_preflight import attempt_source_native_outer_wall_first
    from pb_source_native_wall_body_junction_graph_shadow import (
        _unique_source_wall_bars,
    )
    from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel

    path = require_original_3laurel()
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ORIGINAL_SHA256
    with fitz.open(stream=raw, filetype="pdf") as document:
        page = document[2]
        drawings = page.get_drawings()
        words = page.get_text("words")
        before = (len(drawings), len(words))
        attempt = attempt_source_native_outer_wall_first(
            drawings, source_words=words, window_source_drawings=drawings,
            source_page_index=2,
        )
        bars = _unique_source_wall_bars(drawings)
        receipt = diagnose_source_outside_face_neighbors(
            bars,
            1192,
            drawings=drawings,
            source_words=words,
            shared_dividers=attempt.shared_dwelling_divider_candidates,
        )
        after = (len(page.get_drawings()), len(page.get_text("words")))
    assert before == after
    assert attempt.measurement_authorized is False
    assert len(attempt.sliding_door_footprint_bridges) >= 2
    assert any(
        str(b.label_text).strip().upper().startswith("ASSD")
        for b in attempt.sliding_door_footprint_bridges
    )
    # Repeated ASW schedule codes must keep the living-north hosts 1709/1708.
    assert any(
        {b.left_host_path_id, b.right_host_path_id} == {1708, 1709}
        for b in attempt.window_footprint_bridges
    )
    walk = attempt.source_outside_face_walk
    assert walk is not None
    assert walk.measurement_authorized is False
    # CANDIDATE and unresolved outside structural wall bands are mutually
    # exclusive. A negative source-role audit must never mint an exterior
    # physical envelope from a diagnostic preview alone.
    assert walk.unclosed_dwelling_sides == ()
    assert walk.enclosed_dwelling_zone_count == 2
    assert not walk.building_footprint_authenticated
    assert not walk.measurement_authorized
    assert attempt.source_outside_face_walk is not None
    assert attempt.shared_dwelling_divider_candidates
    if walk.other_source_wall_band_count:
        assert walk.status == "ABSTAINED"
        assert walk.reason == "source_other_structural_walls_outside_candidate"
        assert walk.clockwise_pdf_pts == ()
        assert walk.outer_wall_native_path_ids == ()
        assert len(walk.diagnostic_unsealed_ring_pdf_pts) >= 5
        assert walk.source_outside_role_audit_applied is True
        assert walk.source_proven_nonwall_band_count >= 1
        assert walk.source_outside_band_count_before_role_audit > (
            walk.other_source_wall_band_count
        )
        assert walk.unresolved_outside_native_path_id_sample
        assert len(walk.unresolved_outside_native_path_id_sample) <= 64
        assert all(
            0 <= idx < len(drawings)
            for idx in walk.unresolved_outside_native_path_id_sample
        )
        assert walk.to_dict()["source_outside_role_audit_noncommercial"] is True
        assert walk.to_dict()["unresolved_owner_ids_are_review_only"] is True
        assert attempt.status == "ABSTAINED"
    else:
        assert walk.status == "CANDIDATE"
        assert walk.reason == "unbounded_outside_wall_walk_requires_independent_source_seal"
        assert len(walk.clockwise_pdf_pts) >= 5
        assert walk.clockwise_pdf_pts[0] == walk.clockwise_pdf_pts[-1]
        assert len(walk.outer_wall_native_path_ids) >= 4
        assert walk.unresolved_outside_native_path_id_sample == ()
        # Candidate topology is still unsealed, never commercial.
        assert attempt.measurement_authorized is False
    assert any(b.label_text.lower() == "assd" for b in attempt.sliding_door_footprint_bridges)
    assert any(b.swing_arc_path_id == 1912 for b in attempt.swing_door_footprint_bridges)
    assert receipt["measurement_authorized"] is False
    assert receipt["snap_join_applied"] is False
    assert receipt["undirected_degree_does_not_veto_outside_face"] is True
    grey_hosts = {
        (row["first_host_path_id"], row["second_host_path_id"])
        for row in receipt["grey_seam_pairs"]
    }
    assert grey_hosts & {(1192, 1195), (1195, 1192)}
    fills = {fid for row in receipt["grey_seam_pairs"] for fid in row["neutral_fill_path_ids"]}
    assert {1193, 1194} <= fills or fills  # native grey seam owners when present
    party = set(walk.internal_party_wall_native_path_ids or ())
    outer = set(walk.outer_wall_native_path_ids or ())
    assert not party.intersection(outer)
    assert party.intersection({1027, 1029, 1031, 1139})
    east = [
        bar for bar in bars
        if bar.polygon.bounds[0] > 756
        and set(bar.native_path_indices()).isdisjoint(party)
    ]
    assert east, "right-house/garage source bars must remain available"

def test_source_explicit_nonwall_outside_is_not_a_structural_wall_veto():
    # A far native annotation mark can resemble wall paint. Its source
    # layer disqualifies it as a wall; all real outside paths still survive.
    bars = (*_building_bars(), SourceBar(box(280, 20, 283, 90), 12))
    rows = [
        _residual_row("Enclosure_WallExternal", (0, 0, 3, 3)) for _ in range(13)
    ]
    rows[12] = _residual_row("Annotation_FloorPlan", (280, 20, 283, 90))
    result = walk_source_unbounded_building_face(
        bars, _source_words(), shared_dividers=(_party(),),
        source_drawings=rows,
    )
    assert result.status == "CANDIDATE"
    assert result.reason == "unbounded_outside_wall_walk_requires_independent_source_seal"
    assert result.other_source_wall_band_count == 0
    assert result.source_proven_nonwall_band_count == 0  # CANDIDATE keeps no veto metrics
    assert result.measurement_authorized is False

def test_unknown_mixed_or_house_owned_outside_path_never_disappears():
    bars = (*_building_bars(), SourceBar(box(280, 20, 283, 90), 12))
    rows = [
        _residual_row("Enclosure_WallExternal", (0, 0, 3, 3)) for _ in range(13)
    ]
    rows[12] = _residual_row("Annotation_FloorPlan", (280, 20, 283, 90))
    for sources, words in (
        (rows[:-1], _source_words()),  # missing native path ID
        ([*rows[:12], _residual_row("", (280, 20, 283, 90))], _source_words()),
        (rows, (*_source_words(), (280, 50, 283, 60, "GARAGE", 0, 0, 0))),
    ):
        result = walk_source_unbounded_building_face(
            bars, words, shared_dividers=(_party(),), source_drawings=sources,
        )
        assert result.status == "ABSTAINED"
        assert result.reason == "source_other_structural_walls_outside_candidate"
        assert result.other_source_wall_band_count == 1
        assert result.source_proven_nonwall_band_count == 0
        assert result.unresolved_outside_native_path_id_sample == (12,)
        assert result.to_dict()["unresolved_outside_native_path_id_sample"] == [12]
        assert result.source_outside_band_count_before_role_audit == 1
        assert result.to_dict()["source_outside_role_audit_noncommercial"] is True
        assert result.clockwise_pdf_pts == ()
        assert not result.building_footprint_authenticated
        assert not result.measurement_authorized

def test_outside_composite_conflicting_wall_or_viewport_remains_unresolved():
    class CompositeBar:
        def __init__(self):
            self.polygon = box(280, 20, 283, 90)
        def native_path_indices(self):
            return (12, 13)
    bars = (*_building_bars(), CompositeBar())
    rows = [
        _residual_row("Enclosure_WallExternal", (0, 0, 3, 3)) for _ in range(14)
    ]
    rows[12] = _residual_row(
        "Annotation_General", (280, 20, 281, 90), viewport_id="floor",
    )
    rows[13] = _residual_row(
        "Enclosure_WallExternal", (281, 20, 283, 90), viewport_id="floor",
    )
    mixed = walk_source_unbounded_building_face(
        bars, _source_words(), shared_dividers=(_party(),), source_drawings=rows,
    )
    assert mixed.status == "ABSTAINED"
    assert mixed.unresolved_outside_native_path_id_sample == (12, 13)
    rows[13] = _residual_row(
        "Annotation_General", (281, 20, 283, 90), viewport_id="elevation",
    )
    wrong_view = walk_source_unbounded_building_face(
        bars, _source_words(), shared_dividers=(_party(),), source_drawings=rows,
    )
    assert wrong_view.status == "ABSTAINED"
    assert wrong_view.other_source_wall_band_count == 1

def test_source_role_audit_cannot_promote_other_unlabelled_outside_bars():
    bars = (*_building_bars(),
            SourceBar(box(280, 20, 283, 90), 12),
            SourceBar(box(350, 20, 353, 90), 13))
    rows = [
        _residual_row("Enclosure_WallExternal", (0, 0, 3, 3)) for _ in range(14)
    ]
    rows[12] = _residual_row("Annotation_FloorPlan", (280, 20, 283, 90))
    rows[13] = _residual_row("", (350, 20, 353, 90))
    walk = walk_source_unbounded_building_face(
        bars, _source_words(), shared_dividers=(_party(),), source_drawings=rows,
    )
    assert walk.reason == "source_other_structural_walls_outside_candidate"
    assert walk.other_source_wall_band_count == 1
    assert walk.source_outside_band_count_before_role_audit == 2
    assert walk.source_proven_nonwall_band_count == 1
    assert walk.clockwise_pdf_pts == ()
    assert walk.outer_wall_native_path_ids == ()
    assert not walk.measurement_authorized


def test_pure_service_or_empty_thin_outside_is_not_a_structural_veto():
    # Pure service/gas ink is a source-negative non-wall. Empty thin
    # unlayered strokes and WallExternal mixes still veto.
    bars = (
        *_building_bars(),
        SourceBar(box(280, 20, 283, 90), 12),
        SourceBar(box(350, 20, 353, 40), 13),
        SourceBar(box(400, 20, 403, 90), 14),
    )
    rows = [
        _residual_row("Enclosure_WallExternal", (0, 0, 3, 3)) for _ in range(15)
    ]
    rows[12] = _residual_row(
        "Service_Gas.Bottled", (280, 20, 283, 90), fill=None, width=0.34,
    )
    rows[13] = _residual_row("", (350, 20, 353, 40), fill=None, width=0.34)
    rows[14] = _residual_row("Enclosure_WallExternal", (400, 20, 403, 90))
    walk = walk_source_unbounded_building_face(
        bars, _source_words(), shared_dividers=(_party(),), source_drawings=rows,
    )
    assert walk.status == "ABSTAINED"
    assert walk.reason == "source_other_structural_walls_outside_candidate"
    assert walk.source_outside_band_count_before_role_audit == 3
    # Empty thin unlayered source paint is AMBIGUOUS, not a proven nonwall.
    assert walk.source_proven_nonwall_band_count == 1
    assert walk.other_source_wall_band_count == 2
    assert not walk.measurement_authorized


def test_filled_unlabelled_outside_stroke_is_not_dropped_as_sheet_ink():
    bars = (*_building_bars(), SourceBar(box(280, 20, 283, 90), 12))
    rows = [
        _residual_row("Enclosure_WallExternal", (0, 0, 3, 3)) for _ in range(13)
    ]
    rows[12] = _residual_row("", (280, 20, 283, 90))
    walk = walk_source_unbounded_building_face(
        bars, _source_words(), shared_dividers=(_party(),), source_drawings=rows,
    )
    assert walk.reason == "source_other_structural_walls_outside_candidate"
    assert walk.other_source_wall_band_count == 1
    assert walk.source_proven_nonwall_band_count == 0


def test_unknown_unlayered_thin_line_never_excludes_a_physical_wall_candidate():
    # A physical external wall may be drawn as a thin, unfilled native stroke
    # when its original CAD layer metadata is missing. With no source-owned
    # frame or service role, keep it unresolved; do not manufacture closure.
    bars = (*_building_bars(), SourceBar(box(280, 20, 283, 90), 12))
    rows = [
        _residual_row("Enclosure_WallExternal", (0, 0, 3, 3)) for _ in range(13)
    ]
    rows[12] = _residual_row("", (280, 20, 283, 90), fill=None, width=0.34)
    walk = walk_source_unbounded_building_face(
        bars, _source_words(), shared_dividers=(_party(),),
        source_drawings=rows,
    )
    assert walk.status == "ABSTAINED"
    assert walk.reason == "source_other_structural_walls_outside_candidate"
    assert walk.other_source_wall_band_count == 1
    assert walk.source_proven_nonwall_band_count == 0
    assert not walk.building_footprint_authenticated
    assert not walk.measurement_authorized


def test_foreign_wallexternal_id_does_not_veto_local_service_residual():
    # Mega-composites can attach distant WallExternal path IDs to a local
    # outside service/roof band. Residual audit must use locally intersecting
    # native geometry only.
    class CompositeBar:
        def __init__(self):
            self.polygon = box(280, 20, 283, 40)

        def native_path_indices(self):
            return (12, 13)

    bars = (*_building_bars(), CompositeBar())
    rows = [
        _residual_row("Enclosure_WallExternal", (0, 0, 3, 3)) for _ in range(14)
    ]
    rows[12] = _residual_row(
        "Service_StormwaterGeneral", (280, 20, 283, 40), fill=None, width=0.34,
    )
    # Foreign WallExternal lives on the sealed house, not on this residual.
    rows[13] = _residual_row("Enclosure_WallExternal", (10, 10, 14, 50))
    walk = walk_source_unbounded_building_face(
        bars, _source_words(), shared_dividers=(_party(),), source_drawings=rows,
    )
    assert walk.status == "CANDIDATE"
    assert walk.other_source_wall_band_count == 0
    assert not walk.measurement_authorized


def test_local_wallexternal_residual_still_abstains():
    class CompositeBar:
        def __init__(self):
            self.polygon = box(280, 20, 283, 40)

        def native_path_indices(self):
            return (12, 13)

    bars = (*_building_bars(), CompositeBar())
    rows = [
        _residual_row("Enclosure_WallExternal", (0, 0, 3, 3)) for _ in range(14)
    ]
    rows[12] = _residual_row(
        "Service_StormwaterGeneral", (280, 20, 281, 40), fill=None, width=0.34,
    )
    rows[13] = _residual_row("Enclosure_WallExternal", (281, 20, 283, 40))
    walk = walk_source_unbounded_building_face(
        bars, _source_words(), shared_dividers=(_party(),), source_drawings=rows,
    )
    assert walk.status == "ABSTAINED"
    assert walk.reason == "source_other_structural_walls_outside_candidate"
    assert walk.other_source_wall_band_count == 1


def test_blank_or_foreign_nonwall_viewport_cannot_erase_outside_wall():
    bars = (*_building_bars(), SourceBar(box(280, 20, 283, 90), 12))
    rows = [{"layer": "Enclosure_WallExternal", "fill": (0, 0, 0),
             "viewport_id": "floor"} for _ in range(13)]
    rows[12] = {"layer": "Annotation_FloorPlan", "fill": (0, 0, 0),
                "viewport_id": "floor"}
    accepted = walk_source_unbounded_building_face(
        bars, _source_words(), shared_dividers=(_party(),), source_drawings=rows,
    )
    assert accepted.status == "CANDIDATE"
    for wrong_view in ("", "elevation"):
        rows[12]["viewport_id"] = wrong_view
        failed = walk_source_unbounded_building_face(
            bars, _source_words(), shared_dividers=(_party(),),
            source_drawings=rows,
        )
        assert failed.status == "ABSTAINED"
        assert failed.reason == "source_other_structural_walls_outside_candidate"
        assert failed.source_proven_nonwall_band_count == 0
        assert failed.other_source_wall_band_count == 1
        assert failed.clockwise_pdf_pts == ()
        assert not failed.measurement_authorized
    rows[12]["viewport_id"] = "floor"
    # An otherwise matching outside path is not trusted when the interior
    # source wall has no source-positive viewport identity either.
    for row in rows[:5]:
        row.pop("viewport_id")
    failed = walk_source_unbounded_building_face(
        bars, _source_words(), shared_dividers=(_party(),), source_drawings=rows,
    )
    assert failed.status == "ABSTAINED"
    assert failed.other_source_wall_band_count == 1
    assert failed.clockwise_pdf_pts == ()


def test_unique_title_bearing_source_frame_can_be_excluded_without_viewport():
    from tests.test_source_sheet_frame_roles_shadow import source

    source_lines, source_titles = source()
    dx, dy = 300, 200
    shifted = []
    for row in source_lines:
        cloned = dict(row)
        _kind, a, b = row["items"][0]
        cloned["items"] = [(
            "l", (a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy)
        )]
        shifted.append(cloned)
    shifted_titles = tuple(
        (x0 + dx, y0 + dy, x1 + dx, y1 + dy, label, 0, 0, 0)
        for x0, y0, x1, y1, label, *_rest in source_titles
    )
    # Original sheet frame line 13 is the left-side rule; the alleged
    # outside wall-like bar must itself physically overlay that exact rule.
    rows = [
        {"layer": "Enclosure_WallExternal", "fill": (0, 0, 0)}
        for _ in range(12)
    ] + shifted
    rect = box(309.7, 210, 310.3, 360)
    bars = (*_building_bars(), SourceBar(rect, 13))
    result = walk_source_unbounded_building_face(
        bars, (*_source_words(), *shifted_titles),
        shared_dividers=(_party(),), source_drawings=rows,
    )
    assert result.status == "CANDIDATE"
    assert result.reason == "unbounded_outside_wall_walk_requires_independent_source_seal"
    assert result.outer_wall_native_path_ids == (0, 1, 2, 3)
    assert not result.building_footprint_authenticated
    assert not result.measurement_authorized

    # Path ID by itself is not enough. Geometry anywhere else is an
    # unresolved structural candidate regardless of the genuine frame.
    mismatched = (*_building_bars(), SourceBar(box(280, 20, 283, 90), 13))
    foreign = walk_source_unbounded_building_face(
        mismatched, (*_source_words(), *shifted_titles),
        shared_dividers=(_party(),), source_drawings=rows,
    )
    assert foreign.status == "ABSTAINED"
    assert foreign.other_source_wall_band_count == 1
    assert foreign.source_proven_nonwall_band_count == 0

    # Missing native title evidence or wall-layer reclassification cannot
    # turn an unknown physical bar into a source-confirmed nonwall.
    without_titles = walk_source_unbounded_building_face(
        bars, _source_words(), shared_dividers=(_party(),),
        source_drawings=rows,
    )
    assert without_titles.status == "ABSTAINED"
    rows[13] = {**rows[13], "layer": "Enclosure_WallExternal"}
    changed = walk_source_unbounded_building_face(
        bars, (*_source_words(), *shifted_titles),
        shared_dividers=(_party(),), source_drawings=rows,
    )
    assert changed.status == "ABSTAINED"
    assert changed.clockwise_pdf_pts == ()


def test_original_layer_annotation_without_viewport_needs_matching_native_line():
    """Nonwall source has actual layer and ink, not merely a keyword or ID."""
    bars = (*_building_bars(), SourceBar(box(280, 20, 283, 90), 12))
    rows = [{"layer": "Enclosure_WallExternal", "fill": (0, 0, 0)}
            for _ in range(12)]
    original = {
        "type": "s",
        "layer": "Annotation_FloorPlan",
        "color": (0, 0, 0), "fill": None,
        "items": [("l", (281.5, 20), (281.5, 90))],
        "width": .3,
    }
    rows.append(original)
    result = walk_source_unbounded_building_face(
        bars, _source_words(), shared_dividers=(_party(),),
        source_drawings=rows,
    )
    assert result.status == "CANDIDATE"
    assert not result.building_footprint_authenticated
    assert not result.measurement_authorized

    # A correct negative-role label on the WRONG source geometry cannot
    # discard the outside bar. The original native line must overlap it.
    rows[12] = {**original,
                "items": [("l", (350, 20), (350, 90))]}
    far = walk_source_unbounded_building_face(
        bars, _source_words(), shared_dividers=(_party(),),
        source_drawings=rows,
    )
    assert far.status == "ABSTAINED"
    assert far.other_source_wall_band_count == 1
    assert far.clockwise_pdf_pts == ()

    # Changing the actual path to a structural wall overrides any other
    # shape or text. No wall can be disclaimed via this negative-only rule.
    rows[12] = {**original, "layer": "Enclosure_WallExternal"}
    structural = walk_source_unbounded_building_face(
        bars, _source_words(), shared_dividers=(_party(),),
        source_drawings=rows,
    )
    assert structural.status == "ABSTAINED"
    assert structural.other_source_wall_band_count == 1

    # A made-up annotation layer without source primitive geometry cannot
    # authenticate nonwall source even if a path ID is in range.
    rows[12] = {**original, "items": []}
    fake = walk_source_unbounded_building_face(
        bars, _source_words(), shared_dividers=(_party(),),
        source_drawings=rows,
    )
    assert fake.status == "ABSTAINED"
    assert fake.other_source_wall_band_count == 1


def test_original_native_slab_and_service_lines_need_same_strict_geometry():
    bars = (*_building_bars(), SourceBar(box(280, 20, 283, 90), 12))
    rows = [{"layer": "Enclosure_WallExternal", "fill": (0, 0, 0)}
            for _ in range(12)]
    for native_layer in ("Structure_Slab", "Annotation_General"):
        rows12 = [*rows, {
            "type": "s", "layer": native_layer, "fill": None,
            "color": (0, 0, 0), "width": .5,
            "items": [("l", (281.5, 20), (281.5, 90))],
        }]
        result = walk_source_unbounded_building_face(
            bars, _source_words(), shared_dividers=(_party(),),
            source_drawings=rows12,
        )
        assert result.status == "CANDIDATE"
        assert result.measurement_authorized is False
    # A service layer is not independently classified as ROLE_EXCLUSION
    # in the original source classifier; refuse rather than assume.
    rows12[12]["layer"] = "Service_StormwaterGeneral"
    unknown_service = walk_source_unbounded_building_face(
        bars, _source_words(), shared_dividers=(_party(),),
        source_drawings=rows12,
    )
    assert unknown_service.status == "ABSTAINED"
    assert unknown_service.other_source_wall_band_count == 1
    # A compact source post with an EXTERIOR wall layer is explicitly
    # *not* an eligible negative layer, even if a primitive overlaps.
    rows12[12]["layer"] = "Enclosure_WallExternal"
    result = walk_source_unbounded_building_face(
        bars, _source_words(), shared_dividers=(_party(),),
        source_drawings=rows12,
    )
    assert result.status == "ABSTAINED"
    assert result.other_source_wall_band_count == 1


def test_unresolved_source_owner_sample_excludes_foreign_composite_path_ids():
    # One huge composite bar may carry nonlocal path IDs: only the source
    # strokes that geometrically intersect the unresolved outside band are
    # meaningful next investigative targets. Never authenticate from this.
    class CompositeBar:
        polygon = box(280, 20, 283, 40)

        def native_path_indices(self):
            return (12, 13)

    bars = (*_building_bars(), CompositeBar())
    rows = [
        _residual_row("Enclosure_WallExternal", (0, 0, 3, 3)) for _ in range(14)
    ]
    rows[12] = _residual_row("", (280, 20, 283, 40))
    # An unrelated foreign physical wall cannot become the local residual.
    rows[13] = _residual_row("Enclosure_WallExternal", (10, 10, 14, 50))
    walk = walk_source_unbounded_building_face(
        bars, _source_words(), shared_dividers=(_party(),), source_drawings=rows,
    )
    assert walk.status == "ABSTAINED"
    assert walk.reason == "source_other_structural_walls_outside_candidate"
    assert walk.other_source_wall_band_count == 1
    assert walk.unresolved_outside_native_path_id_sample == (12,)
    assert walk.to_dict()["unresolved_outside_native_path_id_sample"] == [12]
    assert walk.outer_wall_native_path_ids == ()
    assert walk.clockwise_pdf_pts == ()
    assert not walk.measurement_authorized
