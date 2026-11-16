"""Do not redetect windows/doors at source wall ink breaks: reuse native receipts."""

from dataclasses import dataclass, replace

import fitz
from shapely.geometry import Polygon, box

from pb_new_wall_graph_diagnostic import NativeWallGraphDiagnostic
from pb_source_sliding_door_footprint_continuity import (
    ExteriorSlidingDoorFootprintBridge,
)
from pb_source_wall_endpoint_aperture_review_shadow import (
    CONTACT_PT,
    STATUS_EXCLUSION,
    STATUS_INTERNAL,
    STATUS_UNION_COVERS,
    STATUS_UNMATCHED,
)
from pb_source_wall_endpoint_aperture_review_shadow import (
    reconcile_original_wall_ink_endpoints_with_hosted_apertures as audit,
)
from pb_source_window_footprint_continuity import WindowFootprintBridge


@dataclass
class _Bar:
    polygon: Polygon
    original_path_id: int

    def native_path_indices(self):
        return (self.original_path_id,)


def _drawings():
    return (
        {
            "rect": fitz.Rect(0, 0, 10, 2),
            "layer": "Enclosure_WallExternal",
            "fill": (0.0, 0.0, 0.0),
        },
        {
            "rect": fitz.Rect(20, 0, 30, 2),
            "layer": "Enclosure_WallExternal",
            "fill": (0.0, 0.0, 0.0),
        },
        {
            "rect": fitz.Rect(11, 3, 12, 4),
            "layer": "Annotation_General",
            "fill": (0.0, 0.0, 0.0),
        },
    )


def _window():
    return WindowFootprintBridge(
        left_host_path_id=0,
        right_host_path_id=1,
        marker_path_ids=(3, 4),
        label_text="ASW",
        bounds_pdf_pts=(10.0, 0.0, 20.0, 2.0),
        axis="h",
        page_index=2,
    )


def _graph():
    return NativeWallGraphDiagnostic(
        component_count=2,
        largest_component_band_count=2,
        largest_component_open_endpoints_pdf_pts=(
            (10.0, 1.0),
            (20.0, 1.0),
            (50.0, 50.0),
        ),
        connectivity_status="unclosed",
    )


def _run(*, graph=None, drawings=None, bridges=None, page=2):
    return audit(
        _graph() if graph is None else graph,
        source_page_index=page,
        original_source_drawings=_drawings() if drawings is None else drawings,
        existing_native_aperture_bridges=(_window(),) if bridges is None else bridges,
    )


def test_existing_original_source_window_is_not_redetected_as_missing_wall():
    original = _graph()
    result = _run(graph=original)
    assert result.source_hosted_aperture_terminal_count == 2
    assert result.source_unmatched_wall_ink_terminal_count == 1
    assert result.source_ambiguous_aperture_terminal_count == 0
    assert {x.original_aperture_kind for x in result.endpoint_reviews[:2]} == {"window"}
    assert all(x.original_host_path_ids == (0, 1) for x in result.endpoint_reviews[:2])
    assert result.endpoint_reviews[2].original_host_path_ids == ()
    assert original.component_count == 2  # no graph edits, no invented joins
    assert original.largest_component_open_endpoints_pdf_pts[0] == (10.0, 1.0)
    assert result.to_dict()["source_closed_outer_footprint_authenticated"] is False
    assert result.to_dict()["measurement_authorized"] is False


def test_printed_window_alone_or_fake_host_wall_cannot_cover_source_gap():
    altered = list(_drawings())
    altered[0] = dict(altered[0], layer="Finish_Floor")
    r = _run(drawings=altered)
    assert r.source_hosted_aperture_terminal_count == 0
    assert r.source_unmatched_wall_ink_terminal_count == 3
    altered[0] = dict(_drawings()[0], fill=(1.0, 1.0, 1.0))
    assert _run(drawings=altered).source_hosted_aperture_terminal_count == 0
    assert _run(bridges=()).source_hosted_aperture_terminal_count == 0


def test_wrong_page_and_unverified_viewport_cannot_match_hosted_aperture():
    assert _run(page=3).source_hosted_aperture_terminal_count == 0
    altered = list(_drawings())
    altered[0] = dict(altered[0], source_viewport_id="GROUND")
    altered[1] = dict(altered[1], source_viewport_id="ROOF")
    assert _run(drawings=altered).source_hosted_aperture_terminal_count == 0


def test_existing_sliding_and_window_conflict_abstains_no_arbitrary_pick():
    window = _window()
    sliding = ExteriorSlidingDoorFootprintBridge(
        first_host_path_id=0,
        second_host_path_id=1,
        jamb_cap_path_ids=(3, 4),
        sliding_track_path_ids=(5, 6, 7, 8),
        label_text="ASD",
        bounds_pdf_pts=(10.0, 0.0, 20.0, 2.0),
        axis="h",
        page_index=2,
    )
    r = _run(bridges=(window, sliding))
    assert r.source_hosted_aperture_terminal_count == 0
    assert r.source_ambiguous_aperture_terminal_count == 2
    assert r.source_unmatched_wall_ink_terminal_count == 1
    assert not r.measurement_authorized


