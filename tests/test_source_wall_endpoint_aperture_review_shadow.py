"""Do not redetect windows/doors at source wall ink breaks: reuse native receipts."""

from dataclasses import replace

import fitz
from pb_new_wall_graph_diagnostic import NativeWallGraphDiagnostic
from pb_source_window_footprint_continuity import WindowFootprintBridge
from pb_source_sliding_door_footprint_continuity import (
    ExteriorSlidingDoorFootprintBridge,
)
from pb_source_wall_endpoint_aperture_review_shadow import (
    reconcile_original_wall_ink_endpoints_with_hosted_apertures as audit,
)


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
