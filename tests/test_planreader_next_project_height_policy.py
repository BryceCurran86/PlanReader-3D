"""Project owner confirms the one source FFL/FCL figure is the height default."""
from __future__ import annotations
from pathlib import Path

import pytest

from planreader_next.engine import SourceConflict, load_native_page
from planreader_next.height_evidence import section_ffl_fcl_heights, rcp_material_height_callouts
from planreader_next.project_height_policy import resolve_project_standard_height, select_applicable_height


def _3laurel_rule(page):
    return {
        "rule": "all_walls_and_ceilings_unless_otherwise_stated",
        "owner_authorized": True,
        "project_id": "3Laurel",
        "source_sha256": page.source_sha256,
        "section_page_index": page.page_index,
        "source_height_receipt": section_ffl_fcl_heights(page)[0],
    }


def test_owner_authorised_source_default_applies_even_without_cut_crossing():
    from tests.test_planreader_next_height_evidence import _section
    page = _section()
    standard = resolve_project_standard_height(
        {page.page_index:page}, "3Laurel", page.source_sha256,
        _3laurel_rule(page)
    )
    assert standard["height_mm"] == "2700"
    for physical_id in ("BED", "ROBE", "LAUNDRY", "GARAGE", "HALLWAY"):
        result = select_applicable_height({page.page_index:page}, standard)
        assert result["height_mm"] == "2700", physical_id
        assert result["basis"] == "OWNER_AUTHORIZED_PROJECT_FFL_FCL_STANDARD"
        assert result["local_override"] is False
        assert result["commercial_publishable"] is False


def test_unapproved_or_other_source_project_default_refused():
    from tests.test_planreader_next_height_evidence import _section
    section = _section()
    pages={section.page_index:section}
    policy=_3laurel_rule(section)
    for variant in (
        dict(policy, owner_authorized=False),
        dict(policy, project_id="Maryborough"),
        dict(policy, source_sha256="f"*64),
        dict(policy, rule="assume_2700_for_all_jobs"),
    ):
        with pytest.raises(SourceConflict,match="project_height_policy_not_owner_authorized_for_source"):
            resolve_project_standard_height(pages,"3Laurel",section.source_sha256,variant)
    forged=dict(policy, source_height_receipt=dict(policy["source_height_receipt"],height_mm="2740"))
    with pytest.raises(SourceConflict,match="height_receipt_value_mismatch"):
        resolve_project_standard_height(pages,"3Laurel",section.source_sha256,forged)


def test_local_rcp_callout_overrides_project_default_only_with_room_zone_scope():
    from tests.test_planreader_next_height_evidence import _section, _rcp
    section=_section()
    rcp=_rcp()
    from dataclasses import replace
    rcp=replace(rcp,source_sha256=section.source_sha256)
    pages={section.page_index:section, rcp.page_index:rcp}
    standard=resolve_project_standard_height(
        pages,"3Laurel",section.source_sha256,_3laurel_rule(section)
    )
    receipt=next(x for x in rcp_material_height_callouts(rcp)
                 if x["height_mm"]=="2400" and x["material_code_candidate"]=="GRID")
    with pytest.raises(SourceConflict,match="local_height_override_zone_scope_missing"):
        select_applicable_height(pages,standard,
                                 local_receipt=receipt,local_page_index=8,
                                 local_scope_reviewed=False,local_zone_id=None)
    override=select_applicable_height(pages,standard,
                                      local_receipt=receipt,local_page_index=8,
                                      local_scope_reviewed=True,local_zone_id="OFFICE")
    assert override["height_mm"] == "2400"
    assert override["basis"]=="SOURCE_RCP_LOCAL_CEILING_ZONE_OVERRIDE"
    assert override["local_override"] is True
    other=select_applicable_height(pages,standard)
    assert other["height_mm"]=="2700"


def test_real_3laurel_printed_2700_as_owner_standard_with_no_global_cross_cut_restriction():
    from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel
    original=require_original_3laurel()
    page=load_native_page(original,6)
    assert page.source_sha256==ORIGINAL_SHA256
    rule=_3laurel_rule(page)
    standard=resolve_project_standard_height({6:page},"3Laurel",page.source_sha256,rule)
    assert standard["height_mm"]=="2700"
    assert standard["source_height_receipt"]["dimension_segment_refs"]==["d5955i0"]



def test_original_3laurel_owner_standard_cli_is_source_bound_and_create_only(tmp_path):
    import json
    import subprocess
    import sys
    from tests.original_source_3laurel import require_original_3laurel
    original=str(require_original_3laurel())
    output=tmp_path/"original-height-rule.json"
    cmd=[sys.executable,"-m","planreader_next","heights","--pdf",original,
         "--page","6","--drawing-type","section",
         "--owner-standard-for-project","3Laurel","--output",str(output)]
    root=Path(__file__).resolve().parents[1]
    first=subprocess.run(cmd,cwd=root,capture_output=True,text=True)
    assert first.returncode==0,first.stderr
    data=json.loads(output.read_text(encoding="utf8"))
    standard=data["project_standard_height_policy"]
    assert standard["owner_authorized"]
    assert standard["source_height_receipt"]["height_mm"]=="2700"
    assert standard["source_height_receipt"]["dimension_segment_refs"]==["d5955i0"]
    assert not data["commercial_publishable"]
    second=subprocess.run(cmd,cwd=root,capture_output=True,text=True)
    assert second.returncode==2
    assert "FileExistsError" in second.stderr
