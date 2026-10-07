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
    *,
    line_by_id: Optional[dict[str, tuple[float, float, float, float]]] = None,
    unit_by_id: Optional[dict[str, tuple[float, float]]] = None,
    endpoint_index: Optional[
        dict[tuple[int, int], tuple[SourceObservationRecord, ...]]
    ] = None,
) -> Optional[SourceObservationRecord]:
    jamb_line = (
        line_by_id.get(jamb.observation_id)
        if line_by_id is not None
        else _line(jamb)
    )
    if jamb_line is None:
        return None
    jamb_endpoints = _endpoints(jamb_line)
    jamb_unit = (
        unit_by_id.get(jamb.observation_id)
        if unit_by_id is not None
        else _unit(*jamb_endpoints)
    )

    candidate_records: Sequence[SourceObservationRecord] = records
    if endpoint_index is not None:
        bx = math.floor(float(dimension_point[0]) / _COORD_TOL)
        by = math.floor(float(dimension_point[1]) / _COORD_TOL)
        indexed: dict[str, SourceObservationRecord] = {}
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for record in endpoint_index.get((bx + dx, by + dy), ()):
                    indexed[record.observation_id] = record
        candidate_records = tuple(indexed.values())

    matches: list[SourceObservationRecord] = []
    for record in candidate_records:
        if record.observation_id in excluded_ids:
            continue
        geometry = (
            line_by_id.get(record.observation_id)
            if line_by_id is not None
            else _line(record)
        )
        record_unit = (
            unit_by_id.get(record.observation_id)
            if unit_by_id is not None
            else (_unit(*_endpoints(geometry)) if geometry is not None else None)
        )
        if (
            geometry is None
            or jamb_unit is None
            or record_unit is None
            or abs(_cross(record_unit, jamb_unit)) > _PARALLEL_TOL
        ):
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
        physical_opening_authority: PhysicalOpeningAuthority | None = None,
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
        self._physical = (
            physical_opening_authority
            if physical_opening_authority is not None
            else PhysicalOpeningAuthority(visibility_authority)
        )
        self._visible_page_cache: dict[
            tuple[str, str, str, str, str], tuple[SourceObservationRecord, ...]
        ] = {}
        self._visible_geometry_cache: dict[
            tuple[str, str, str, str, str],
            tuple[
                dict[str, tuple[float, float, float, float]],
                dict[str, tuple[float, float]],
                dict[tuple[int, int], tuple[SourceObservationRecord, ...]],
            ],
        ] = {}
        self._trusted_text_snapshot_cache: dict[
            tuple[str, str, str, str],
            tuple[
                bool,
                dict[str, tuple[tuple[str, str, tuple[float, ...]], ...]],
            ],
        ] = {}

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
        cache_key = (
            existence.document_id,
            existence.revision_id,
            existence.source_sha256,
            existence.snapshot_id,
            str(existence.page_id),
        )
        cached = self._visible_page_cache.get(cache_key)
        if cached is not None:
            return cached
        records: list[SourceObservationRecord] = []
        page_ids = self._visibility.visible_observation_ids_for_page(
            existence.snapshot_id,
            str(existence.page_id),
        )
        for observation_id in snapshot_ids:
            if str(observation_id) not in page_ids:
                continue
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
        resolved = tuple(records)
        self._visible_page_cache[cache_key] = resolved
        return resolved

    def _visible_geometry_index(
        self,
        existence: PhysicalOpeningExistenceRecord,
        records: Sequence[SourceObservationRecord],
    ) -> tuple[
        dict[str, tuple[float, float, float, float]],
        dict[str, tuple[float, float]],
        dict[tuple[int, int], tuple[SourceObservationRecord, ...]],
    ]:
        cache_key = (
            existence.document_id,
            existence.revision_id,
            existence.source_sha256,
            existence.snapshot_id,
            str(existence.page_id),
        )
        cached = self._visible_geometry_cache.get(cache_key)
        if cached is not None:
            return cached

        line_by_id: dict[str, tuple[float, float, float, float]] = {}
        unit_by_id: dict[str, tuple[float, float]] = {}
        endpoint_rows: dict[
            tuple[int, int], list[SourceObservationRecord]
        ] = {}
        for record in records:
            geometry = _line(record)
            if geometry is None:
                continue
            line_by_id[record.observation_id] = geometry
            direction = _unit(*_endpoints(geometry))
            if direction is not None:
                unit_by_id[record.observation_id] = direction
            for x, y in _endpoints(geometry):
                key = (
                    math.floor(float(x) / _COORD_TOL),
                    math.floor(float(y) / _COORD_TOL),
                )
                endpoint_rows.setdefault(key, []).append(record)

        resolved = (
            line_by_id,
            unit_by_id,
            {key: tuple(rows) for key, rows in endpoint_rows.items()},
        )
        self._visible_geometry_cache[cache_key] = resolved
        return resolved

    def _trusted_text_snapshot(
        self,
        existence: PhysicalOpeningExistenceRecord,
        snapshot_ids: Sequence[str],
    ) -> tuple[
        bool,
        dict[str, tuple[tuple[str, str, tuple[float, ...]], ...]],
    ]:
        cache_key = (
            existence.document_id,
            existence.revision_id,
            existence.source_sha256,
            existence.snapshot_id,
        )
        cached = self._trusted_text_snapshot_cache.get(cache_key)
        if cached is not None:
            return cached
        integrity_conflict = False
        by_page: dict[str, list[tuple[str, str, tuple[float, ...]]]] = {}
        text_ids = self._text.observation_ids_for_snapshot(
            existence.snapshot_id
        )
        for observation_id in snapshot_ids:
            if str(observation_id) not in text_ids:
                continue
            result = self._text.resolve_text(
                ObservationSelector(
                    document_id=existence.document_id,
                    revision_id=existence.revision_id,
                    source_sha256=existence.source_sha256,
                    snapshot_id=existence.snapshot_id,
                    observation_id=observation_id,
                )
            )
            if result.status is EvidenceResolutionStatus.CONFLICT:
                integrity_conflict = True
                continue
            if (
                result.status is EvidenceResolutionStatus.CORROBORATED
                and result.trusted_text is not None
                and result.receipt is not None
            ):
                by_page.setdefault(str(result.receipt.page_id), []).append(
                    (
                        observation_id,
                        result.trusted_text,
                        tuple(float(value) for value in result.receipt.geometry),
                    )
                )
        resolved = (
            integrity_conflict,
            {page_id: tuple(rows) for page_id, rows in by_page.items()},
        )
        self._trusted_text_snapshot_cache[cache_key] = resolved
        return resolved

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
        line_by_id, unit_by_id, endpoint_index = self._visible_geometry_index(
            existence,
            all_visible,
        )
        support_ids = set(existence.source_observation_ids)
        candidates: list[
            tuple[SourceObservationRecord, SourceObservationRecord, SourceObservationRecord]
        ] = []
        for record in all_visible:
            if record.observation_id in support_ids:
                continue
            geometry = line_by_id.get(record.observation_id)
            if geometry is None:
                continue
            dimension_axis = unit_by_id.get(record.observation_id)
            if dimension_axis is None or abs(_cross(dimension_axis, axis)) > _PARALLEL_TOL:
                continue
            if not _matches_endpoint_set(geometry, jambs, axis):
                continue
            associations = _endpoint_associations(geometry, jambs)
            if associations is None:
                continue
            excluded = support_ids | {record.observation_id}
            first_witness = _witness_for(
                associations[0][0],
                associations[0][1],
                all_visible,
                excluded,
                line_by_id=line_by_id,
                unit_by_id=unit_by_id,
                endpoint_index=endpoint_index,
            )
            second_witness = _witness_for(
                associations[1][0],
                associations[1][1],
                all_visible,
                excluded,
                line_by_id=line_by_id,
                unit_by_id=unit_by_id,
                endpoint_index=endpoint_index,
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
        text_integrity_conflict, trusted_text_by_page = self._trusted_text_snapshot(
            existence,
            source_result.snapshot.observation_ids,
        )
        trusted_rows = trusted_text_by_page.get(str(existence.page_id), ())
        trusted_text_seen = bool(trusted_rows)
        for observation_id, trusted_text, receipt_geometry in trusted_rows:
            value = _numeric_dimension_mm(trusted_text)
            if value is None:
                continue
            if not _bbox_bound_to_dimension_line(
                receipt_geometry, dimension_geometry, axis
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
