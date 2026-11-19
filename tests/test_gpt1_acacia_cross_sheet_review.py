"""Source-neutral Acacia room exclusions, schedule owner and figured-height vetoes."""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_gpt1_acacia_source_packet import (
    ACACIA_ORIGINAL_SHA256, ACACIA_REQUIRED_ROLES,
    AcaciaOriginalPackage, AcaciaOriginalSheet,
)
from pb_gpt1_acacia_cross_sheet_review import (
    ROOM_KEY, SCHEDULE_CODES,
    AcaciaCrossSheetDimension, AcaciaOpeningWitness,
    reconcile_acacia_schedule_hosts, review_acacia_dimension_or_height,
    review_acacia_finishes, review_acacia_legend_room,
)


def _package():
    return AcaciaOriginalPackage(
        "ORIGINAL_ROLES_AUTHENTICATED_REVIEW_ONLY", "source-verified-review",
        ACACIA_ORIGINAL_SHA256["Brisbane"], "Brisbane", 10,
        tuple(AcaciaOriginalSheet(i, name, f"{i + 1}/10", scale,
                                  6917 if i == 1 else 2841 if i == 9 else 5000)
              for i, name, scale in ACACIA_REQUIRED_ROLES),
        original_byte_roles_verified=True,
    )


@pytest.mark.parametrize("outdoor_id", [1, 11, 12, 13, 14, 15])
def test_outdoor_courts_carport_services_cannot_be_indoor_floor_finish(outdoor_id):
    label, _kind = ROOM_KEY[outdoor_id]
    r = review_acacia_legend_room(
        _package(), outdoor_id, source_key_transcribed=label
    )
    assert r.status == "EXCLUDED_FROM_ENCLOSED_FINISH"
    assert r.floor_or_wall_quantity_authorized is False
    assert r.indoor_floor_finish_authorized is False


@pytest.mark.parametrize("inside", [2, 3, 4, 5, 6, 7, 8, 9, 10])
def test_nominal_room_key_name_is_not_a_physical_face(inside):
    r = review_acacia_legend_room(_package(), inside)
    assert r.status == "ROOM_LABEL_ONLY_NEEDS_PHYSICAL_FACE"
    assert r.floor_or_wall_quantity_authorized is False
    assert r.indoor_floor_finish_authorized is False


@pytest.mark.parametrize("key", [0, 16, "3", True, -1])
def test_spurious_unknown_or_untyped_key_never_mints_room(key):
    r = review_acacia_legend_room(_package(), key)
    assert r.status == "ABSTAINED"


def test_source_key_alias_wrong_name_abstains():
    r = review_acacia_legend_room(_package(), 11,
                                  source_key_transcribed="LIVING")
    assert r.status == "ABSTAINED"
    assert r.floor_or_wall_quantity_authorized is False


def test_forged_region_or_fake_source_packet_cannot_bind_physical_instances():
    bad = replace(_package(), source_sha256="0" * 64)
    assert review_acacia_legend_room(bad, 3).status == "ABSTAINED"
    assert reconcile_acacia_schedule_hosts(
        bad, (_receipt("W2"),)
    ).status == "ABSTAINED"
    assert review_acacia_finishes(bad)[0] == "ABSTAINED"


def _receipt(code="W2", *, host="opening-1", assembly="assembly-1",
             floor_path=400, schedule_path=500, verified=True):
    return AcaciaOpeningWitness(
        code, _package().source_sha256, 1, 9,
        (floor_path,), (schedule_path,),
        verified, host, assembly,
    )


def test_original_schedule_has_16_unique_codes_but_no_installation_count():
    assert len(SCHEDULE_CODES) == 16
    assert len(set(SCHEDULE_CODES)) == 16
    result = reconcile_acacia_schedule_hosts(_package(), ())
    assert result.status == "ABSTAINED"
    assert result.customer_row_authorized is False


def test_single_authentic_host_is_only_review_candidate():
    result = reconcile_acacia_schedule_hosts(
        _package(), (_receipt(),)
    )
    assert result.status == "HOST_SCHEDULE_CORRESPONDENCE_REVIEW_ONLY"
    assert result.authenticated_candidate_codes == ("W2",)
    assert result.candidate_assembly_ids == ("assembly-1",)
    assert result.installed_opening_quantity_authorized is False
    assert result.customer_row_authorized is False


