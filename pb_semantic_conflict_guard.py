"""Semantic conflict diagnostic and abstention guard for PlanReader production pipeline (AG-08).

Guards the production evidence pipeline against conflicting semantic evidence without
silently altering quantities.

Detects:
1. Incompatible material identities (e.g. contradictory finishes/substrates on the same face)
2. Room label conflicts (e.g. contradictory functional labels or conflicting room area claims)
3. Schedule vs drawing mismatches (e.g. opening size or type disagreements between schedule and plan)
4. Opening definition mismatches (e.g. detail definition conflicting with schedule/elevation)
5. Incompatible wall classifications (e.g. a wall classified simultaneously as external facade and internal partition)

Invariants:
- MUST NOT silently change quantities.
- Attaches structured conflict provenance to report diagnostics and takeoff row notes.
- Escalates status to Review/Conflict when contradictory claims cannot be reconciled.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import EvidenceResolutionStatus, canonical_contract_json, stable_contract_id
import pb_takeoff_row_contract as takeoff_contract


SEMANTIC_CONFLICT_GUARD_SCHEMA_VERSION = "1.0.0"

# Conflict Kinds
CONFLICT_KIND_INCOMPATIBLE_MATERIALS = "incompatible_material_identities"
CONFLICT_KIND_ROOM_LABEL_CONFLICT = "room_label_conflict"
CONFLICT_KIND_SCHEDULE_DRAWING_MISMATCH = "schedule_vs_drawing_mismatch"
CONFLICT_KIND_OPENING_DEFINITION_MISMATCH = "opening_definition_mismatch"
CONFLICT_KIND_INCOMPATIBLE_WALL_CLASSIFICATION = "incompatible_wall_classifications"

# Mutually exclusive substrate pairs (when applied to the same face/layer)
_EXCLUSIVE_SUBSTRATE_SETS = (
    {"brick", "weatherboard"},
    {"brick", "lineaboard"},
    {"brick_veneer", "lightweight_cladding"},
    {"concrete_block", "timber_framing"},
    {"glazed_curtain_wall", "masonry"},
)

# Mutually exclusive room functional groups
_EXCLUSIVE_ROOM_GROUPS = (
    {"bathroom", "ensuite", "powder_room"},
    {"bedroom", "bed"},
    {"garage", "carport"},
    {"kitchen", "pantry"},
)


@dataclass(frozen=True)
class SemanticConflictRecord:
    """Structured record of a diagnosed semantic conflict in the production pipeline."""
    conflict_id: str
    conflict_kind: str
    subject_id: str
    status: EvidenceResolutionStatus
    description: str
    sources: tuple[str, ...]
    suggested_action: str
    schema_version: str = SEMANTIC_CONFLICT_GUARD_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "conflict_kind": self.conflict_kind,
            "subject_id": self.subject_id,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "description": self.description,
            "sources": list(self.sources),
            "suggested_action": self.suggested_action,
            "schema_version": self.schema_version,
        }


def _norm_token(val: Any) -> str:
    return str(val or "").strip().lower().replace(" ", "_").replace("-", "_")


def check_incompatible_material_identities(
    materials: Sequence[str],
    subject_id: str = "",
    sources: Optional[Sequence[str]] = None,
) -> Optional[SemanticConflictRecord]:
    """Detect mutually exclusive material/substrate claims on the same element face."""
    norm_materials = {_norm_token(m) for m in materials if _norm_token(m)}
    if len(norm_materials) < 2:
        return None

    for exclusive_set in _EXCLUSIVE_SUBSTRATE_SETS:
        overlap = norm_materials.intersection(exclusive_set)
        if len(overlap) >= 2:
            mat_str = " vs ".join(sorted(overlap))
            src_list = tuple(sources or ["drawing_text", "schedule"])
            cid = stable_contract_id(
                "conflict_materials",
                {"subject_id": subject_id, "materials": sorted(overlap)},
                digest_chars=16,
            )
            return SemanticConflictRecord(
                conflict_id=cid,
                conflict_kind=CONFLICT_KIND_INCOMPATIBLE_MATERIALS,
                subject_id=subject_id or "substrate",
                status=EvidenceResolutionStatus.CONFLICT,
                description=f"Incompatible materials claimed for same element face: {mat_str}",
                sources=src_list,
                suggested_action="abstain_from_arbitrary_selection",
            )
    return None


def check_room_label_conflict(
    room_id: str,
    labels: Sequence[str],
    areas_m2: Optional[Sequence[float]] = None,
    sources: Optional[Sequence[str]] = None,
) -> Optional[SemanticConflictRecord]:
    """Detect conflicting functional identities or contradictory area claims for a room."""
    norm_labels = {_norm_token(lbl) for lbl in labels if _norm_token(lbl)}

    # 1. Check functional role collision across exclusive groups
    matched_groups = []
    for grp in _EXCLUSIVE_ROOM_GROUPS:
        if any(lbl in grp or any(member in lbl for member in grp) for lbl in norm_labels):
            matched_groups.append(grp)

    if len(matched_groups) >= 2:
        lbl_str = " vs ".join(sorted(labels))
        cid = stable_contract_id(
            "conflict_room_labels",
            {"room_id": room_id, "labels": sorted(norm_labels)},
            digest_chars=16,
        )
        return SemanticConflictRecord(
            conflict_id=cid,
            conflict_kind=CONFLICT_KIND_ROOM_LABEL_CONFLICT,
            subject_id=room_id,
            status=EvidenceResolutionStatus.CONFLICT,
            description=f"Conflicting functional room labels for space {room_id}: {lbl_str}",
            sources=tuple(sources or ["plan_text"]),
            suggested_action="flag_review_required",
        )

    # 2. Check contradictory area claims (>5% discrepancy)
    if areas_m2 and len(areas_m2) >= 2:
        valid_areas = [a for a in areas_m2 if a is not None and math.isfinite(a) and a > 0]
        if len(valid_areas) >= 2:
            min_a, max_a = min(valid_areas), max(valid_areas)
            if min_a > 0 and (max_a - min_a) / min_a > 0.05:
                cid = stable_contract_id(
                    "conflict_room_areas",
                    {"room_id": room_id, "areas": valid_areas},
                    digest_chars=16,
                )
                return SemanticConflictRecord(
                    conflict_id=cid,
                    conflict_kind=CONFLICT_KIND_ROOM_LABEL_CONFLICT,
                    subject_id=room_id,
                    status=EvidenceResolutionStatus.CONFLICT,
                    description=f"Contradictory room area claims for space {room_id}: {min_a} m² vs {max_a} m²",
                    sources=tuple(sources or ["plan_schedule_discrepancy"]),
                    suggested_action="flag_review_required",
                )

    return None


def check_schedule_vs_drawing_mismatch(
    schedule_spec: Dict[str, Any],
    drawing_spec: Dict[str, Any],
    subject_id: str = "",
) -> Optional[SemanticConflictRecord]:
    """Detect when schedule attributes contradict drawing observations beyond tolerance."""
    sched_w = float(schedule_spec.get("width_mm") or (float(schedule_spec.get("width_m") or 0) * 1000))
    draw_w = float(drawing_spec.get("width_mm") or (float(drawing_spec.get("width_m") or 0) * 1000))

    if sched_w > 0 and draw_w > 0:
        delta = abs(sched_w - draw_w)
        if delta / sched_w > 0.05:
            cid = stable_contract_id(
                "conflict_schedule_drawing",
                {"subject_id": subject_id, "sched_w": sched_w, "draw_w": draw_w},
                digest_chars=16,
            )
            return SemanticConflictRecord(
                conflict_id=cid,
                conflict_kind=CONFLICT_KIND_SCHEDULE_DRAWING_MISMATCH,
                subject_id=subject_id or "opening",
                status=EvidenceResolutionStatus.CONFLICT,
                description=(
                    f"Schedule vs drawing width mismatch for {subject_id}: "
                    f"schedule claims {sched_w:.0f}mm, drawing shows {draw_w:.0f}mm (delta {delta:.0f}mm)"
                ),
                sources=("opening_schedule", "drawing_plan"),
                suggested_action="flag_review_required",
            )

    sched_family = _norm_token(schedule_spec.get("family"))
    draw_family = _norm_token(drawing_spec.get("family"))
    if sched_family and draw_family and sched_family != draw_family:
        cid = stable_contract_id(
            "conflict_schedule_drawing_family",
            {"subject_id": subject_id, "sched_fam": sched_family, "draw_fam": draw_family},
            digest_chars=16,
        )
        return SemanticConflictRecord(
            conflict_id=cid,
            conflict_kind=CONFLICT_KIND_SCHEDULE_DRAWING_MISMATCH,
            subject_id=subject_id or "opening",
            status=EvidenceResolutionStatus.CONFLICT,
            description=f"Schedule family '{sched_family}' contradicts drawing family '{draw_family}' for {subject_id}",
            sources=("opening_schedule", "drawing_plan"),
            suggested_action="flag_review_required",
        )

    return None


def check_opening_definition_mismatch(
    detail_spec: Dict[str, Any],
    schedule_spec: Dict[str, Any],
    opening_id: str = "",
) -> Optional[SemanticConflictRecord]:
    """Detect opening definition discrepancies between detail definitions and schedule."""
    det_fam = _norm_token(detail_spec.get("family"))
    sched_fam = _norm_token(schedule_spec.get("family"))

    if det_fam and sched_fam and det_fam != sched_fam:
        cid = stable_contract_id(
            "conflict_opening_detail_family",
            {"opening_id": opening_id, "det": det_fam, "sched": sched_fam},
            digest_chars=16,
        )
        return SemanticConflictRecord(
            conflict_id=cid,
            conflict_kind=CONFLICT_KIND_OPENING_DEFINITION_MISMATCH,
            subject_id=opening_id or "opening_detail",
            status=EvidenceResolutionStatus.CONFLICT,
            description=f"Opening detail family '{det_fam}' contradicts schedule family '{sched_fam}'",
            sources=("detail_definition", "schedule"),
            suggested_action="flag_review_required",
        )

    det_w = float(detail_spec.get("width_mm") or 0)
    sched_w = float(schedule_spec.get("width_mm") or 0)
    if det_w > 0 and sched_w > 0 and abs(det_w - sched_w) / sched_w > 0.05:
        cid = stable_contract_id(
            "conflict_opening_detail_width",
            {"opening_id": opening_id, "det_w": det_w, "sched_w": sched_w},
            digest_chars=16,
        )
        return SemanticConflictRecord(
            conflict_id=cid,
            conflict_kind=CONFLICT_KIND_OPENING_DEFINITION_MISMATCH,
            subject_id=opening_id or "opening_detail",
            status=EvidenceResolutionStatus.CONFLICT,
            description=f"Detail width {det_w:.0f}mm disagrees with schedule width {sched_w:.0f}mm",
            sources=("detail_definition", "schedule"),
            suggested_action="flag_review_required",
        )

    return None


def check_incompatible_wall_classifications(
    classifications: Sequence[str],
    wall_id: str = "",
    sources: Optional[Sequence[str]] = None,
) -> Optional[SemanticConflictRecord]:
    """Detect contradictory wall role classifications (e.g. external facade vs internal partition)."""
    norm_classes = {_norm_token(c) for c in classifications if _norm_token(c)}

    has_external = any(
        any(token in c for token in ("external", "facade", "exterior"))
        for c in norm_classes
    )
    has_internal = any(
        any(token in c for token in ("internal", "partition", "interior"))
        for c in norm_classes
    )

    if has_external and has_internal:
        cid = stable_contract_id(
            "conflict_wall_classification",
            {"wall_id": wall_id, "classifications": sorted(norm_classes)},
            digest_chars=16,
        )
        return SemanticConflictRecord(
            conflict_id=cid,
            conflict_kind=CONFLICT_KIND_INCOMPATIBLE_WALL_CLASSIFICATION,
            subject_id=wall_id or "wall",
            status=EvidenceResolutionStatus.CONFLICT,
            description=(
                f"Contradictory wall classifications for {wall_id}: "
                f"classified as both external facade and internal partition"
            ),
            sources=tuple(sources or ["wall_role_authority", "elevation_mapping"]),
            suggested_action="abstain_from_commercial_row",
        )

    return None


def _runtime_field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _runtime_status(value: Any) -> str:
    status = _runtime_field(value, "status", "")
    return str(getattr(status, "value", status) or "").strip().lower()


def _coerce_explicit_conflict(value: Any) -> Optional[SemanticConflictRecord]:
    if isinstance(value, SemanticConflictRecord):
        return value
    if not isinstance(value, Mapping):
        return None
    try:
        status_raw = value.get("status", EvidenceResolutionStatus.CONFLICT.value)
        status = (
            status_raw
            if isinstance(status_raw, EvidenceResolutionStatus)
            else EvidenceResolutionStatus(str(status_raw).strip().lower())
        )
        return SemanticConflictRecord(
            conflict_id=str(value["conflict_id"]),
            conflict_kind=str(value["conflict_kind"]),
            subject_id=str(value.get("subject_id") or ""),
            status=status,
            description=str(value["description"]),
            sources=tuple(str(item) for item in value.get("sources", ()) if str(item)),
            suggested_action=str(value.get("suggested_action") or "flag_review_required"),
            schema_version=str(
                value.get("schema_version") or SEMANTIC_CONFLICT_GUARD_SCHEMA_VERSION
            ),
        )
    except Exception:
        return None


def collect_runtime_semantic_conflicts(
    app: Any,
    *,
    finishes: Optional[Sequence[Any]] = None,
) -> List[SemanticConflictRecord]:
    """Collect identity-proven semantic conflicts available in customer runtime.

    No proximity, count, page-neighbourhood, or benchmark truth is used. The
    collector consumes source-bound finish records sharing the exact same
    physical face id and opening detail definitions bound to an existing
    opening mark or semantic id. Already-structured explicit conflicts are also
    retained when valid.
    """
    collected: List[SemanticConflictRecord] = []

    for raw in getattr(app, "detected_semantic_conflicts", ()) or ():
        conflict = _coerce_explicit_conflict(raw)
        if conflict is not None:
            collected.append(conflict)

    finish_records: List[Any] = list(finishes or ())
    if not finish_records:
        finish_records.extend(
            getattr(app, "source_bound_wall_finish_records", ()) or ()
        )

    by_face: Dict[str, List[Any]] = {}
    for record in finish_records:
        status = _runtime_status(record)
        if status and status != EvidenceResolutionStatus.CORROBORATED.value:
            continue
        material = str(_runtime_field(record, "finish_material", "") or "").strip()
        faces = _runtime_field(record, "physical_face_ids", ()) or ()
        if not material or not isinstance(faces, (list, tuple, set, frozenset)):
            continue
        for face_id in faces:
            face = str(face_id or "").strip()
            if face:
                by_face.setdefault(face, []).append(record)

    for face_id, records in sorted(by_face.items()):
        materials = [
            str(_runtime_field(record, "finish_material", "") or "").strip()
            for record in records
        ]
        sources = []
        for record in records:
            record_id = str(_runtime_field(record, "record_id", "") or "").strip()
            if record_id:
                sources.append(f"bound_wall_finish:{record_id}")
        conflict = check_incompatible_material_identities(
            materials,
            subject_id=face_id,
            sources=tuple(dict.fromkeys(sources)),
        )
        if conflict is not None:
            collected.append(conflict)

    details = getattr(app, "opening_detail_definitions", ()) or ()
    openings = getattr(app, "building_openings", ()) or ()
    mark_map = getattr(app, "opening_mark_map", {}) or {}

    details_by_record: Dict[str, Any] = {}
    details_by_semantic: Dict[str, Any] = {}
    for detail in details:
        status = _runtime_status(detail)
        if status and status != EvidenceResolutionStatus.CORROBORATED.value:
            continue
        record_id = str(_runtime_field(detail, "record_id", "") or "").strip()
        semantic_id = str(
            _runtime_field(detail, "semantic_identity_id", "") or ""
        ).strip()
        if record_id:
            details_by_record[record_id] = detail
        if semantic_id:
            details_by_semantic[semantic_id] = detail

    for opening in openings:
        if not isinstance(opening, Mapping):
            continue
        mark = str(
            opening.get("type_mark")
            or opening.get("mark")
            or opening.get("opening_tag")
            or ""
        ).strip().upper()
        opening_id = str(opening.get("opening_id") or opening.get("id") or "").strip()
        detail = None
        detail_record_id = str(opening.get("detail_record_id") or "").strip()
        detail_semantic_id = str(
            opening.get("detail_semantic_identity_id") or ""
        ).strip()
        if detail_record_id:
            detail = details_by_record.get(detail_record_id)
        if detail is None and detail_semantic_id:
            detail = details_by_semantic.get(detail_semantic_id)
        if detail is None and mark and isinstance(mark_map, Mapping):
            mapped = str(mark_map.get(mark) or mark_map.get(mark.lower()) or "").strip()
            if mapped:
                detail = details_by_semantic.get(mapped)
        if detail is None:
            continue

        observed_width_mm = 0.0
        try:
            if opening.get("width_mm") is not None:
                observed_width_mm = float(opening.get("width_mm") or 0.0)
            elif opening.get("width_m") is not None:
                observed_width_mm = float(opening.get("width_m") or 0.0) * 1000.0
        except (TypeError, ValueError, OverflowError):
            observed_width_mm = 0.0

        observed_family = _norm_token(opening.get("family"))
        if observed_family in {"", "opening", "unknown", "unresolved"}:
            observed_family = ""

        detail_spec = {
            "family": _runtime_field(detail, "family", ""),
            "width_mm": _runtime_field(detail, "width_mm", 0.0),
        }
        observed_spec = {
            "family": observed_family,
            "width_mm": observed_width_mm,
        }
        if not observed_family and observed_width_mm <= 0.0:
            continue

        conflict = check_opening_definition_mismatch(
            detail_spec,
            observed_spec,
            opening_id=mark or opening_id,
        )
        if conflict is not None:
            detail_id = str(_runtime_field(detail, "record_id", "") or "").strip()
            evidence_ids = opening.get("source_evidence_ids", ()) or ()
            sources = tuple(
                item
                for item in (
                    f"opening_detail:{detail_id}" if detail_id else "",
                    *(str(eid) for eid in evidence_ids),
                )
                if item
            )
            collected.append(
                SemanticConflictRecord(
                    conflict_id=conflict.conflict_id,
                    conflict_kind=conflict.conflict_kind,
                    subject_id=conflict.subject_id,
                    status=conflict.status,
                    description=conflict.description,
                    sources=sources or conflict.sources,
                    suggested_action=conflict.suggested_action,
                )
            )

    unique: Dict[str, SemanticConflictRecord] = {}
    for conflict in collected:
        unique.setdefault(conflict.conflict_id, conflict)
    return [unique[key] for key in sorted(unique)]


def _conflict_matches_row(
    conflict: SemanticConflictRecord,
    row: Mapping[str, Any],
) -> bool:
    subject = str(conflict.subject_id or "").strip().lower()
    location = str(row.get("location") or "").lower()
    notes = str(row.get("notes") or "").lower()
    source_reference = str(row.get("source_reference") or "").lower()

    if subject and (
        subject in location or subject in notes or subject in source_reference
    ):
        return True

    for source in conflict.sources:
        token = str(source or "").strip().lower()
        if (
            token
            and (
                token.startswith("bound_wall_finish:")
                or token.startswith("opening_detail:")
            )
            and token in source_reference
        ):
            return True
    return False


def annotate_rows_with_conflicts(
    rows: List[Tuple[Any, ...]],
    conflicts: Sequence[SemanticConflictRecord],
) -> List[Tuple[Any, ...]]:
    """Annotate affected canonical takeoff rows without altering quantities.

    Field access is by the shared takeoff-row contract, never by hard-coded
    positional indices. Conflicts escalate quantity_status to Review and append
    structured provenance to notes; all numerical values are preserved.
    """
    if not conflicts or not rows:
        return rows

    valid_conflicts = [
        conflict
        for conflict in conflicts
        if isinstance(conflict, SemanticConflictRecord)
    ]
    if not valid_conflicts:
        return rows

    updated_rows: List[Tuple[Any, ...]] = []
    for values in rows:
        named = takeoff_contract.mapping_from_values(
            values,
            takeoff_contract.CORE_FIELDS,
        )
        matched = [
            conflict
            for conflict in valid_conflicts
            if _conflict_matches_row(conflict, named)
        ]
        if matched:
            existing_notes = str(named.get("notes") or "")
            additions = []
            for conflict in matched:
                source_text = ", ".join(conflict.sources)
                addition = (
                    f"[SEMANTIC CONFLICT: {conflict.description} "
                    f"| id={conflict.conflict_id} "
                    f"| kind={conflict.conflict_kind}"
                    f"{' | sources=' + source_text if source_text else ''}]"
                )
                if addition not in existing_notes:
                    additions.append(addition)
            if additions:
                named["notes"] = " ".join(
                    part for part in (existing_notes, *additions) if part
                )
            if str(named.get("quantity_status") or "") not in ("Manual", "Excluded"):
                named["quantity_status"] = "Review"

        updated_rows.append(
            takeoff_contract.values_from_mapping(
                named,
                takeoff_contract.CORE_FIELDS,
            )
        )

    return updated_rows


__all__ = [
    "CONFLICT_KIND_INCOMPATIBLE_MATERIALS",
    "CONFLICT_KIND_INCOMPATIBLE_WALL_CLASSIFICATION",
    "CONFLICT_KIND_OPENING_DEFINITION_MISMATCH",
    "CONFLICT_KIND_ROOM_LABEL_CONFLICT",
    "CONFLICT_KIND_SCHEDULE_DRAWING_MISMATCH",
    "SEMANTIC_CONFLICT_GUARD_SCHEMA_VERSION",
    "SemanticConflictRecord",
    "annotate_rows_with_conflicts",
    "collect_runtime_semantic_conflicts",
    "check_incompatible_material_identities",
    "check_incompatible_wall_classifications",
    "check_opening_definition_mismatch",
    "check_room_label_conflict",
    "check_schedule_vs_drawing_mismatch",
]
