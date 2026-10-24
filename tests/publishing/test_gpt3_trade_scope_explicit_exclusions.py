"""Measured construction scope is not deleted by painting-specific keywords."""
from __future__ import annotations

import pytest

from pb_jobhub_publishing_contract import PublishingMode
from pb_jobhub_publishing_pipeline import build_publishing_package_from_workspace
from test_publishing_pipeline_e2e import test_dbs


@pytest.mark.parametrize(("section", "substrate", "finish"), [
    ("Concreting", "Screed", "SL01"),
    ("Waterproofing", "Mastic sealant", "MS01"),
    ("Glazing", "Powdercoat aluminium", "PC01"),
    ("Tiling screed", "Concrete substrate", "TS01"),
    ("Exclude from painting", "Fireproof acoustic sealant", "FS01"),
])
def test_genuine_firm_multi_trade_items_not_discarded_on_keyword(
    section, substrate, finish, test_dbs,
):
    local, _, _ = test_dbs
    local.execute("""
        INSERT INTO takeoff_rows (
            id, workspace_id, section, location, substrate, finish_tag,
            element, unit, quantity, rate, total_price,
            commercial_authority_status, commercial_authority_source
        ) VALUES (1,1,?,?,?,?,?,?,10,20,200,'firm','documented_dimension')
    """, (section, "Level 1", substrate, finish, "Construction scope", "m2"))
    pkg = build_publishing_package_from_workspace(
        local, 1, PublishingMode.COMMERCIAL, acting_user="Estimator",
    )
    assert len(pkg.quantities) == 1
    assert pkg.quantities[0].quantity == 10.0
    assert pkg.quantities[0].section == section
    assert pkg.excluded_items == []


def test_explicit_excluded_source_scope_is_documented_not_billed(test_dbs):
    local, _, _ = test_dbs
    local.execute("""
        INSERT INTO takeoff_rows (
            id, workspace_id, section, location, substrate, finish_tag,
            element, unit, quantity, rate, total_price,
            commercial_authority_status, commercial_authority_source,
            notes
        ) VALUES (1,1,'Paint','Level 1','Plasterboard','P01',
                    'Wall coating','m2',10,20,200,'firm','documented_dimension','')
    """)
    local.execute("""
        INSERT INTO takeoff_rows (
            id, workspace_id, section, location, substrate, finish_tag,
            element, unit, quantity, rate, total_price,
            commercial_authority_status, commercial_authority_source,
            notes
        ) VALUES (2,1,'Roofing','Roof','Metal','PC02',
                    'Factory coated roofing','m2',20,30,600,
                    'excluded','excluded','Explicitly supplied by roofing contractor')
    """)
    pkg = build_publishing_package_from_workspace(
        local, 1, PublishingMode.COMMERCIAL, acting_user="Estimator",
    )
    assert len(pkg.quantities) == 1
    assert pkg.quantities[0].element == "Wall coating"
    assert len(pkg.excluded_items) == 1
    assert pkg.excluded_items[0].trade == "Roofing"
    assert "Explicitly supplied" in pkg.excluded_items[0].reason
    assert pkg.excluded_items[0].item_code == "PC02"


def test_excluded_source_type_also_removes_source_owned_excluded_line(test_dbs):
    local, _, _ = test_dbs
    local.execute("""
        INSERT INTO takeoff_rows (
            id, workspace_id, section, location, substrate, finish_tag,
            element, unit, quantity, rate, total_price,
            commercial_authority_status, commercial_authority_source
        ) VALUES (1,1,'Tiling','Wet Area','Mastic','TS','Tile mastic',
                    'm2',3,10,30,'firm','excluded')
    """)
    pkg = build_publishing_package_from_workspace(
        local, 1, PublishingMode.DRAFT,
    )
    assert len(pkg.quantities) == 0
    assert len(pkg.excluded_items) == 1


def test_legacy_unproven_keyword_cannot_gain_excluded_authority(test_dbs):
    local, _, _ = test_dbs
    local.execute("""
        INSERT INTO takeoff_rows (
            id, workspace_id, section, location, substrate, finish_tag,
            element, unit, quantity, rate, total_price,
            commercial_authority_status, commercial_authority_source
        ) VALUES (1,1,'Screed','Unit 1','Mastic','SL','Sealant',
                    'm2',7,10,70,NULL,NULL)
    """)
    pkg = build_publishing_package_from_workspace(
        local, 1, PublishingMode.DRAFT,
    )
    assert len(pkg.quantities) == 1
    assert pkg.quantities[0].authority_status == "provisional"
    assert pkg.excluded_items == []
