"""Producer-bound figured opening-dimension authority.

The authority is deliberately narrow. A width can be corroborated only when:
1. the supplied selector independently proves one G17 physical opening;
2. the same authenticated snapshot contains an explicit dimension line whose
   endpoints align with the two proven jamb axes;
3. two visible witness lines connect that dimension line to the jambs; and
4. producer-owned PDF text-integrity authority corroborates a numeric figured
   label bound to that dimension line.

No geometric gap is converted to millimetres. No schedule row, nearest text,
default size, inferred height, host binding, deduction, commercial quantity or
JobHub publication is authorized here.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Iterable, Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_pdf_text_integrity_authority import PdfTextIntegrityAuthority
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PhysicalOpeningAuthority,
    PhysicalOpeningExistenceRecord,
)
from pb_source_observation_authority import ObservationSelector, SourceObservationRecord
from pb_source_visibility_authority import SourceVisibilityAuthority


OPENING_WIDTH_RESOLVED = "opening_width_resolved"
OPENING_WIDTH_UNRESOLVED = "opening_width_unresolved"
OPENING_HEIGHT_UNRESOLVED = "opening_height_unresolved"
OPENING_DIMENSION_EXISTENCE_REQUIRED = "opening_dimension_existence_required"
OPENING_DIMENSION_JAMBS_UNRESOLVED = "opening_dimension_jambs_unresolved"
OPENING_DIMENSION_WITNESS_TOPOLOGY_REQUIRED = "opening_dimension_witness_topology_required"
OPENING_DIMENSION_TRUSTED_TEXT_REQUIRED = "opening_dimension_trusted_text_required"
OPENING_DIMENSION_TEXT_BINDING_REQUIRED = "opening_dimension_text_binding_required"
OPENING_DIMENSION_TEXT_CONFLICT = "opening_dimension_text_conflict"
OPENING_DIMENSION_TEXT_INTEGRITY_CONFLICT = "opening_dimension_text_integrity_conflict"
OPENING_HEIGHT_EVIDENCE_UNAVAILABLE = "opening_height_evidence_unavailable"

_COORD_TOL = 1e-6
_PARALLEL_TOL = 1e-9
_NUMERIC_DIMENSION_RE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*$")
_OPENING_DIMENSION_AUTHORITY_SEAL = object()


@dataclass(frozen=True)
class OpeningDimensionResult:
    status: EvidenceResolutionStatus
    proposition: Optional[str]
    value_mm: Optional[float]
    axis: str
    reason_codes: tuple[str, ...]
    dimension_record_id: Optional[str] = None
    opening_existence_record: Optional[PhysicalOpeningExistenceRecord] = None
    source_observation_ids: tuple[str, ...] = ()
    text_observation_id: Optional[str] = None


def _point_close(left: tuple[float, float], right: tuple[float, float]) -> bool:
    return abs(left[0] - right[0]) <= _COORD_TOL and abs(left[1] - right[1]) <= _COORD_TOL


def _line(record: SourceObservationRecord) -> Optional[tuple[float, float, float, float]]:
    if len(record.geometry) != 4:
        return None
    try:
        result = tuple(float(value) for value in record.geometry)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in result):
        return None
    if math.hypot(result[2] - result[0], result[3] - result[1]) <= _COORD_TOL:
        return None
    return result  # type: ignore[return-value]


def _endpoints(line: Sequence[float]) -> tuple[tuple[float, float], tuple[float, float]]:
    return ((float(line[0]), float(line[1])), (float(line[2]), float(line[3])))


def _midpoint(line: Sequence[float]) -> tuple[float, float]:
    return ((float(line[0]) + float(line[2])) / 2.0, (float(line[1]) + float(line[3])) / 2.0)


def _unit(first: tuple[float, float], second: tuple[float, float]) -> Optional[tuple[float, float]]:
    dx, dy = second[0] - first[0], second[1] - first[1]
    length = math.hypot(dx, dy)
    if length <= _COORD_TOL:
        return None
    return (dx / length, dy / length)


def _cross(left: tuple[float, float], right: tuple[float, float]) -> float:
    return left[0] * right[1] - left[1] * right[0]


def _parallel(left: Sequence[float], right: Sequence[float]) -> bool:
    lu = _unit(*_endpoints(left))
    ru = _unit(*_endpoints(right))
    if lu is None or ru is None:
        return False
    return abs(_cross(lu, ru)) <= _PARALLEL_TOL


def _projection(point: tuple[float, float], axis: tuple[float, float]) -> float:
    return point[0] * axis[0] + point[1] * axis[1]


def _point_on_infinite_line(point: tuple[float, float], line: Sequence[float]) -> bool:
    first, second = _endpoints(line)
    direction = _unit(first, second)
    if direction is None:
        return False
    delta = (point[0] - first[0], point[1] - first[1])
    return abs(_cross(direction, delta)) <= _COORD_TOL


def _record_endpoint_degree(
    record: SourceObservationRecord,
    records: Sequence[SourceObservationRecord],
) -> tuple[int, int]:
    geometry = _line(record)
    if geometry is None:
        return (0, 0)
    first, second = _endpoints(geometry)
    counts = []
    for point in (first, second):
        count = 0
        for other in records:
            if other.observation_id == record.observation_id:
                continue
            other_line = _line(other)
            if other_line is None:
                continue
            if any(_point_close(point, candidate) for candidate in _endpoints(other_line)):
                count += 1
        counts.append(count)
    return (counts[0], counts[1])


def _proven_jambs(
    records: Sequence[SourceObservationRecord],
) -> tuple[SourceObservationRecord, SourceObservationRecord] | None:
    candidates = [
        record
        for record in records
        if min(_record_endpoint_degree(record, records)) >= 1
    ]
    if len(candidates) != 2:
        return None
    left, right = candidates
    left_line, right_line = _line(left), _line(right)
    if left_line is None or right_line is None or not _parallel(left_line, right_line):
        return None
    return (left, right)


def _matches_endpoint_set(
    line: Sequence[float],
    jambs: tuple[SourceObservationRecord, SourceObservationRecord],
    axis: tuple[float, float],
) -> bool:
    jamb_lines = tuple(_line(item) for item in jambs)
    if any(item is None for item in jamb_lines):
        return False
    jamb_mids = tuple(_midpoint(item) for item in jamb_lines if item is not None)
    expected = sorted(_projection(point, axis) for point in jamb_mids)
    actual = sorted(_projection(point, axis) for point in _endpoints(line))
    return all(abs(left - right) <= _COORD_TOL for left, right in zip(actual, expected))


def _endpoint_associations(
    dimension_line: Sequence[float],
    jambs: tuple[SourceObservationRecord, SourceObservationRecord],
) -> tuple[tuple[tuple[float, float], SourceObservationRecord], ...] | None:
    pairs: list[tuple[tuple[float, float], SourceObservationRecord]] = []
    for point in _endpoints(dimension_line):
        matches = [
            jamb
            for jamb in jambs
            if _line(jamb) is not None and _point_on_infinite_line(point, _line(jamb) or ())
        ]
        if len(matches) != 1:
            return None
        pairs.append((point, matches[0]))
    if pairs[0][1].observation_id == pairs[1][1].observation_id:
        return None
    return tuple(pairs)


def _witness_for(
    dimension_point: tuple[float, float],
    jamb: SourceObservationRecord,
    records: Sequence[SourceObservationRecord],
    excluded_ids: set[str],
) -> Optional[SourceObservationRecord]:
    jamb_line = _line(jamb)
    if jamb_line is None:
        return None
    jamb_endpoints = _endpoints(jamb_line)
    matches: list[SourceObservationRecord] = []
    for record in records:
        if record.observation_id in excluded_ids:
            continue
        geometry = _line(record)
        if geometry is None or not _parallel(geometry, jamb_line):
            continue
        first, second = _endpoints(geometry)
        if _point_close(first, dimension_point) and any(
            _point_close(second, point) for point in jamb_endpoints
        ):
            matches.append(record)
        elif _point_close(second, dimension_point) and any(
            _point_close(first, point) for point in jamb_endpoints
        ):
            matches.append(record)
    if len(matches) != 1:
        return None
    return matches[0]


def _bbox_bound_to_dimension_line(
    bbox: Sequence[float],
    line: Sequence[float],
    axis: tuple[float, float],
) -> bool:
    if len(bbox) != 4:
        return False
    try:
        x0, y0, x1, y1 = (float(value) for value in bbox)
    except (TypeError, ValueError):
        return False
    if not all(math.isfinite(value) for value in (x0, y0, x1, y1)):
        return False
    center = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
    first, second = _endpoints(line)
    low, high = sorted((_projection(first, axis), _projection(second, axis)))
    along = _projection(center, axis)
    if along < low - _COORD_TOL or along > high + _COORD_TOL:
        return False

    direction = _unit(first, second)
    if direction is None:
        return False
    corners = ((x0, y0), (x0, y1), (x1, y0), (x1, y1))
    distances = [
        abs(_cross(direction, (corner[0] - first[0], corner[1] - first[1])))
        for corner in corners
    ]
    glyph_scale = max(_COORD_TOL, min(abs(x1 - x0), abs(y1 - y0)))
    return min(distances) <= glyph_scale / 2.0 + _COORD_TOL


def _numeric_dimension_mm(text: str) -> Optional[float]:
    match = _NUMERIC_DIMENSION_RE.fullmatch(str(text or ""))
    if match is None:
        return None
    token = match.group(1).replace(",", ".")
    try:
        value = float(token)
    except ValueError:
        return None
    if not math.isfinite(value) or value <= 0.0:
        return None
    return value


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


class OpeningDimensionAuthority:
    """Read-only selector-based opening-dimension resolver minted by the producer."""

    def __init__(
        self,
        visibility_authority: SourceVisibilityAuthority,
        text_integrity_authority: PdfTextIntegrityAuthority,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _OPENING_DIMENSION_AUTHORITY_SEAL:
            raise TypeError(
                "OpeningDimensionAuthority must be obtained from "
                "SourceVisibilityProducer.opening_dimension_authority()"
            )
        if type(visibility_authority) is not SourceVisibilityAuthority:
            raise TypeError(
                "visibility_authority must be producer-owned SourceVisibilityAuthority"
            )
        if type(text_integrity_authority) is not PdfTextIntegrityAuthority:
            raise TypeError(
                "text_integrity_authority must be producer-owned PdfTextIntegrityAuthority"
            )
        self._visibility = visibility_authority
        self._text = text_integrity_authority
        self._physical = PhysicalOpeningAuthority(visibility_authority)

    def _unresolved(
        self,
        axis: str,
        reasons: Iterable[str],
        *,
        status: EvidenceResolutionStatus = EvidenceResolutionStatus.ABSTAINED,
        existence: PhysicalOpeningExistenceRecord | None = None,
    ) -> OpeningDimensionResult:
        return OpeningDimensionResult(
            status=status,
            proposition=None,
            value_mm=None,
            axis=axis,
            reason_codes=_dedupe(reasons),
            opening_existence_record=existence,
        )

    def _visible_records(
        self,
        existence: PhysicalOpeningExistenceRecord,
    ) -> tuple[SourceObservationRecord, ...]:
        records: list[SourceObservationRecord] = []
        for observation_id in existence.source_observation_ids:
            result = self._visibility.resolve_visible(
                ObservationSelector(
                    document_id=existence.document_id,
                    revision_id=existence.revision_id,
                    source_sha256=existence.source_sha256,
                    snapshot_id=existence.snapshot_id,
                    observation_id=observation_id,
                )
            )
            if (
                result.status is EvidenceResolutionStatus.CORROBORATED
                and result.observation is not None
            ):
                records.append(result.observation)
        return tuple(records)

    def _all_visible_records(
        self,
        existence: PhysicalOpeningExistenceRecord,
        snapshot_ids: Sequence[str],
    ) -> tuple[SourceObservationRecord, ...]:
        records: list[SourceObservationRecord] = []
        for observation_id in snapshot_ids:
            result = self._visibility.resolve_visible(
                ObservationSelector(
                    document_id=existence.document_id,
                    revision_id=existence.revision_id,
                    source_sha256=existence.source_sha256,
                    snapshot_id=existence.snapshot_id,
                    observation_id=observation_id,
                )
            )
            if (
                result.status is EvidenceResolutionStatus.CORROBORATED
                and result.observation is not None
                and result.observation.page_id == existence.page_id
            ):
                records.append(result.observation)
        return tuple(records)

    def resolve_width(self, selector: ObservationSelector) -> OpeningDimensionResult:
        if not isinstance(selector, ObservationSelector):
            raise TypeError("selector must be ObservationSelector")

        existence_result = self._physical.prove_existence(selector)
        existence = existence_result.existence_record
        if (
            existence_result.status is not EvidenceResolutionStatus.CORROBORATED
            or existence_result.proposition != PHYSICAL_OPENING_EXISTS
            or existence is None
        ):
            status = (
                EvidenceResolutionStatus.CONFLICT
                if existence_result.status is EvidenceResolutionStatus.CONFLICT
                else EvidenceResolutionStatus.ABSTAINED
            )
            return self._unresolved(
                "width",
                (OPENING_DIMENSION_EXISTENCE_REQUIRED, *existence_result.reason_codes),
                status=status,
            )

        source_result = existence_result.source_observation
        if source_result is None or source_result.snapshot is None:
            return self._unresolved(
                "width", (OPENING_DIMENSION_EXISTENCE_REQUIRED,), existence=existence
            )

        support = self._visible_records(existence)
        if len(support) != len(existence.source_observation_ids):
            return self._unresolved(
                "width", (OPENING_DIMENSION_EXISTENCE_REQUIRED,), existence=existence
            )
        jambs = _proven_jambs(support)
        if jambs is None:
            return self._unresolved(
                "width", (OPENING_DIMENSION_JAMBS_UNRESOLVED,), existence=existence
            )
        jamb_lines = tuple(_line(item) for item in jambs)
        assert jamb_lines[0] is not None and jamb_lines[1] is not None
        axis = _unit(_midpoint(jamb_lines[0]), _midpoint(jamb_lines[1]))
        if axis is None:
            return self._unresolved(
                "width", (OPENING_DIMENSION_JAMBS_UNRESOLVED,), existence=existence
            )

        all_visible = self._all_visible_records(
            existence, source_result.snapshot.observation_ids
        )
        support_ids = set(existence.source_observation_ids)
        candidates: list[
            tuple[SourceObservationRecord, SourceObservationRecord, SourceObservationRecord]
        ] = []
        for record in all_visible:
            if record.observation_id in support_ids:
                continue
            geometry = _line(record)
            if geometry is None:
                continue
            dimension_axis = _unit(*_endpoints(geometry))
            if dimension_axis is None or abs(_cross(dimension_axis, axis)) > _PARALLEL_TOL:
                continue
            if not _matches_endpoint_set(geometry, jambs, axis):
                continue
            associations = _endpoint_associations(geometry, jambs)
            if associations is None:
                continue
            excluded = support_ids | {record.observation_id}
            first_witness = _witness_for(
                associations[0][0], associations[0][1], all_visible, excluded
            )
            second_witness = _witness_for(
                associations[1][0], associations[1][1], all_visible, excluded
            )
            if first_witness is None or second_witness is None:
                continue
            if first_witness.observation_id == second_witness.observation_id:
                continue
            candidates.append((record, first_witness, second_witness))

        if len(candidates) != 1:
            reasons = (
                OPENING_DIMENSION_WITNESS_TOPOLOGY_REQUIRED,
                OPENING_DIMENSION_TEXT_CONFLICT if len(candidates) > 1 else "",
            )
            status = (
                EvidenceResolutionStatus.CONFLICT
                if len(candidates) > 1
                else EvidenceResolutionStatus.ABSTAINED
            )
            return self._unresolved("width", reasons, status=status, existence=existence)

        dimension_line, first_witness, second_witness = candidates[0]
        dimension_geometry = _line(dimension_line)
        assert dimension_geometry is not None

        bound_text: list[tuple[str, float]] = []
        text_integrity_conflict = False
        trusted_text_seen = False
        for observation_id in source_result.snapshot.observation_ids:
            text_result = self._text.resolve_text(
                ObservationSelector(
                    document_id=existence.document_id,
                    revision_id=existence.revision_id,
                    source_sha256=existence.source_sha256,
                    snapshot_id=existence.snapshot_id,
                    observation_id=observation_id,
                )
            )
            if text_result.status is EvidenceResolutionStatus.CONFLICT:
                text_integrity_conflict = True
                continue
            if (
                text_result.status is not EvidenceResolutionStatus.CORROBORATED
                or text_result.trusted_text is None
                or text_result.receipt is None
                or text_result.receipt.page_id != existence.page_id
            ):
                continue
            trusted_text_seen = True
            value = _numeric_dimension_mm(text_result.trusted_text)
            if value is None:
                continue
            if not _bbox_bound_to_dimension_line(
                text_result.receipt.geometry, dimension_geometry, axis
            ):
                continue
            bound_text.append((observation_id, value))

        if text_integrity_conflict:
            return self._unresolved(
                "width",
                (OPENING_DIMENSION_TEXT_INTEGRITY_CONFLICT,),
                status=EvidenceResolutionStatus.CONFLICT,
                existence=existence,
            )
        if not bound_text:
            reason = (
                OPENING_DIMENSION_TEXT_BINDING_REQUIRED
                if trusted_text_seen
                else OPENING_DIMENSION_TRUSTED_TEXT_REQUIRED
            )
            return self._unresolved("width", (reason,), existence=existence)

        distinct_values = sorted({round(value, 9) for _oid, value in bound_text})
        if len(distinct_values) != 1:
            return self._unresolved(
                "width",
                (OPENING_DIMENSION_TEXT_CONFLICT,),
                status=EvidenceResolutionStatus.CONFLICT,
                existence=existence,
            )

        value_mm = float(distinct_values[0])
        text_ids = tuple(sorted(oid for oid, _value in bound_text))
        source_ids = tuple(
            sorted(
                {
                    *existence.source_observation_ids,
                    dimension_line.observation_id,
                    first_witness.observation_id,
                    second_witness.observation_id,
                    *text_ids,
                }
            )
        )
        payload = {
            "opening_existence_record_id": existence.record_id,
            "axis": "width",
            "value_mm": value_mm,
            "source_observation_ids": source_ids,
        }
        return OpeningDimensionResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            proposition=OPENING_WIDTH_RESOLVED,
            value_mm=value_mm,
            axis="width",
            reason_codes=(OPENING_WIDTH_RESOLVED,),
            dimension_record_id=stable_contract_id(
                "opening_dimension", payload, digest_chars=32
            ),
            opening_existence_record=existence,
            source_observation_ids=source_ids,
            text_observation_id=text_ids[0] if len(text_ids) == 1 else None,
        )

    def resolve_height(self, selector: ObservationSelector) -> OpeningDimensionResult:
        if not isinstance(selector, ObservationSelector):
            raise TypeError("selector must be ObservationSelector")
        existence_result = self._physical.prove_existence(selector)
        existence = existence_result.existence_record
        if (
            existence_result.status is not EvidenceResolutionStatus.CORROBORATED
            or existence_result.proposition != PHYSICAL_OPENING_EXISTS
            or existence is None
        ):
            status = (
                EvidenceResolutionStatus.CONFLICT
                if existence_result.status is EvidenceResolutionStatus.CONFLICT
                else EvidenceResolutionStatus.ABSTAINED
            )
            return self._unresolved(
                "height",
                (OPENING_DIMENSION_EXISTENCE_REQUIRED, *existence_result.reason_codes),
                status=status,
            )
        return self._unresolved(
            "height", (OPENING_HEIGHT_EVIDENCE_UNAVAILABLE,), existence=existence
        )


__all__ = [
    "OpeningDimensionAuthority",
    "OpeningDimensionResult",
    "OPENING_DIMENSION_EXISTENCE_REQUIRED",
    "OPENING_DIMENSION_JAMBS_UNRESOLVED",
    "OPENING_DIMENSION_TEXT_BINDING_REQUIRED",
    "OPENING_DIMENSION_TEXT_CONFLICT",
    "OPENING_DIMENSION_TEXT_INTEGRITY_CONFLICT",
    "OPENING_DIMENSION_TRUSTED_TEXT_REQUIRED",
    "OPENING_DIMENSION_WITNESS_TOPOLOGY_REQUIRED",
    "OPENING_HEIGHT_EVIDENCE_UNAVAILABLE",
    "OPENING_HEIGHT_UNRESOLVED",
    "OPENING_WIDTH_RESOLVED",
    "OPENING_WIDTH_UNRESOLVED",
]