def test_nearby_annotated_window_not_matching_an_actual_wall_host_end():
    graph = replace(
        _graph(),
        largest_component_open_endpoints_pdf_pts=((15.0, 1.0),),
    )
    r = _run(graph=graph)
    assert r.source_hosted_aperture_terminal_count == 0
    assert r.source_unmatched_wall_ink_terminal_count == 1


def test_unknown_aperture_receipts_do_not_create_wall_or_mask_endpoints():
    class FakeAperture:
        def __init__(self):
            self.page_index = 2
            self.left_host_path_id = 0
            self.right_host_path_id = 1
            self.bounds_pdf_pts = (10.0, 0.0, 20.0, 2.0)
            self.axis = "h"

    r = _run(bridges=(FakeAperture(),))
    assert r.source_hosted_aperture_terminal_count == 0
    assert r.source_unmatched_wall_ink_terminal_count == 3


def _leftover_drawings(layer):
    return _drawings() + (
        {
            "rect": fitz.Rect(49, 49, 51, 51),
            "layer": layer,
            "fill": (0.0, 0.0, 0.0),
        },
    )


def test_unique_joinery_terminal_on_post_aperture_union_is_not_missing_wall():
    original = _graph()
    r = audit(
        original,
        source_page_index=2,
        original_source_drawings=_leftover_drawings("Interior_Joinery"),
        existing_native_aperture_bridges=(_window(),),
        source_wall_union=box(49, 49, 51, 51),
        wall_bars=(_Bar(box(49, 49, 51, 51), 3),),
    )
    leftover = r.endpoint_reviews[2]
    assert leftover.status == STATUS_EXCLUSION
    assert leftover.source_owner_role == "exclusion"
    assert leftover.native_path_ids == (3,)
    assert r.source_hosted_aperture_terminal_count == 2
    assert r.source_unmatched_wall_ink_terminal_count == 0
    assert r.source_exclusion_or_joinery_terminal_count == 1
    assert original.largest_component_open_endpoints_pdf_pts[2] == (50.0, 50.0)
    assert r.measurement_authorized is False
    assert r.to_dict()["source_closed_outer_footprint_authenticated"] is False


def test_unique_internal_wall_terminal_is_not_building_outer_face():
    r = audit(
        _graph(),
        source_page_index=2,
        original_source_drawings=_leftover_drawings("Enclosure_WallInternal"),
        existing_native_aperture_bridges=(_window(),),
        source_wall_union=box(49, 49, 51, 51),
        wall_bars=(_Bar(box(49, 49, 51, 51), 3),),
    )
    assert r.endpoint_reviews[2].status == STATUS_INTERNAL
    assert r.source_internal_wall_terminal_count == 1
    assert r.source_unmatched_wall_ink_terminal_count == 0
    assert r.measurement_authorized is False


def test_exterior_terminal_on_own_source_union_is_not_verified_closed():
    r = audit(
        _graph(),
        source_page_index=2,
        original_source_drawings=_leftover_drawings("Enclosure_WallExternal"),
        existing_native_aperture_bridges=(_window(),),
        source_wall_union=box(49, 49, 51, 51),
        wall_bars=(_Bar(box(49, 49, 51, 51), 3),),
    )
    leftover = r.endpoint_reviews[2]
    # The union contains this exact wall bar; zero distance alone is NOT
    # a distinct wall continuation or a source-authenticated aperture.
    assert leftover.status == STATUS_UNMATCHED
    assert leftover.source_owner_role == "exterior"
    assert leftover.post_aperture_union_distance_pdf_pts == 0.0
    assert r.source_post_aperture_union_covered_terminal_count == 0
    assert r.source_unmatched_wall_ink_terminal_count == 1
    assert r.measurement_authorized is False


