"""
test_source_spider_fitting_glass_fin_shadow.py

Unit tests for SourceSpiderFittingGlassFinShadowAuthority.
"""

import pytest
from pb_source_spider_fitting_glass_fin_shadow import (
    SourceSpiderFittingGlassFinShadowAuthority,
    SpiderFittingType,
    FinSupportType,
    GlassFinSpec,
    SpiderFittingSpec,
    PointSupportedFacadeExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_spider_fitting_callout_parsing():
    parsed1 = SourceSpiderFittingGlassFinShadowAuthority.parse_spider_callout(
        "4-WAY SPIDER FITTING SS316 W/ M14 ROTULES GLASS FIN MOUNTED"
    )
    assert parsed1["fitting_type"] == SpiderFittingType.FOUR_ARM
    assert parsed1["rotule_dia_mm"] == 14.0
    assert parsed1["support_type"] == FinSupportType.GLASS_FIN

    parsed2 = SourceSpiderFittingGlassFinShadowAuthority.parse_spider_callout(
        "2-WAY 90 DEGREE CORNER SPIDER M16 ROTULE"
    )
    assert parsed2["fitting_type"] == SpiderFittingType.TWO_ARM_90
    assert parsed2["rotule_dia_mm"] == 16.0

    parsed3 = SourceSpiderFittingGlassFinShadowAuthority.parse_spider_callout(
        "SINGLE ARM SPIDER STEEL COLUMN MOUNTED"
    )
    assert parsed3["fitting_type"] == SpiderFittingType.SINGLE_ARM
    assert parsed3["support_type"] == FinSupportType.STEEL_COLUMN


def test_glass_fin_callout_parsing():
    parsed_fin1 = SourceSpiderFittingGlassFinShadowAuthority.parse_fin_callout(
        "19mm TOUGHENED GLASS FIN 300mm DEEP H=4.5m"
    )
    assert parsed_fin1["thickness_mm"] == 19.0
    assert parsed_fin1["depth_mm"] == 300.0
    assert parsed_fin1["height_m"] == 4.5
    assert parsed_fin1["is_laminated"] is False

    parsed_fin2 = SourceSpiderFittingGlassFinShadowAuthority.parse_fin_callout(
        "21.52mm LAMINATED STRUCTURAL GLASS FIN 400MM DEEP H=6.0M"
    )
    assert parsed_fin2["thickness_mm"] == 21.52
    assert parsed_fin2["depth_mm"] == 400.0
    assert parsed_fin2["height_m"] == 6.0
    assert parsed_fin2["is_laminated"] is True


def test_facade_snapping():
    pt = (123.4, 456.7)
    snapped = SourceSpiderFittingGlassFinShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (122.5, 457.5)


def test_facade_evaluation_quantities():
    fittings_data = [
        {
            "fitting_id": "SP-01",
            "center_point": (100.0, 100.0),
            "callout": "4-WAY SPIDER FITTING M14 ROTULES",
            "associated_fin_id": "FIN-01",
        },
        {
            "fitting_id": "SP-02",
            "center_point": (100.0, 200.0),
            "callout": "2-WAY 180 DEGREE SPIDER",
            "associated_fin_id": "FIN-01",
        },
        {
            "fitting_id": "SP-03",
            "center_point": (100.0, 300.0),
            "callout": "SINGLE ARM SPIDER",
            "associated_fin_id": "FIN-01",
        },
    ]

    fins_data = [
        {
            "fin_id": "FIN-01",
            "center_point": (100.0, 0.0),
            "callout": "19mm TOUGHENED GLASS FIN 300mm DEEP H=4.5m",
        },
        {
            "fin_id": "FIN-02",
            "center_point": (200.0, 0.0),
            "callout": "19mm TOUGHENED GLASS FIN 300mm DEEP H=4.5m",
        },
    ]

    res = SourceSpiderFittingGlassFinShadowAuthority.evaluate_facade(fittings_data, fins_data)

    assert len(res.fittings) == 3
    assert len(res.fins) == 2
    q = res.quantities
    assert q.total_spider_fittings_count == 3
    # SP-01 (4 rotules) + SP-02 (2 rotules) + SP-03 (1 rotule) = 7 rotules
    assert q.total_rotule_bolts_count == 7
    assert q.fittings_by_type["FOUR_ARM"] == 1
    assert q.fittings_by_type["TWO_ARM_180"] == 1
    assert q.fittings_by_type["SINGLE_ARM"] == 1

    assert q.total_glass_fins_count == 2
    assert pytest.approx(q.total_fin_height_linear_meters, 0.001) == 9.0  # 4.5 + 4.5
    # Area: 2 * (4.5 * 0.3) = 2 * 1.35 = 2.70 m2
    assert pytest.approx(q.total_fin_area_m2, 0.001) == 2.70

    assert res.status == "CANDIDATE"
    assert res.commercial_projection_allowed is False
    assert res.takeoff_eligible is False