def test_composite_w1_d1_share_one_aperture_not_two_wall_holes():
    windows = (
        _receipt("W1", host="shared-exterior-frame", assembly="W1D1", schedule_path=15),
        _receipt("D1", host="shared-exterior-frame", assembly="W1D1", schedule_path=16),
    )
    r = reconcile_acacia_schedule_hosts(_package(), windows)
    assert r.status == "HOST_SCHEDULE_CORRESPONDENCE_REVIEW_ONLY"
    assert r.composite_assembly_count == 1
    assert r.candidate_assembly_ids == ("W1D1",)
    assert r.customer_row_authorized is False


@pytest.mark.parametrize("bad", [
    _receipt("W8"),
    _receipt("W2", floor_path=6917),
    _receipt("W2", schedule_path=2841),
    _receipt("W2", verified=False),
    _receipt("W2", floor_path=-1),
    _receipt("W2", host=""),
    replace(_receipt("W2"), original_source_sha256="e" * 64),
    replace(_receipt("W2"), floor_page_index=0),
    replace(_receipt("W2"), schedule_page_index=8),
])
def test_unknown_unhosted_foreign_or_out_of_range_opening_abstains(bad):
    r = reconcile_acacia_schedule_hosts(_package(), (bad,))
    assert r.status == "ABSTAINED"
    assert not r.authenticated_candidate_codes
    assert r.customer_row_authorized is False


def test_competing_codes_on_one_host_cannot_look_like_two_openings():
    r = reconcile_acacia_schedule_hosts(
        _package(),
        (_receipt("W2"), _receipt("W3", schedule_path=501)),
    )
    assert r.status == "ABSTAINED"
    assert r.reasons == ("competing_schedule_codes_one_physical_host",)


def test_same_physical_aperture_and_same_code_cannot_be_counted_twice():
    r = reconcile_acacia_schedule_hosts(
        _package(), (_receipt("W2"), _receipt("W2")),
    )
    assert r.status == "ABSTAINED"
    assert r.reasons == ("duplicate_physical_aperture_schedule_code",)


def test_one_assembly_cannot_be_reused_on_two_distant_hosts():
    r = reconcile_acacia_schedule_hosts(
        _package(), (_receipt("SD1"), _receipt("SD2", host="distant", schedule_path=510)),
    )
    assert r.status == "ABSTAINED"
    assert r.reasons == ("one_assembly_reused_on_distinct_floor_hosts",)


def _dim(kind="figured_setout"):
    return AcaciaCrossSheetDimension(
        kind, _package().source_sha256, 8 if kind == "figured_setout" else 7,
        1, (4000,), (100,), 2400., True,
    )


def test_setout_and_section_host_witnesses_are_not_quantities():
    for kind in ("figured_setout", "section_height"):
        status, reason = review_acacia_dimension_or_height(
            _package(), _dim(kind)
        )
        assert status == "SOURCE_FIGURE_AND_PHYSICAL_HOST_REVIEW_ONLY"
        assert "no_finished_face" in reason


@pytest.mark.parametrize("tamper", [
    {"source_sha256": "0" * 64},
    {"reference_page_index": 7},
    {"floor_page_index": 9},
    {"floor_wall_face_native_path_ids": ()},
    {"reference_figure_native_path_ids": ()},
    {"figured_value_mm": 0.0},
    {"figured_value_mm": float("nan")},
    {"source_role_and_physical_host_independently_verified": False},
])
def test_dimension_wrong_provenance_or_host_abstains(tamper):
    r = review_acacia_dimension_or_height(
        _package(), replace(_dim(), **tamper)
    )
    assert r[0] == "ABSTAINED"


def test_missing_design_options_spec_never_assigns_paint_tile_or_ceiling_finish():
    status, reason = review_acacia_finishes(_package())
    assert status == "ABSTAINED"
    assert reason == "acacia_house_design_options_material_specification_missing"


