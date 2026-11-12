"""Owner-authorised standard ceiling/wall height, with local source overrides.

The owner explicitly directs: use the FFL-to-FCL height for ALL walls and
ceilings in the SAME job unless a more local drawn ceiling height is stated.
This controls heights ONLY. It supplies no wall length, opening or area.
"""
from __future__ import annotations
from decimal import Decimal
from typing import Any, Mapping
from .engine import NativePage, SourceConflict
from .height_evidence import SECTION_FFL_FCL, RCP_MATERIAL_HEIGHT, section_ffl_fcl_heights, validate_height_receipt

_RULE = "all_walls_and_ceilings_unless_otherwise_stated"


def resolve_project_standard_height(
    pages: Mapping[int, NativePage],
    project_id: str,
    source_sha256: str,
    policy: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if policy is None:
        return None
    if not isinstance(policy, Mapping):
        raise SourceConflict("project_height_policy_invalid")
    if (
        policy.get("rule") != _RULE
        or policy.get("owner_authorized") is not True
        or policy.get("project_id") != project_id
        or policy.get("source_sha256") != source_sha256
    ):
        raise SourceConflict("project_height_policy_not_owner_authorized_for_source")
    section_index = policy.get("section_page_index")
    if type(section_index) is not int or section_index not in pages:
        raise SourceConflict("project_height_section_source_page_missing")
    section = pages[section_index]
    if section.source_sha256 != source_sha256 or section.page_index != section_index:
        raise SourceConflict("project_height_source_mismatch")
    candidates = section_ffl_fcl_heights(section)
    if len(candidates) != 1:
        raise SourceConflict("project_standard_ffl_fcl_figure_not_unique")
    declared = policy.get("source_height_receipt")
    if not isinstance(declared, dict):
        raise SourceConflict("project_standard_height_receipt_missing")
    proved = validate_height_receipt(section, declared)
    if proved != candidates[0] or proved["height_source_kind"] != SECTION_FFL_FCL:
        raise SourceConflict("project_standard_height_not_section_ffl_fcl")
    # A scanned PDF is NOT the user's authority; the owner-authorised project
    # rule supplies the application scope. This is never a universal default
    # across all projects.
    return {
        "rule": _RULE,
        "project_id": project_id,
        "source_sha256": source_sha256,
        "height_mm": proved["height_mm"],
        "source_height_receipt": proved,
        "section_page_index": section_index,
        "scope": "ALL_PROJECT_WALLS_AND_CEILINGS_UNLESS_LOCAL_OVERRIDE",
        "owner_authorized": True,
        "commercial_publishable": False,
        "benchmark_credit": False,
    }


def select_applicable_height(
    pages: Mapping[int, NativePage],
    standard: Mapping[str, Any],
    *,
    local_receipt: Mapping[str, Any] | None = None,
    local_page_index: int | None = None,
    local_scope_reviewed: bool = False,
    local_zone_id: str | None = None,
) -> dict[str, Any]:
    """Prefer an explicit physically scoped RCP height over the project default."""
    standard_receipt = standard["source_height_receipt"]
    if local_receipt is None:
        return {
            "height_mm": standard["height_mm"],
            "basis": "OWNER_AUTHORIZED_PROJECT_FFL_FCL_STANDARD",
            "source_page_index": standard["section_page_index"],
            "source_height_receipt": standard_receipt,
            "local_override": False,
            "commercial_publishable": False,
        }
    if not isinstance(local_receipt, Mapping):
        raise SourceConflict("local_height_override_invalid")
    if (
        type(local_page_index) is not int or local_page_index not in pages
        or local_scope_reviewed is not True
        or type(local_zone_id) is not str or not local_zone_id.strip()
    ):
        raise SourceConflict("local_height_override_zone_scope_missing")
    source_page = pages[local_page_index]
    if source_page.source_sha256 != standard["source_sha256"]:
        raise SourceConflict("local_height_override_source_mismatch")
    proved = validate_height_receipt(source_page, dict(local_receipt))
    if proved["height_source_kind"] != RCP_MATERIAL_HEIGHT:
        raise SourceConflict("local_height_override_not_rcp_callout")
    return {
        "height_mm": proved["height_mm"],
        "basis": "SOURCE_RCP_LOCAL_CEILING_ZONE_OVERRIDE",
        "source_page_index": local_page_index,
        "source_height_receipt": proved,
        "local_zone_id": local_zone_id,
        "local_override": True,
        "commercial_publishable": False,
    }
