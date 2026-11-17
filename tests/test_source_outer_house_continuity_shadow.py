"""Outer-house/garage continuity: no snap, no x-crop, outdoor proof only."""
from __future__ import annotations

from types import SimpleNamespace

from shapely.geometry import box

from pb_migration_contracts import EvidenceResolutionStatus
from pb_new_exterior_wall_preflight import attempt_source_native_outer_wall_first
from pb_source_native_exterior_endpoint_authority_shadow import REASON_NEAR_MISS
from pb_source_outer_house_continuity_shadow import (
    ROLE_OUTDOOR,
    ROLE_POST,
    ROLE_STRUCTURAL,
    ROLE_UNPROVEN,
    authenticate_outer_house_seams,
    bar_proven_outside_envelope,
    census_source_outside_candidate,
    classify_outside_envelope_role,
)


def _strip(source_id, bounds):
    return SimpleNamespace(
        polygon=box(*bounds),
        path_index=source_id,
        native_path_indices=lambda: (source_id,),
    )


def _drawing(layer="Enclosure_WallExternal"):
    return {"layer": layer, "fill": (0.0, 0.0, 0.0)}


class _Rect:
    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1


def _filled_wall(bounds, layer="Enclosure_WallExternal"):
    x0, y0, x1, y1 = bounds
    return {
        "layer": layer,
        "fill": (0.0, 0.0, 0.0),
        "color": None,
        "rect": bounds,
        "items": (("re", _Rect(x0, y0, x1, y1)),),
    }


def test_point425_and_wider_outer_seams_are_not_snapped():
    drawings = (_drawing(), _drawing(), _drawing(), _drawing(), _drawing(), _drawing())
    bars = (
        _strip(0, (0, 0, 10, 1)),
        _strip(1, (10.425, 0, 20.425, 1)),
        _strip(2, (30, 0, 40, 1)),
        _strip(3, (40.850, 0, 50.850, 1)),
        _strip(4, (60, 0, 70, 1)),
        _strip(5, (71.984, 0, 81.984, 1)),
    )
    seams = authenticate_outer_house_seams(bars, drawings)
    seps = {round(item["separation_pdf_pts"], 3) for item in seams}
    assert {0.425, 0.85, 1.984} <= seps
    assert all(item["snap_join_applied"] is False for item in seams)
    assert all(item["physical_join_authenticated"] is False for item in seams)
    assert all(item["status"] == EvidenceResolutionStatus.ABSTAINED.value for item in seams)
    assert all(item["reason"] == REASON_NEAR_MISS for item in seams)


def test_shared_living_alfresco_wall_is_kept_as_envelope():
    bar = _strip(0, (100, 100, 200, 103))
    drawings = (_drawing(),)
    words = (
        (110, 99, 160, 104, "LIVING"),
        (170, 99, 210, 104, "ALFRESCO"),
    )
    role, reason = classify_outside_envelope_role(bar, drawings, words)
    assert role == ROLE_STRUCTURAL
    assert "kept_as_envelope" in reason
    assert bar_proven_outside_envelope(bar, drawings, words) is False


def test_unique_alfresco_label_excludes_only_that_bar():
    outdoor = _strip(0, (600, 100, 700, 103))
    house = _strip(1, (800, 100, 900, 103))
    drawings = (_drawing(), _drawing())
    words = ((620, 99, 680, 104, "ALFRESCO"), (820, 99, 860, 104, "BED5"))
    outdoor_role, _ = classify_outside_envelope_role(outdoor, drawings, words)
    house_role, _ = classify_outside_envelope_role(house, drawings, words)
    # The printed ALFRESCO label identifies the outdoor space, not the
    # physically painted exterior wall face beside that space.
    assert outdoor_role == ROLE_STRUCTURAL
    assert bar_proven_outside_envelope(outdoor, drawings, words) is False
    assert house_role in {ROLE_STRUCTURAL, ROLE_UNPROVEN}
    assert bar_proven_outside_envelope(house, drawings, words) is False