def test_both_free_ends_of_one_source_external_wall_stay_unmatched():
    # Without a second wall or an independent aperture, an isolated source
    # external bar is OPEN at both ends even though its own union covers both.
    bar = _Bar(box(0, 0, 10, 2), 0)
    drawing = {
        "rect": fitz.Rect(0, 0, 10, 2),
        "layer": "Enclosure_WallExternal",
        "fill": (0.0, 0.0, 0.0),
    }
    graph = NativeWallGraphDiagnostic(
        component_count=1,
        largest_component_band_count=1,
        largest_component_open_endpoints_pdf_pts=((0.0, 1.0), (10.0, 1.0)),
        connectivity_status="unclosed",
    )
    result = audit(
        graph,
        source_page_index=0,
        original_source_drawings=(drawing,),
        existing_native_aperture_bridges=(),
        source_wall_union=bar.polygon,
        wall_bars=(bar,),
    )
    assert result.source_unmatched_wall_ink_terminal_count == 2
    assert result.source_post_aperture_union_covered_terminal_count == 0
    assert all(row.status == STATUS_UNMATCHED for row in result.endpoint_reviews)
    assert all(row.source_owner_role == "exterior" for row in result.endpoint_reviews)
    assert all(row.post_aperture_union_distance_pdf_pts == 0.0 for row in result.endpoint_reviews)
    assert result.source_closed_outer_footprint_authenticated is False
    assert result.measurement_authorized is False


def test_exterior_terminal_off_union_stays_unmatched_no_snap():
    far = _Bar(box(52.5, 49, 55, 51), 3)
    r = audit(
        _graph(),
        source_page_index=2,
        original_source_drawings=_leftover_drawings("Enclosure_WallExternal"),
        existing_native_aperture_bridges=(_window(),),
        source_wall_union=box(80, 80, 90, 90),
        wall_bars=(far,),
    )
    leftover = r.endpoint_reviews[2]
    assert leftover.status == STATUS_UNMATCHED
    assert r.source_unmatched_wall_ink_terminal_count == 1
    near = box(52.5, 49, 55, 51).distance(box(49.9, 49.9, 50.1, 50.1))
    assert float(near) > CONTACT_PT
    assert r.measurement_authorized is False


def test_competing_joinery_and_external_roles_abstain():
    drawings = _leftover_drawings("Interior_Joinery") + (
        {
            "rect": fitz.Rect(49.2, 49.2, 50.8, 50.8),
            "layer": "Enclosure_WallExternal",
            "fill": (0.0, 0.0, 0.0),
        },
    )
    r = audit(
        _graph(),
        source_page_index=2,
        original_source_drawings=drawings,
        existing_native_aperture_bridges=(_window(),),
        source_wall_union=box(49, 49, 51, 51),
        wall_bars=(_Bar(box(49, 49, 51, 51), 3), _Bar(box(49.2, 49.2, 50.8, 50.8), 4)),
    )
    assert r.endpoint_reviews[2].status == "ambiguous_competing_source_roles"
    assert r.source_ambiguous_owner_role_terminal_count == 1
    assert r.source_unmatched_wall_ink_terminal_count == 0
    assert r.measurement_authorized is False


def test_original_3laurel_p3_raw_terminals_are_not_missing_outer_walls():
    import hashlib

    from pb_new_exterior_wall_preflight import attempt_source_native_outer_wall_first
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
        after = (len(page.get_drawings()), len(page.get_text("words")))
    assert before == after
    review = attempt.source_wall_endpoint_aperture_review
    graph = attempt.graph
    walk = attempt.source_outside_face_walk
    assert attempt.measurement_authorized is False
    assert review.measurement_authorized is False
    assert review.to_dict()["source_closed_outer_footprint_authenticated"] is False
    assert review.source_hosted_aperture_terminal_count == 1
    assert attempt.garage_door_footprint_bridges
    assert attempt.window_footprint_bridges
    # Figured dimensions like "21" must not silence unique printed ASD labels.
    assert len(attempt.sliding_door_footprint_bridges) >= 1
    assert all(
        str(b.label_text).strip().upper().startswith("ASD")
        for b in attempt.sliding_door_footprint_bridges
    )
    # Raw graph still has the original open tips; review does not join them.
    assert len(graph.largest_component_open_endpoints_pdf_pts) == 7
    raw_review_pts = {
        (round(pt[0], 3), round(pt[1], 3))
        for pt in (
            (730.408, 237.842),
            (739.212, 218.065),
            (759.621, 218.094),
            (784.708, 317.589),
            (839.983, 265.139),
            (863.653, 267.974),
        )
    }
    classified = {
        (round(row.endpoint_pdf_pts[0], 3), round(row.endpoint_pdf_pts[1], 3)): (
            row.status
        )
        for row in review.endpoint_reviews
    }
    for pt in raw_review_pts:
        assert classified[pt] != STATUS_UNMATCHED
        assert classified[pt] in {
            STATUS_EXCLUSION, STATUS_INTERNAL, STATUS_UNION_COVERS,
            "ambiguous_competing_source_roles",
        }
    assert walk is not None
    assert walk.status == "ABSTAINED"
    assert walk.measurement_authorized is False
    party = set(walk.internal_party_wall_native_path_ids or ())
    outer = set(walk.outer_wall_native_path_ids or ())
    assert not party.intersection(outer)
    assert party.intersection({1027, 1029, 1031, 1139})
