"""Fail-closed, review-only joins from source height to actual plan face REFERENCES.

This is the final GPT1 height scope handoff. It never turns a topology wall
into an authenticated finished lining, or a source RCP rectangle into a
measured ceiling zone. Physical ownership remains the geometry lane's task.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from shapely.geometry import LineString

from .engine import NativePage, SourceConflict
from .section_scope import section_cut_region_height_candidates
from .rcp_zone_scope import associate_reviewed_rcp_zone_with_plan_face


def _checked_inventory(
    plan: NativePage, enclosure: Mapping[str, Any],
) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    if not isinstance(enclosure, Mapping):
        raise SourceConflict("height_enclosure_missing")
    inventory = enclosure.get("source_wall_inventory")
    if not isinstance(inventory, Mapping) or (
        inventory.get("source_sha256") != plan.source_sha256
        or inventory.get("page_index") != plan.page_index
    ):
        raise SourceConflict("height_wall_inventory_source_mismatch")
    if inventory.get("topology_only") is not True:
        raise SourceConflict("height_wall_inventory_claimed_physical")
    locators = inventory.get("region_locators")
    faces = inventory.get("faces")
    if not isinstance(locators, list) or not isinstance(faces, list):
        raise SourceConflict("height_wall_inventory_invalid")
    regions: dict[str, Mapping[str, Any]] = {}
    for locator in locators:
        region_id = locator.get("region_id")
        if (
            type(region_id) is not str or not region_id
            or region_id in regions
            or locator.get("source_sha256") != plan.source_sha256
            or locator.get("page_index") != plan.page_index
        ):
            raise SourceConflict("height_region_locator_identity_invalid")
        regions[region_id] = locator
    face_lookup: dict[str, Mapping[str, Any]] = {}
    source_segments = {segment.ref: segment for segment in plan.segments}
    if len(source_segments) != len(plan.segments):
        raise SourceConflict("height_duplicate_native_source_segment")
    for face in faces:
        item_id = face.get("item_id")
        if type(item_id) is not str or not item_id or item_id in face_lookup:
            raise SourceConflict("height_face_identity_invalid")
        if face.get("region_id") not in regions:
            # The initial source inventory may contain faces for abstained or
            # unlocatable topology rings. They are NOT eligible for a scope.
            continue
        if (
            face.get("face_segment_ref") not in source_segments
            or face.get("item_id") not in regions[face["region_id"]].get(
                "wall_face_item_ids", []
            )
            or face.get("topology_only") is not True
            or face.get("physical_wall_authenticated") is not False
        ):
            raise SourceConflict("height_face_source_receipt_invalid")
        face_lookup[item_id] = face
    return regions, face_lookup


def section_height_to_plan_face_candidates(
    plan: NativePage,
    section: NativePage,
    enclosure: Mapping[str, Any],
) -> dict[str, Any]:
    """Source A-A cut height -> eligible region -> its native wall face refs.

    A cut intersecting a room DOES NOT imply that all its walls have the same
    lining height. Therefore every link explicitly abstains from quantity.
    """
    regions_by_id, faces = _checked_inventory(plan, enclosure)
    source_regions = enclosure.get("regions")
    if not isinstance(source_regions, list):
        raise SourceConflict("height_region_source_polygons_missing")
    cut = section_cut_region_height_candidates(plan, section, source_regions)
    native_words = {w.ref: w for w in plan.words}
    native_segments = {s.ref: s for s in plan.segments}
    axis = cut["source_plan_section_cut"]["cut_axis_pdf_pts"]
    section_line = LineString([(axis[0], axis[1]), (axis[2], axis[3])])
    linked: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    region_candidates = cut["cut_intersecting_region_candidates"]
    for proposal in region_candidates:
        region_id = proposal["region_id"]
        locator = regions_by_id.get(region_id)
        if locator is None:
            unresolved.append({"region_id": region_id,
                               "reason_code": "source_region_not_in_wall_inventory"})
            continue
        labels = locator.get("room_label_word_refs") or []
        if (
            proposal.get("region_topology_status") != "candidate"
            or len(labels) != 1
            or len(locator.get("room_label_texts") or []) != 1
            or labels[0] not in native_words
            or native_words[labels[0]].text != locator["room_label_texts"][0]
        ):
            unresolved.append({
                "region_id": region_id,
                "reason_code": "section_region_or_label_identity_not_unique",
            })
            continue
        own = sorted(
            (face for face in faces.values() if face["region_id"] == region_id),
            key=lambda face: face["item_id"],
        )
        if not own:
            unresolved.append({"region_id": region_id,
                               "reason_code": "section_region_has_no_source_wall_face"})
            continue
        for face in own:
            source = native_segments[face["face_segment_ref"]]
            face_line = LineString([(source.x1, source.y1), (source.x2, source.y2)])
            physically_crosses_face = not face_line.intersection(section_line).is_empty
            linked.append({
                "region_id": region_id,
                "room_label_word_ref": labels[0],
                "room_label_text": native_words[labels[0]].text,
                "face_item_id": face["item_id"],
                "face_segment_ref": source.ref,
                "face_role_hypothesis": face.get("face_role_hypothesis"),
                "interrupted_by_opening_ids_topology_only": list(
                    face.get("interrupted_by_opening_ids") or []
                ),
                "source_sha256": plan.source_sha256,
                "plan_page_index": plan.page_index,
                "section_page_index": section.page_index,
                "section_reference": cut["source_plan_section_cut"]["section_reference"],
                "source_section_marker_word_refs": list(
                    cut["source_plan_section_cut"]["plan_marker_word_refs"]
                ),
                "source_section_dash_segment_refs": list(
                    cut["source_plan_section_cut"]["plan_dashed_source_segment_refs"]
                ),
                "height_mm_source_candidate": proposal["height_mm_source_candidate"],
                "height_source_receipt": proposal["height_source_receipt"],
                "section_cut_crosses_region": True,
                "section_cut_crosses_this_face": physically_crosses_face,
                "applicable_ceiling_height_authenticated": False,
                "physical_wall_authenticated": False,
                "finished_face_authenticated": False,
                "hosted_opening_authenticated": False,
                "wall_lining_reaches_fcl_authenticated": False,
                "wall_finish_area_eligible": False,
                "commercial_publishable": False,
                "benchmark_credit": False,
            })
    return {
        "schema_version": "0.1.0-shadow",
        "source_sha256": plan.source_sha256,
        "plan_page_index": plan.page_index,
        "section_page_index": section.page_index,
        "section_height_mm_source_candidate": cut["height_mm_source_candidate"],
        "section_region_crossings": len(region_candidates),
        "face_height_scope_candidates": linked,
        "unresolved_regions": unresolved,
        "physical_wall_height_authenticated": False,
        "wall_finish_area_eligible": False,
        "commercial_publishable": False,
        "benchmark_credit": False,
        "official_score": None,
    }


def reviewed_rcp_height_to_plan_face_candidates(
    plan: NativePage,
    rcp: NativePage,
    enclosure: Mapping[str, Any],
    selections: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Reviewer-selected original RCP material/height -> exact plan region/face.

    No spatial transform between plan and RCP has been assumed. Explicit room
    correspondence remains required, and reviewer selection is not proof of
    finished ceiling geometry or permission to issue quantity.
    """
    regions, faces = _checked_inventory(plan, enclosure)
    if type(selections) not in (list, tuple):
        raise SourceConflict("rcp_height_scope_selections_invalid")
    links: list[dict[str, Any]] = []
    abstentions: list[dict[str, str]] = []
    for selection in selections:
        if not isinstance(selection, Mapping):
            raise SourceConflict("rcp_height_scope_selection_invalid")
        region_id = selection.get("region_id")
        face_id = selection.get("face_item_id")
        face = faces.get(face_id) if type(face_id) is str else None
        locator = regions.get(region_id) if type(region_id) is str else None
        if face is None or locator is None or face["region_id"] != region_id:
            abstentions.append({
                "face_item_id": str(face_id),
                "reason_code": "rcp_height_face_not_owned_by_selected_region",
            })
            continue
        room_label_ref = selection.get("room_label_word_ref")
        if room_label_ref not in locator.get("room_label_word_refs", []):
            abstentions.append({
                "face_item_id": face_id,
                "reason_code": "rcp_height_label_not_owned_by_selected_region",
            })
            continue
        try:
            receipt = associate_reviewed_rcp_zone_with_plan_face(
                plan, rcp,
                source_rectangle_ref=selection.get("rcp_source_rectangle_ref"),
                height_word_ref=selection.get("rcp_height_word_ref"),
                item_id=face_id,
                plan_face_segment_ref=face["face_segment_ref"],
                plan_room_label_word_ref=room_label_ref,
                cross_sheet_correspondence_reviewed=selection.get(
                    "cross_sheet_correspondence_reviewed"
                ),
            )
        except (SourceConflict, TypeError, ValueError) as exc:
            abstentions.append({
                "face_item_id": face_id,
                "reason_code": str(exc) if isinstance(exc, SourceConflict)
                               else "rcp_height_scope_selection_invalid",
            })
            continue
        links.append({
            **receipt,
            "region_id": region_id,
            "face_item_id": face_id,
            "interrupted_by_opening_ids_topology_only": list(
                face.get("interrupted_by_opening_ids") or []
            ),
            "finished_face_authenticated": False,
            "wall_finish_area_eligible": False,
            "benchmark_credit": False,
            "commercial_publishable": False,
        })

    # One plan face cannot be simultaneously assigned to two RCP zones by
    # two user selections. Both results must abstain, even for equal heights.
    counts = Counter(link["face_item_id"] for link in links)
    accepted = [link for link in links if counts[link["face_item_id"]] == 1]
    for face_id, number in counts.items():
        if number > 1:
            abstentions.append({
                "face_item_id": face_id,
                "reason_code": "competing_rcp_height_zone_claims",
            })
    return {
        "schema_version": "0.1.0-shadow",
        "source_sha256": plan.source_sha256,
        "plan_page_index": plan.page_index,
        "rcp_page_index": rcp.page_index,
        "face_height_scope_candidates": accepted,
        "abstentions": abstentions,
        "physical_ceiling_zone_authenticated": False,
        "wall_finish_area_eligible": False,
        "commercial_publishable": False,
        "benchmark_credit": False,
        "official_score": None,
    }



