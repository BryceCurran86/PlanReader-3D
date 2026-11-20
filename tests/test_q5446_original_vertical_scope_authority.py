"""Cross-document vertical-scope protections; never create quantities from text."""
from __future__ import annotations

import pytest
from pb_gpt1_q5446_original_area_schedule_shadow import SOURCE_SHA256
from pb_gptmax_q5446_finish_support_shadow import SOURCE_IDS
from pb_q5446_original_vertical_scope_authority import (
    correlate_authenticated_q5446_vertical_scope,
    inspect_original_q5446_vertical_scope,
)

INC = (
    "INSULATION: Bradford R2.5 Glasswool batts to ceiling of roof space "
    "(excludes garage ceiling space). Reflective foil to external walls and "
    "wall between garage and house. CEILINGS: 2440mm nominal internal "
    "ceiling height, measured overall to frame plates. "
    "BATHROOM & ENSUITE: Ceramic wall tiles to shower recess, with floor "
    "tiles and skirting tiles throughout. "
    "LAUNDRY: Ceramic wall tiles above laundry tub, with floor tiles "
    "and skirting tiles throughout."
)
P4 = (
    "Promotion S 43 - 14 Provide full height ceramic wall tiling "
    "(as per standard range and specification) to master ensuite in lieu of standard. "
    "Promotion S 43 - 15 Provide 2740mm ceiling height to single storey/ground floor "
    "of double storey dwelling and garage including roof tilers guardrail in lieu of standard."
)
P5 = (
    "Promotion S 43 - 22 Provide 2340mm high x up to 820mm wide flush panel hinged "
    "doors to ground floor of dwelling in lieu of standard 2040mm high flush panel hinged doors. "
    "Note: Including standard rear garage access door (if applicable) (design specific). "
    "Promotion S 44 - 3 Provide 2400mm high standard hinged, sliding, alfresco "
    "door(s) in lieu of standard. Note: Only available with 2740mm ceiling heights."
)


def _derive(inc=INC, p4=P4, p5=P5, **overrides):
    source = dict(
        plan_sha256=SOURCE_SHA256,
        inclusions_sha256=SOURCE_IDS["standard_inclusions"],
        sales_sha256=SOURCE_IDS["scope_and_allowance_reference"],
    )
    source.update(overrides)
    return correlate_authenticated_q5446_vertical_scope(inc, p4, p5, **source)


def test_ground_promotion_does_not_falsely_override_first_floor():
    q = _derive()
    assert q.status == "SOURCE_CORROBORATED_VERTICAL_SCOPE_REVIEW"
    assert q.standard_frame_plate_nominal_height_mm == 2440
    assert q.promoted_ground_dwelling_and_garage_height_mm == 2740
    assert q.first_floor_nominal_reference_height_mm == 2440
    assert q.finished_ceiling_height_authorized is False
    assert q.physical_wall_height_authorized is False


def test_door_and_master_ensuite_scope_are_not_broadcast():
    q = _derive()
    assert q.promoted_hinged_sliding_alfresco_door_height_mm == 2400
    assert q.promoted_ground_flush_panel_hinged_door_height_mm == 2340
    assert q.promoted_ground_flush_panel_maximum_width_mm == 820
    assert q.installed_opening_height_authorized is False
    assert q.master_ensuite_full_height_wall_tile_scope is True
    assert q.other_wet_rooms_full_height_tile_scope is False
    assert q.standard_nonmaster_shower_recess_wall_tile_scope is True
    assert q.standard_laundry_above_tub_wall_tile_scope is True
    assert q.standard_wet_room_floor_and_skirting_tiles_scope is True
    assert q.roof_space_r25_glasswool_garage_ceiling_excluded is True
    assert q.reflective_wall_foil_between_garage_and_house_included is True
    assert q.commercial_quantity_authorized is False


def test_missing_master_ensuite_promotion_preserves_other_source_fields():
    q = _derive(p4=P4.replace(
        "Provide full height ceramic wall tiling "
        "(as per standard range and specification) to master ensuite in lieu of standard.",
        "",
    ))
    assert q.status == "SOURCE_CORROBORATED_VERTICAL_SCOPE_REVIEW"
    assert q.master_ensuite_full_height_wall_tile_scope is False


def test_missing_door_promotion_does_not_assume_nominal_door_height():
    q = _derive(p5="No authenticated door promotion")
    assert q.promoted_hinged_sliding_alfresco_door_height_mm is None
    assert q.promoted_ground_flush_panel_hinged_door_height_mm is None


def test_ground_flush_only_never_sets_2400mm_external_door_height():
    q = _derive(p5=P5.split("Promotion S 44 - 3")[0])
    assert q.status == "SOURCE_CORROBORATED_VERTICAL_SCOPE_REVIEW"
    assert q.promoted_ground_flush_panel_hinged_door_height_mm == 2340
    assert q.promoted_ground_flush_panel_maximum_width_mm == 820
    assert q.promoted_hinged_sliding_alfresco_door_height_mm is None
    assert q.installed_opening_height_authorized is False


