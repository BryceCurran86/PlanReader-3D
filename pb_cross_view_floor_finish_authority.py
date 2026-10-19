"""Bind authenticated source material finishes to cross-view canonical floors.

This authority composes existing source-owned facts only:

- CrossViewRoomAreaProducer has already proven one physical room, one
  orthogonal figured-dimension system and one explicit metric area.
- SourceMaterialSemanticProducer has already authenticated material schedule
  definitions and drawing occurrences.
- LiveCanonicalFloorSurfaceComposition already owns the deterministic physical
  floor identity derived from the physical room.

A floor finish resolves first through the strongest same-view relationship:
exactly one authenticated drawing occurrence fully inside the already-proven
room dimension box. When the source places finishes on a separate floor-finish
plan, a fallback may bind only when the room label is unique and the trusted
room-label line and authenticated finish-occurrence line share one exact native
PDF partition/block inside an authenticated FLOOR_FINISH_PLAN viewport. Raw
codes, nearest marks, cross-sheet coordinate transfer, project coordinates and
benchmark values are never inputs.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
import math
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

from pb_cross_view_ceiling_finish_authority import (
    _occurrence_line as _cross_view_occurrence_line,
    _source_bytes as _cross_view_source_bytes,
    _trusted_room_labels_for_pages as _trusted_room_labels_for_pages,
    _viewport_is_authoritative as _cross_viewport_is_authoritative,
)
from pb_cross_view_room_area_authority import (
    CrossViewRoomAreaRecord,
    CrossViewRoomAreaResult,
)
from pb_drawing_evidence_binding import DrawingViewType
from pb_same_view_room_area_authority import (
    SameViewRoomAreaRecord,
    SameViewRoomAreaResult,
)
from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_live_canonical_floor_surface import (
    LiveCanonicalFloorSurfaceComposition,
    LiveCanonicalFloorSurfaceObject,
)
from pb_migration_contracts import (
    EvidenceResolutionStatus,
    QuantityEvidence,
    stable_contract_id,
)
from pb_source_material_semantic_authority import (
    SourceMaterialDefinitionRecord,
    SourceMaterialDefinitionSelector,
    SourceMaterialOccurrenceRecord,
    SourceMaterialOccurrenceScopeResult,
    SourceMaterialSemanticProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import (
    is_authoritative_derived_viewport,
    is_segment_page_viewports_product,
    segment_page_viewports,
    validate_non_overlapping_viewports,
)


CROSS_VIEW_FLOOR_FINISH_SCHEMA_VERSION = "1.2.0"
CROSS_VIEW_FLOOR_FINISH_RESOLVED = "cross_view_floor_finish_resolved"
CROSS_VIEW_FLOOR_FINISH_PARTIAL = "cross_view_floor_finish_partial"
CROSS_VIEW_FLOOR_FINISH_UNAVAILABLE = "cross_view_floor_finish_unavailable"
CROSS_VIEW_FLOOR_FINISH_CONFLICT = "cross_view_floor_finish_conflict"
CROSS_VIEW_FLOOR_FINISH_LINEAGE_CONFLICT = (
    "cross_view_floor_finish_lineage_conflict"
)
CROSS_VIEW_FLOOR_FINISH_OCCURRENCE_UNAVAILABLE = (
    "cross_view_floor_finish_occurrence_unavailable"
)
CROSS_VIEW_FLOOR_FINISH_DEFINITION_UNAVAILABLE = (
    "cross_view_floor_finish_definition_unavailable"
)
CROSS_VIEW_FLOOR_FINISH_QUANTITY_RESOLVED = (
    "authenticated_cross_view_floor_finish_area"
)

_PRODUCER_SEAL = object()
_RECORD_SEAL = object()

# These are normalized semantic families, not drawing abbreviations/codes.
# Every accepted family must still have an authenticated schedule definition
# explicitly identifying a floor role.
_FLOOR_FINISH_SEMANTICS = frozenset(
    {
        "tile",
        "vinyl",
        "epoxy",
    }
)


def _clean(value: object) -> str:
    return str(value or "").strip()


def _norm(value: object) -> str:
    return " ".join(_clean(value).casefold().split())


def _bbox(
    value: object,
) -> Optional[tuple[float, float, float, float]]:
    if not isinstance(value, (tuple, list)) or len(value) != 4:
        return None
    if any(type(item) not in (int, float) for item in value):
        return None
    try:
        result = tuple(float(item) for item in value)
    except (TypeError, ValueError, OverflowError):
        return None
    if (
        not all(math.isfinite(item) for item in result)
        or result[2] <= result[0]
        or result[3] <= result[1]
    ):
        return None
    return result


def _bbox_fully_inside(
    inner: Sequence[float],
    outer: Sequence[float],
    *,
    tolerance: float = 1e-6,
) -> bool:
    return (
        float(inner[0]) >= float(outer[0]) - tolerance
        and float(inner[1]) >= float(outer[1]) - tolerance
        and float(inner[2]) <= float(outer[2]) + tolerance
        and float(inner[3]) <= float(outer[3]) + tolerance
    )


def _definition_is_floor_finish(
    definition: SourceMaterialDefinitionRecord,
) -> bool:
    semantic = _clean(definition.semantic_finish).lower()
    if semantic not in _FLOOR_FINISH_SEMANTICS:
        return False
    text = " ".join(
        _clean(value).lower()
        for value in (
            definition.description,
            definition.substrate,
            definition.finish,
        )
        if _clean(value)
    )
    if not text:
        return False
    # A stale generic "tile" finish semantic does not turn a physical wall
    # tile, floor drain or underfloor/subfloor specification into finished
    # floor covering merely because its original description says "floor".
    import re
    if re.search(
        r"\b(?:under[\s-]*floor|sub[\s-]*floor|"
        r"floor[\s-]*(?:drain|insulation)|wall[\s-]*til(?:e|es|ing))\b",
        text,
    ):
        return False
    # The semantic family is already authenticated upstream. This role gate
    # simply prevents a confirmed wall-tile definition from being applied to a
    # floor because both normalize to the generic semantic "tile".
    return any(
        phrase in text
        for phrase in (
            "floor ",
            "flooring",
            "floor tile",
            "floor finish",
            "floor coating",
        )
    )


def _dimension_box(
    record: CrossViewRoomAreaRecord | SameViewRoomAreaRecord,
) -> Optional[tuple[float, float, float, float]]:
    evidence = record.area_evidence
    if (
        evidence.status is not EvidenceResolutionStatus.CORROBORATED
        or evidence.kind != "explicit_room_area"
        or evidence.method
        not in {
            "authenticated_cross_view_figured_dimensions",
            "authenticated_same_view_figured_dimensions",
        }
    ):
        return None
    metadata = evidence.metadata if isinstance(evidence.metadata, Mapping) else {}
    box = _bbox(metadata.get("source_dimension_box_pdf_pts"))
    if box is None:
        return None
    if _clean(metadata.get("source_dimension_page_id")) != _clean(
        record.source_dimension_page_id
    ):
        return None
    return box


def _area_value(
    record: CrossViewRoomAreaRecord | SameViewRoomAreaRecord,
) -> Optional[float]:
    evidence = record.area_evidence
    if (
        evidence.status is not EvidenceResolutionStatus.CORROBORATED
        or _clean(evidence.unit).lower() not in {"m2", "m²"}
        or type(evidence.normalized_value) not in (int, float)
    ):
        return None
    try:
        value = float(evidence.normalized_value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(value) or value <= 0.0:
        return None
    return value


def _expected_floor_id(
    *,
    document_id: str,
    physical_room_id: str,
) -> str:
    return stable_contract_id(
        "physical_room_floor_surface",
        {
            "document_id": document_id,
            "physical_room_id": physical_room_id,
            "surface_role": "floor",
        },
        digest_chars=32,
    )


def _matching_floor(
    floors: LiveCanonicalFloorSurfaceComposition,
    area_record: CrossViewRoomAreaRecord | SameViewRoomAreaRecord,
) -> Optional[LiveCanonicalFloorSurfaceObject]:
    expected_id = _expected_floor_id(
        document_id=area_record.area_evidence.document_id,
        physical_room_id=area_record.physical_room_id,
    )
    matches = [
        floor
        for floor in floors.floors
        if (
            floor.source_room_face_record_id
            == area_record.source_room_face_record_id
            and floor.canonical_floor_id == expected_id
            and floor.physical_floor_surface_id == expected_id
        )
    ]
    if len(matches) != 1:
        return None
    floor = matches[0]
    # The floor finish may borrow only the exact corroborated figured-area
    # evidence already attached to this canonical floor. Matching the numeric
    # area and physical room alone must not cross-bind another area claim.
    area_evidence = area_record.area_evidence
    if (
        area_evidence.status is not EvidenceResolutionStatus.CORROBORATED
        or type(area_evidence.evidence_id) is not str
        or not area_evidence.evidence_id
        or area_evidence.evidence_id != area_evidence.evidence_id.strip()
        or not isinstance(floor.evidence_ids, (tuple, list))
        or not floor.evidence_ids
        or any(type(value) is not str or not value or value != value.strip()
               for value in floor.evidence_ids)
        or len(set(floor.evidence_ids)) != len(floor.evidence_ids)
        or area_evidence.evidence_id not in floor.evidence_ids
    ):
        return None
    value = _area_value(area_record)
    if value is None:
        return None
    if type(floor.metric_area_m2) not in (int, float):
        return None
    try:
        floor_value = float(floor.metric_area_m2)
    except (TypeError, ValueError, OverflowError):
        return None
    if (
        not math.isfinite(floor_value)
        or abs(floor_value - value) > 1e-9
        or type(floor.metric_area_quantity_id) is not str
        or not floor.metric_area_quantity_id
        or floor.metric_area_quantity_id != floor.metric_area_quantity_id.strip()
        or _clean(floor.metric_area_authority)
        != MeasurementAuthorityType.DOCUMENTED_DIMENSION.value
    ):
        return None
    metadata = (
        area_record.area_evidence.metadata
        if isinstance(area_record.area_evidence.metadata, Mapping)
        else {}
    )
    if floor.document_id != area_record.area_evidence.document_id:
        return None
    if _clean(metadata.get("source_sha256")).lower() != floor.source_sha256.lower():
        return None
    if _clean(metadata.get("room_revision_id")) != floor.revision_id:
        return None
    return floor


def _floor_finish_viewports(
    source: SourceVisibilityProducer,
    *,
    revision_id: str,
) -> Mapping[tuple[str, str], tuple[float, float, float, float]]:
    published = source.published_snapshot_for_revision(revision_id)
    payload = _cross_view_source_bytes(source, revision_id)
    if published is None or payload is None:
        return MappingProxyType({})

    import fitz

    decoded = sorted({int(value) for value in published.coverage.decoded_pages})
    output: dict[tuple[str, str], tuple[float, float, float, float]] = {}
    pdf = fitz.open(stream=payload, filetype="pdf")
    try:
        for page_number in decoded:
            if page_number < 1 or page_number > pdf.page_count:
                continue
            viewports = tuple(
                segment_page_viewports(
                    pdf.load_page(page_number - 1),
                    page_number=page_number,
                )
            )
            if (
                not viewports
                or any(
                    not is_segment_page_viewports_product(viewport)
                    for viewport in viewports
                )
            ):
                continue
            sibling_non_overlapping = validate_non_overlapping_viewports(viewports)
            for viewport in viewports:
                if (
                    viewport.view_type
                    != DrawingViewType.FLOOR_FINISH_PLAN.value
                    or not _cross_viewport_is_authoritative(
                        viewport,
                        sibling_non_overlapping=sibling_non_overlapping,
                    )
                    or viewport.bounding_box is None
                ):
                    continue
                bbox = _bbox(viewport.bounding_box)
                if bbox is not None:
                    output[(str(page_number), _clean(viewport.view_id))] = bbox
    finally:
        pdf.close()
    return MappingProxyType(output)


def _source_owned_mark_eligible_for_existing_physical_floor(
    *,
    floor: LiveCanonicalFloorSurfaceObject,
    occurrence: SourceMaterialOccurrenceRecord,
    source_owned_shadow: bool,
) -> bool:
    """Do not reinterpret cross-sheet mark containment as physical equality.

    A new, independently issued cross-sheet structural correspondence receipt
    is needed before this isolated mode could accept p11→p7 finishes.
    Existing same-view/default quantities keep their original authority.
    """
    if type(source_owned_shadow) is not bool:
        raise ValueError("source-owned floor mode must be an explicit boolean")
    return (
        not source_owned_shadow
        or _clean(floor.page_id) == _clean(occurrence.page_id)
    )


def _source_owned_floor_finish_viewports(
    producer: SourceMaterialSemanticProducer,
    *,
    published: object,
    permitted_page_ids: Sequence[str],
) -> Mapping[tuple[str, str], tuple[float, float, float, float]]:
    """Consume ONLY the material producer's authentic bounded F07 view products.

    A geometrically plausible box, unsealed viewport, copied provenance,
    overlapping sibling, or foreign page cannot acquire commercial ownership.
    This is source viewport evidence only, not a room/floor equivalence grant.
    """
    allowed = set(permitted_page_ids)
    grouped = {}
    views = producer.published_plan_viewports()
    for view in views:
        page_id = str(view.page_number)
        if (
            page_id not in allowed
            or not is_segment_page_viewports_product(view)
        ):
            return MappingProxyType({})
        provenance = view.provenance or {}
        if any(
            str(provenance.get(key) or "") != str(expected)
            for key, expected in (
                ("document_id", published.revision.document_id),
                ("revision_id", published.revision.revision_id),
                ("source_sha256", published.revision.source_sha256),
                ("snapshot_id", published.snapshot.snapshot_id),
            )
        ):
            return MappingProxyType({})
        grouped.setdefault(page_id, []).append(view)
    if not grouped:
        return MappingProxyType({})
    result = {}
    for page_id, siblings in sorted(grouped.items()):
        if not validate_non_overlapping_viewports(siblings):
            return MappingProxyType({})
        for view in siblings:
            if (
                view.view_type != DrawingViewType.FLOOR_FINISH_PLAN.value
                or not is_authoritative_derived_viewport(view)
                or view.bounding_box is None
            ):
                continue
            key = (page_id, _clean(view.view_id))
            box = _bbox(view.bounding_box)
            if not key[1] or box is None or key in result:
                return MappingProxyType({})
            result[key] = box
    return MappingProxyType(result)


def _occurrences_on_page(
    results: Sequence[SourceMaterialOccurrenceScopeResult],
    *,
    page_id: str,
) -> tuple[SourceMaterialOccurrenceRecord, ...]:
    # A completed viewport/plan scope may repeat the same source-issued
    # observation already returned by another completed scope. Counting the
    # *identical* receipt twice would make one true finish look ambiguous.
    # Conversely, a reused ID with different evidence cannot choose a winner.
    by_id: dict[str, list[SourceMaterialOccurrenceRecord]] = {}
    by_evidence: dict[str, set[str]] = {}
    for result in results:
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or not result.scope_complete
        ):
            continue
        for record in result.records:
            if (
                type(record) is not SourceMaterialOccurrenceRecord
                or _clean(record.page_id) != _clean(page_id)
                or type(record.record_id) is not str
                or not record.record_id
                or record.record_id != record.record_id.strip()
                or type(record.source_evidence_id) is not str
                or not record.source_evidence_id
                or record.source_evidence_id != record.source_evidence_id.strip()
            ):
                continue
            by_id.setdefault(record.record_id, []).append(record)
            by_evidence.setdefault(record.source_evidence_id, set()).add(
                record.record_id
            )

    # No string label, nominal material area, or approximate bbox can
    # collapse *different* physical observations. Both sides of a conflicting
    # issuer identity are withheld, independently of result iteration order.
    disputed = {
        record_id
        for record_id, rows in by_id.items()
        if any(row != rows[0] for row in rows[1:])
    }
    for owners in by_evidence.values():
        if len(owners) != 1:
            disputed.update(owners)
    return tuple(
        sorted(
            (rows[0] for record_id, rows in by_id.items()
             if record_id not in disputed),
            key=lambda record: (
                record.bbox_pdf_pts,
                record.code,
                record.record_id,
            ),
        )
    )


@dataclass(frozen=True)
class CrossViewFloorFinishRecord:
    physical_room_id: str
    source_room_face_record_id: str
    canonical_floor_id: str
    physical_floor_surface_id: str
    source_dimension_page_id: str
    finish_code: str
    semantic_finish: str
    definition_record_id: str
    occurrence_record_id: str
    occurrence_evidence_id: str
    occurrence_bbox_pdf_pts: tuple[float, float, float, float]
    support_snapshot_id: str
    quantity: QuantityEvidence
    schema_version: str = CROSS_VIEW_FLOOR_FINISH_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("CrossViewFloorFinishRecord is producer-owned")


@dataclass(frozen=True)
class CrossViewFloorFinishResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    records: tuple[CrossViewFloorFinishRecord, ...]
    unresolved_canonical_floor_ids: tuple[str, ...]
    schema_version: str = CROSS_VIEW_FLOOR_FINISH_SCHEMA_VERSION

    @property
    def quantities(self) -> tuple[QuantityEvidence, ...]:
        # External quantity consumers must observe the same unambiguous
        # canonical floor identity gate as records_by_floor_id. A duplicate
        # floor finish cannot reach takeoff through this convenience property.
        return tuple(
            record.quantity for record in self.records_by_floor_id.values()
        )

    @property
    def records_by_floor_id(self) -> Mapping[str, CrossViewFloorFinishRecord]:
        # A reconstructed ABSTAINED/CONFLICT result cannot emit signed floor
        # quantities merely by carrying stale prior-run records.
        if self.status not in (
            EvidenceResolutionStatus.CORROBORATED,
            EvidenceResolutionStatus.CANDIDATE,
        ):
            return MappingProxyType({})
        # Consumers may receive a reconstructed result dataclass instead of
        # the producer's already-quarantined records. Reapply BOTH the native
        # material-mark ownership gate and the physical room/surface gate here:
        # two independently keyed floors cannot reuse one source occurrence,
        # source face, physical room, or physical floor. Never elect by order.
        # Reconstructed/public containers are not issuer receipts. A rogue
        # entry cannot be silently filtered, leaving a valid-looking sibling
        # that might share the contested original physical source identity.
        if any(type(record) is not CrossViewFloorFinishRecord
               for record in self.records):
            return MappingProxyType({})
        sealed = self.records
        if any(type(record.quantity) is not QuantityEvidence
               for record in sealed):
            return MappingProxyType({})
        # A typed dataclass can be reconstructed with unhashable/malformed
        # source owner fields. Validate before Counter or set construction:
        # bad source observations must abstain, not crash customer projection.
        source_owner_fields = (
            "canonical_floor_id", "physical_floor_surface_id",
            "physical_room_id", "source_room_face_record_id",
            "occurrence_record_id", "occurrence_evidence_id",
        )
        if any(
            type(getattr(record, field)) is not str
            or not getattr(record, field)
            or getattr(record, field) != getattr(record, field).strip()
            for record in sealed for field in source_owner_fields
        ):
            return MappingProxyType({})
        if any(
            not isinstance(record.quantity.evidence_ids, (tuple, list))
            or any(type(eid) is not str or not eid or eid != eid.strip()
                   for eid in record.quantity.evidence_ids)
            for record in sealed
        ):
            return MappingProxyType({})
        survivors, _ = _quarantine_reused_floor_finish_occurrences(sealed)
        source_fields = (
            "canonical_floor_id",
            "physical_floor_surface_id",
            "physical_room_id",
            "source_room_face_record_id",
        )
        # Count ALL submitted records, including those that the lower-level
        # gate rejected for a malformed floor ID. Otherwise a caller could
        # rekey one rival as invalid and let its contested sibling survive.
        duplicates = {
            field: Counter(getattr(record, field, None) for record in sealed)
            for field in source_fields + (
                "occurrence_record_id", "occurrence_evidence_id",
            )
        }
        quantity_ids = Counter(
            getattr(record.quantity, "quantity_id", None)
            for record in sealed
        )
        # Count an occurrence mark carried as *secondary* evidence on a
        # different floor too. A rekeyed record cannot conceal reuse by
        # changing just its primary occurrence_evidence_id.
        primary_original_marks = {
            record.occurrence_evidence_id for record in sealed
            if type(record.occurrence_evidence_id) is str
            and record.occurrence_evidence_id
        }
        source_mark_references = Counter(
            source_id
            for record in sealed
            if type(record.quantity) is QuantityEvidence
            for source_id in set(record.quantity.evidence_ids)
            if source_id in primary_original_marks
        )
        def unique_owner(record: CrossViewFloorFinishRecord) -> bool:
            if (
                type(record.quantity) is not QuantityEvidence
                or record.quantity.family != "floor_finish_area"
                or record.quantity.status != AuthorityStatus.FIRM.value
                or record.quantity.authority !=
                   MeasurementAuthorityType.DOCUMENTED_DIMENSION.value
                or record.quantity.abstained
                or record.quantity.unit not in ("m2", "m²")
                or record.quantity.input_entity_ids != (record.canonical_floor_id,)
                or type(record.quantity.quantity_id) is not str
                or not record.quantity.quantity_id
                or quantity_ids[record.quantity.quantity_id] != 1
                or source_mark_references[record.occurrence_evidence_id] != 1
                or any(
                    source_id != record.occurrence_evidence_id
                    and source_id in primary_original_marks
                    for source_id in record.quantity.evidence_ids
                )
            ):
                return False
            # An independently rekeyed result cannot keep the ORIGINAL
            # measurement's internal provenance on its new floor. Even when
            # its top-level input ID is altered, the signed quantity metadata
            # must still name the same source face and exact material mark.
            metadata = record.quantity.metadata
            if not isinstance(metadata, Mapping):
                return False
            owner_fields = {
                "canonical_floor_id": record.canonical_floor_id,
                "physical_floor_surface_id": record.physical_floor_surface_id,
                "source_room_face_record_id": record.source_room_face_record_id,
                "source_dimension_page_id": record.source_dimension_page_id,
                "finish_occurrence_record_id": record.occurrence_record_id,
                "finish_occurrence_evidence_id": record.occurrence_evidence_id,
                "finish_definition_record_id": record.definition_record_id,
                "finish_code": record.finish_code,
                "support_snapshot_id": record.support_snapshot_id,
            }
            if (
                any(metadata.get(key) != expected
                    for key, expected in owner_fields.items())
                or record.occurrence_evidence_id not in record.quantity.evidence_ids
            ):
                return False
            return all(
                type(getattr(record, field, None)) is str
                and bool(getattr(record, field))
                and getattr(record, field) == getattr(record, field).strip()
                and duplicates[field][getattr(record, field)] == 1
                for field in duplicates
            )
        return MappingProxyType({
            record.canonical_floor_id: record
            for record in survivors if unique_owner(record)
        })


def _unique_documented_area_owner_receipts(
    same_view: Sequence[SameViewRoomAreaRecord],
    cross_view: Sequence[CrossViewRoomAreaRecord],
) -> tuple[
    dict[str, CrossViewRoomAreaRecord | SameViewRoomAreaRecord],
    tuple[str, ...],
]:
    """Select only unambiguous source-room areas, preserving producer priority.

    One cross-view documented measurement legitimately supersedes one or more
    supplementary same-view candidates. But two entries from the SAME
    authority claiming one physical source-room face cannot silently overwrite
    each other or mint a floor finish from insertion order.
    """
    def valid(value: object) -> bool:
        return isinstance(value, str) and bool(value) and value == value.strip()

    def grouped(rows):
        out = {}
        for record in rows:
            source_id = getattr(record, "source_room_face_record_id", None)
            if valid(source_id):
                out.setdefault(source_id, []).append(record)
        return out

    supplementary = grouped(same_view)
    authoritative = grouped(cross_view)
    selected = {}
    disputed = set()
    for source_id in sorted(set(supplementary) | set(authoritative)):
        high = authoritative.get(source_id, ())
        low = supplementary.get(source_id, ())
        if len(high) > 1:
            disputed.add(source_id)
        elif high:
            # An independent single source-proven cross-view measurement
            # retains priority over possibly duplicated supplements.
            selected[source_id] = high[0]
        elif len(low) > 1:
            disputed.add(source_id)
        elif low:
            selected[source_id] = low[0]

    # A producer-owned figured area receipt cannot independently authenticate
    # the metric finish quantity of two different physical source rooms.
    # Quarantine both owners rather than choosing first/last or copying area.
    evidence_owners = {}
    for source_id, record in tuple(selected.items()):
        evidence_id = getattr(
            getattr(record, "area_evidence", None), "evidence_id", None
        )
        if not valid(evidence_id):
            disputed.add(source_id)
            del selected[source_id]
            continue
        evidence_owners.setdefault(evidence_id, set()).add(source_id)
    for source_ids in evidence_owners.values():
        if len(source_ids) > 1:
            disputed.update(source_ids)
            for source_id in source_ids:
                selected.pop(source_id, None)

    # Exact source room-label observation and producer receipt identities
    # likewise cannot be owned by two independently quantified room floors.
    # No string/name/geometry similarity is involved in this check.
    for field in ("source_label_observation_ids", "source_label_receipt_ids"):
        receipt_owners = {}
        for source_id, record in tuple(selected.items()):
            raw = getattr(record, field, ()) or ()
            if not isinstance(raw, (tuple, list)):
                disputed.add(source_id)
                continue
            ids = tuple(raw)
            if (
                any(not valid(receipt) for receipt in ids)
                or len(ids) != len(set(ids))
            ):
                disputed.add(source_id)
                continue
            for receipt in ids:
                receipt_owners.setdefault(receipt, set()).add(source_id)
        for source_ids in receipt_owners.values():
            if len(source_ids) > 1:
                disputed.update(source_ids)
    # Different physical source faces must NOT claim the same original room.
    # A duplicated physical_room_id with distinct source-room face receipts
    # cannot be resolved by insertion order or a finish/material code. Retain
    # unrelated physically unique room measurements unchanged.
    physical_owners = {}
    for source_id, record in selected.items():
        physical_room_id = getattr(record, "physical_room_id", None)
        if not valid(physical_room_id):
            disputed.add(source_id)
            continue
        physical_owners.setdefault(physical_room_id, set()).add(source_id)
    for owners in physical_owners.values():
        if len(owners) > 1:
            disputed.update(owners)
    for source_id in disputed:
        selected.pop(source_id, None)
    return selected, tuple(sorted(disputed))


def _quarantine_reused_floor_finish_occurrences(
    records: Sequence[CrossViewFloorFinishRecord],
) -> tuple[tuple[CrossViewFloorFinishRecord, ...], tuple[str, ...]]:
    """Withhold contested original material marks before any FIRM quantity.

    A producer occurrence ID and its original text/ink evidence ID are
    independent owner identities. Two rekeyed occurrence IDs cannot turn ONE
    original mark into finishes on two distinct physical floor surfaces.
    Keep unrelated measured floors when the source evidence is genuinely
    independent; never select the first or last competing record.
    """
    occurrence_owners: dict[str, set[tuple[str, str]]] = {}
    original_mark_owners: dict[str, set[tuple[str, str]]] = {}
    invalid_floor_ids: set[str] = set()

    def valid(value: object) -> bool:
        return (
            type(value) is str
            and bool(value)
            and value == value.strip()
        )

    for record in records:
        floor_id = record.canonical_floor_id
        physical_id = record.physical_floor_surface_id
        occurrence_id = record.occurrence_record_id
        original_mark_id = record.occurrence_evidence_id
        if (
            not valid(floor_id)
            or not valid(physical_id)
            or not valid(occurrence_id)
            or not valid(original_mark_id)
        ):
            if valid(floor_id):
                invalid_floor_ids.add(floor_id)
            continue
        physical_owner = (floor_id, physical_id)
        occurrence_owners.setdefault(occurrence_id, set()).add(physical_owner)
        original_mark_owners.setdefault(original_mark_id, set()).add(
            physical_owner
        )

    disputed_occurrences = {
        original_id
        for original_id, owners in occurrence_owners.items()
        if len(owners) > 1
    }
    disputed_original_marks = {
        original_id
        for original_id, owners in original_mark_owners.items()
        if len(owners) > 1
    }
    surviving = tuple(
        record
        for record in records
        if (
            valid(record.canonical_floor_id)
            and valid(record.physical_floor_surface_id)
            and valid(record.occurrence_record_id)
            and valid(record.occurrence_evidence_id)
            and record.canonical_floor_id not in invalid_floor_ids
            and record.occurrence_record_id not in disputed_occurrences
            and record.occurrence_evidence_id not in disputed_original_marks
        )
    )
    unresolved = tuple(sorted({
        record.canonical_floor_id
        for record in records
        if (
            valid(record.canonical_floor_id)
            and (
                record.canonical_floor_id in invalid_floor_ids
                or not valid(record.physical_floor_surface_id)
                or not valid(record.occurrence_record_id)
                or not valid(record.occurrence_evidence_id)
                or record.occurrence_record_id in disputed_occurrences
                or record.occurrence_evidence_id in disputed_original_marks
            )
        )
    }))
    return surviving, unresolved

class CrossViewFloorFinishProducer:
    def __init__(
        self,
        *,
        source: SourceVisibilityProducer,
        room_areas: Optional[CrossViewRoomAreaResult],
        floors: LiveCanonicalFloorSurfaceComposition,
        same_view_room_areas: Optional[SameViewRoomAreaResult] = None,
        _physical_plan_page_ids: tuple[str, ...] = (),
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "CrossViewFloorFinishProducer must be obtained from from_source()"
            )
        if type(source) is not SourceVisibilityProducer:
            raise TypeError("source must be exact SourceVisibilityProducer")
        if room_areas is not None and type(room_areas) is not CrossViewRoomAreaResult:
            raise TypeError("room_areas must be CrossViewRoomAreaResult or None")
        if (
            same_view_room_areas is not None
            and type(same_view_room_areas) is not SameViewRoomAreaResult
        ):
            raise TypeError(
                "same_view_room_areas must be SameViewRoomAreaResult or None"
            )
        if room_areas is None and same_view_room_areas is None:
            raise ValueError("at least one documented room-area result is required")
        if type(floors) is not LiveCanonicalFloorSurfaceComposition:
            raise TypeError(
                "floors must be LiveCanonicalFloorSurfaceComposition"
            )
        self._source = source
        self._room_areas = room_areas
        self._same_view_room_areas = same_view_room_areas
        self._floors = floors
        self._physical_plan_page_ids = _physical_plan_page_ids

    @classmethod
    def from_source(
        cls,
        *,
        source: SourceVisibilityProducer,
        room_areas: Optional[CrossViewRoomAreaResult],
        floors: LiveCanonicalFloorSurfaceComposition,
        same_view_room_areas: Optional[SameViewRoomAreaResult] = None,
    ) -> "CrossViewFloorFinishProducer":
        return cls(
            source=source,
            room_areas=room_areas,
            floors=floors,
            same_view_room_areas=same_view_room_areas,
            _seal=_PRODUCER_SEAL,
        )

    @classmethod
    def for_source_owned_plan_view_shadow(
        cls,
        *,
        source: SourceVisibilityProducer,
        room_areas: Optional[CrossViewRoomAreaResult],
        floors: LiveCanonicalFloorSurfaceComposition,
        page_ids: Sequence[str],
        same_view_room_areas: Optional[SameViewRoomAreaResult] = None,
    ) -> "CrossViewFloorFinishProducer":
        """Explicit consumer of source-owned plan products; commercial default untouched."""
        if (
            not isinstance(page_ids, (tuple, list))
            or not page_ids
            or any(
                type(page) is not str or not page.isdecimal()
                or int(page) <= 0 or str(int(page)) != page
                for page in page_ids
            )
        ):
            raise ValueError("page_ids must be nonempty canonical page IDs")
        return cls(
            source=source,
            room_areas=room_areas,
            floors=floors,
            same_view_room_areas=same_view_room_areas,
            _physical_plan_page_ids=tuple(sorted(set(page_ids), key=int)),
            _seal=_PRODUCER_SEAL,
        )

    def publish(self) -> CrossViewFloorFinishResult:
        # Same-view documented area is supplemental. Preserve established
        # cross-view authority for a source room when both producers resolve,
        # exactly as the live room-area bridge does.
        area_by_source_room, disputed_area_source_ids = (
            _unique_documented_area_owner_receipts(
                self._same_view_room_areas.records
                if self._same_view_room_areas is not None else (),
                self._room_areas.records
                if self._room_areas is not None else (),
            )
        )
        area_records = tuple(
            area_by_source_room[key]
            for key in sorted(area_by_source_room)
        )
        unresolved_disputed_area_floors = {
            floor.canonical_floor_id
            for floor in self._floors.floors
            if floor.source_room_face_record_id in disputed_area_source_ids
        }
        if not area_records:
            return CrossViewFloorFinishResult(
                status=(
                    EvidenceResolutionStatus.CONFLICT
                    if disputed_area_source_ids
                    else EvidenceResolutionStatus.ABSTAINED
                ),
                reason_codes=(
                    (CROSS_VIEW_FLOOR_FINISH_CONFLICT,)
                    if disputed_area_source_ids
                    else (CROSS_VIEW_FLOOR_FINISH_UNAVAILABLE,)
                ),
                records=(),
                unresolved_canonical_floor_ids=tuple(sorted(
                    unresolved_disputed_area_floors
                )),
            )

        document_ids: set[str] = set()
        revision_ids: set[str] = set()
        source_hashes: set[str] = set()
        for record in area_records:
            metadata = (
                record.area_evidence.metadata
                if isinstance(record.area_evidence.metadata, Mapping)
                else {}
            )
            document_id = _clean(record.area_evidence.document_id)
            revision = _clean(metadata.get("room_revision_id"))
            source_hash = _clean(metadata.get("source_sha256")).lower()
            if document_id:
                document_ids.add(document_id)
            if revision:
                revision_ids.add(revision)
            if source_hash:
                source_hashes.add(source_hash)
        if (
            len(document_ids) != 1
            or len(revision_ids) != 1
            or len(source_hashes) != 1
        ):
            return CrossViewFloorFinishResult(
                status=EvidenceResolutionStatus.CONFLICT,
                reason_codes=(CROSS_VIEW_FLOOR_FINISH_LINEAGE_CONFLICT,),
                records=(),
                unresolved_canonical_floor_ids=tuple(
                    sorted(
                        floor.canonical_floor_id
                        for floor in self._floors.floors
                    )
                ),
            )

        document_id = next(iter(document_ids))
        revision_id = next(iter(revision_ids))
        published = self._source.published_snapshot_for_revision(revision_id)
        if (
            published is None
            or published.revision.document_id != document_id
            or published.revision.revision_id != revision_id
            or published.revision.source_sha256.lower() != next(iter(source_hashes))
        ):
            return CrossViewFloorFinishResult(
                status=EvidenceResolutionStatus.CONFLICT,
                reason_codes=(CROSS_VIEW_FLOOR_FINISH_LINEAGE_CONFLICT,),
                records=(),
                unresolved_canonical_floor_ids=tuple(
                    sorted(
                        floor.canonical_floor_id
                        for floor in self._floors.floors
                    )
                ),
            )

        material_producer = (
            SourceMaterialSemanticProducer.for_physical_plan_view_shadow(
                self._source, page_ids=self._physical_plan_page_ids
            )
            if self._physical_plan_page_ids else
            SourceMaterialSemanticProducer.from_source_visibility_producer(
                self._source
            )
        )
        material_authority = material_producer.publish(revision_id)
        occurrence_results = material_producer.published_occurrence_results()

        records: list[CrossViewFloorFinishRecord] = []
        unresolved: set[str] = set(unresolved_disputed_area_floors)
        conflict = bool(disputed_area_source_ids)

        # Cross-view fallback: a floor-finish plan may carry the room label and
        # finish code separately from the figured-dimension view that measured
        # the room. Bind only through exact native source ownership: one unique
        # documented-room label, one authenticated FLOOR_FINISH_PLAN viewport,
        # and one material occurrence in the exact same native block.
        by_label: dict[
            str,
            list[CrossViewRoomAreaRecord | SameViewRoomAreaRecord],
        ] = {}
        for area_record in area_records:
            label = _norm(area_record.room_label)
            if label:
                by_label.setdefault(label, []).append(area_record)
        unique_area_by_label = {
            label: rows[0]
            for label, rows in by_label.items()
            if len(rows) == 1
        }

        cross_view_candidates: dict[
            str,
            list[
                tuple[
                    SourceMaterialOccurrenceRecord,
                    SourceMaterialDefinitionRecord,
                    object,
                    object,
                ]
            ],
        ] = {}
        floor_finish_viewports = (
            _source_owned_floor_finish_viewports(
                material_producer,
                published=published,
                permitted_page_ids=self._physical_plan_page_ids,
            )
            if self._physical_plan_page_ids else
            _floor_finish_viewports(
                self._source, revision_id=revision_id,
            )
        )
        if floor_finish_viewports and unique_area_by_label:
            support_page_ids = tuple(
                sorted({page_id for page_id, _viewport_id in floor_finish_viewports})
            )
            trusted_labels = _trusted_room_labels_for_pages(
                self._source,
                revision_id=revision_id,
                page_ids=support_page_ids,
                candidate_labels=tuple(unique_area_by_label),
            )
            label_lines_by_view: dict[tuple[str, str], list[tuple[object, str]]] = {}
            for (page_id, viewport_id), viewport_bbox in floor_finish_viewports.items():
                for line in trusted_labels.get(page_id, ()):
                    label = _norm(line.text)
                    if (
                        label not in unique_area_by_label
                        or not _bbox_fully_inside(line.bbox, viewport_bbox)
                    ):
                        continue
                    label_lines_by_view.setdefault(
                        (page_id, viewport_id),
                        [],
                    ).append((line, label))

            for result in occurrence_results:
                if (
                    result.status is not EvidenceResolutionStatus.CORROBORATED
                    or not result.scope_complete
                ):
                    continue
                for occurrence in result.records:
                    key = (
                        _clean(occurrence.page_id),
                        _clean(occurrence.viewport_id),
                    )
                    viewport_bbox = floor_finish_viewports.get(key)
                    if (
                        viewport_bbox is None
                        or occurrence.semantic_finish not in _FLOOR_FINISH_SEMANTICS
                        or not _bbox_fully_inside(
                            occurrence.bbox_pdf_pts,
                            viewport_bbox,
                        )
                    ):
                        continue
                    definition_result = material_authority.resolve_definition(
                        SourceMaterialDefinitionSelector(
                            document_id=occurrence.document_id,
                            revision_id=occurrence.revision_id,
                            source_sha256=occurrence.source_sha256,
                            snapshot_id=occurrence.snapshot_id,
                            code=occurrence.code,
                        )
                    )
                    definition = definition_result.record
                    if (
                        definition_result.status
                        is not EvidenceResolutionStatus.CORROBORATED
                        or definition is None
                        or occurrence.snapshot_id != published.snapshot.snapshot_id
                        or definition.snapshot_id != published.snapshot.snapshot_id
                        or definition.record_id != occurrence.definition_record_id
                        or definition.semantic_finish != occurrence.semantic_finish
                        or not _definition_is_floor_finish(definition)
                    ):
                        continue
                    occurrence_line = _cross_view_occurrence_line(
                        self._source,
                        revision_id=revision_id,
                        occurrence=occurrence,
                    )
                    if occurrence_line is None:
                        continue
                    same_block_labels = [
                        (line, label)
                        for line, label in label_lines_by_view.get(key, ())
                        if (
                            line.source_partition_id
                            == occurrence_line.source_partition_id
                            and line.block_no == occurrence_line.block_no
                        )
                    ]
                    labels = {label for _line, label in same_block_labels}
                    if len(labels) != 1:
                        if len(labels) > 1:
                            conflict = True
                        continue
                    label = next(iter(labels))
                    matching_label_lines = [
                        line
                        for line, candidate_label in same_block_labels
                        if candidate_label == label
                    ]
                    if len(matching_label_lines) != 1:
                        conflict = True
                        continue
                    area_record = unique_area_by_label[label]
                    cross_view_candidates.setdefault(
                        area_record.physical_room_id,
                        [],
                    ).append(
                        (
                            occurrence,
                            definition,
                            occurrence_line,
                            matching_label_lines[0],
                        )
                    )

        for area_record in area_records:
            floor = _matching_floor(self._floors, area_record)
            if floor is None:
                expected = _expected_floor_id(
                    document_id=area_record.area_evidence.document_id,
                    physical_room_id=area_record.physical_room_id,
                )
                unresolved.add(expected)
                continue
            box = _dimension_box(area_record)
            if box is None:
                unresolved.add(floor.canonical_floor_id)
                continue

            candidates: list[
                tuple[
                    SourceMaterialOccurrenceRecord,
                    SourceMaterialDefinitionRecord,
                ]
            ] = []
            for occurrence in _occurrences_on_page(
                occurrence_results,
                page_id=area_record.source_dimension_page_id,
            ):
                if occurrence.semantic_finish not in _FLOOR_FINISH_SEMANTICS:
                    continue
                if not _bbox_fully_inside(occurrence.bbox_pdf_pts, box):
                    continue
                definition_result = material_authority.resolve_definition(
                    SourceMaterialDefinitionSelector(
                        document_id=occurrence.document_id,
                        revision_id=occurrence.revision_id,
                        source_sha256=occurrence.source_sha256,
                        snapshot_id=occurrence.snapshot_id,
                        code=occurrence.code,
                    )
                )
                definition = definition_result.record
                if (
                    definition_result.status
                    is not EvidenceResolutionStatus.CORROBORATED
                    or definition is None
                    or occurrence.snapshot_id != published.snapshot.snapshot_id
                    or definition.snapshot_id != published.snapshot.snapshot_id
                    or definition.record_id != occurrence.definition_record_id
                    or definition.semantic_finish != occurrence.semantic_finish
                    or not _definition_is_floor_finish(definition)
                ):
                    continue
                candidates.append((occurrence, definition))

            binding_mode = "dimension_box"
            support_source_partition_id = ""
            support_block_no = None
            if len(candidates) > 1:
                unresolved.add(floor.canonical_floor_id)
                conflict = True
                continue
            if len(candidates) == 1:
                occurrence, definition = candidates[0]
                # The explicit source-owned F07 shadow authenticates the
                # finish DRAWING, not cross-sheet PHYSICAL room equivalence.
                # A p11 mark inside p11 figured dimensions cannot silently
                # become a p7 physical-floor material without an independent
                # source wall/room correspondence producer. Preserve the
                # ordinary existing consumer unmodified.
                if not _source_owned_mark_eligible_for_existing_physical_floor(
                    floor=floor,
                    occurrence=occurrence,
                    source_owned_shadow=bool(self._physical_plan_page_ids),
                ):
                    unresolved.add(floor.canonical_floor_id)
                    continue
            else:
                # A native text block can span several physical spaces. An
                # identical room label on two pages and a code in its text
                # block do not establish physical wall, source-room-face or
                # canonical-floor equivalence. Keep all exact-block candidate
                # observations for diagnosis, but do not turn them into
                # commercial floor-finish area without a separately proven
                # cross-page *physical* owner. The dimension-box path above
                # is unchanged and retains authenticated same-view output.
                owned = cross_view_candidates.get(area_record.physical_room_id, ())
                unresolved.add(floor.canonical_floor_id)
                if len(owned) > 1:
                    conflict = True
                continue
            area_value = _area_value(area_record)
            if area_value is None:
                unresolved.add(floor.canonical_floor_id)
                continue
            area_metadata = (
                area_record.area_evidence.metadata
                if isinstance(area_record.area_evidence.metadata, Mapping)
                else {}
            )
            figured_dimension_ids = tuple(
                sorted(
                    {
                        _clean(value)
                        for value in (
                            area_metadata.get("figured_dimension_ids") or ()
                        )
                        if _clean(value)
                    }
                )
            )
            if len(figured_dimension_ids) != 2:
                unresolved.add(floor.canonical_floor_id)
                continue

            evidence_ids = tuple(
                dict.fromkeys(
                    (
                        *(
                            _clean(value)
                            for value in floor.evidence_ids
                            if _clean(value)
                        ),
                        area_record.area_evidence.evidence_id,
                        occurrence.source_evidence_id,
                        *definition.source_definition_ids,
                    )
                )
            )
            quantity_payload = {
                "family": "floor_finish_area",
                "canonical_floor_id": floor.canonical_floor_id,
                "area_evidence_id": area_record.area_evidence.evidence_id,
                "finish_occurrence_record_id": occurrence.record_id,
                "finish_definition_record_id": definition.record_id,
                "value_m2": round(area_value, 6),
            }
            quantity = QuantityEvidence(
                quantity_id=stable_contract_id(
                    "qty_floor_finish_area",
                    quantity_payload,
                    digest_chars=32,
                ),
                family="floor_finish_area",
                semantic_key=(
                    f"floor_finish_area:{floor.canonical_floor_id}:"
                    f"{occurrence.code}:{occurrence.semantic_finish}"
                ),
                value=round(area_value, 6),
                unit="m2",
                input_entity_ids=(floor.canonical_floor_id,),
                formula="authenticated_cross_view_room_area_with_source_finish",
                formula_version=CROSS_VIEW_FLOOR_FINISH_SCHEMA_VERSION,
                evidence_ids=evidence_ids,
                authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
                status=AuthorityStatus.FIRM.value,
                confidence=1.0,
                abstained=False,
                reason_codes=(CROSS_VIEW_FLOOR_FINISH_QUANTITY_RESOLVED,),
                metadata={
                    "source_sha256": floor.source_sha256,
                    "revision_id": floor.revision_id,
                    "page_no": floor.page_id,
                    "viewport_id": floor.viewport_id,
                    "source_dimension_page_id": area_record.source_dimension_page_id,
                    "room_label": area_record.room_label,
                    "figured_dimension_ids": list(figured_dimension_ids),
                    "canonical_floor_id": floor.canonical_floor_id,
                    "physical_floor_surface_id": floor.physical_floor_surface_id,
                    "source_room_face_record_id": floor.source_room_face_record_id,
                    "finish_code": occurrence.code,
                    "semantic_finish": occurrence.semantic_finish,
                    "support_snapshot_id": published.snapshot.snapshot_id,
                    "support_page_id": occurrence.page_id,
                    "support_viewport_id": occurrence.viewport_id,
                    "support_source_partition_id": support_source_partition_id,
                    "support_block_no": support_block_no,
                    "finish_binding_mode": binding_mode,
                    "finish_definition_record_id": definition.record_id,
                    "finish_occurrence_record_id": occurrence.record_id,
                    "finish_occurrence_evidence_id": occurrence.source_evidence_id,
                    "finish_occurrence_bbox_pdf_pts": list(
                        occurrence.bbox_pdf_pts
                    ),
                    "section": "Internal",
                    "element": "Floor finish area",
                    "location": area_record.room_label,
                    "substrate": "Other",
                    "finish_system": occurrence.semantic_finish,
                    "inclusion_status": "INCLUSION",
                    "row_role": "floor_area",
                },
            )
            records.append(
                CrossViewFloorFinishRecord(
                    physical_room_id=area_record.physical_room_id,
                    source_room_face_record_id=area_record.source_room_face_record_id,
                    canonical_floor_id=floor.canonical_floor_id,
                    physical_floor_surface_id=floor.physical_floor_surface_id,
                    source_dimension_page_id=area_record.source_dimension_page_id,
                    finish_code=occurrence.code,
                    semantic_finish=occurrence.semantic_finish,
                    definition_record_id=definition.record_id,
                    occurrence_record_id=occurrence.record_id,
                    occurrence_evidence_id=occurrence.source_evidence_id,
                    occurrence_bbox_pdf_pts=occurrence.bbox_pdf_pts,
                    support_snapshot_id=published.snapshot.snapshot_id,
                    quantity=quantity,
                    _seal=_RECORD_SEAL,
                )
            )

        # The per-floor candidate gate also needs its inverse: one exact
        # material occurrence is not a valid owner for multiple physical
        # floor identities. Never publish either contested commercial row.
        unique_records, disputed_floor_ids = (
            _quarantine_reused_floor_finish_occurrences(records)
        )
        if disputed_floor_ids:
            unresolved.update(disputed_floor_ids)
            conflict = True
        records = list(unique_records)
        records.sort(key=lambda record: record.canonical_floor_id)
        unresolved_ids = tuple(sorted(unresolved))
        if records and not unresolved_ids:
            status = EvidenceResolutionStatus.CORROBORATED
            reasons = (CROSS_VIEW_FLOOR_FINISH_RESOLVED,)
        elif records:
            status = EvidenceResolutionStatus.CANDIDATE
            reasons = (CROSS_VIEW_FLOOR_FINISH_PARTIAL,)
        elif conflict:
            status = EvidenceResolutionStatus.CONFLICT
            reasons = (CROSS_VIEW_FLOOR_FINISH_CONFLICT,)
        else:
            status = EvidenceResolutionStatus.ABSTAINED
            reasons = (
                CROSS_VIEW_FLOOR_FINISH_OCCURRENCE_UNAVAILABLE,
                CROSS_VIEW_FLOOR_FINISH_DEFINITION_UNAVAILABLE,
            )
        return CrossViewFloorFinishResult(
            status=status,
            reason_codes=reasons,
            records=tuple(records),
            unresolved_canonical_floor_ids=unresolved_ids,
        )


def enrich_live_canonical_floor_finishes(
    floors: LiveCanonicalFloorSurfaceComposition,
    finishes: CrossViewFloorFinishResult,
) -> LiveCanonicalFloorSurfaceComposition:
    """Attach resolved finish semantics/evidence to the same canonical floors."""

    if type(floors) is not LiveCanonicalFloorSurfaceComposition:
        raise TypeError("floors must be LiveCanonicalFloorSurfaceComposition")
    if type(finishes) is not CrossViewFloorFinishResult:
        raise TypeError("finishes must be CrossViewFloorFinishResult")

    # The public result may have been reconstructed from individually valid
    # producer records with rekeyed physical owners. Enrichment must consume
    # the same cross-room-quarantined view as downstream QuantityEvidence, not
    # the raw tuple which can contain aliases of one source material mark.
    eligible = finishes.records_by_floor_id
    by_floor: dict[str, list[CrossViewFloorFinishRecord]] = {
        floor_id: [record] for floor_id, record in eligible.items()
    }
    enriched: list[LiveCanonicalFloorSurfaceObject] = []
    conflict = len(eligible) != len(finishes.records)
    resolved = 0
    for floor in floors.floors:
        matches = by_floor.get(floor.canonical_floor_id, ())
        if len(matches) > 1:
            conflict = True
            enriched.append(floor)
            continue
        if not matches:
            enriched.append(floor)
            continue
        record = matches[0]
        # Canonical floor ID agreement is necessary, not sufficient. Every
        # producer-owned floor finish must retain exactly the same physical
        # source room, floor surface and QuantityEvidence input ancestry.
        physical_room_id = getattr(record, "physical_room_id", None)
        quantity_inputs = getattr(
            getattr(record, "quantity", None), "input_entity_ids", None
        )
        if (
            not isinstance(physical_room_id, str) or not physical_room_id
            or physical_room_id != physical_room_id.strip()
            or record.physical_floor_surface_id != floor.physical_floor_surface_id
            or record.source_room_face_record_id != floor.source_room_face_record_id
            or _expected_floor_id(
                document_id=floor.document_id,
                physical_room_id=physical_room_id,
            ) != floor.canonical_floor_id
            or quantity_inputs != (floor.canonical_floor_id,)
        ):
            conflict = True
            enriched.append(floor)
            continue
        if floor.finish_descriptor not in (None, "", record.semantic_finish):
            conflict = True
            enriched.append(floor)
            continue
        enriched.append(
            replace(
                floor,
                finish_descriptor=record.semantic_finish,
                evidence_ids=tuple(
                    dict.fromkeys(
                        (
                            *floor.evidence_ids,
                            *record.quantity.evidence_ids,
                        )
                    )
                ),
                # A finish-specific firm QuantityEvidence now exists, but the
                # canonical surface itself still does not bypass commercial
                # review/signoff gates.
                commercial_quantity_authority=False,
            )
        )
        resolved += 1

    if conflict:
        return LiveCanonicalFloorSurfaceComposition(
            status=EvidenceResolutionStatus.CONFLICT,
            reason_codes=(CROSS_VIEW_FLOOR_FINISH_CONFLICT,),
            floors=tuple(enriched),
            source_pages=floors.source_pages,
        )
    if resolved == len(floors.floors) and resolved:
        return LiveCanonicalFloorSurfaceComposition(
            status=floors.status,
            reason_codes=(
                *floors.reason_codes,
                CROSS_VIEW_FLOOR_FINISH_RESOLVED,
            ),
            floors=tuple(enriched),
            source_pages=floors.source_pages,
        )
    if resolved:
        return LiveCanonicalFloorSurfaceComposition(
            status=EvidenceResolutionStatus.CANDIDATE,
            reason_codes=(
                *floors.reason_codes,
                CROSS_VIEW_FLOOR_FINISH_PARTIAL,
            ),
            floors=tuple(enriched),
            source_pages=floors.source_pages,
        )
    return floors


__all__ = [
    "CROSS_VIEW_FLOOR_FINISH_CONFLICT",
    "CROSS_VIEW_FLOOR_FINISH_DEFINITION_UNAVAILABLE",
    "CROSS_VIEW_FLOOR_FINISH_LINEAGE_CONFLICT",
    "CROSS_VIEW_FLOOR_FINISH_OCCURRENCE_UNAVAILABLE",
    "CROSS_VIEW_FLOOR_FINISH_PARTIAL",
    "CROSS_VIEW_FLOOR_FINISH_QUANTITY_RESOLVED",
    "CROSS_VIEW_FLOOR_FINISH_RESOLVED",
    "CROSS_VIEW_FLOOR_FINISH_SCHEMA_VERSION",
    "CROSS_VIEW_FLOOR_FINISH_UNAVAILABLE",
    "CrossViewFloorFinishProducer",
    "CrossViewFloorFinishRecord",
    "CrossViewFloorFinishResult",
    "enrich_live_canonical_floor_finishes",
]