def reconcile_face_height_sources(
    section_packet: Mapping[str, Any],
    rcp_packet: Mapping[str, Any],
    *,
    owner_authorized_project_standard: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """A confirmed project standard is superseded by a reviewed local RCP.

    Without a validated project-wide standard, two distinct height sources
    remain ambiguous. Never promote a topology-only face to wall m2.
    """
    if (
        section_packet.get("source_sha256") != rcp_packet.get("source_sha256")
        or section_packet.get("plan_page_index") != rcp_packet.get("plan_page_index")
    ):
        raise SourceConflict("height_sources_cross_document_or_plan_page_mismatch")
    claimed = (
        list(section_packet.get("face_height_scope_candidates", []))
        + list(rcp_packet.get("face_height_scope_candidates", []))
    )
    by_face: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    for lane, packet in (("section", section_packet), ("rcp", rcp_packet)):
        for row in packet.get("face_height_scope_candidates", []):
            face_id = row.get("face_item_id")
            if type(face_id) is not str or not face_id:
                raise SourceConflict("height_source_face_identity_missing")
            if (
                row.get("source_sha256") != section_packet["source_sha256"]
                or row.get("wall_finish_area_eligible") is not False
                or row.get("commercial_publishable") is not False
            ):
                raise SourceConflict("height_source_candidate_not_shadow_only")
            by_face.setdefault(face_id, []).append((lane, row))
    if owner_authorized_project_standard is not None:
        standard = owner_authorized_project_standard
        if (
            standard.get("rule") != "all_walls_and_ceilings_unless_otherwise_stated"
            or standard.get("owner_authorized") is not True
            or standard.get("source_sha256") != section_packet["source_sha256"]
            or not isinstance(standard.get("source_height_receipt"), Mapping)
        ):
            raise SourceConflict("height_reconciliation_standard_not_owner_source_approved")
    accepted = []
    abstentions = []
    for face_id, rows in sorted(by_face.items()):
        if (
            len(rows) == 2 and owner_authorized_project_standard is not None
            and {kind for kind, _ in rows} == {"section", "rcp"}
            and next(row for kind,row in rows if kind == "section")[
                "height_mm_source_candidate"
            ] == owner_authorized_project_standard["height_mm"]
            and next(row for kind,row in rows if kind == "rcp").get(
                "cross_sheet_correspondence_reviewed"
            ) is True
        ):
            # The local RCP figure is explicitly 'otherwise stated' and takes
            # precedence; note it is still NOT a measured wall surface.
            local = next(row for kind,row in rows if kind == "rcp")
            accepted.append({
                "face_item_id": face_id,
                "height_source_kind": "rcp",
                "height_mm_source_candidate": local["height_mm"],
                "source_sha256": section_packet["source_sha256"],
                "plan_page_index": section_packet["plan_page_index"],
                "source_face_segment_ref": local["plan_face_segment_ref"],
                "project_standard_height_mm": owner_authorized_project_standard["height_mm"],
                "height_policy_basis": "LOCAL_RCP_OVERRIDES_OWNER_AUTHORIZED_STANDARD",
                "wall_finish_area_eligible": False,
                "commercial_publishable": False,
                "benchmark_credit": False,
                "status": "LOCAL_OVERRIDE_SCOPE_REVIEWED_GEOMETRY_STILL_UNVERIFIED",
            })
            continue
        if len(rows) != 1:
            abstentions.append({
                "face_item_id": face_id,
                "reason_code": "multiple_height_sources_require_ceiling_zone_authority",
                "height_source_kinds": [kind for kind, _ in rows],
                "printed_height_mm_candidates": sorted(set(
                    str(row["height_mm_source_candidate"] if kind == "section"
                        else row["height_mm"])
                    for kind, row in rows
                )),
            })
            continue
        kind, row = rows[0]
        accepted.append({
            "face_item_id": face_id,
            "height_source_kind": kind,
            "height_mm_source_candidate": (
                row["height_mm_source_candidate"] if kind == "section"
                else row["height_mm"]
            ),
            "source_sha256": section_packet["source_sha256"],
            "plan_page_index": section_packet["plan_page_index"],
            "source_face_segment_ref": (
                row["face_segment_ref"] if kind == "section"
                else row["plan_face_segment_ref"]
            ),
            "wall_finish_area_eligible": False,
            "commercial_publishable": False,
            "benchmark_credit": False,
            "status": "UNIQUE_SOURCE_LANE_BUT_PHYSICAL_HEIGHT_SCOPE_UNVERIFIED",
        })
    return {
        "schema_version": "0.1.0-shadow",
        "source_sha256": section_packet["source_sha256"],
        "plan_page_index": section_packet["plan_page_index"],
        "source_height_candidates_count": len(claimed),
        "unique_source_lane_face_candidates": accepted,
        "abstentions": abstentions,
        "physical_height_scope_authenticated": False,
        "wall_finish_area_eligible": False,
        "commercial_publishable": False,
        "benchmark_credit": False,
        "official_score": None,
    }
