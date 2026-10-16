import re
p = "C:/claude-work/ft3-p11-p7/tools/diag_ft3_p11_p7_floor_correspondence.py"
s = open(p, encoding="utf-8").read()

# ---- 1. pure functions + classify_floor rewrite
start = s.index("def classify_floor(")
end = s.index("# -------------------------------------------------------------------------------------- source-dependent steps")
new_pure = '''def side_ownership(
    box: Sequence[float],
    segments: Mapping[str, Mapping[str, float]],
    owners: Mapping[str, Iterable[str]],
    grid_flags: Mapping[str, bool],
    *,
    tol: float = COORD_TOL,
    min_len: float = MIN_LEN,
) -> dict[str, dict[str, Any]]:
    """W4 source-primitive ownership behind each box side (which candidates own the primitives lying on the side).

    ``owners`` maps a source primitive id to every W4 candidate id that contains it; a primitive claimed by several
    candidates, or by none, means the side's wall evidence is candidate-level only (no unique physical-wall identity).
    """
    x0, y0, x1, y1 = (float(v) for v in box)
    out: dict[str, dict[str, Any]] = {}
    for name, orient, coord, lo, hi in (("x0", "V", x0, y0, y1), ("x1", "V", x1, y0, y1), ("y0", "H", y0, x0, x1), ("y1", "H", y1, x0, x1)):
        prims = []
        for pid, seg in segments.items():
            a, b, c, d = float(seg["x1"]), float(seg["y1"]), float(seg["x2"]), float(seg["y2"])
            if math.hypot(c - a, d - b) < min_len:
                continue
            if orient == "V" and abs(a - c) < AXIS_TOL and abs(a - coord) <= tol and min(b, d) < hi and max(b, d) > lo:
                prims.append(pid)
            elif orient == "H" and abs(b - d) < AXIS_TOL and abs(b - coord) <= tol and min(a, c) < hi and max(a, c) > lo:
                prims.append(pid)
        claimants: collections.Counter = collections.Counter()
        unowned = multi = 0
        for pid in sorted(prims):
            cands = set(owners.get(pid, ()))
            if not cands:
                unowned += 1
                continue
            multi += len(cands) > 1
            claimants.update(cands)
        out[name] = {
            "primitives_on_side": len(prims), "unowned_by_any_w4_candidate": unowned, "owned_by_multiple_candidates": multi,
            "distinct_candidates": len(claimants), "grid_opposed_candidates": sum(1 for c in claimants if grid_flags.get(c)),
        }
    return out


def ownership_blockers(ownership: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> list[str]:
    """Authority blockers from side ownership on every page: any shared or unowned primitive keeps the relation at candidate level."""
    reasons: list[str] = []
    for page, sides in ownership.items():
        if any(v["owned_by_multiple_candidates"] for v in sides.values()):
            reasons.append(f"page_{page}_box_side_primitive_claimed_by_several_w4_candidates")
        if any(v["unowned_by_any_w4_candidate"] for v in sides.values()):
            reasons.append(f"page_{page}_box_side_primitive_unowned_by_w4")
    return reasons


def face_equivalence(
    face_polygon: Sequence[Sequence[float]],
    target_faces: Mapping[str, Sequence[Sequence[float]]],
    translation: Sequence[float],
    *,
    top: int = 3,
) -> list[dict[str, Any]]:
    """Every target-sheet face overlapping a support-sheet face under the translation, by IoU (all alternatives retained)."""
    from shapely.affinity import translate
    from shapely.geometry import Polygon

    moved = translate(Polygon(face_polygon).buffer(0), xoff=translation[0], yoff=translation[1])
    rows = []
    for face_id in sorted(target_faces):
        other = Polygon(target_faces[face_id]).buffer(0)
        if other.is_empty or not moved.intersects(other):
            continue
        inter = moved.intersection(other).area
        if inter <= 1e-6:
            continue
        rows.append({"face_id": face_id, "iou": round(inter / moved.union(other).area, 4), "area_pt2": round(other.area, 1)})
    rows.sort(key=lambda r: (-r["iou"], r["face_id"]))
    return rows[:top]


STANDING_AUTHORITY_BLOCKERS = (
    "support_page_has_no_source_owned_room_face_or_label_authority",
    "no_physical_wall_equivalence_authority_for_box_sides",
)


def classify_floor(
    correspondence: Mapping[str, Any],
    *,
    registration_unique: bool,
    marks_inside: Sequence[Mapping[str, Any]],
    other_labelled_boxes_overlapping: int,
    material_code: str,
    min_margin_pt: float = 5.0,
    authority_blockers: Sequence[str] = (),
) -> dict[str, Any]:
    """Typed outcome using existing EvidenceResolutionStatus values only (strings).

    The best this diagnostic can say is ``candidate``: geometric ownership consistent on both sheets.  It never emits
    ``corroborated`` because unique authenticated wall/face equivalence needs authorities that do not exist yet
    (``authority_blockers`` lists what is missing).
    """
    reasons: list[str] = []
    codes = collections.Counter(m["code"] for m in marks_inside)
    if not registration_unique:
        reasons.append("registration_not_unique")
    if not correspondence["wall_bounded_on_both_sheets"]:
        reasons.append("box_not_wall_bounded_on_both_sheets")
    elif not correspondence["wall_evidence_identical_on_both_sheets"]:
        reasons.append("wall_evidence_differs_between_sheets")
    if other_labelled_boxes_overlapping:
        reasons.append("overlapping_measured_boxes")
    if any(m["margin_pt"] < min_margin_pt for m in marks_inside):
        reasons.append("mark_too_close_to_box_side")
    if any(not m.get("registered_region", True) for m in marks_inside):
        reasons.append("mark_in_unregistered_region")
    if len(codes) > 1:
        status, reasons = "conflict", reasons + ["competing_finish_codes_in_box"]
    elif not codes:
        status, reasons = "abstained", reasons + ["no_finish_mark_in_box"]
    elif material_code not in codes:
        status, reasons = "abstained", reasons + ["box_owned_by_other_finish_code"]
    elif reasons:
        status = "abstained"
    else:
        status = "candidate"
        reasons = ["floor_geometrically_owned_equivalence_not_authenticated"]
    return {"status": status, "reason_codes": reasons, "finish_codes_in_box": dict(codes),
            "authority_blockers": list(authority_blockers) if status == "candidate" else [],
            "authenticated_physical_wall_face_equivalence": False}


'''
s = s[:start] + new_pure + s[end:]