def test_unique_post_label_is_not_a_wall():
    post = _strip(0, (410, 200, 414, 204))
    drawings = (_drawing("Structure_Post"),)
    words = ((409, 199, 416, 205, "POST"),)
    role, _reason = classify_outside_envelope_role(post, drawings, words)
    assert role == ROLE_POST
    assert bar_proven_outside_envelope(post, drawings, words) is True


def test_naive_x_crop_is_never_applied_to_right_house_bars():
    drawings = (
        _filled_wall((100, 100, 400, 110)),
        _filled_wall((100, 340, 400, 350)),
        _filled_wall((100, 100, 110, 350)),
        _filled_wall((390, 100, 400, 350)),
        _filled_wall((780, 190, 990, 193)),
    )
    census = census_source_outside_candidate(drawings, page_index=2)
    assert census["naive_x_filter_applied"] is False
    assert census["snap_join_applied"] is False
    assert census["measurement_authorized"] is False
    right = [row for row in census["outside_bars"] if row["bounds_pdf_pts"][0] >= 780]
    assert right
    assert all(row["envelope_role"] != ROLE_OUTDOOR for row in right)


def test_proven_outdoor_ink_does_not_drop_right_house_from_preflight():
    house = [
        _filled_wall((100, 100, 400, 110)),
        _filled_wall((100, 340, 400, 350)),
        _filled_wall((100, 100, 110, 350)),
        _filled_wall((390, 100, 400, 350)),
    ]
    outdoor = _filled_wall((600, 120, 690, 123))
    right = _filled_wall((780, 190, 990, 193))
    words = ((610, 119, 670, 124, "PORCH"), (800, 189, 850, 194, "GARAGE"))
    attempt = attempt_source_native_outer_wall_first(
        house + [outdoor, right],
        source_ink_already_scoped=True,
        source_words=words,
    )
    assert attempt.status == "ABSTAINED"
    assert attempt.reason == "source_exterior_other_wall_ink_outside_candidate"
    assert attempt.measurement_authorized is False
    assert attempt.rejected_candidate_bbox_pdf_pts is not None


def test_sliding_detector_is_consumed_not_reimplemented():
    from pb_new_exterior_wall_preflight import detect_exterior_sliding_door_footprint_bridges

    module = getattr(detect_exterior_sliding_door_footprint_bridges, "__module__", "")
    assert module in {
        "pb_source_sliding_door_footprint_continuity",
        "pb_new_exterior_wall_preflight",
    }
    attempt = attempt_source_native_outer_wall_first((), source_ink_already_scoped=True)
    assert attempt.sliding_door_footprint_bridges == ()
    assert attempt.measurement_authorized is False


def test_grey_seam_detector_is_consumed_not_reimplemented():
    from pb_new_exterior_wall_preflight import detect_source_neutral_wall_seams

    module = getattr(detect_source_neutral_wall_seams, "__module__", "")
    assert module in {
        "pb_source_neutral_wall_seam_continuity",
        "pb_new_exterior_wall_preflight",
    }
    attempt = attempt_source_native_outer_wall_first((), source_ink_already_scoped=True)
    assert attempt.neutral_wall_seams == ()
    assert attempt.measurement_authorized is False


def test_rejected_left_loop_keeps_4373_census_and_right_house():
    house = [
        _filled_wall((100, 100, 400, 110)),
        _filled_wall((100, 340, 400, 350)),
        _filled_wall((100, 100, 110, 350)),
        _filled_wall((390, 100, 400, 350)),
    ]
    right = _filled_wall((780, 190, 990, 193))
    attempt = attempt_source_native_outer_wall_first(
        house + [right], source_ink_already_scoped=True,
    )
    assert attempt.status == "ABSTAINED"
    assert attempt.reason == "source_exterior_other_wall_ink_outside_candidate"
    assert attempt.diagnostic_closed_wall_loop_count == 1
    assert attempt.diagnostic_rejected_loop_bbox_pdf_pts == attempt.rejected_candidate_bbox_pdf_pts
    assert attempt.diagnostic_wall_bands_outside_loop >= 1
    assert 4 in attempt.diagnostic_outside_source_path_sample
    census = census_source_outside_candidate(house + [right])
    assert census["left_only_closed_loop_rejected"] is True
    assert census["naive_x_filter_applied"] is False
    assert census["measurement_authorized"] is False


