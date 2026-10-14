"""Material classification must honour the dominant authenticated finish.

An incidental grout or skirting adjective does not turn a tile floor into
epoxy/paint. Competing explicit finishing systems must remain unresolved.
"""
from pb_material_schedule_v1222 import semantic_finish_from_schedule_entry as semantic


def test_source_defined_floor_tile_with_grout_and_satin_skirt_is_tile():
    entry = {
        "status": "Confirmed",
        "description": (
            "Stoneware FLOOR TILE - 600x600 grey slip-rated surface. "
            "GROUT: GREY EPOXY. 100MM ALUMINIUM SKIRTING - BLACK SATIN"
        ),
        "substrate": "",
        "finish": (
            "Stoneware FLOOR TILE - 600x600 grey slip-rated surface. "
            "GROUT: GREY EPOXY. 100MM ALUMINIUM SKIRTING - BLACK SATIN"
        ),
    }
    assert semantic(entry) == "tile"


def test_explicit_coating_on_a_separate_non_tile_finish_remains_paint():
    assert semantic({
        "status": "Confirmed",
        "description": "Fibre cement panels",
        "substrate": "Fibre Cement",
        "finish": "Dulux low sheen paint",
    }) == "paint"


def test_independently_specified_tile_and_paint_in_one_ambiguous_field_abstains():
    assert semantic({
        "status": "Confirmed",
        "description": "Floor tile and wall paint",
        "finish": "Porcelain FLOOR TILE; separate paint on wall",
    }) == ""


def test_no_independent_finish_authority_abstains():
    assert semantic({
        "status": "Candidate",
        "description": "Porcelain floor tile",
        "finish": "Porcelain floor tile",
    }) == ""


def test_floor_tile_epoxy_grout_not_misclassified_as_epoxy_finish():
    assert semantic({
        "status": "Confirmed",
        "description": "Porcelain floor tiles with epoxy grout",
        "finish": "Porcelain floor tiles with epoxy grout",
    }) == "tile"


def test_strict_satin_only_finish_still_paint():
    assert semantic({
        "status": "Confirmed",
        "description": "Wall",
        "finish": "Black satin",
    }) == "paint"