# ---- 2. W4 evidence: owners, grid flags, W5 faces
s = s.replace(
    "    from pb_source_composite_room_face_authority import _fully_grid_opposed_wall_evidence\n    from pb_source_visibility_authority import SourceVisibilityProducer\n",
    "    from pb_source_composite_room_face_authority import _fully_grid_opposed_wall_evidence\n    from pb_source_room_face_authority import SourceRoomFaceSelector, build_source_room_face_authority\n    from pb_source_visibility_authority import SourceVisibilityProducer\n",
)
a = s.index("    for page, scope in ((SOURCE_PAGE, scope7), (MARK_PAGE, scope11)):\n        grid_ids, _ = _fully_grid_opposed_wall_evidence(scope)")
b = s.index("def _capture_measured_floors")
new_block = '''    for page, scope, authority in ((SOURCE_PAGE, scope7, auth7), (MARK_PAGE, scope11, auth11)):
        grid_ids, _ = _fully_grid_opposed_wall_evidence(scope)
        kept, excluded = [], 0
        owners: dict[str, list[str]] = collections.defaultdict(list)
        for record in scope.records:
            for pid in record.physical_identity.source_primitive_ids:
                owners[pid].append(record.wall_candidate_id)
            if record.wall_candidate_id in grid_ids:
                excluded += 1
            else:
                kept.extend(record.physical_identity.source_primitive_ids)
        room_scope = build_source_room_face_authority(authority).resolve_scope(SourceRoomFaceSelector(
            document_id=scope.document_id, revision_id=scope.revision_id, source_sha256=scope.source_sha256,
            snapshot_id=scope.snapshot_id, page_id=scope.page_id, decision_scope_id=scope.decision_scope_id,
        ))
        out[str(page)] = {
            "w4_status": scope.status.value, "w4_scope_complete": bool(scope.scope_complete), "w4_reason_codes": list(scope.reason_codes),
            "w4_records": len(scope.records), "grid_opposed_excluded": excluded, "primitive_ids": sorted(set(kept)),
            "viewport_id": scope.viewport_id,
            "primitive_owners": {k: sorted(set(v)) for k, v in owners.items()},
            "grid_flags": {r.wall_candidate_id: r.wall_candidate_id in grid_ids for r in scope.records},
            "w5_status": room_scope.status.value, "w5_scope_complete": bool(room_scope.scope_complete),
            "faces_published": {f.face_id: {"record_id": f.record_id, "polygon": [list(p) for p in f.polygon_pdf_pts]} for f in room_scope.records},
            "faces_withheld": {f.face_id: [list(p) for p in f.polygon_pdf_pts] for f in room_scope.abstained_faces},
        }
    return out


'''
s = s[:a] + new_block + s[b:]
s = s.replace(
    '"page_evidence": {p: {k: v for k, v in evidence[p].items() if k != "primitive_ids"} for p in evidence},',
    '"page_evidence": {p: {k: v for k, v in evidence[p].items() if k in ("w4_status", "w4_scope_complete", "w4_reason_codes", "w4_records", "grid_opposed_excluded", "viewport_id", "w5_status", "w5_scope_complete")} | {"faces_published": len(evidence[p]["faces_published"]), "faces_withheld": len(evidence[p]["faces_withheld"])} for p in evidence},',
)

# keep native segments per page
s = s.replace('''    lines: dict[int, Lines] = {}
    for page in (SOURCE_PAGE, MARK_PAGE):
        segs = {s["id"]: s for s in _native_segments(payload, page)}
        lines[page] = build_lines(segs[i] for i in evidence[str(page)]["primitive_ids"] if i in segs)''', '''    lines: dict[int, Lines] = {}
    segments: dict[int, dict[str, Any]] = {}
    for page in (SOURCE_PAGE, MARK_PAGE):
        segments[page] = {seg["id"]: seg for seg in _native_segments(payload, page)}
        lines[page] = build_lines(segments[page][i] for i in evidence[str(page)]["primitive_ids"] if i in segments[page])''')

