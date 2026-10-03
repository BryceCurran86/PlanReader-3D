"""Opening Detail Definition Authority customer-runtime bridge (AG-06).

Consumes `OpeningDetailDefinitionRecord` from `pb_opening_detail_definition_authority.py`
and enriches physical opening objects hosted on physical walls in the customer building model.

Target Relationship:
  opening mark/tag -> schedule/detail definition -> physical opening -> host wall -> deduction -> quantity/3D

Core Invariants:
1. Schedule and detail definitions describe opening TYPES, not physical instances.
2. Multiple appearances of the same opening across plan, elevation, schedule, and detail
   are consolidated into a SINGLE physical opening on its host wall.
3. Detail definitions enrich opening dimensions (width, height, area), family, subtype,
   and material with immutable provenance.
4. Each consolidated physical opening deducts from its host wall's gross area exactly ONCE.
5. No speculative openings or duplicate deductions are created.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_opening_detail_definition_authority import (
    OpeningDetailDefinitionRecord,
)
from pb_opening_schedule_v171 import ScheduleEntry


@dataclass
class ConsolidatedPhysicalOpening:
    """Consolidated physical opening object hosted on an authenticated physical wall."""
    opening_id: str
    type_mark: str
    host_wall_id: str
    width_m: float
    height_m: float
    area_m2: float
    family: str = "opening"
    subtype: str = ""
    material: str = ""
    deducts: bool = True
    detail_record_id: Optional[str] = None
    detail_semantic_identity_id: Optional[str] = None
    plan_page_id: Optional[str] = None
    elevation_page_id: Optional[str] = None
    schedule_page_id: Optional[str] = None
    detail_page_id: Optional[str] = None
    source_evidence_ids: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not math.isfinite(self.width_m) or self.width_m < 0.0:
            raise ValueError("width_m must be a finite non-negative number")
        if not math.isfinite(self.height_m) or self.height_m < 0.0:
            raise ValueError("height_m must be a finite non-negative number")
        if not math.isfinite(self.area_m2) or self.area_m2 < 0.0:
            raise ValueError("area_m2 must be a finite non-negative number")
        self.source_evidence_ids = sorted(
            {
                str(value).strip()
                for value in self.source_evidence_ids
                if str(value).strip()
            }
        )


def detail_definition_to_schedule_entry(
    record: OpeningDetailDefinitionRecord,
    type_mark: str = "",
) -> ScheduleEntry:
    """Convert an OpeningDetailDefinitionRecord into a ScheduleEntry."""
    if type(record) is not OpeningDetailDefinitionRecord:
        raise TypeError("record must be OpeningDetailDefinitionRecord")

    mark = type_mark or f"{record.family[0].upper()}_{record.width_mm}x{record.height_mm}"
    desc_parts = [p for p in (record.material, record.subtype, record.family) if p]
    desc = " ".join(desc_parts)

    page_no = int(record.page_id) if str(record.page_id).isdigit() else 0
    return ScheduleEntry(
        type_mark=mark,
        width_mm=record.width_mm,
        height_mm=record.height_mm,
        description=desc,
        count=1,
        count_explicit=False,
        page_no=page_no,
        bbox=record.source_bbox,
        parse_source=f"opening_detail_definition:{record.record_id}",
        dimension_basis=record.dimension_basis,
    )


def _explicit_physical_opening_id(raw: Mapping[str, Any]) -> str:
    """Return only an existing producer/canonical physical identity.

    A type mark or host wall is classification/relationship evidence, not an
    instance identity. Never synthesize a physical identity from those fields.
    """
    for field_name in (
        "physical_opening_id",
        "canonical_opening_id",
        "opening_id",
    ):
        value = str(raw.get(field_name) or "").strip()
        if value:
            return value
    return ""


def _one_consistent_text(
    items: Sequence[Mapping[str, Any]],
    keys: Sequence[str],
    *,
    default: str = "",
) -> str:
    values = {
        str(item.get(key) or "").strip()
        for item in items
        for key in keys
        if str(item.get(key) or "").strip()
    }
    if len(values) > 1:
        raise ValueError(
            "conflicting observations for one physical opening identity: "
            + ", ".join(sorted(values))
        )
    return next(iter(values), default)


def _one_consistent_positive_float(
    items: Sequence[Mapping[str, Any]],
    key: str,
) -> float:
    values: set[float] = set()
    for item in items:
        raw = item.get(key)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError, OverflowError):
            continue
        if math.isfinite(value) and value > 0.0:
            values.add(value)
    if len(values) > 1:
        raise ValueError(
            f"conflicting {key} observations for one physical opening identity"
        )
    return next(iter(values), 0.0)


def consolidate_opening_identities(
    raw_openings: Sequence[Dict[str, Any]],
) -> List[ConsolidatedPhysicalOpening]:
    """Merge observations only when they share one explicit physical identity.

    Wall, type mark, geometry and schedule type describe an opening but cannot
    prove two observations are the same physical instance. Observations with no
    producer/canonical physical identity therefore remain outside this
    customer-deduction bridge rather than being collapsed or double-counted.
    """

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for raw in raw_openings:
        if not isinstance(raw, Mapping):
            continue
        opening_id = _explicit_physical_opening_id(raw)
        if not opening_id:
            continue
        grouped.setdefault(opening_id, []).append(dict(raw))

    consolidated: List[ConsolidatedPhysicalOpening] = []
    for opening_id in sorted(grouped):
        items = grouped[opening_id]

        wall_id = _one_consistent_text(
            items,
            ("host_wall_id", "wall_ref", "wall_id"),
        )
        mark = _one_consistent_text(
            items,
            ("type_mark", "mark", "opening_tag"),
        ).upper()

        width_m = _one_consistent_positive_float(items, "width_m")
        height_m = _one_consistent_positive_float(items, "height_m")
        explicit_area_m2 = _one_consistent_positive_float(items, "area_m2")

        family_values = {
            str(item.get("family") or "").strip()
            for item in items
            if str(item.get("family") or "").strip()
            and str(item.get("family") or "").strip() != "opening"
        }
        if len(family_values) > 1:
            raise ValueError(
                "conflicting family observations for one physical opening identity"
            )
        family = next(iter(family_values), "opening")

        subtype = _one_consistent_text(items, ("subtype",))
        material = _one_consistent_text(items, ("material",))
        detail_rec_id = _one_consistent_text(items, ("detail_record_id",)) or None
        detail_sem_id = (
            _one_consistent_text(items, ("detail_semantic_identity_id",)) or None
        )
        plan_p = _one_consistent_text(items, ("plan_page_id",)) or None
        elev_p = _one_consistent_text(items, ("elevation_page_id",)) or None
        sched_p = _one_consistent_text(items, ("schedule_page_id",)) or None
        det_p = _one_consistent_text(items, ("detail_page_id",)) or None

        evidence_ids = sorted(
            {
                str(eid).strip()
                for item in items
                for eid in (item.get("source_evidence_ids") or ())
                if str(eid).strip()
            }
        )

        if width_m > 0.0 and height_m > 0.0:
            area_m2 = round(width_m * height_m, 4)
        else:
            area_m2 = explicit_area_m2

        consolidated.append(
            ConsolidatedPhysicalOpening(
                opening_id=opening_id,
                type_mark=mark,
                host_wall_id=wall_id,
                width_m=width_m,
                height_m=height_m,
                area_m2=area_m2,
                family=family,
                subtype=subtype,
                material=material,
                deducts=True,
                detail_record_id=detail_rec_id,
                detail_semantic_identity_id=detail_sem_id,
                plan_page_id=plan_p,
                elevation_page_id=elev_p,
                schedule_page_id=sched_p,
                detail_page_id=det_p,
                source_evidence_ids=evidence_ids,
            )
        )

    return consolidated

def enrich_openings_with_detail_definitions(
    openings: Sequence[ConsolidatedPhysicalOpening | Dict[str, Any]],
    detail_records: Sequence[OpeningDetailDefinitionRecord],
    mark_to_semantic_identity: Optional[Mapping[str, str]] = None,
) -> List[ConsolidatedPhysicalOpening]:
    """Enrich physical openings with verified width, height, family, subtype, material from detail definitions."""
    details_by_id: Dict[str, OpeningDetailDefinitionRecord] = {
        r.record_id: r for r in detail_records if isinstance(r, OpeningDetailDefinitionRecord)
    }
    details_by_sem_id: Dict[str, OpeningDetailDefinitionRecord] = {
        r.semantic_identity_id: r for r in detail_records if isinstance(r, OpeningDetailDefinitionRecord)
    }

    mark_map = dict(mark_to_semantic_identity or {})

    enriched: List[ConsolidatedPhysicalOpening] = []

    for op in openings:
        if isinstance(op, ConsolidatedPhysicalOpening):
            op_dict = {
                "opening_id": op.opening_id,
                "type_mark": op.type_mark,
                "host_wall_id": op.host_wall_id,
                "width_m": op.width_m,
                "height_m": op.height_m,
                "area_m2": op.area_m2,
                "family": op.family,
                "subtype": op.subtype,
                "material": op.material,
                "deducts": op.deducts,
                "detail_record_id": op.detail_record_id,
                "detail_semantic_identity_id": op.detail_semantic_identity_id,
                "plan_page_id": op.plan_page_id,
                "elevation_page_id": op.elevation_page_id,
                "schedule_page_id": op.schedule_page_id,
                "detail_page_id": op.detail_page_id,
                "source_evidence_ids": list(op.source_evidence_ids),
            }
        else:
            op_dict = dict(op)

        mark = str(op_dict.get("type_mark") or "").strip().upper()

        matched_detail: Optional[OpeningDetailDefinitionRecord] = None

        # 1. Match by explicit detail_record_id
        if op_dict.get("detail_record_id") and op_dict["detail_record_id"] in details_by_id:
            matched_detail = details_by_id[op_dict["detail_record_id"]]

        # 2. Match by semantic identity via mark map
        elif mark and mark in mark_map and mark_map[mark] in details_by_sem_id:
            matched_detail = details_by_sem_id[mark_map[mark]]

        # 3. Match by semantic identity directly
        elif op_dict.get("detail_semantic_identity_id") in details_by_sem_id:
            matched_detail = details_by_sem_id[op_dict["detail_semantic_identity_id"]]

        if matched_detail is not None:
            w_m = round(matched_detail.width_mm / 1000.0, 4)
            h_m = round(matched_detail.height_mm / 1000.0, 4)
            area_m = round(w_m * h_m, 4)

            op_dict["width_m"] = w_m
            op_dict["height_m"] = h_m
            op_dict["area_m2"] = area_m
            op_dict["family"] = matched_detail.family
            op_dict["subtype"] = matched_detail.subtype
            op_dict["material"] = matched_detail.material
            op_dict["detail_record_id"] = matched_detail.record_id
            op_dict["detail_semantic_identity_id"] = matched_detail.semantic_identity_id
            op_dict["detail_page_id"] = matched_detail.page_id
            ev_list = op_dict.setdefault("source_evidence_ids", [])
            for oid in matched_detail.source_observation_ids:
                if oid not in ev_list:
                    ev_list.append(oid)

        enriched.append(
            ConsolidatedPhysicalOpening(
                opening_id=str(op_dict["opening_id"]),
                type_mark=str(op_dict.get("type_mark") or ""),
                host_wall_id=str(op_dict.get("host_wall_id") or ""),
                width_m=float(op_dict.get("width_m") or 0.0),
                height_m=float(op_dict.get("height_m") or 0.0),
                area_m2=float(op_dict.get("area_m2") or 0.0),
                family=str(op_dict.get("family") or "opening"),
                subtype=str(op_dict.get("subtype") or ""),
                material=str(op_dict.get("material") or ""),
                deducts=bool(op_dict.get("deducts", True)),
                detail_record_id=op_dict.get("detail_record_id"),
                detail_semantic_identity_id=op_dict.get("detail_semantic_identity_id"),
                plan_page_id=op_dict.get("plan_page_id"),
                elevation_page_id=op_dict.get("elevation_page_id"),
                schedule_page_id=op_dict.get("schedule_page_id"),
                detail_page_id=op_dict.get("detail_page_id"),
                source_evidence_ids=op_dict.get("source_evidence_ids", []),
            )
        )

    return enriched


def apply_opening_deductions_to_walls(
    walls: Sequence[Dict[str, Any]],
    consolidated_openings: Sequence[ConsolidatedPhysicalOpening],
) -> List[Dict[str, Any]]:
    """Apply consolidated opening deductions to host walls exactly once.

    Invariants:
    1. Each consolidated opening deducts only from its designated host wall.
    2. Net wall area = max(0.0, gross_m2 - total_opening_deduction_m2).
    3. Multiple cross-sheet references to the same opening deduct only ONCE.
    """
    deductions_by_wall: Dict[str, float] = {}
    openings_by_wall: Dict[str, List[str]] = {}

    for op in consolidated_openings:
        if not op.deducts or not op.host_wall_id or op.area_m2 <= 0.0:
            continue
        deductions_by_wall[op.host_wall_id] = round(
            deductions_by_wall.get(op.host_wall_id, 0.0) + op.area_m2, 4
        )
        openings_by_wall.setdefault(op.host_wall_id, []).append(op.opening_id)

    updated_walls: List[Dict[str, Any]] = []

    for w in walls:
        wall_dict = dict(w)
        wid = str(wall_dict.get("wall_ref") or wall_dict.get("id") or wall_dict.get("wall_id") or "")

        gross_m2 = float(wall_dict.get("gross_m2") or 0.0)
        ded_m2 = deductions_by_wall.get(wid, float(wall_dict.get("opening_deduction_m2") or 0.0))

        net_m2 = max(0.0, round(gross_m2 - ded_m2, 4)) if gross_m2 > 0.0 else float(wall_dict.get("net_m2") or 0.0)

        wall_dict["opening_deduction_m2"] = ded_m2
        wall_dict["net_m2"] = net_m2
        if wid in openings_by_wall:
            wall_dict["consolidated_opening_ids"] = openings_by_wall[wid]

        updated_walls.append(wall_dict)

    return updated_walls


__all__ = [
    "ConsolidatedPhysicalOpening",
    "apply_opening_deductions_to_walls",
    "consolidate_opening_identities",
    "detail_definition_to_schedule_entry",
    "enrich_openings_with_detail_definitions",
]