@pytest.mark.parametrize("kind", ("figured_setout", "section_height"))
@pytest.mark.parametrize("tamper", [
    {"floor_wall_face_native_path_ids": (6917,)},  # floor p2 exclusive bound
    {"floor_wall_face_native_path_ids": (4000, 4000)},  # duplicate source mark
    {"floor_wall_face_native_path_ids": (True,)},  # bool is not an index
    {"floor_wall_face_native_path_ids": ("4000",)},
    {"floor_wall_face_native_path_ids": [4000]},  # mutable/untyped witness
    {"reference_figure_native_path_ids": (5000,)},  # p8/p9 exclusive bound
    {"reference_figure_native_path_ids": (100, 100)},
    {"reference_figure_native_path_ids": (True,)},
    {"reference_figure_native_path_ids": ("100",)},
    {"reference_figure_native_path_ids": [100]},
    {"source_role_and_physical_host_independently_verified": "yes"},
    {"source_role_and_physical_host_independently_verified": 1},
])
def test_cross_sheet_native_path_identity_must_be_bounded_and_typed(kind, tamper):
    result = review_acacia_dimension_or_height(
        _package(), replace(_dim(kind), **tamper)
    )
    assert result == (
        "ABSTAINED", "original_cross_page_physical_host_or_figure_unverified"
    )


@pytest.mark.parametrize("kind", ("figured_setout", "section_height"))
@pytest.mark.parametrize("page_index", (1, 7, 8, 9))
@pytest.mark.parametrize("invalid_count", (0, True, -1, "5000"))
def test_untrusted_original_native_path_census_cannot_admit_dimension(
    kind, page_index, invalid_count,
):
    packet = _package()
    bad_sheets = tuple(
        replace(s, source_page_path_count=invalid_count)
        if s.page_index == page_index else s for s in packet.sheets
    )
    assert review_acacia_dimension_or_height(
        replace(packet, sheets=bad_sheets), _dim(kind)
    )[0] == "ABSTAINED"


@pytest.mark.parametrize("kind", ("figured_setout", "section_height"))
def test_cross_sheet_last_valid_native_index_is_still_review_only(kind):
    packet = _package()
    source_page = 8 if kind == "figured_setout" else 7
    sheet_counts = {s.page_index: s.source_page_path_count for s in packet.sheets}
    witness = replace(
        _dim(kind),
        floor_wall_face_native_path_ids=(sheet_counts[1] - 1,),
        reference_figure_native_path_ids=(sheet_counts[source_page] - 1,),
    )
    status, reason = review_acacia_dimension_or_height(packet, witness)
    assert status == "SOURCE_FIGURE_AND_PHYSICAL_HOST_REVIEW_ONLY"
    assert "no_finished_face_or_customer_metric_authority" in reason


@pytest.mark.parametrize("tamper", [
    {"floor_host_native_path_ids": None},
    {"floor_host_native_path_ids": []},
    {"floor_host_native_path_ids": [400]},
    {"floor_host_native_path_ids": (True,)},
    {"floor_host_native_path_ids": ("400",)},
    {"floor_host_native_path_ids": (400, 400)},
    {"schedule_native_path_ids": None},
    {"schedule_native_path_ids": []},
    {"schedule_native_path_ids": [500]},
    {"schedule_native_path_ids": (True,)},
    {"schedule_native_path_ids": ("500",)},
    {"schedule_native_path_ids": (500, 500)},
    {"original_host_ink_authenticated": "yes"},
    {"original_host_ink_authenticated": 1},
    {"physical_aperture_identity": 15},
    {"physical_aperture_identity": "   "},
    {"assembly_identity": 15},
    {"assembly_identity": "   "},
])
def test_malformed_acacia_host_receipt_abstains_without_exception(tamper):
    receipt = replace(_receipt("W2"), **tamper)
    result = reconcile_acacia_schedule_hosts(_package(), (receipt,))
    assert result.status == "ABSTAINED"
    assert result.reasons == ("unproved_floor_or_schedule_source_host",)
    assert result.installed_opening_quantity_authorized is False
    assert result.customer_row_authorized is False


