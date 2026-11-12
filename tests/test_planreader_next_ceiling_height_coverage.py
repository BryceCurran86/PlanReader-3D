"""Owner project height coverage over true source-backed region candidates.

These tests never promote a topology-only ring to ceiling m2 or FIRM.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from planreader_next.ceiling_height_coverage import report_ceiling_height_coverage
from planreader_next.engine import SourceConflict, load_native_page
from planreader_next.height_evidence import (
    section_ffl_fcl_heights, rcp_material_height_callouts,
)
from tests.test_planreader_next_height_evidence import _section
from tests.test_planreader_next_rcp_zone_scope import _plan_fixture, _rcp_fixture


def fixture_rows():
    plan = replace(_plan_fixture(), page_index=2)
    section = _section()
    rcp = _rcp_fixture()
    pages = {2: plan, 6: section, 8: rcp}
    policy = {
        "rule": "all_walls_and_ceilings_unless_otherwise_stated",
        "owner_authorized": True,
        "project_id": "3Laurel",
        "source_sha256": plan.source_sha256,
        "section_page_index": 6,
        "source_height_receipt": section_ffl_fcl_heights(section)[0],
    }
    enclosure = {
        "source_sha256": plan.source_sha256,
        "page_index": plan.page_index,
        "regions": [
            {
                "region_id": "office", "status": "candidate",
                "likely_cavity_pocket": False,
                "room_label_words": [{
                    "text": "OFFICE", "native_word_ref": "room-word",
                }],
                "boundary_polygon_pdf_pts": [[0,0],[20,0],[20,20],[0,20]],
            },
            {
                "region_id": "hall", "status": "abstained",
                "likely_cavity_pocket": False,
                "room_label_words": [],
            },
            {
                "region_id": "cavity", "status": "candidate",
                "likely_cavity_pocket": True, "room_label_words": [],
            },
        ],
    }
    receipt = next(
        r for r in rcp_material_height_callouts(rcp)
        if r["material_code_candidate"] == "GRID" and r["height_mm"] == "2400"
    )
    override = {
        "region_id": "office",
        "rcp_page_index": 8,
        "rcp_source_rectangle_ref": "zone:grid",
        "height_source_receipt": receipt,
        "plan_room_label_word_ref": "room-word",
        "cross_sheet_correspondence_reviewed": True,
        "ceiling_zone_id": "office-grid",
    }
    return plan, pages, policy, enclosure, override


def test_owner_standard_nominal_on_all_non_cavity_regions_without_section_cut():
    plan, pages, policy, enclosure, _ = fixture_rows()
    result = report_ceiling_height_coverage(
        plan, pages, enclosure, project_id="3Laurel", owner_policy=policy,
    )
    assert result["detected_region_count"] == 3
    assert result["candidate_regions_with_nominal_height"] == 2
    rows = {row["region_id"]: row for row in result["ceiling_region_height_rows"]}
    assert rows["office"]["height_mm"] == "2700"
    assert rows["hall"]["height_mm"] == "2700"
    assert rows["hall"]["region_topology_status"] == "abstained"
    assert rows["cavity"]["height_mm"] is None
    assert rows["cavity"]["height_status"] == "NOT_A_CEILING_REGION_CAVITY_POCKET"
    assert result["measured_ceiling_area_count"] == 0
    assert all(x["measured_ceiling_area_m2"] is None
               and not x["physical_ceiling_zone_authenticated"]
               and not x["actual_ceiling_exists_authenticated"]
               for x in rows.values())
    assert not result["commercial_publishable"] and result["official_score"] is None


def test_local_rcp_override_exact_area_only_and_explicit_plan_label():
    plan, pages, policy, enclosure, override = fixture_rows()
    result = report_ceiling_height_coverage(
        plan, pages, enclosure, project_id="3Laurel", owner_policy=policy,
        reviewed_local_overrides=[override],
    )
    rows = {x["region_id"]: x for x in result["ceiling_region_height_rows"]}
    assert rows["office"]["height_mm"] == "2400"
    assert rows["office"]["height_policy_basis"] == "SOURCE_RCP_LOCAL_CEILING_ZONE_OVERRIDE"
    assert rows["office"]["height_source_receipt"]["height_word_ref"] == override["height_source_receipt"]["height_word_ref"]
    assert rows["office"]["rcp_source_rectangle_ref"] == "zone:grid"
    assert rows["hall"]["height_mm"] == "2700"
    assert rows["cavity"]["height_mm"] is None
    assert result["candidate_regions_with_nominal_height"] == 2
    assert not result["commercial_publishable"]


@pytest.mark.parametrize("mutation,reason", [
    ({"cross_sheet_correspondence_reviewed": False}, "local_height_override_zone_scope_missing"),
    ({"ceiling_zone_id": ""}, "local_height_override_zone_scope_missing"),
    ({"plan_room_label_word_ref": "not-office"}, "local_ceiling_height_region_label_not_unique"),
    ({"rcp_source_rectangle_ref": "whole-plan"}, "local_height_rcp_source_rectangle_not_unique"),
    ({"rcp_page_index": 77}, "local_ceiling_height_rcp_page_missing"),
])
def test_unproven_local_height_never_falls_back_to_standard(mutation, reason):
    plan, pages, policy, enclosure, override = fixture_rows()
    result = report_ceiling_height_coverage(
        plan, pages, enclosure, project_id="3Laurel", owner_policy=policy,
        reviewed_local_overrides=[dict(override, **mutation)],
    )
    by_id = {x["region_id"]: x for x in result["ceiling_region_height_rows"]}
    assert by_id["office"]["height_mm"] is None
    assert by_id["office"]["height_status"] == reason
    assert by_id["hall"]["height_mm"] == "2700"
    assert result["abstentions"] == [{"region_id": "office", "reason_code": reason}]


def test_competing_local_height_claims_abstain_for_that_region():
    plan, pages, policy, enclosure, override = fixture_rows()
    result = report_ceiling_height_coverage(
        plan, pages, enclosure, project_id="3Laurel", owner_policy=policy,
        reviewed_local_overrides=[override, override],
    )
    rows = {x["region_id"]: x for x in result["ceiling_region_height_rows"]}
    assert rows["office"]["height_mm"] is None
    assert rows["office"]["height_status"] == "competing_local_ceiling_heights"
    assert rows["hall"]["height_mm"] == "2700"


def test_missing_or_wrong_project_authority_cannot_invent_nominal_heights():
    plan, pages, policy, enclosure, _ = fixture_rows()
    unknown = report_ceiling_height_coverage(
        plan, pages, enclosure, project_id="3Laurel", owner_policy=None,
    )
    assert unknown["candidate_regions_with_nominal_height"] == 0
    assert len(unknown["abstentions"]) == 2
    with pytest.raises(SourceConflict, match="project_height_policy_not_owner_authorized_for_source"):
        report_ceiling_height_coverage(
            plan, pages, enclosure, project_id="Maryborough", owner_policy=policy,
        )


def test_wrong_source_or_reused_region_identity_refuses_coverage():
    plan, pages, policy, enclosure, _ = fixture_rows()
    with pytest.raises(SourceConflict, match="ceiling_height_coverage_enclosure_source_mismatch"):
        report_ceiling_height_coverage(
            plan, pages, dict(enclosure, source_sha256="f"*64),
            project_id="3Laurel", owner_policy=policy,
        )
    with pytest.raises(SourceConflict, match="ceiling_height_region_identity_invalid"):
        report_ceiling_height_coverage(
            plan, pages, dict(enclosure, regions=enclosure["regions"]*2),
            project_id="3Laurel", owner_policy=policy,
        )


def test_local_claim_must_replay_original_height_and_material_word():
    plan, pages, policy, enclosure, override = fixture_rows()
    counterfeit = dict(
        override, height_source_receipt=dict(
            override["height_source_receipt"], height_mm="3000",
        )
    )
    result = report_ceiling_height_coverage(
        plan, pages, enclosure, project_id="3Laurel", owner_policy=policy,
        reviewed_local_overrides=[counterfeit],
    )
    row = result["ceiling_region_height_rows"][0]
    assert row["height_mm"] is None
    assert row["height_status"] == "height_receipt_value_mismatch"


def test_original_3laurel_source_pdf_region_height_coverage_if_available():
    from planreader_next.enclosure import propose_room_enclosures
    from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel

    original = require_original_3laurel()
    plan = load_native_page(original, 2)
    section = load_native_page(original, 6)
    assert plan.source_sha256 == ORIGINAL_SHA256
    policy = {
        "rule": "all_walls_and_ceilings_unless_otherwise_stated",
        "owner_authorized": True,
        "project_id": "3Laurel",
        "source_sha256": plan.source_sha256,
        "section_page_index": 6,
        "source_height_receipt": section_ffl_fcl_heights(section)[0],
    }
    rings = propose_room_enclosures(plan, Path(original), include_cross_sheet_height=False)
    data = report_ceiling_height_coverage(
        plan, {2: plan, 6: section}, rings,
        project_id="3Laurel", owner_policy=policy,
    )
    assert data["detected_region_count"] == 15
    assert data["candidate_regions_with_nominal_height"] == 13
    assert sum(x["height_mm"] is None for x in data["ceiling_region_height_rows"]) == 2
    assert data["measured_ceiling_area_count"] == 0
    assert not data["commercial_publishable"]



def test_rcp_only_local_height_when_no_global_ffl_fcl_standard():
    """Maryborough-style RCP supplies specific zone height without 2700 default."""
    plan, pages, policy, enclosure, override = fixture_rows()
    out = report_ceiling_height_coverage(
        plan, pages, enclosure, project_id="Maryborough",
        owner_policy=None, reviewed_local_overrides=[override],
    )
    found = {row["region_id"]: row for row in out["ceiling_region_height_rows"]}
    assert found["office"]["height_mm"] == "2400"
    assert found["office"]["height_policy_basis"] == "SOURCE_RCP_LOCAL_CEILING_ZONE_HEIGHT"
    assert found["office"]["height_status"] == "RCP_ZONE_HEIGHT_REVIEW_REQUIRED"
    assert found["hall"]["height_mm"] is None
    assert found["hall"]["height_status"] == "NO_OWNER_APPROVED_PROJECT_HEIGHT"
    assert found["cavity"]["height_mm"] is None
    assert out["project_standard_height_mm"] is None
    assert out["candidate_regions_with_nominal_height"] == 1
    assert not out["commercial_publishable"]
    assert out["measured_ceiling_area_count"] == 0


def test_unreviewed_rcp_only_claim_has_no_fabricated_local_height():
    plan, pages, policy, enclosure, override = fixture_rows()
    out = report_ceiling_height_coverage(
        plan, pages, enclosure, project_id="Maryborough",
        owner_policy=None,
        reviewed_local_overrides=[dict(
            override, cross_sheet_correspondence_reviewed=False,
        )],
    )
    assert out["ceiling_region_height_rows"][0]["height_mm"] is None
    assert out["ceiling_region_height_rows"][0]["height_status"] == (
        "local_height_override_zone_scope_missing"
    )


def test_cli_rejects_section_standard_without_owner_approval_and_unscoped_review(tmp_path):
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    base = [
        sys.executable, "-m", "planreader_next.ceiling_height_coverage",
        "--pdf", str(tmp_path/"missing.pdf"), "--plan-page", "2",
        "--project-id", "3Laurel", "--output", str(tmp_path/"result.json"),
    ]
    section_without_owner = subprocess.run(
        base + ["--section-page", "6"],
        cwd=root, capture_output=True, text=True,
    )
    assert section_without_owner.returncode != 0
    assert "BOTH --section-page and --owner-authorized" in section_without_owner.stderr
    unscoped_review = subprocess.run(
        base + ["--section-page", "6", "--owner-authorized",
                "--reviewed-local-overrides", str(tmp_path/"selection.json")],
        cwd=root, capture_output=True, text=True,
    )
    assert unscoped_review.returncode != 0
    assert "require --rcp-page" in unscoped_review.stderr
    assert not (tmp_path/"result.json").exists()