# ---- 3. per-floor ownership audit + blockers
s = s.replace('''        floor["correspondence"] = {**classify_floor(corr, registration_unique=registration["unique"], marks_inside=inside, other_labelled_boxes_overlapping=overlaps, material_code=material_code),
                                   "geometry": corr, "marks_inside_box": inside}''', '''        box_target = tuple(corr["box_target_sheet"])
        ownership = {
            str(MARK_PAGE): side_ownership(box, segments[MARK_PAGE], evidence[str(MARK_PAGE)]["primitive_owners"], evidence[str(MARK_PAGE)]["grid_flags"]),
            str(SOURCE_PAGE): side_ownership(box_target, segments[SOURCE_PAGE], evidence[str(SOURCE_PAGE)]["primitive_owners"], evidence[str(SOURCE_PAGE)]["grid_flags"]),
        }
        blockers = [*STANDING_AUTHORITY_BLOCKERS, *ownership_blockers(ownership)]
        if not evidence[str(SOURCE_PAGE)]["w4_scope_complete"]:
            blockers.append(f"page_{SOURCE_PAGE}_w4_scope_incomplete")
        floor["correspondence"] = {**classify_floor(corr, registration_unique=registration["unique"], marks_inside=inside, other_labelled_boxes_overlapping=overlaps,
                                                    material_code=material_code, authority_blockers=blockers),
                                   "geometry": corr, "marks_inside_box": inside, "w4_ownership_behind_box_sides": ownership}''')

# ---- 4. per-mark binding table and result keys
s = s.replace('''    owners = [f for f in result["measured_floors"] if f["correspondence"]["status"] == "corroborated"]
    result["uniquely_owned_floors"] = [''', '''    face_index_support = {**{k: v["polygon"] for k, v in evidence[str(MARK_PAGE)]["faces_published"].items()}, **evidence[str(MARK_PAGE)]["faces_withheld"]}
    face_index_target = {**{k: v["polygon"] for k, v in evidence[str(SOURCE_PAGE)]["faces_published"].items()}, **evidence[str(SOURCE_PAGE)]["faces_withheld"]}
    record_to_face = {v["record_id"]: k for k, v in evidence[str(SOURCE_PAGE)]["faces_published"].items()}
    measured_faces = {f["room_label"]: record_to_face.get(f["source_room_face_record_id"]) for f in result["measured_floors"]}
    from shapely.geometry import Point, Polygon

    for m in marks:
        if m["code"] != material_code:
            continue
        holders = [fid for fid, poly in sorted(face_index_support.items()) if Polygon(poly).buffer(0).contains(Point(*m["center"]))]
        equiv = [face_equivalence(face_index_support[fid], face_index_target, translation) for fid in holders]
        in_boxes = [f["room_label"] for f in result["measured_floors"] if "marks_inside_box" in f["correspondence"]
                    and any(mi["center"] == m["center"] for mi in f["correspondence"]["marks_inside_box"])]
        reasons = []
        if not m["local_registration"]["registered_region"]:
            reasons.append("mark_in_unregistered_region")
        if not in_boxes:
            reasons.append("outside_every_measured_box")
        for f in result["measured_floors"]:
            if f["room_label"] in in_boxes and f["correspondence"]["status"] != "candidate":
                reasons += [f"{f['room_label']}:{r}" for r in f["correspondence"]["reason_codes"]]
        top = equiv[0][0] if equiv and equiv[0] else None
        if top is not None and top["face_id"] in measured_faces.values():
            face_join = "mark_face_is_measured_floor_face"
        else:
            face_join = "mark_face_differs_from_measured_floor_face_only_the_dimension_box_relates_them" if in_boxes else "no_measured_floor_face"
        m["binding"] = {"inside_measured_boxes": in_boxes, "support_page_faces_containing_mark": [h[-12:] for h in holders],
                        "target_page_face_alternatives_by_iou": equiv, "face_level_join": face_join, "blockers_before_any_binding": reasons}
    owners = [f for f in result["measured_floors"] if f["correspondence"]["status"] == "candidate"]
    result["geometric_candidate_owner_floors"] = [''')
s = s.replace('''        "floor_finish_quantity_requires_authenticated_material_definition_and_occurrence_scope"
        if owners else "no_measured_floor_uniquely_owned_by_material_marks"''', '''        "geometric_candidate_owner_found_authenticated_equivalence_and_material_authority_still_required"
        if owners else "no_measured_floor_geometrically_owned_by_material_marks"''')
s = s.replace('''"uniquely_owned_floors": [f["room_label"] for f in report.get("uniquely_owned_floors", [])],''', '''"geometric_candidate_owner_floors": [f["room_label"] for f in report.get("geometric_candidate_owner_floors", [])],''')
open(p, "w", encoding="utf-8").write(s)
print("patched")