def test_sliding_alfresco_only_never_promotes_ground_internal_flush_door():
    q = _derive(p5="Promotion S 44 - 3" + P5.split("Promotion S 44 - 3")[1])
    assert q.status == "SOURCE_CORROBORATED_VERTICAL_SCOPE_REVIEW"
    assert q.promoted_hinged_sliding_alfresco_door_height_mm == 2400
    assert q.promoted_ground_flush_panel_hinged_door_height_mm is None
    assert q.promoted_ground_flush_panel_maximum_width_mm is None
    assert q.commercial_quantity_authorized is False


@pytest.mark.parametrize("role", ["plan_sha256", "inclusions_sha256", "sales_sha256"])
def test_foreign_or_swapped_pdf_role_never_authorizes_height(role):
    q = _derive(**{role: "0" * 64})
    assert q.status == "ABSTAINED"
    assert q.to_dict()["commercial_quantity_authorized"] is False


@pytest.mark.parametrize("p4, reason", [
    ("No authenticated ground floor height.", "source_ground_floor_promotion_scope_unverified"),
    (P4.replace("dwelling and garage", "dwelling"),
     "source_ground_floor_promotion_scope_unverified"),
    (P4 + " Provide 2700mm ceiling height elsewhere.",
     "conflicting_or_ambiguous_original_ceiling_promotions"),
])
def test_missing_wrong_scope_or_competing_height_abstains(p4, reason):
    q = _derive(p4=p4)
    assert q.status == "ABSTAINED"
    assert q.reason_codes == (reason,)


def test_nominal_reference_not_authenticated_abstains():
    assert _derive(inc="Ceiling height unavailable").status == "ABSTAINED"


def test_private_original_three_document_height_scope_positive():
    from tests.original_source_q5446 import require_original_q5446_triple
    q = inspect_original_q5446_vertical_scope(*require_original_q5446_triple())
    assert q.status == "SOURCE_CORROBORATED_VERTICAL_SCOPE_REVIEW"
    assert q.promoted_ground_dwelling_and_garage_height_mm == 2740
    assert q.first_floor_nominal_reference_height_mm == 2440
    assert q.promoted_hinged_sliding_alfresco_door_height_mm == 2400
    assert q.promoted_ground_flush_panel_hinged_door_height_mm == 2340
    assert q.promoted_ground_flush_panel_maximum_width_mm == 820
    assert q.master_ensuite_full_height_wall_tile_scope is True
    assert q.roof_space_r25_glasswool_garage_ceiling_excluded is True
    assert q.reflective_wall_foil_between_garage_and_house_included is True
    assert q.standard_nonmaster_shower_recess_wall_tile_scope is True
    assert q.standard_laundry_above_tub_wall_tile_scope is True
    assert q.standard_wet_room_floor_and_skirting_tiles_scope is True
    assert q.commercial_quantity_authorized is False


def test_tampered_private_inclusions_abstain(tmp_path):
    from tests.original_source_q5446 import require_original_q5446_triple
    plan, inclusions, sales = require_original_q5446_triple()
    damaged = tmp_path / "untrusted_inclusions.pdf"
    damaged.write_bytes(inclusions.read_bytes() + b"\n%modified")
    q = inspect_original_q5446_vertical_scope(plan, damaged, sales)
    assert q.status == "ABSTAINED"
    assert q.reason_codes == ("original_vertical_source_sha_or_role_mismatch",)


def test_garage_ceiling_upgrade_does_not_claim_r25_batts_when_excluded():
    q = _derive()
    assert q.promoted_ground_dwelling_and_garage_height_mm == 2740
    assert q.roof_space_r25_glasswool_garage_ceiling_excluded is True
    assert q.reflective_wall_foil_between_garage_and_house_included is True
    assert q.commercial_quantity_authorized is False


def test_missing_insulation_statements_never_infer_garage_batts_scope():
    q = _derive(inc=INC.replace(
        "Bradford R2.5 Glasswool batts to ceiling of roof space "
        "(excludes garage ceiling space). ",
        "",
    ).replace(
        "Reflective foil to external walls and wall between garage and house. ",
        "",
    ))
    assert q.status == "SOURCE_CORROBORATED_VERTICAL_SCOPE_REVIEW"
    assert q.roof_space_r25_glasswool_garage_ceiling_excluded is False
    assert q.reflective_wall_foil_between_garage_and_house_included is False
    assert q.commercial_quantity_authorized is False


def test_standard_wet_room_wall_tile_scope_does_not_claim_full_height_elsewhere():
    q = _derive()
    assert q.master_ensuite_full_height_wall_tile_scope is True
    assert q.standard_nonmaster_shower_recess_wall_tile_scope is True
    assert q.standard_laundry_above_tub_wall_tile_scope is True
    assert q.other_wet_rooms_full_height_tile_scope is False
    assert q.physical_wall_height_authorized is False
    assert q.commercial_quantity_authorized is False


def test_unspecified_shower_and_laundry_tiles_do_not_get_inferred():
    q = _derive(inc=INC.replace(
        "Ceramic wall tiles to shower recess, with floor "
        "tiles and skirting tiles throughout. ",
        "",
    ).replace(
        "Ceramic wall tiles above laundry tub, with floor tiles "
        "and skirting tiles throughout.",
        "",
    ))
    assert q.standard_nonmaster_shower_recess_wall_tile_scope is False
    assert q.standard_laundry_above_tub_wall_tile_scope is False
    assert q.standard_wet_room_floor_and_skirting_tiles_scope is False
    assert q.other_wet_rooms_full_height_tile_scope is False
