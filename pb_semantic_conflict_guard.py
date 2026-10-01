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


def annotate_rows_with_conflicts(
    rows: List[Tuple[Any, ...]],
    conflicts: Sequence[SemanticConflictRecord],
) -> List[Tuple[Any, ...]]:
    """Annotate takeoff rows affected by semantic conflicts without altering quantities.

    Preserves atomic 21-field contract while appending conflict provenance into notes.
    """
    if not conflicts or not rows:
        return rows

    conflicts_by_subject: Dict[str, List[SemanticConflictRecord]] = {}
    for c in conflicts:
        conflicts_by_subject.setdefault(c.subject_id.lower(), []).append(c)

    updated_rows: List[Tuple[Any, ...]] = []
    for r in rows:
        r_list = list(r)
        # In canonical 21-field takeoff row: index 13 = notes, index 8 = quantity_status, index 3 = location
        location = str(r_list[3] if len(r_list) > 3 else "").lower()
        notes = str(r_list[13] if len(r_list) > 13 else "")

        matched_conflicts = []
        for sub_id, clist in conflicts_by_subject.items():
            if sub_id and sub_id in location or sub_id in notes.lower():
                matched_conflicts.extend(clist)

        if matched_conflicts:
            conflict_notes = "; ".join(f"[SEMANTIC CONFLICT: {c.description}]" for c in matched_conflicts)
            new_notes = f"{notes} {conflict_notes}".strip() if notes else conflict_notes
            if len(r_list) > 13:
                r_list[13] = new_notes
            if len(r_list) > 8 and str(r_list[8]) not in ("Manual", "Excluded"):
                r_list[8] = "Review"

        updated_rows.append(tuple(r_list))

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
    "check_incompatible_material_identities",
    "check_incompatible_wall_classifications",
    "check_opening_definition_mismatch",
    "check_room_label_conflict",
    "check_schedule_vs_drawing_mismatch",
]