def test_true_master_bed_exterior_wall_beside_porch_text_is_not_discarded():
    # Original 3Laurel top master-bedroom wall lies near a PORCH annotation.
    # Label proximity must not remove its physical Enclosure_WallExternal ink.
    bar = _strip(0, (884.629, 189.637, 989.511, 192.431))
    drawings = (_drawing("Enclosure_WallExternal"),)
    words = ((960, 188, 985, 193, "PORCH"),)
    role, reason = classify_outside_envelope_role(bar, drawings, words)
    assert role == ROLE_STRUCTURAL
    assert reason == "original_source_wall_kept_despite_outdoor_text"
    assert bar_proven_outside_envelope(bar, drawings, words) is False


def test_unknown_layer_outdoor_label_is_not_physical_exclusion_proof():
    bar = _strip(0, (100, 100, 200, 103))
    drawings = (_drawing("UnlabelledNativePaths"),)
    words = ((110, 99, 150, 104, "ALFRESCO"),)
    role, reason = classify_outside_envelope_role(bar, drawings, words)
    assert role == ROLE_UNPROVEN
    assert reason == "outdoor_name_alone_does_not_exclude_wall"
    assert bar_proven_outside_envelope(bar, drawings, words) is False


def test_independent_roof_site_layer_can_still_exclude_non_wall_ink():
    bar = _strip(0, (100, 100, 200, 103))
    drawings = (_drawing("Site_Roof_Outline"),)
    words = ((110, 99, 150, 104, "ALFRESCO"),)
    role, reason = classify_outside_envelope_role(bar, drawings, words)
    assert role == ROLE_OUTDOOR
    assert reason.startswith("source_exclusion_")
    assert bar_proven_outside_envelope(bar, drawings, words) is True


def test_composite_with_a_real_wall_owner_cannot_be_discarded_as_roof():
    bar = SimpleNamespace(
        polygon=box(100, 100, 200, 103),
        path_index=0,
        native_path_indices=lambda: (0, 1),
    )
    drawings = (_drawing("Site_Roof_Outline"), _drawing("Enclosure_WallExternal"))
    words = ((110, 99, 150, 104, "ALFRESCO"),)
    role, _reason = classify_outside_envelope_role(bar, drawings, words)
    assert role == ROLE_STRUCTURAL
    assert bar_proven_outside_envelope(bar, drawings, words) is False


def test_post_label_next_to_long_wall_does_not_turn_wall_into_post():
    bar = _strip(0, (100, 100, 200, 103))
    drawings = (_drawing("Enclosure_WallExternal"),)
    words = ((110, 99, 145, 104, "POST"),)
    role, _reason = classify_outside_envelope_role(bar, drawings, words)
    assert role == ROLE_STRUCTURAL
    assert bar_proven_outside_envelope(bar, drawings, words) is False


def test_compact_post_label_must_not_override_original_wall_layer():
    bar = _strip(0, (410, 200, 414, 204))
    drawings = (_drawing("Enclosure_WallExternal"),)
    words = ((409, 199, 416, 205, "POST"),)
    role, reason = classify_outside_envelope_role(bar, drawings, words)
    assert role == ROLE_STRUCTURAL
    assert reason == "original_source_wall_kept_despite_outdoor_text"
    assert not bar_proven_outside_envelope(bar, drawings, words)
