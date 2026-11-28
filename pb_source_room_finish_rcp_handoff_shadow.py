"""Order 7 (MAX #7159430612): Generic room/finish/RCP cross-view source evidence handoff shadow.

Consolidates:
1. Room legend number-to-name & bubble-to-polygon linkage (`#4730`)
2. Green-hatch ordinary-finish exclusion + epoxy/coldroom specialty linkage (`#4731`)
3. RCP ceiling material/height bubble association preserving distinct heights (`#4739`)
4. Generic typed cross-view room-to-RCP ceiling witness addressing Gap C
   (`CrossViewCeilingFinishProducer` returning 0 when room name & RCP ceiling
   bubble sit in different PyMuPDF text blocks), with ZERO named-job production
   rules.

Default-off shadow handoff only (`commercial_authority_granted=False`,
`issuer_wiring_owned_by="MAX"`). Never edits MAX issuer/export code.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Sequence

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_green_exclusion_epoxy_linkage_shadow import (
    FinishLegendDefinitionInput,
    FloorExclusionRoomCandidate,
    FloorFinishLabelObservation,
    link_green_exclusions_and_epoxy_labels,
)
from pb_source_green_hatch_room_exclusion import SourceGreenHatchRoomWitness
from pb_source_rcp_bubble_height_material_shadow import (
    RcpCeilingZonePolygon,
    RcpMaterialHeightBubble,
    associate_rcp_bubbles_to_ceiling_zones_shadow,
)
from pb_source_room_legend_linkage_shadow import (
    PhysicalRoomFaceCandidate,
    RoomLegendTableRowInput,
    RoomNumberBubbleCandidate,
    link_room_legend_to_physical_rooms,
    parse_room_legend_rows,
)


def _clean(value: object) -> str:
    return str(value or "").strip()


def _norm_label(value: object) -> str:
    return " ".join(_clean(value).upper().split())


def _canonical_sha(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class CrossViewRoomCeilingLinkInput:
    """Explicit source-owned room polygon metadata for generic floor-plan -> RCP pairing."""

    physical_room_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    floor_plan_page_id: str
    floor_plan_viewport_id: str
    canonical_floor_id: str | None = None
    explicit_room_label: str | None = None
    rcp_zone_id: str | None = None


@dataclass(frozen=True)
class TypedCrossViewRoomFinishRcpRecord:
    """Consumer-ready generic room/finish/RCP source evidence record for MAX issuer wiring."""

    record_id: str
    physical_room_id: str
    resolved_room_name: str | None
    room_name_source: str | None  # "room_legend_bubble" | "explicit_plan_label"
    green_hatch_ordinary_excluded: bool
    green_exclusion_classification: str | None
    specialty_finish_codes: tuple[str, ...]
    rcp_zone_id: str | None
    rcp_material_code: str | None
    rcp_ceiling_height_mm: int | None
    rcp_raked_height_range_mm: tuple[int, int] | None
    cross_view_ceiling_ready: bool
    blocking_reasons: tuple[str, ...]
    issuer_wiring_owned_by: str = "MAX"
    commercial_authority_granted: bool = False
    shadow_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "physical_room_id": self.physical_room_id,
            "resolved_room_name": self.resolved_room_name,
            "room_name_source": self.room_name_source,
            "green_hatch_ordinary_excluded": self.green_hatch_ordinary_excluded,
            "green_exclusion_classification": self.green_exclusion_classification,
            "specialty_finish_codes": list(self.specialty_finish_codes),
            "rcp_zone_id": self.rcp_zone_id,
            "rcp_material_code": self.rcp_material_code,
            "rcp_ceiling_height_mm": self.rcp_ceiling_height_mm,
            "rcp_raked_height_range_mm": (
                list(self.rcp_raked_height_range_mm) if self.rcp_raked_height_range_mm else None
            ),
            "cross_view_ceiling_ready": self.cross_view_ceiling_ready,
            "blocking_reasons": list(self.blocking_reasons),
            "issuer_wiring_owned_by": "MAX",
            "commercial_authority_granted": False,
            "shadow_only": True,
        }


@dataclass(frozen=True)
class RoomFinishRcpHandoffPacket:
    packet_id: str
    records: tuple[TypedCrossViewRoomFinishRcpRecord, ...]
    distinct_ceiling_heights_preserved_mm: tuple[int, ...]
    green_excluded_room_count: int
    cross_view_ceiling_ready_count: int
    explicit_distinct_heights_preserved: bool = True
    commercial_authority_granted: bool = False
    shadow_only: bool = True
    digest_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "records": [r.to_dict() for r in self.records],
            "distinct_ceiling_heights_preserved_mm": list(self.distinct_ceiling_heights_preserved_mm),
            "green_excluded_room_count": self.green_excluded_room_count,
            "cross_view_ceiling_ready_count": self.cross_view_ceiling_ready_count,
            "explicit_distinct_heights_preserved": True,
            "commercial_authority_granted": False,
            "shadow_only": True,
            "digest_sha256": self.digest_sha256,
        }


def assemble_room_finish_rcp_handoff_shadow(
    *,
    rooms: Sequence[CrossViewRoomCeilingLinkInput],
    legend_rows: Sequence[RoomLegendTableRowInput] = (),
    room_faces: Sequence[PhysicalRoomFaceCandidate] = (),
    room_number_bubbles: Sequence[RoomNumberBubbleCandidate] = (),
    exclusion_room_candidates: Sequence[FloorExclusionRoomCandidate] = (),
    green_hatch_witnesses: Sequence[SourceGreenHatchRoomWitness] = (),
    floor_finish_label_observations: Sequence[FloorFinishLabelObservation] = (),
    finish_legend_definitions: Sequence[FinishLegendDefinitionInput] = (),
    rcp_zones: Sequence[RcpCeilingZonePolygon] = (),
    rcp_bubbles: Sequence[RcpMaterialHeightBubble] = (),
    rcp_zone_label_by_id: dict[str, str] | None = None,
) -> RoomFinishRcpHandoffPacket:
    """Assemble generic typed room/finish/RCP source evidence addressing Gap C."""
    # 1. Room legend linkage (numbered bubbles -> legend room names)
    legend_by_room: dict[str, str] = {}
    if legend_rows and room_faces and room_number_bubbles:
        parsed_legend = parse_room_legend_rows(legend_rows)
        leg_report = link_room_legend_to_physical_rooms(
            legend_result=parsed_legend,
            room_faces=room_faces,
            number_callouts=room_number_bubbles,
        )
        for link in leg_report.room_links:
            if link.status is EvidenceResolutionStatus.CORROBORATED and link.linked_room_name:
                legend_by_room[link.room_face_id] = link.linked_room_name

    # 2. Green hatch exclusion + specialty epoxy/coldroom linkage
    green_by_floor: dict[str, Any] = {}
    if exclusion_room_candidates and green_hatch_witnesses:
        gr_report = link_green_exclusions_and_epoxy_labels(
            rooms=exclusion_room_candidates,
            green_witnesses=green_hatch_witnesses,
            label_observations=floor_finish_label_observations,
            finish_legend_definitions=finish_legend_definitions,
        )
        for item in gr_report.room_records:
            green_by_floor[item.canonical_floor_id] = item
            green_by_floor[item.source_room_face_record_id] = item

    # 3. RCP ceiling bubble association (distinct heights strictly preserved!)
    rcp_by_zone: dict[str, Any] = {}
    rcp_zone_lineage: dict[str, tuple[str, str, str]] = {}
    distinct_heights: tuple[int, ...] = ()
    if rcp_zones:
        for z in rcp_zones:
            rcp_zone_lineage[z.zone_id] = z.lineage.normalized()[:3]
        rcp_report = associate_rcp_bubbles_to_ceiling_zones_shadow(rcp_zones, rcp_bubbles)
        distinct_heights = rcp_report.distinct_heights_preserved_mm
        for assoc in rcp_report.associations:
            rcp_by_zone[assoc.zone_id] = assoc

    zones_by_norm_label: dict[str, list[str]] = {}
    for zid, raw_lbl in (rcp_zone_label_by_id or {}).items():
        norm = _norm_label(raw_lbl)
        if norm:
            zones_by_norm_label.setdefault(norm, []).append(zid)

    out_records: list[TypedCrossViewRoomFinishRcpRecord] = []
    green_count = 0
    rcp_ready_count = 0

    for room in sorted(rooms, key=lambda r: r.physical_room_id):
        rid = _clean(room.physical_room_id)
        if not rid:
            continue
        r_rev = (_clean(room.document_id), _clean(room.revision_id), _clean(room.source_sha256).lower())
        reasons: list[str] = []

        leg_name = legend_by_room.get(rid)
        exp_name = _clean(room.explicit_room_label) or None
        if leg_name and exp_name and _norm_label(leg_name) != _norm_label(exp_name):
            resolved_name = None
            name_source = None
            reasons.append("conflicting_room_legend_and_explicit_plan_label")
        elif leg_name:
            resolved_name = leg_name
            name_source = "room_legend_bubble"
        elif exp_name:
            resolved_name = exp_name
            name_source = "explicit_plan_label"
        else:
            resolved_name = None
            name_source = None

        gr = green_by_floor.get(_clean(room.canonical_floor_id)) or green_by_floor.get(rid)
        green_excluded = bool(gr is not None and gr.ordinary_finish_exclusion_indicated)
        if green_excluded:
            green_count += 1
        gr_cls = gr.classification if gr is not None else None
        spec_codes = tuple(gr.linked_finish_codes) if gr is not None else ()

        # Generic cross-view floor-plan room -> RCP ceiling zone pairing (Gap C: decoupled from single block_no)
        paired_zone_id: str | None = None
        if _clean(room.rcp_zone_id):
            paired_zone_id = _clean(room.rcp_zone_id)
        elif resolved_name is not None:
            matches = zones_by_norm_label.get(_norm_label(resolved_name), [])
            if len(matches) == 1:
                paired_zone_id = matches[0]
            elif len(matches) > 1:
                reasons.append("ambiguous_multiple_rcp_zones_for_room_label")

        rcp_mat: str | None = None
        rcp_h: int | None = None
        rcp_raked: tuple[int, int] | None = None
        rcp_ready = False

        if paired_zone_id is None:
            reasons.append("no_cross_view_rcp_zone_paired")
        elif paired_zone_id not in rcp_by_zone:
            reasons.append("paired_rcp_zone_missing_from_rcp_report")
        elif rcp_zone_lineage.get(paired_zone_id) != r_rev:
            reasons.append("cross_revision_rcp_ceiling_pairing_rejected")
        else:
            assoc = rcp_by_zone[paired_zone_id]
            if assoc.abstained:
                reasons.extend(assoc.blocking_reasons)
            elif green_excluded:
                rcp_mat = assoc.material_code
                rcp_h = assoc.height_mm
                rcp_raked = assoc.raked_height_range_mm
                reasons.append("ordinary_ceiling_quarantined_in_green_hatched_room")
            else:
                rcp_mat = assoc.material_code
                rcp_h = assoc.height_mm
                rcp_raked = assoc.raked_height_range_mm
                if rcp_mat is None:
                    reasons.append("rcp_zone_missing_ceiling_material_code")
                else:
                    rcp_ready = True
                    rcp_ready_count += 1

        dedup = tuple(dict.fromkeys(reasons))
        rec_payload = {
            "physical_room_id": rid,
            "resolved_room_name": resolved_name,
            "green_hatch_ordinary_excluded": green_excluded,
            "green_exclusion_classification": gr_cls,
            "specialty_finish_codes": list(spec_codes),
            "rcp_zone_id": paired_zone_id,
            "rcp_material_code": rcp_mat,
            "rcp_ceiling_height_mm": rcp_h,
            "rcp_raked_height_range_mm": list(rcp_raked) if rcp_raked else None,
            "cross_view_ceiling_ready": rcp_ready,
            "blocking_reasons": list(dedup),
        }
        rec_sha = _canonical_sha(rec_payload)
        out_records.append(
            TypedCrossViewRoomFinishRcpRecord(
                record_id=f"room_finish_rcp_{rec_sha[:16]}",
                physical_room_id=rid,
                resolved_room_name=resolved_name,
                room_name_source=name_source,
                green_hatch_ordinary_excluded=green_excluded,
                green_exclusion_classification=gr_cls,
                specialty_finish_codes=spec_codes,
                rcp_zone_id=paired_zone_id,
                rcp_material_code=rcp_mat,
                rcp_ceiling_height_mm=rcp_h,
                rcp_raked_height_range_mm=rcp_raked,
                cross_view_ceiling_ready=rcp_ready,
                blocking_reasons=dedup,
                issuer_wiring_owned_by="MAX",
                commercial_authority_granted=False,
                shadow_only=True,
            )
        )

    pkt_payload = {
        "records": [r.to_dict() for r in out_records],
        "distinct_ceiling_heights_preserved_mm": list(distinct_heights),
        "green_excluded_room_count": green_count,
        "cross_view_ceiling_ready_count": rcp_ready_count,
    }
    pkt_sha = _canonical_sha(pkt_payload)
    return RoomFinishRcpHandoffPacket(
        packet_id=f"room_finish_rcp_pkt_{pkt_sha[:16]}",
        records=tuple(out_records),
        distinct_ceiling_heights_preserved_mm=distinct_heights,
        green_excluded_room_count=green_count,
        cross_view_ceiling_ready_count=rcp_ready_count,
        explicit_distinct_heights_preserved=True,
        commercial_authority_granted=False,
        shadow_only=True,
        digest_sha256=pkt_sha,
    )
