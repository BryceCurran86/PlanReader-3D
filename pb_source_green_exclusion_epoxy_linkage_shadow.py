"""Read-only shadow linkage of green-hatch exclusions and epoxy/coldroom floor labels.

Implements Work Order Item 27 for the floor owner with zero customer writes:
- Consumes authenticated ``SourceGreenHatchRoomWitness`` objects from
  ``pb_source_green_hatch_room_exclusion`` alongside physical room polygons,
  contained text observations, and same-revision/SHA finish-legend definitions.
- Preserves green diagonal hatch exclusion witnesses and epoxy/coldroom/aisle
  label linkages as distinct typed evidence on each physical room face.
- Fails closed (CONFLICT / ABSTAINED) on overlapping room polygons, conflicting
  finish codes inside one room, duplicate/conflicting finish-legend definitions,
  cross-revision/SHA mismatches, or degenerate polygons.
- Never grants commercial authority, specialty finish permission, or customer
  publication.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_source_green_hatch_room_exclusion import (
    SourceGreenHatchRoomWitness,
    _inside,
    _source_polygon_is_simple,
)

SCHEMA_VERSION = "1.0.0"

CLASS_GREEN_HATCH_AND_EXCLUSION = "green_hatch_and_exclusion_corroborated"
CLASS_GREEN_HATCH_WITH_EPOXY = "green_hatch_with_epoxy_finish_candidate"
CLASS_GREEN_HATCH_ONLY = "green_hatch_only_ordinary_finish_excluded"
CLASS_EPOXY_LABEL_ONLY = "epoxy_label_without_green_hatch"
CLASS_EXCLUSION_LABEL_ONLY = "exclusion_label_without_green_hatch"
CLASS_UNLINKED = "no_green_hatch_or_specialty_label"
CLASS_CONFLICT = "green_exclusion_epoxy_linkage_conflict"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FINISH_CODE_RE = re.compile(
    r"^(?:FT|FL|EP|EX|RF|CR|VF|CT|CP|TL)[- ]?\d{1,3}[A-Z]?$",
    re.IGNORECASE,
)
_EPOXY_PHRASE_RE = re.compile(
    r"\b(?:epoxy|polyurethane\s+screed|resin\s+floor(?:ing)?|seamless\s+resin|trowelled\s+resin)\b",
    re.IGNORECASE,
)
_EXCLUSION_PHRASE_RE = re.compile(
    r"\b(?:cold\s*room|cool\s*room|freezer|refrigerat(?:ed|ion)|chiller|walk[- ]?in\s+cool|"
    r"aisle\s+excl\w*|equipment\s+(?:zone|area|bay|pad)|future\s+tenancy|"
    r"excl(?:uded|\.)?\s+from\s+contract|"
    r"by\s+(?:others|lessee|tenant|specialist|contractor)|not\s+in\s+contract|n\.?i\.?c\.?)\b",
    re.IGNORECASE,
)

Point = tuple[float, float]


def _req_str(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _req_sha256(value: object, name: str) -> str:
    clean = _req_str(value, name).lower()
    if not _SHA256_RE.fullmatch(clean):
        raise ValueError(f"{name} must be a 64-char hex sha256")
    return clean


def _req_pt(value: object, name: str) -> Point:
    if type(value) is not tuple or len(value) != 2:
        raise ValueError(f"{name} must be a finite 2-tuple")
    x, y = value
    if isinstance(x, bool) or isinstance(y, bool):
        raise ValueError(f"{name} must be numeric")
    fx, fy = float(x), float(y)
    if not (math.isfinite(fx) and math.isfinite(fy)):
        raise ValueError(f"{name} must be finite")
    return (fx, fy)


def _norm_space(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _canonical_finish_code(value: str) -> str:
    return re.sub(r"[\s\u2010\u2011\u2012\u2013\u2014\u2212-]+", "", _norm_space(value).upper())


@dataclass(frozen=True)
class FloorExclusionRoomCandidate:
    canonical_floor_id: str
    physical_floor_surface_id: str
    source_room_face_record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    viewport_id: str
    polygon_pdf_pts: tuple[Point, ...]

    def __post_init__(self) -> None:
        for field in (
            "canonical_floor_id", "physical_floor_surface_id",
            "source_room_face_record_id", "document_id", "revision_id",
            "page_id", "viewport_id",
        ):
            object.__setattr__(self, field, _req_str(getattr(self, field), field))
        object.__setattr__(self, "source_sha256", _req_sha256(self.source_sha256, "source_sha256"))


@dataclass(frozen=True)
class FloorFinishLabelObservation:
    observation_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    viewport_id: str
    raw_text: str
    anchor_pt_pdf_pts: Point

    def __post_init__(self) -> None:
        for field in ("observation_id", "document_id", "revision_id", "page_id", "viewport_id", "raw_text"):
            object.__setattr__(self, field, _req_str(getattr(self, field), field))
        object.__setattr__(self, "source_sha256", _req_sha256(self.source_sha256, "source_sha256"))
        object.__setattr__(self, "anchor_pt_pdf_pts", _req_pt(self.anchor_pt_pdf_pts, "anchor_pt_pdf_pts"))


@dataclass(frozen=True)
class FinishLegendDefinitionInput:
    definition_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    legend_page_id: str
    finish_code: str
    description: str

    def __post_init__(self) -> None:
        for field in ("definition_id", "document_id", "revision_id", "legend_page_id", "finish_code", "description"):
            object.__setattr__(self, field, _req_str(getattr(self, field), field))
        object.__setattr__(self, "source_sha256", _req_sha256(self.source_sha256, "source_sha256"))
        object.__setattr__(self, "finish_code", _canonical_finish_code(self.finish_code))


@dataclass(frozen=True)
class GreenExclusionEpoxyLinkageShadow:
    record_id: str
    canonical_floor_id: str
    physical_floor_surface_id: str
    source_room_face_record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    viewport_id: str
    classification: str
    status: EvidenceResolutionStatus
    green_hatch_witness_id: str | None
    green_hatch_native_path_ids: tuple[int, ...]
    ordinary_finish_exclusion_indicated: bool
    epoxy_label_observation_ids: tuple[str, ...]
    exclusion_label_observation_ids: tuple[str, ...]
    linked_finish_codes: tuple[str, ...]
    linked_legend_definition_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    commercial_quantity_allowed: bool = False
    customer_write_allowed: bool = False
    specialty_authority_granted: bool = False


@dataclass(frozen=True)
class GreenExclusionEpoxyLinkageReport:
    schema_version: str
    room_records: tuple[GreenExclusionEpoxyLinkageShadow, ...]
    unmatched_green_witness_ids: tuple[str, ...]
    conflicting_legend_codes: tuple[str, ...]
    reason_codes: tuple[str, ...]
    commercial_quantity_allowed: bool = False
    customer_write_allowed: bool = False
    specialty_authority_granted: bool = False


def _valid_polygon(poly: Sequence[Point]) -> bool:
    if not poly or len(poly) < 3:
        return False
    try:
        pts = tuple(_req_pt(p, "polygon_pt") for p in poly)
    except ValueError:
        return False
    return _source_polygon_is_simple(pts)


def link_green_exclusions_and_epoxy_labels(
    *,
    rooms: Sequence[FloorExclusionRoomCandidate],
    green_witnesses: Sequence[SourceGreenHatchRoomWitness],
    label_observations: Sequence[FloorFinishLabelObservation],
    finish_legend_definitions: Sequence[FinishLegendDefinitionInput] = (),
) -> GreenExclusionEpoxyLinkageReport:
    """Link source-native green-hatch exclusion witnesses and contained epoxy/exclusion labels."""
    seen_floors: set[str] = set()
    for room in rooms:
        if room.canonical_floor_id in seen_floors:
            raise ValueError(f"duplicate_canonical_floor_id:{room.canonical_floor_id}")
        seen_floors.add(room.canonical_floor_id)

    seen_obs: set[str] = set()
    for obs in label_observations:
        if obs.observation_id in seen_obs:
            raise ValueError(f"duplicate_label_observation_id:{obs.observation_id}")
        seen_obs.add(obs.observation_id)

    # Index green-hatch witnesses strictly by (canonical_floor_id, physical_floor_surface_id,
    # source_room_face_record_id, source_sha256, page_id). Duplicate witnesses conflict.
    witness_by_key: dict[tuple[str, str, str, str, str], list[SourceGreenHatchRoomWitness]] = {}
    for w in green_witnesses:
        if type(w) is not SourceGreenHatchRoomWitness:
            raise TypeError("green_witnesses must contain SourceGreenHatchRoomWitness instances")
        wkey = (
            w.canonical_floor_id, w.physical_floor_surface_id,
            w.source_room_face_record_id, w.source_sha256, w.page_id,
        )
        witness_by_key.setdefault(wkey, []).append(w)

    # Index finish-legend code definitions by (doc, rev, sha, code); duplicate codes conflict.
    legend_by_key: dict[tuple[str, str, str, str], list[FinishLegendDefinitionInput]] = {}
    for defn in finish_legend_definitions:
        lkey = (defn.document_id, defn.revision_id, defn.source_sha256, defn.finish_code)
        legend_by_key.setdefault(lkey, []).append(defn)

    conflicting_legend_codes: set[str] = set()
    report_reasons: set[str] = set()
    for (_doc, _rev, _sha, code), defs in sorted(legend_by_key.items()):
        if len(defs) > 1:
            conflicting_legend_codes.add(code)
            report_reasons.add("conflicting_finish_legend_code_definition")

    ordered_rooms = sorted(
        rooms,
        key=lambda r: (r.document_id, r.revision_id, r.source_sha256, r.page_id, r.viewport_id, r.canonical_floor_id),
    )
    valid_poly = {r.canonical_floor_id: _valid_polygon(r.polygon_pdf_pts) for r in ordered_rooms}

    # Map each label observation to all valid containing rooms in the exact same
    # (doc, rev, sha, page_id, viewport_id). Labels inside >1 overlapping room fail closed.
    obs_by_room: dict[str, list[FloorFinishLabelObservation]] = {r.canonical_floor_id: [] for r in ordered_rooms}
    overlapping_rooms: set[str] = set()
    for obs in sorted(label_observations, key=lambda o: o.observation_id):
        hits = [
            r for r in ordered_rooms
            if valid_poly[r.canonical_floor_id]
            and r.document_id == obs.document_id
            and r.revision_id == obs.revision_id
            and r.source_sha256 == obs.source_sha256
            and r.page_id == obs.page_id
            and r.viewport_id == obs.viewport_id
            and _inside(obs.anchor_pt_pdf_pts[0], obs.anchor_pt_pdf_pts[1], r.polygon_pdf_pts)
        ]
        if len(hits) > 1:
            for r in hits:
                overlapping_rooms.add(r.canonical_floor_id)
            report_reasons.add("label_in_multiple_overlapping_room_polygons")
        elif len(hits) == 1:
            obs_by_room[hits[0].canonical_floor_id].append(obs)

    matched_witness_ids: set[str] = set()
    records: list[GreenExclusionEpoxyLinkageShadow] = []

    for room in ordered_rooms:
        r_reasons: list[str] = []
        wkey = (
            room.canonical_floor_id, room.physical_floor_surface_id,
            room.source_room_face_record_id, room.source_sha256, room.page_id,
        )
        matched_ws = witness_by_key.get(wkey, [])
        green_wid: str | None = None
        green_paths: tuple[int, ...] = ()
        has_conflict = False

        if not valid_poly[room.canonical_floor_id]:
            records.append(
                GreenExclusionEpoxyLinkageShadow(
                    record_id=stable_contract_id(
                        "green_exclusion_epoxy_linkage_shadow",
                        {"canonical_floor_id": room.canonical_floor_id, "status": "abstained", "reason": "invalid_polygon"},
                    ),
                    canonical_floor_id=room.canonical_floor_id,
                    physical_floor_surface_id=room.physical_floor_surface_id,
                    source_room_face_record_id=room.source_room_face_record_id,
                    document_id=room.document_id,
                    revision_id=room.revision_id,
                    source_sha256=room.source_sha256,
                    page_id=room.page_id,
                    viewport_id=room.viewport_id,
                    classification=CLASS_UNLINKED,
                    status=EvidenceResolutionStatus.ABSTAINED,
                    green_hatch_witness_id=None,
                    green_hatch_native_path_ids=(),
                    ordinary_finish_exclusion_indicated=False,
                    epoxy_label_observation_ids=(),
                    exclusion_label_observation_ids=(),
                    linked_finish_codes=(),
                    linked_legend_definition_ids=(),
                    reason_codes=("invalid_or_degenerate_room_polygon",),
                )
            )
            continue

        if len(matched_ws) > 1:
            has_conflict = True
            r_reasons.append("duplicate_green_hatch_witness_for_room")
        elif len(matched_ws) == 1:
            w = matched_ws[0]
            matched_witness_ids.add(w.witness_id)
            green_wid = w.witness_id
            green_paths = w.native_path_ids

        if room.canonical_floor_id in overlapping_rooms:
            has_conflict = True
            r_reasons.append("label_in_multiple_overlapping_room_polygons")

        epoxy_obs_ids: list[str] = []
        excl_obs_ids: list[str] = []
        finish_codes: set[str] = set()
        legend_def_ids: list[str] = []

        for obs in obs_by_room[room.canonical_floor_id]:
            text = _norm_space(obs.raw_text)
            if _EPOXY_PHRASE_RE.search(text):
                epoxy_obs_ids.append(obs.observation_id)
            if _EXCLUSION_PHRASE_RE.search(text):
                excl_obs_ids.append(obs.observation_id)
            if _FINISH_CODE_RE.fullmatch(re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2212]", "-", text)):
                code = _canonical_finish_code(text)
                finish_codes.add(code)
                lkey = (room.document_id, room.revision_id, room.source_sha256, code)
                defs = legend_by_key.get(lkey, [])
                if len(defs) > 1:
                    has_conflict = True
                    r_reasons.append("conflicting_finish_legend_code_definition")
                elif len(defs) == 1:
                    defn = defs[0]
                    legend_def_ids.append(defn.definition_id)
                    if _EPOXY_PHRASE_RE.search(defn.description):
                        epoxy_obs_ids.append(obs.observation_id)
                    if _EXCLUSION_PHRASE_RE.search(defn.description):
                        excl_obs_ids.append(obs.observation_id)

        if len(finish_codes) > 1:
            has_conflict = True
            r_reasons.append("multiple_distinct_finish_codes_in_one_room")

        epoxy_ids = tuple(sorted(set(epoxy_obs_ids)))
        excl_ids = tuple(sorted(set(excl_obs_ids)))
        codes_sorted = tuple(sorted(finish_codes))
        def_ids_sorted = tuple(sorted(set(legend_def_ids)))

        if has_conflict:
            classification = CLASS_CONFLICT
            status = EvidenceResolutionStatus.CONFLICT
        elif green_wid is not None and epoxy_ids:
            classification = CLASS_GREEN_HATCH_WITH_EPOXY
            status = EvidenceResolutionStatus.CORROBORATED
            r_reasons.append("green_hatch_ordinary_exclusion_plus_epoxy_label_candidate")
            if excl_ids:
                r_reasons.append("coldroom_or_exclusion_text_corroborated")
        elif green_wid is not None and excl_ids:
            classification = CLASS_GREEN_HATCH_AND_EXCLUSION
            status = EvidenceResolutionStatus.CORROBORATED
            r_reasons.append("green_hatch_corroborated_with_exclusion_text")
        elif green_wid is not None:
            classification = CLASS_GREEN_HATCH_ONLY
            status = EvidenceResolutionStatus.CORROBORATED
            r_reasons.append("green_hatch_ordinary_finish_exclusion_witness_only")
        elif epoxy_ids:
            classification = CLASS_EPOXY_LABEL_ONLY
            status = EvidenceResolutionStatus.CORROBORATED
            r_reasons.append("epoxy_label_linked_without_green_hatch")
        elif excl_ids:
            classification = CLASS_EXCLUSION_LABEL_ONLY
            status = EvidenceResolutionStatus.CORROBORATED
            r_reasons.append("exclusion_text_linked_without_green_hatch")
        else:
            classification = CLASS_UNLINKED
            status = EvidenceResolutionStatus.ABSTAINED
            r_reasons.append("no_green_hatch_or_specialty_label_in_room")

        ordered_reasons = tuple(dict.fromkeys(r_reasons))
        rec_id = stable_contract_id(
            "green_exclusion_epoxy_linkage_shadow",
            {
                "canonical_floor_id": room.canonical_floor_id,
                "source_sha256": room.source_sha256,
                "page_id": room.page_id,
                "viewport_id": room.viewport_id,
                "green_hatch_witness_id": green_wid,
                "epoxy_label_observation_ids": epoxy_ids,
                "exclusion_label_observation_ids": excl_ids,
                "classification": classification,
                "status": status.value,
                "reason_codes": ordered_reasons,
            },
        )
        records.append(
            GreenExclusionEpoxyLinkageShadow(
                record_id=rec_id,
                canonical_floor_id=room.canonical_floor_id,
                physical_floor_surface_id=room.physical_floor_surface_id,
                source_room_face_record_id=room.source_room_face_record_id,
                document_id=room.document_id,
                revision_id=room.revision_id,
                source_sha256=room.source_sha256,
                page_id=room.page_id,
                viewport_id=room.viewport_id,
                classification=classification,
                status=status,
                green_hatch_witness_id=green_wid,
                green_hatch_native_path_ids=green_paths,
                ordinary_finish_exclusion_indicated=(green_wid is not None and not has_conflict),
                epoxy_label_observation_ids=epoxy_ids,
                exclusion_label_observation_ids=excl_ids,
                linked_finish_codes=codes_sorted,
                linked_legend_definition_ids=def_ids_sorted,
                reason_codes=ordered_reasons,
                commercial_quantity_allowed=False,
                customer_write_allowed=False,
                specialty_authority_granted=False,
            )
        )

    unmatched_w = tuple(
        sorted(w.witness_id for w in green_witnesses if w.witness_id not in matched_witness_ids)
    )
    return GreenExclusionEpoxyLinkageReport(
        schema_version=SCHEMA_VERSION,
        room_records=tuple(records),
        unmatched_green_witness_ids=unmatched_w,
        conflicting_legend_codes=tuple(sorted(conflicting_legend_codes)),
        reason_codes=tuple(sorted(report_reasons)),
        commercial_quantity_allowed=False,
        customer_write_allowed=False,
        specialty_authority_granted=False,
    )


__all__ = [
    "CLASS_CONFLICT",
    "CLASS_EPOXY_LABEL_ONLY",
    "CLASS_EXCLUSION_LABEL_ONLY",
    "CLASS_GREEN_HATCH_AND_EXCLUSION",
    "CLASS_GREEN_HATCH_ONLY",
    "CLASS_GREEN_HATCH_WITH_EPOXY",
    "CLASS_UNLINKED",
    "FinishLegendDefinitionInput",
    "FloorExclusionRoomCandidate",
    "FloorFinishLabelObservation",
    "GreenExclusionEpoxyLinkageReport",
    "GreenExclusionEpoxyLinkageShadow",
    "SCHEMA_VERSION",
    "link_green_exclusions_and_epoxy_labels",
]
