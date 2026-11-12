"""Source-referenced draft takeoffs for walls, ceiling lining, doors and frames.

Works on exact native evidence from an original PDF and reviewed mappings.
It is deliberately not a live detection, physical-host authority or commercial
issuer. Any absent or contradictory source evidence stays an ABSTAIN.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from hashlib import sha256
import math
import re
from typing import Any, Mapping

from .engine import (
    NativePage, NativeSegment, NativeWord, SourceConflict,
    _figured_mm, _measure_one, _required_text, measure_page,
)


def _page(pages: Mapping[int, NativePage], value: Any) -> NativePage:
    if type(value) is not int or value not in pages:
        raise SourceConflict("source_page_unavailable")
    return pages[value]


def _word(page: NativePage, ref: Any) -> NativeWord:
    if not isinstance(ref, str) or not ref:
        raise SourceConflict("source_word_reference_required")
    found = next((word for word in page.words if word.ref == ref), None)
    if found is None:
        raise SourceConflict("native_source_word_not_owned_by_page")
    return found


def _segment(page: NativePage, ref: Any) -> NativeSegment:
    if not isinstance(ref, str) or not ref:
        raise SourceConflict("source_segment_reference_required")
    found = next((s for s in page.segments if s.ref == ref), None)
    if found is None or found.kind not in ("line", "rect_edge"):
        raise SourceConflict("native_wall_or_aperture_segment_missing")
    length = math.hypot(found.x2 - found.x1, found.y2 - found.y1)
    if not math.isfinite(length) or length < 2:
        raise SourceConflict("native_source_segment_degenerate")
    return found


def _centre(word: NativeWord) -> tuple[float, float]:
    x0, y0, x1, y1 = word.bbox
    return ((x0 + x1) / 2, (y0 + y1) / 2)


def _distance_to_line(point: tuple[float, float], seg: NativeSegment) -> float:
    dx, dy = seg.x2 - seg.x1, seg.y2 - seg.y1
    t = ((point[0] - seg.x1) * dx + (point[1] - seg.y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(point[0] - seg.x1 - t * dx, point[1] - seg.y1 - t * dy)


def _segment_inside_line(opening: NativeSegment, host: NativeSegment) -> bool:
    host_dx, host_dy = host.x2 - host.x1, host.y2 - host.y1
    denom = host_dx * host_dx + host_dy * host_dy
    if denom <= 0:
        return False
    for point in ((opening.x1, opening.y1), (opening.x2, opening.y2)):
        t = ((point[0] - host.x1) * host_dx + (point[1] - host.y1) * host_dy) / denom
        if not 0 <= t <= 1 or _distance_to_line(point, host) > 0.001:
            return False
    return True


def _row(family: str, entity: str, page: NativePage, quantity: Decimal | int,
         unit: str, refs: Mapping[str, Any], **extra: Any) -> dict[str, Any]:
    lineage = "|".join((page.source_sha256, family, entity, str(page.page_index),
                        repr(sorted((str(k), repr(v)) for k, v in refs.items()))))
    number = Decimal(quantity)
    return {
        "row_id": sha256(lineage.encode("utf-8")).hexdigest()[:24],
        "trade": family, "physical_id": entity,
        "quantity": format(number.normalize(), "f"), "unit": unit,
        "source_sha256": page.source_sha256, "page_index": page.page_index,
        "evidence_refs": dict(refs), "status": "MEASURED_DRAFT_REVIEW_REQUIRED",
        "commercial_publishable": False, "benchmark_credit": False, **extra,
    }


def _door(page_map: Mapping[int, NativePage], row: Mapping[str, Any],
          wall_refs: Mapping[str, tuple[NativePage, NativeSegment]]
          ) -> tuple[list[dict[str, Any]], list[dict[str, str]], Decimal, str]:
    door_id = _required_text(row, "door_id")
    wall_id = _required_text(row, "host_wall_id")
    if wall_id not in wall_refs:
        raise SourceConflict("door_host_wall_not_in_reviewed_wall_scope")
    plan = _page(page_map, row.get("plan_page_index"))
    schedule = _page(page_map, row.get("schedule_page_index"))
    wall_page, wall_segment = wall_refs[wall_id]
    if plan.page_index != wall_page.page_index:
        raise SourceConflict("door_and_host_wall_source_page_mismatch")
    if row.get("opening_reviewed") is not True:
        raise SourceConflict("physical_door_opening_not_reviewed")
    aperture = _segment(plan, row.get("opening_segment_ref"))
    if aperture.ref == wall_segment.ref or not _segment_inside_line(aperture, wall_segment):
        raise SourceConflict("door_aperture_not_on_single_authenticated_host_line")
    plan_code = _word(plan, row.get("plan_code_word_ref"))
    sched_code = _word(schedule, row.get("schedule_code_word_ref"))
    if plan_code.text.strip().upper() != sched_code.text.strip().upper():
        raise SourceConflict("plan_schedule_door_code_mismatch")
    # The word "DOOR" occurs throughout original 3Laurel notes. It is NOT
    # a unique numbered schedule/plan instance identity.
    if not re.fullmatch(r"D[1-9][0-9]*[A-Z]?", plan_code.text.strip().upper()):
        raise SourceConflict("door_code_not_source_identified")
    if _distance_to_line(_centre(plan_code), aperture) > 85:
        raise SourceConflict("door_code_not_near_source_aperture")
    width_word = _word(schedule, row.get("schedule_width_word_ref"))
    height_word = _word(schedule, row.get("schedule_height_word_ref"))
    if len({sched_code.ref, width_word.ref, height_word.ref}) != 3:
        raise SourceConflict("door_schedule_source_receipts_reused")
    if max(abs(_centre(word)[1] - _centre(sched_code)[1])
           for word in (width_word, height_word)) > 20:
        raise SourceConflict("schedule_figures_not_in_door_row")
    width_mm, height_mm = _figured_mm(width_word), _figured_mm(height_word)
    if not Decimal("400") <= width_mm <= Decimal("12000"):
        raise SourceConflict("door_schedule_width_not_credible")
    if not Decimal("1000") <= height_mm <= Decimal("6000"):
        raise SourceConflict("door_schedule_height_not_credible")
    source_wall_len = math.hypot(wall_segment.x2 - wall_segment.x1, wall_segment.y2 - wall_segment.y1)
    aperture_len = math.hypot(aperture.x2 - aperture.x1, aperture.y2 - aperture.y1)
    wall_length_word = _word(wall_page, row.get("host_wall_length_word_ref"))
    if _distance_to_line(_centre(wall_length_word), wall_segment) > 32:
        raise SourceConflict("door_host_wall_length_dimension_unbound")
    wall_mm = _figured_mm(wall_length_word)
    if abs(Decimal(str(aperture_len / source_wall_len)) / (width_mm / wall_mm)
           - Decimal(1)) > Decimal("0.05"):
        raise SourceConflict("door_opening_width_disagrees_with_host_wall_scale")
    refs = {
        "opening_segment_ref": aperture.ref,
        "host_wall_id": wall_id, "host_wall_segment_ref": wall_segment.ref,
        "plan_code_word_ref": plan_code.ref,
        "schedule_code_word_ref": sched_code.ref,
        "schedule_width_word_ref": width_word.ref,
        "schedule_height_word_ref": height_word.ref,
        "schedule_page_index": schedule.page_index,
    }
    area = (width_mm * height_mm / Decimal("1000000"))
    outputs = [
        _row("door_count", door_id, plan, 1, "ea", refs,
             width_m=format((width_mm / Decimal("1000")).normalize(), "f"),
             height_m=format((height_mm / Decimal("1000")).normalize(), "f")),
        _row("door_leaf_area", door_id, plan, area, "m2", refs),
    ]
    failures: list[dict[str, str]] = []
    if row.get("frame_reviewed") is not True:
        failures.append({"family": "door_frame", "physical_id": door_id,
                         "reason_code": "frame_geometry_not_reviewed"})
    else:
        try:
            frame_word = _word(schedule, row.get("frame_word_ref"))
            if frame_word.text.strip().upper() not in ("FRAME", "FRAMED", "DOORFRAME"):
                raise SourceConflict("frame_presence_not_verified_from_schedule")
            if abs(_centre(frame_word)[1] - _centre(sched_code)[1]) > 20:
                raise SourceConflict("frame_not_in_own_door_schedule_row")
            configuration = row.get("frame_configuration")
            if configuration not in ("three_sided", "four_sided"):
                raise SourceConflict("frame_sides_not_authenticated")
            perimeter_mm = height_mm * 2 + (width_mm if configuration == "three_sided" else width_mm * 2)
            frame_refs = {**refs, "frame_word_ref": frame_word.ref,
                          "frame_configuration": configuration}
            outputs.extend([
                _row("door_frame_count", door_id, plan, 1, "ea", frame_refs),
                _row("door_frame_length", door_id, plan, perimeter_mm / Decimal("1000"),
                     "m", frame_refs),
            ])
        except SourceConflict as exc:
            failures.append({"family": "door_frame", "physical_id": door_id,
                             "reason_code": str(exc)})
    return outputs, failures, area, wall_id


def _wall(page_map: Mapping[int, NativePage], row: Mapping[str, Any],
          successful_doors: Mapping[str, tuple[Decimal, str]],
          requested_doors: Mapping[str, str],
          project_standard_height: Mapping[str, Any] | None = None,
          ) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    wall_id = _required_text(row, "wall_id")
    page = _page(page_map, row.get("page_index"))
    segment = _segment(page, row.get("face_segment_ref"))
    if row.get("face_basis") != "internal_finished_wall_face":
        raise SourceConflict("wall_finished_face_not_reviewed")
    length_word = _word(page, row.get("length_word_ref"))
    if _distance_to_line(_centre(length_word), segment) > 32:
        raise SourceConflict("wall_figured_length_not_at_source_face")
    length_mm = _figured_mm(length_word)
    height_source_refs: dict[str, Any] = {}
    if project_standard_height is not None:
        from .project_height_policy import select_applicable_height
        from .height_evidence import RCP_MATERIAL_HEIGHT
        local_claim = row.get("height_source_receipt")
        if local_claim is not None and (
            not isinstance(local_claim, Mapping)
            or local_claim.get("height_source_kind") not in (
                RCP_MATERIAL_HEIGHT, "ffl_to_fcl_section"
            )
        ):
            raise SourceConflict("wall_height_override_kind_invalid")
        if (
            local_claim is not None
            and local_claim.get("height_source_kind") != RCP_MATERIAL_HEIGHT
            and dict(local_claim) != project_standard_height["source_height_receipt"]
        ):
            raise SourceConflict("wall_standard_height_source_receipt_mismatch")
        selected = select_applicable_height(
            page_map, project_standard_height,
            local_receipt=(
                local_claim
                if local_claim is not None
                and local_claim.get("height_source_kind") == RCP_MATERIAL_HEIGHT
                else None
            ),
            local_page_index=row.get("height_source_page_index"),
            local_scope_reviewed=row.get("height_applies_to_wall_reviewed") is True,
            local_zone_id=row.get("height_ceiling_zone_id"),
        )
        source_height_page = _page(page_map, selected["source_page_index"])
        height_word = _word(
            source_height_page, selected["source_height_receipt"]["height_word_ref"]
        )
        height_mm = Decimal(selected["height_mm"])
        # Conflicting independently typed height figures must not override a
        # source-owned standard or a reviewed RCP local height receipt.
        if row.get("height_word_ref") is not None and (
            row["height_word_ref"] != height_word.ref
        ):
            raise SourceConflict("wall_height_word_conflicts_with_project_rule")
        receipt = selected["source_height_receipt"]
        height_source_refs.update({
            "height_source_kind": receipt["height_source_kind"],
            "height_witness_word_refs": tuple(receipt["witness_word_refs"]),
            "height_dimension_segment_refs": tuple(receipt["dimension_segment_refs"]),
            "height_material_word_ref": receipt["material_word_ref"],
            "height_source_scope_reviewed": True,
            "height_policy_basis": selected["basis"],
            "project_standard_height_mm": project_standard_height["height_mm"],
            "local_height_override": selected["local_override"],
        })
        if selected["local_override"]:
            height_source_refs["height_ceiling_zone_id_claimed"] = selected["local_zone_id"]
    else:
        source_height_page = _page(page_map, row.get("height_source_page_index"))
        height_word = _word(source_height_page, row.get("height_word_ref"))
        height_mm = _figured_mm(height_word)
        height_claim = row.get("height_source_receipt")
        if height_claim is not None:
            from .height_evidence import (
                RCP_MATERIAL_HEIGHT, validate_height_receipt,
            )
            if row.get("height_applies_to_wall_reviewed") is not True:
                raise SourceConflict("wall_height_scope_not_reviewed")
            proved = validate_height_receipt(
                source_height_page, height_claim,
                rcp_viewport_pdf_pts=row.get("height_rcp_viewport_pdf_pts"),
            )
            if proved["height_word_ref"] != height_word.ref:
                raise SourceConflict("wall_height_word_receipt_mismatch")
            if proved["height_source_kind"] == RCP_MATERIAL_HEIGHT:
                ceiling_zone = row.get("height_ceiling_zone_id")
                if type(ceiling_zone) is not str or not ceiling_zone.strip():
                    raise SourceConflict("rcp_height_wall_zone_scope_missing")
                height_source_refs["height_ceiling_zone_id_claimed"] = ceiling_zone
            height_source_refs.update({
                "height_source_kind": proved["height_source_kind"],
                "height_witness_word_refs": tuple(proved["witness_word_refs"]),
                "height_dimension_segment_refs": tuple(proved["dimension_segment_refs"]),
                "height_material_word_ref": proved["material_word_ref"],
                "height_source_scope_reviewed": True,
            })
    finish_word = _word(page, row.get("finish_word_ref"))
    if _distance_to_line(_centre(finish_word), segment) > 90:
        raise SourceConflict("wall_finish_not_at_source_face")
    if not (Decimal("500") <= height_mm <= Decimal("12000")):
        raise SourceConflict("wall_height_not_source_supported")
    if not (Decimal("100") <= length_mm <= Decimal("100000")):
        raise SourceConflict("wall_figured_length_invalid")
    refs = {
        "wall_segment_ref": segment.ref, "length_word_ref": length_word.ref,
        "height_word_ref": height_word.ref,
        "height_source_page_index": source_height_page.page_index,
        "finish_word_ref": finish_word.ref,
        **height_source_refs,
    }
    gross = length_mm * height_mm / Decimal("1000000")
    outputs = [
        _row("wall_length", wall_id, page, length_mm / Decimal("1000"), "m", refs),
        _row("wall_finish_gross_area", wall_id, page, gross, "m2", refs,
             finish_code=finish_word.text.strip().upper()),
    ]
    failures: list[dict[str, str]] = []
    deductions = row.get("deduct_door_ids", [])
    if not isinstance(deductions, list) or any(not isinstance(x, str) or not x for x in deductions):
        raise SourceConflict("wall_opening_deduction_receipts_invalid")
    if len(set(deductions)) != len(deductions):
        raise SourceConflict("wall_door_deduction_reused")
    hosted = {door for door, host in requested_doors.items() if host == wall_id}
    if hosted != set(deductions):
        failures.append({"family": "wall_finish_net_area", "physical_id": wall_id,
                         "reason_code": "reviewed_wall_door_universe_incomplete"})
    elif any(door not in successful_doors for door in deductions):
        failures.append({"family": "wall_finish_net_area", "physical_id": wall_id,
                         "reason_code": "door_opening_source_authority_missing"})
    else:
        deductible = sum((successful_doors[door][0] for door in deductions), Decimal("0"))
        net = gross - deductible
        if net < 0:
            failures.append({"family": "wall_finish_net_area", "physical_id": wall_id,
                             "reason_code": "wall_door_deduction_exceeds_gross_area"})
        else:
            outputs.append(_row("wall_finish_net_area", wall_id, page, net, "m2",
                                {**refs, "deduct_door_ids": tuple(sorted(deductions))},
                                finish_code=finish_word.text.strip().upper()))
    return outputs, failures


def measure_building_components(
    pages: Mapping[int, NativePage], selection: Mapping[str, Any],
) -> dict[str, Any]:
    """One create-only-review JSON packet: floors, ceilings, walls, doors, frames."""
    if not pages:
        raise SourceConflict("source_pages_missing")
    source_sha = _required_text(selection, "source_sha256")
    project = _required_text(selection, "project_id")
    revision = _required_text(selection, "revision_id")
    if any(page.source_sha256 != source_sha or index != page.page_index
           for index, page in pages.items()):
        raise SourceConflict("multi_page_source_sha_or_index_conflict")
    from .project_height_policy import resolve_project_standard_height
    project_standard_height = resolve_project_standard_height(
        pages, project, source_sha, selection.get("project_standard_height_policy"),
    )
    inputs = {name: selection.get(name, []) for name in ("rooms", "ceilings", "walls", "doors")}
    if any(not isinstance(value, list) for value in inputs.values()):
        raise SourceConflict("building_family_selection_invalid")
    for family, key in (
        ("rooms", "room_id"), ("ceilings", "ceiling_id"),
        ("walls", "wall_id"), ("doors", "door_id"),
    ):
        ids = [_required_text(row, key) for row in inputs[family]]
        if len(ids) != len(set(ids)):
            raise SourceConflict(f"duplicate_{family}_physical_id")
    # One source-RCP candidate rectangle cannot be sold as multiple distinct
    # ceiling zones merely by assigning different physical IDs to the rows.
    selected_rcp = [
        (row.get("rcp_page_index"), row.get("rcp_source_rectangle_ref"))
        for row in inputs["ceilings"] if row.get("rcp_page_index") is not None
    ]
    if len(selected_rcp) != len(set(selected_rcp)):
        raise SourceConflict("duplicate_ceiling_rcp_source_zone_claim")
    for family in ("rooms", "ceilings"):
        shapes = [
            (row.get("page_index"), "polygon", tuple(sorted(row["boundary_segment_refs"])))
            if "boundary_segment_refs" in row
            else (row.get("page_index"), "rectangle", row.get("rectangle_ref"))
            for row in inputs[family]
        ]
        if len(set(shapes)) != len(shapes):
            raise SourceConflict(f"duplicate_{family}_source_surface")
    wall_refs: dict[str, tuple[NativePage, NativeSegment]] = {}
    for row in inputs["walls"]:
        wall_id = _required_text(row, "wall_id")
        page = _page(pages, row.get("page_index"))
        wall_refs[wall_id] = (page, _segment(page, row.get("face_segment_ref")))
    if len({(p.page_index, segment.ref) for p, segment in wall_refs.values()}) != len(wall_refs):
        raise SourceConflict("duplicate_physical_wall_segment")
    openings = [
        (row.get("plan_page_index"), row.get("opening_segment_ref"))
        for row in inputs["doors"]
    ]
    if len(set(openings)) != len(openings):
        raise SourceConflict("duplicate_physical_door_aperture")
    requested_doors = {
        _required_text(row, "door_id"): _required_text(row, "host_wall_id")
        for row in inputs["doors"]
    }

    quantities: list[dict[str, Any]] = []
    abstentions: list[dict[str, str]] = []
    # A reviewed ceiling zone can carry its own printed RCP height to walls
    # that are explicitly reviewed as belonging to the SAME ceiling zone.
    # The key is the ceiling's physical ID, not a nearest-word association.
    ceiling_zone_source_heights: dict[str, tuple[int, dict[str, Any]]] = {}
    ceiling_zones_with_invalid_height: set[str] = set()
    for row in inputs["rooms"]:
        try:
            page = _page(pages, row.get("page_index"))
            packet = measure_page(page, {
                "source_sha256": source_sha, "page_index": page.page_index,
                "project_id": project, "revision_id": revision, "rooms": [row],
            })
            quantities.extend(packet["quantities"])
            abstentions.extend({**x, "family": "floor_finish"} for x in packet["abstentions"])
        except (SourceConflict, TypeError, ValueError, InvalidOperation, ZeroDivisionError) as exc:
            abstentions.append({"family": "floor_finish",
                                "physical_id": str(row.get("room_id", "")),
                                "reason_code": str(exc) if isinstance(exc, SourceConflict) else "invalid_floor_observation"})
    for row in inputs["ceilings"]:
        ceiling_id = str(row.get("ceiling_id", ""))
        try:
            page = _page(pages, row.get("page_index"))
            rcp_source_page = (
                _page(pages, row.get("rcp_page_index"))
                if row.get("rcp_page_index") is not None
                else None
            )
            quantity = _measure_one(
                page, row, expected_basis="source_owned_ceiling_zone",
                trade="ceiling_finish", finish_page=rcp_source_page,
            )
            quantity["ceiling_id"] = ceiling_id
            # Ceiling area and height are independent sources. A same-bubble
            # RCP material/height is a SPECIFIC local exception to a project
            # standard. Its material word must be the source word already
            # authenticated as belonging to the reviewed ceiling zone.
            from .height_evidence import RCP_MATERIAL_HEIGHT, rcp_material_height_callouts, validate_height_receipt
            local_claim = row.get("height_source_receipt")
            auto_owned_callout = False
            if local_claim is None:
                local = [
                    receipt for receipt in rcp_material_height_callouts(
                        rcp_source_page or page
                    )
                    if receipt["material_word_ref"] == row.get("finish_word_ref")
                    and (
                        row.get("rcp_height_word_ref") is None
                        or receipt["height_word_ref"] == row["rcp_height_word_ref"]
                    )
                ]
                if len(local) == 1:
                    local_claim = local[0]
                    auto_owned_callout = True
                elif len(local) > 1:
                    ceiling_zones_with_invalid_height.add(ceiling_id)
                    abstentions.append({
                        "family": "ceiling_height", "physical_id": ceiling_id,
                        "reason_code": "multiple_explicit_rcp_heights_for_ceiling_material",
                    })
            if local_claim is not None:
                try:
                    if (
                        row.get("height_ceiling_zone_reviewed") is not True
                        and not auto_owned_callout
                    ):
                        raise SourceConflict("rcp_height_ceiling_zone_not_reviewed")
                    evidence = validate_height_receipt(
                        rcp_source_page or page, local_claim,
                        rcp_viewport_pdf_pts=row.get("height_rcp_viewport_pdf_pts"),
                    )
                    if evidence["height_source_kind"] != RCP_MATERIAL_HEIGHT:
                        raise SourceConflict("ceiling_height_not_from_rcp_material_callout")
                    if evidence["material_word_ref"] != row.get("finish_word_ref"):
                        raise SourceConflict("rcp_height_material_not_owned_by_ceiling_zone")
                    quantity["height_mm_source_candidate"] = evidence["height_mm"]
                    quantity["height_word_ref"] = evidence["height_word_ref"]
                    quantity["height_material_word_ref"] = evidence["material_word_ref"]
                    quantity["height_source_receipt"] = evidence
                    quantity["height_zone_scope"] = "REVIEWED_DRAFT_NOT_AUTHENTICATED"
                    quantity["height_policy_basis"] = "SOURCE_RCP_LOCAL_CEILING_ZONE_OVERRIDE"
                    if project_standard_height is not None:
                        quantity["project_standard_height_mm"] = project_standard_height["height_mm"]
                    ceiling_zone_source_heights[ceiling_id] = (
                        (rcp_source_page or page).page_index, evidence
                    )
                except SourceConflict as exc:
                    ceiling_zones_with_invalid_height.add(ceiling_id)
                    abstentions.append({
                        "family": "ceiling_height", "physical_id": ceiling_id,
                        "reason_code": str(exc),
                    })
            elif project_standard_height is not None and len(local) == 0:
                standard_receipt = project_standard_height["source_height_receipt"]
                quantity["height_mm_source_candidate"] = project_standard_height["height_mm"]
                quantity["height_word_ref"] = standard_receipt["height_word_ref"]
                quantity["height_source_receipt"] = standard_receipt
                quantity["height_policy_basis"] = "OWNER_AUTHORIZED_PROJECT_FFL_FCL_STANDARD"
                quantity["height_source_page_index"] = project_standard_height["section_page_index"]
                quantity["height_zone_scope"] = "OWNER_STANDARD_UNLESS_EXPLICIT_OVERRIDE"
            quantities.append(quantity)
        except (SourceConflict, TypeError, ValueError, InvalidOperation, ZeroDivisionError) as exc:
            abstentions.append({"family": "ceiling_finish", "physical_id": ceiling_id,
                                "reason_code": str(exc) if isinstance(exc, SourceConflict) else "invalid_ceiling_observation"})
    successful_doors: dict[str, tuple[Decimal, str]] = {}
    for row in inputs["doors"]:
        door_id = str(row.get("door_id", ""))
        try:
            produced, failures, opening_area, host_id = _door(pages, row, wall_refs)
            quantities.extend(produced)
            abstentions.extend(failures)
            successful_doors[door_id] = (opening_area, host_id)
        except (SourceConflict, TypeError, ValueError, InvalidOperation, ZeroDivisionError) as exc:
            abstentions.append({"family": "door", "physical_id": door_id,
                                "reason_code": str(exc) if isinstance(exc, SourceConflict) else "invalid_door_observation"})
            if row.get("frame_reviewed") is True:
                abstentions.append({"family": "door_frame", "physical_id": door_id,
                                    "reason_code": "door_source_authority_missing"})
    for row in inputs["walls"]:
        wall_id = str(row.get("wall_id", ""))
        try:
            wall_row = row
            zone_id = row.get("height_ceiling_zone_id")
            if (
                project_standard_height is not None
                and type(zone_id) is str
                and zone_id in ceiling_zones_with_invalid_height
            ):
                raise SourceConflict("linked_ceiling_zone_height_unresolved")
            if (
                project_standard_height is not None
                and "height_source_receipt" not in row
                and type(zone_id) is str
                and zone_id in ceiling_zone_source_heights
            ):
                if row.get("height_applies_to_wall_reviewed") is not True:
                    raise SourceConflict("local_ceiling_zone_wall_scope_not_reviewed")
                zone_page, zone_receipt = ceiling_zone_source_heights[zone_id]
                wall_row = {
                    **row,
                    "height_source_page_index": zone_page,
                    "height_source_receipt": zone_receipt,
                }
                # The project standard cannot silently replace an RCP-local
                # height already authenticated to this reviewed ceiling zone.
                wall_row.pop("height_word_ref", None)
            produced, failures = _wall(
                pages, wall_row, successful_doors, requested_doors, project_standard_height,
            )
            quantities.extend(produced)
            abstentions.extend(failures)
        except (SourceConflict, TypeError, ValueError, InvalidOperation, ZeroDivisionError) as exc:
            abstentions.append({"family": "wall_finish", "physical_id": wall_id,
                                "reason_code": str(exc) if isinstance(exc, SourceConflict) else "invalid_wall_observation"})
    if len({q["row_id"] for q in quantities}) != len(quantities):
        raise SourceConflict("duplicate_building_quantity_identity")
    return {
        "schema_version": "0.2.0",
        "project_id": project, "revision_id": revision,
        "source_sha256": source_sha,
        "source_pages": sorted(pages),
        "project_standard_height": project_standard_height,
        "quantities": quantities, "abstentions": abstentions,
        "commercial_publishable": False, "official_score": None,
    }
