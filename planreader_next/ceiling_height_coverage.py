"""Project-scoped ceiling-height coverage for source-native *candidate* regions.

An owner-approved section FFL-to-FCL figure supplies a project's nominal wall
and ceiling height, except where a reviewed source RCP callout states otherwise.
No topology-only region becomes a physical room or measurable ceiling area.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .engine import NativePage, SourceConflict, load_native_page
from .enclosure import propose_room_enclosures
from .height_evidence import (
    RCP_MATERIAL_HEIGHT, rcp_material_height_callouts,
    section_ffl_fcl_heights, validate_height_receipt,
)
from .project_height_policy import (
    resolve_project_standard_height, select_applicable_height,
)
from .rcp_zone_scope import propose_rcp_source_zone_rectangles


def report_ceiling_height_coverage(
    plan: NativePage,
    pages: Mapping[int, NativePage],
    enclosure: Mapping[str, Any],
    *,
    project_id: str,
    owner_policy: Mapping[str, Any] | None,
    reviewed_local_overrides: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Assign SOURCE NOMINAL height to candidates, never ceiling area or scope.

    Explicit local overrides require a uniquely owned RCP source rectangle,
    original height/material evidence, and a reviewed plan-region label match.
    An invalid or competing exception prevents default fall-back for that
    region, rather than hiding a lower/higher ceiling with the project default.
    """
    if not isinstance(enclosure, Mapping) or (
        enclosure.get("source_sha256") != plan.source_sha256
        or enclosure.get("page_index") != plan.page_index
    ):
        raise SourceConflict("ceiling_height_coverage_enclosure_source_mismatch")
    if pages.get(plan.page_index) != plan:
        raise SourceConflict("ceiling_height_coverage_plan_source_not_loaded")
    if any(index != page.page_index or page.source_sha256 != plan.source_sha256
           for index, page in pages.items()):
        raise SourceConflict("ceiling_height_coverage_cross_document_page")
    standard = resolve_project_standard_height(
        pages, project_id, plan.source_sha256, owner_policy,
    )
    regions = enclosure.get("regions")
    if not isinstance(regions, list):
        raise SourceConflict("ceiling_height_coverage_regions_invalid")
    by_id: dict[str, Mapping[str, Any]] = {}
    for region in regions:
        if not isinstance(region, Mapping):
            raise SourceConflict("ceiling_height_region_invalid")
        region_id = region.get("region_id")
        if type(region_id) is not str or not region_id or region_id in by_id:
            raise SourceConflict("ceiling_height_region_identity_invalid")
        by_id[region_id] = region

    if not isinstance(reviewed_local_overrides, (list, tuple)):
        raise SourceConflict("ceiling_height_overrides_invalid")
    selected: dict[str, list[Mapping[str, Any]]] = {}
    for override in reviewed_local_overrides:
        if not isinstance(override, Mapping):
            raise SourceConflict("ceiling_height_override_invalid")
        region_id = override.get("region_id")
        if type(region_id) is not str or region_id not in by_id:
            raise SourceConflict("ceiling_height_override_unknown_region")
        selected.setdefault(region_id, []).append(override)

    native_words = {word.ref: word for word in plan.words}
    zone_cache: dict[int, dict[str, Any]] = {}
    outputs: list[dict[str, Any]] = []
    abstentions: list[dict[str, str]] = []

    for region_id, region in by_id.items():
        row: dict[str, Any] = {
            "region_id": region_id,
            "region_topology_status": region.get("status"),
            "room_label_words": region.get("room_label_words", []),
            "source_sha256": plan.source_sha256,
            "plan_page_index": plan.page_index,
            "height_mm": None,
            "height_source_receipt": None,
            "height_policy_basis": None,
            "height_status": "UNRESOLVED",
            "physical_ceiling_zone_authenticated": False,
            "actual_ceiling_exists_authenticated": False,
            "measured_ceiling_area_m2": None,
            "wall_finish_area_eligible": False,
            "commercial_publishable": False,
            "benchmark_credit": False,
        }
        candidates = selected.get(region_id, [])
        if region.get("likely_cavity_pocket") is True:
            row["height_status"] = "NOT_A_CEILING_REGION_CAVITY_POCKET"
            outputs.append(row)
            continue
        if len(candidates) > 1:
            reason = "competing_local_ceiling_heights"
            row["height_status"] = reason
            abstentions.append({"region_id": region_id, "reason_code": reason})
            outputs.append(row)
            continue
        if candidates:
            claim = candidates[0]
            try:
                refs = region.get("room_label_words") or []
                room_ref = claim.get("plan_room_label_word_ref")
                if (len(refs) != 1 or not isinstance(refs[0], Mapping)
                    or refs[0].get("native_word_ref") != room_ref
                    or room_ref not in native_words
                    or native_words[room_ref].text.strip().upper()
                       != str(refs[0].get("text", "")).strip().upper()):
                    raise SourceConflict("local_ceiling_height_region_label_not_unique")
                page_index = claim.get("rcp_page_index")
                if type(page_index) is not int or page_index not in pages:
                    raise SourceConflict("local_ceiling_height_rcp_page_missing")
                rcp = pages[page_index]
                if page_index == plan.page_index:
                    raise SourceConflict("local_ceiling_height_not_cross_sheet")
                if page_index not in zone_cache:
                    zone_cache[page_index] = propose_rcp_source_zone_rectangles(rcp)
                zones = zone_cache[page_index]["source_zone_rectangle_candidates"]
                receipt = claim.get("height_source_receipt")
                matches = [
                    zone for zone in zones
                    if zone["source_rectangle_ref"] == claim.get("rcp_source_rectangle_ref")
                    and isinstance(receipt, Mapping)
                    and receipt.get("height_word_ref") in zone["height_word_refs"]
                    and receipt.get("material_word_ref") in zone["material_word_refs"]
                ]
                if len(matches) != 1:
                    raise SourceConflict("local_height_rcp_source_rectangle_not_unique")
                if standard is not None:
                    choice = select_applicable_height(
                        pages, standard,
                        local_receipt=receipt,
                        local_page_index=page_index,
                        local_scope_reviewed=claim.get(
                            "cross_sheet_correspondence_reviewed"
                        ) is True,
                        local_zone_id=claim.get("ceiling_zone_id"),
                    )
                else:
                    # Maryborough may have source-RCP heights without one
                    # verified global section standard. A scoped RCP bubble
                    # still has valid, independently attested local height.
                    if (
                        claim.get("cross_sheet_correspondence_reviewed") is not True
                        or type(claim.get("ceiling_zone_id")) is not str
                        or not claim["ceiling_zone_id"].strip()
                    ):
                        raise SourceConflict("local_height_override_zone_scope_missing")
                    proved = validate_height_receipt(rcp, dict(receipt))
                    if proved["height_source_kind"] != RCP_MATERIAL_HEIGHT:
                        raise SourceConflict("local_ceiling_height_not_rcp_material")
                    choice = {
                        "height_mm": proved["height_mm"],
                        "basis": "SOURCE_RCP_LOCAL_CEILING_ZONE_HEIGHT",
                        "source_height_receipt": proved,
                    }
                if choice["height_mm"] != matches[0]["height_mm"]:
                    raise SourceConflict("local_ceiling_height_source_zone_disagrees")
                row["height_mm"] = choice["height_mm"]
                row["height_source_receipt"] = choice["source_height_receipt"]
                row["height_policy_basis"] = choice["basis"]
                row["height_status"] = (
                    "LOCAL_RCP_OVERRIDE_REVIEW_REQUIRED"
                    if standard is not None
                    else "RCP_ZONE_HEIGHT_REVIEW_REQUIRED"
                )
                row["rcp_source_rectangle_ref"] = matches[0]["source_rectangle_ref"]
                row["ceiling_zone_id_claimed"] = claim["ceiling_zone_id"]
            except (SourceConflict, TypeError, ValueError) as exc:
                reason = str(exc) if isinstance(exc, SourceConflict) else "local_ceiling_height_invalid"
                row["height_status"] = reason
                abstentions.append({"region_id": region_id, "reason_code": reason})
        elif standard is not None:
            choice = select_applicable_height(pages, standard)
            row["height_mm"] = choice["height_mm"]
            row["height_source_receipt"] = choice["source_height_receipt"]
            row["height_policy_basis"] = choice["basis"]
            row["height_status"] = "OWNER_PROJECT_STANDARD_IF_PHYSICAL_CEILING"
        else:
            row["height_status"] = "NO_OWNER_APPROVED_PROJECT_HEIGHT"
            abstentions.append({
                "region_id": region_id,
                "reason_code": "no_owner_approved_project_height",
            })
        outputs.append(row)

    nominal_count = sum(row["height_mm"] is not None for row in outputs)
    return {
        "schema_version": "0.1.0-shadow",
        "project_id": project_id,
        "source_sha256": plan.source_sha256,
        "plan_page_index": plan.page_index,
        "project_standard_height_mm": standard["height_mm"] if standard else None,
        "project_standard_source_receipt": standard["source_height_receipt"] if standard else None,
        "detected_region_count": len(outputs),
        "candidate_regions_with_nominal_height": nominal_count,
        "not_an_authenticated_ceiling_inventory": True,
        "ceiling_region_height_rows": outputs,
        "abstentions": abstentions,
        "measured_ceiling_area_count": 0,
        "commercial_publishable": False,
        "benchmark_credit": False,
        "official_score": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Source-backed nominal ceiling height for all detected plan regions (not areas)."
    )
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--plan-page", type=int, required=True)
    parser.add_argument("--section-page", type=int)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--owner-authorized", action="store_true")
    parser.add_argument("--rcp-page", type=int)
    parser.add_argument("--reviewed-local-overrides", type=Path)
    parser.add_argument(
        "--stroke-pair-wall-faces", action="store_true",
        help="Opt-in source stroke pairing in dense plans; auto uses bounded label neighbourhoods",
    )
    parser.add_argument(
        "--plan-viewport", nargs=4, type=float,
        metavar=("X0", "Y0", "X1", "Y1"),
        help="Optional PDF-native plan neighbourhood, essential on over-cap dense sheets",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if (args.section_page is None) != (not args.owner_authorized):
        parser.error("A project standard requires BOTH --section-page and --owner-authorized")
    if args.section_page is None and args.rcp_page is None:
        parser.error("Provide a source section standard or an RCP page")
    if args.reviewed_local_overrides is not None and args.rcp_page is None:
        parser.error("Reviewed local overrides require --rcp-page")
    plan = load_native_page(args.pdf, args.plan_page)
    pages = {plan.page_index: plan}
    policy = None
    if args.section_page is not None:
        if args.section_page == plan.page_index:
            raise SourceConflict("ceiling_standard_section_is_plan_page")
        section = load_native_page(args.pdf, args.section_page)
        pages[section.page_index] = section
        evidence = section_ffl_fcl_heights(section)
        if len(evidence) != 1:
            raise SourceConflict("ceiling_standard_source_ffl_fcl_not_unique")
        policy = {
            "rule": "all_walls_and_ceilings_unless_otherwise_stated",
            "owner_authorized": args.owner_authorized,
            "project_id": args.project_id,
            "source_sha256": plan.source_sha256,
            "section_page_index": section.page_index,
            "source_height_receipt": evidence[0],
        }
    reviewed: list[Mapping[str, Any]] = []
    if args.rcp_page is not None:
        if args.rcp_page in pages:
            raise SourceConflict("ceiling_rcp_page_must_be_distinct_from_plan_or_section")
        rcp = load_native_page(args.pdf, args.rcp_page)
        pages[rcp.page_index] = rcp
        if args.reviewed_local_overrides is not None:
            review = json.loads(args.reviewed_local_overrides.read_text(encoding="utf-8"))
            if not isinstance(review, dict) or (
                review.get("source_sha256") != plan.source_sha256
                or review.get("plan_page_index") != plan.page_index
                or review.get("rcp_page_index") != rcp.page_index
                or review.get("project_id") != args.project_id
                or not isinstance(review.get("links"), list)
            ):
                raise SourceConflict("ceiling_reviewed_local_override_source_mismatch")
            reviewed = review["links"]
    enclosures = propose_room_enclosures(
        plan, args.pdf,
        include_cross_sheet_height=False,
        stroke_pair_wall_faces=args.stroke_pair_wall_faces,
        viewport_pdf_pts=args.plan_viewport,
    )
    result = report_ceiling_height_coverage(
        plan, pages, enclosures,
        project_id=args.project_id, owner_policy=policy,
        reviewed_local_overrides=reviewed,
    )
    if args.rcp_page is not None:
        all_callouts = rcp_material_height_callouts(pages[args.rcp_page])
        matched_refs = {
            row["height_source_receipt"]["height_word_ref"]
            for row in result["ceiling_region_height_rows"]
            if row["height_source_receipt"] is not None
            and row["height_source_receipt"]["height_source_kind"]
               == RCP_MATERIAL_HEIGHT
        }
        result["rcp_source_height_material_pair_candidates"] = len(all_callouts)
        result["rcp_callouts_not_yet_associated_with_detected_regions"] = [
            item["height_word_ref"] for item in all_callouts
            if item["height_word_ref"] not in matched_refs
        ]
    # Create-only: never replace an owner's earlier diagnostic.
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
    print(json.dumps({
        "candidate_regions_with_nominal_height": result["candidate_regions_with_nominal_height"],
        "detected_region_count": result["detected_region_count"],
        "measured_ceiling_area_count": 0,
        "commercial_publishable": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