@pytest.mark.parametrize("field,invalid", [
    ("floor", 0),
    ("floor", True),
    ("floor", -1),
    ("floor", "6917"),
    ("schedule", 0),
    ("schedule", True),
    ("schedule", -1),
    ("schedule", "2841"),
])
def test_untrusted_acacia_original_path_census_rejects_opening_host(
    field, invalid,
):
    packet = _package()
    original_page = 1 if field == "floor" else 9
    poisoned_sheets = tuple(
        replace(s, source_page_path_count=invalid)
        if s.page_index == original_page else s for s in packet.sheets
    )
    result = reconcile_acacia_schedule_hosts(
        replace(packet, sheets=poisoned_sheets), (_receipt("W2"),)
    )
    assert result.status == "ABSTAINED"
    assert result.customer_row_authorized is False


def test_last_in_range_acacia_opening_path_stays_noncommercial():
    witness = _receipt("SD3", floor_path=6916, schedule_path=2840)
    result = reconcile_acacia_schedule_hosts(_package(), (witness,))
    assert result.status == "HOST_SCHEDULE_CORRESPONDENCE_REVIEW_ONLY"
    assert result.installed_opening_quantity_authorized is False
    assert result.customer_row_authorized is False


@pytest.mark.parametrize("bad_source_page_count", (0, 9, 11, True, "10"))
def test_acacia_review_requires_exact_original_ten_page_role_packet(
    bad_source_page_count,
):
    packet = replace(_package(), source_pages=bad_source_page_count)
    assert review_acacia_finishes(packet) == (
        "ABSTAINED", "original_four_sheet_roles_unverified"
    )
    assert review_acacia_dimension_or_height(packet, _dim("section_height"))[0] == "ABSTAINED"
    assert reconcile_acacia_schedule_hosts(packet, (_receipt("W2"),)).status == "ABSTAINED"


@pytest.mark.parametrize("invalid_number", ("3/10", "2/9", "", None))
def test_acacia_review_rejects_wrong_scheduled_original_drawing_number(
    invalid_number,
):
    packet = _package()
    corrupted = tuple(
        replace(sheet, drawing_number=invalid_number)
        if sheet.page_index == 1 else sheet
        for sheet in packet.sheets
    )
    rejected = replace(packet, sheets=corrupted)
    assert review_acacia_legend_room(rejected, 3).status == "ABSTAINED"
    assert reconcile_acacia_schedule_hosts(rejected, (_receipt("W2"),)).status == "ABSTAINED"


def test_truthy_original_byte_roles_flag_does_not_authenticate_acacia():
    poisoned = replace(_package(), original_byte_roles_verified="yes")
    assert review_acacia_legend_room(poisoned, 3).status == "ABSTAINED"
    assert review_acacia_finishes(poisoned)[0] == "ABSTAINED"


def test_two_aperture_ids_cannot_reuse_identical_floor_native_witness():
    # Distinct string identities cannot multiply the same installed source
    # observation into two commercial openings. No source dimensions guessed.
    r = reconcile_acacia_schedule_hosts(
        _package(),
        (_receipt("W2", host="opening-a", assembly="frame-a", floor_path=400),
         _receipt("W3", host="opening-b", assembly="frame-b",
                  floor_path=400, schedule_path=501)),
    )
    assert r.status == "ABSTAINED"
    assert r.reasons == ("native_host_witness_reused_for_distinct_apertures",)
    assert not r.customer_row_authorized


def test_distinct_floor_native_hosts_remain_review_only():
    r = reconcile_acacia_schedule_hosts(
        _package(),
        (_receipt("W2", host="opening-a", assembly="frame-a", floor_path=400),
         _receipt("W3", host="opening-b", assembly="frame-b",
                  floor_path=401, schedule_path=501)),
    )
    assert r.status == "HOST_SCHEDULE_CORRESPONDENCE_REVIEW_ONLY"
    assert not r.installed_opening_quantity_authorized


def test_unbounded_or_oversized_opening_receipts_fail_closed():
    # Never consume unlimited foreign iterables into memory.
    def source():
        for index in range(300):
            yield _receipt("W2", host=f"opening-{index}",
                           assembly=f"frame-{index}", floor_path=index)
    r = reconcile_acacia_schedule_hosts(_package(), source())
    assert r.status == "ABSTAINED"
    assert r.reasons == ("schedule_host_receipts_over_limit",)
    assert not r.customer_row_authorized
