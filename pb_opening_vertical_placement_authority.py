"""Producer-owned schedule-row and physical-opening vertical placement authority.

This module proves two separate propositions:

1. an exact producer-owned schedule row explicitly states rough/structural-opening
   bottom/sill and head/top positions with source-backed units; and
2. that row-level placement applies to an exact physical opening instance because
   ScheduleOpeningInstanceBindingAuthority proves the row<->opening relation.

It never assumes door sill = 0, never derives placement from height alone, and never
accepts caller-provided z0/z1, sill/head, units, raw text, confidence or proximity.
"""
from __future__ import annotations

import dataclasses
import math
import re
from collections.abc import Mapping, Sequence
from types import MappingProxyType

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_schedule_v171 import detect_header
from pb_schedule_opening_instance_binding_authority import (
    ScheduleOpeningInstanceBindingAuthority,
    ScheduleOpeningInstanceBindingSelector,
    _row_groups_for_page,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

VERTICAL_PLACEMENT_SCHEMA_VERSION = "1.0.0"

ROW_VERTICAL_PLACEMENT_RESOLVED = "schedule_row_vertical_placement_resolved"
ROW_VERTICAL_SOURCE_SCOPE_UNAVAILABLE = "schedule_row_vertical_source_scope_unavailable"
ROW_VERTICAL_PARTIAL_SOURCE_COVERAGE = "schedule_row_vertical_partial_source_coverage"
ROW_VERTICAL_ROW_UNAVAILABLE = "schedule_row_vertical_row_unavailable"
ROW_VERTICAL_ROW_AMBIGUOUS = "schedule_row_vertical_row_ambiguous"
ROW_VERTICAL_HEADER_UNAVAILABLE = "schedule_row_vertical_header_unavailable"
ROW_VERTICAL_BASIS_UNPROVEN = "schedule_row_vertical_basis_unproven"
ROW_VERTICAL_FIELD_UNAVAILABLE = "schedule_row_vertical_field_unavailable"
ROW_VERTICAL_UNITS_UNPROVEN = "schedule_row_vertical_units_unproven"
ROW_VERTICAL_UNITS_CONFLICT = "schedule_row_vertical_units_conflict"
ROW_VERTICAL_ORDER_INVALID = "schedule_row_vertical_order_invalid"

OPENING_VERTICAL_PLACEMENT_RESOLVED = "opening_vertical_placement_resolved"
OPENING_VERTICAL_UPSTREAM_INCONSISTENT = "opening_vertical_upstream_inconsistent"

_ROW_PRODUCER_SEAL = object()
_ROW_AUTHORITY_SEAL = object()
_OPENING_PRODUCER_SEAL = object()
_OPENING_AUTHORITY_SEAL = object()

_RowKey = tuple[str, str, str, str, str, tuple[str, ...]]
_OpeningKey = tuple[str, str, str, str, str, str]
_LogicalCell = tuple[str, float, float]

_MM_RE = re.compile(r"(?:\bmm\b|millimet(?:er|re)s?)", re.IGNORECASE)
_M_RE = re.compile(r"(?:\bmet(?:er|re)s?\b|(?<![A-Za-z])m\b)", re.IGNORECASE)
_POSITION_RE = re.compile(
    r"^\s*(?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*"
    r"(?:(?:mm|millimet(?:er|re)s?|m|met(?:er|re)s?))?\s*$",
    re.IGNORECASE,
)
# Authenticated words belonging to one printed schedule cell have the ordinary
# inter-word gap. Keep this conservative: over-splitting only abstains, whereas
# over-joining adjacent columns could assign the wrong physical semantics.
_HEADER_WORD_JOIN_GAP = 4.0
_COLUMN_COORD_TOL = 1e-6


def _require_nonempty(value: object, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be a non-empty string")
    return clean


def _unit_tokens(text: str) -> frozenset[str]:
    units: set[str] = set()
    if _MM_RE.search(text or ""):
        units.add("mm")
    if _M_RE.search(text or ""):
        units.add("m")
    return frozenset(units)


def _normalized_heading(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()


def _placement_kind(text: str) -> str | None:
    """Return bottom/top only for explicit rough/structural-opening semantics."""
    norm = _normalized_heading(text)
    words = set(norm.split())
    if not words:
        return None
    # A frame/leaf/clear measurement is a different physical proposition even if
    # another token happens to mention opening.
    if {"frame", "leaf", "clear"} & words:
        return None
    explicit_opening_basis = (
        ("rough" in words and "opening" in words)
        or ("structural" in words and "opening" in words)
    )
    if not explicit_opening_basis:
        return None
    bottom = bool({"sill", "bottom", "base"} & words)
    top = bool({"head", "top"} & words)
    if bottom == top:  # neither or contradictory/multi-semantic heading
        return None
    return "bottom" if bottom else "top"


def _parse_position_mm(header_text: str, cell_text: str) -> tuple[str, float | None, str | None]:
    units = set(_unit_tokens(header_text))
    units.update(_unit_tokens(cell_text))
    if not units:
        return ROW_VERTICAL_UNITS_UNPROVEN, None, None
    if len(units) != 1:
        return ROW_VERTICAL_UNITS_CONFLICT, None, None
    source_units = next(iter(units))
    clean = str(cell_text or "").replace(",", "").strip()
    match = _POSITION_RE.fullmatch(clean)
    if match is None:
        return ROW_VERTICAL_FIELD_UNAVAILABLE, None, source_units
    try:
        raw = float(match.group("value"))
    except ValueError:
        return ROW_VERTICAL_FIELD_UNAVAILABLE, None, source_units
    if not math.isfinite(raw):
        return ROW_VERTICAL_FIELD_UNAVAILABLE, None, source_units
    value_mm = raw if source_units == "mm" else raw * 1000.0
    if not math.isfinite(value_mm):
        return ROW_VERTICAL_FIELD_UNAVAILABLE, None, source_units
    return ROW_VERTICAL_PLACEMENT_RESOLVED, value_mm, source_units


def _row_words(row: Mapping[str, object]) -> tuple[tuple[str, float, float], ...]:
    """Return authenticated row words paired with their horizontal geometry."""
    tokens = [token.strip() for token in str(row.get("text", "")).split("\t")]
    bounds = row.get("bounds", ())
    if not isinstance(bounds, Sequence) or isinstance(bounds, (str, bytes)):
        return ()
    if len(tokens) != len(bounds):
        return ()

    words: list[tuple[str, float, float]] = []
    previous_left = -math.inf
    for token, raw_bound in zip(tokens, bounds):
        if not token:
            return ()
        if (
            not isinstance(raw_bound, Sequence)
            or isinstance(raw_bound, (str, bytes))
            or len(raw_bound) != 2
        ):
            return ()
        try:
            left, right = float(raw_bound[0]), float(raw_bound[1])
        except (TypeError, ValueError):
            return ()
        if not math.isfinite(left) or not math.isfinite(right) or right < left:
            return ()
        if left + _COLUMN_COORD_TOL < previous_left:
            return ()
        words.append((token, left, right))
        previous_left = left
    return tuple(words)


def _logical_header_cells(row: Mapping[str, object]) -> tuple[_LogicalCell, ...]:
    """Reconstruct printed schedule header cells from trusted word geometry."""
    words = _row_words(row)
    if not words:
        return ()

    cells: list[_LogicalCell] = []
    current_text, current_left, current_right = words[0]
    for token, left, right in words[1:]:
        if left - current_right <= _HEADER_WORD_JOIN_GAP:
            current_text = f"{current_text} {token}"
            current_right = max(current_right, right)
            continue
        cells.append((current_text, current_left, current_right))
        current_text, current_left, current_right = token, left, right
    cells.append((current_text, current_left, current_right))
    return tuple(cells)


def _logical_column_text(
    row: Mapping[str, object],
    header_cells: Sequence[_LogicalCell],
    column_index: int,
) -> str:
    """Reconstruct one data cell beneath the authenticated logical header."""
    words = _row_words(row)
    if not words or not header_cells or column_index < 0 or column_index >= len(header_cells):
        return ""

    current = header_cells[column_index]
    if column_index == 0:
        left_boundary = -math.inf
    else:
        previous = header_cells[column_index - 1]
        left_boundary = (previous[2] + current[1]) / 2.0
    if column_index == len(header_cells) - 1:
        right_boundary = math.inf
    else:
        following = header_cells[column_index + 1]
        right_boundary = (current[2] + following[1]) / 2.0

    selected: list[str] = []
    for token, left, right in words:
        center = (left + right) / 2.0
        if center + _COLUMN_COORD_TOL < left_boundary:
            continue
        if center - _COLUMN_COORD_TOL > right_boundary:
            continue
        selected.append(token)
    return " ".join(selected).strip()


@dataclasses.dataclass(frozen=True)
class ScheduleRowVerticalPlacementSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    schedule_page_id: str
    schedule_row_observation_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "schedule_page_id",
        ):
            _require_nonempty(getattr(self, name), name)
        if not self.schedule_row_observation_ids:
            raise ValueError("schedule_row_observation_ids must be non-empty")
        if len(set(self.schedule_row_observation_ids)) != len(self.schedule_row_observation_ids):
            raise ValueError("schedule_row_observation_ids must be unique")
        for observation_id in self.schedule_row_observation_ids:
            _require_nonempty(observation_id, "schedule_row_observation_id")

    @property
    def key(self) -> _RowKey:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.schedule_page_id,
            tuple(sorted(self.schedule_row_observation_ids)),
        )


@dataclasses.dataclass(frozen=True)
class ScheduleRowVerticalPlacementEvidence:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    schedule_page_id: str
    schedule_row_observation_ids: tuple[str, ...]
    header_observation_ids: tuple[str, ...]
    z0_mm: float
    z1_mm: float
    units: str
    bottom_source_units: str
    top_source_units: str
    bottom_basis_source: str
    top_basis_source: str
    raw_text: str
    schema_version: str = VERTICAL_PLACEMENT_SCHEMA_VERSION


@dataclasses.dataclass(frozen=True)
class ScheduleRowVerticalPlacementResult:
    status: EvidenceResolutionStatus
    reason_codes: frozenset[str]
    evidence: ScheduleRowVerticalPlacementEvidence | None = None
    schema_version: str = VERTICAL_PLACEMENT_SCHEMA_VERSION


def _row_blocked(status: EvidenceResolutionStatus, reason: str) -> ScheduleRowVerticalPlacementResult:
    return ScheduleRowVerticalPlacementResult(
        status=status,
        reason_codes=frozenset([reason]),
        evidence=None,
    )


class ScheduleRowVerticalPlacementAuthority:
    def __init__(
        self,
        results: Mapping[_RowKey, ScheduleRowVerticalPlacementResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _ROW_AUTHORITY_SEAL:
            raise ValueError("ScheduleRowVerticalPlacementAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: ScheduleRowVerticalPlacementSelector) -> ScheduleRowVerticalPlacementResult:
        if type(selector) is not ScheduleRowVerticalPlacementSelector:
            raise TypeError("selector must be ScheduleRowVerticalPlacementSelector")
        result = self._results.get(selector.key)
        if result is not None:
            return result
        return _row_blocked(EvidenceResolutionStatus.ABSTAINED, ROW_VERTICAL_ROW_UNAVAILABLE)


class ScheduleRowVerticalPlacementProducer:
    def __init__(
        self,
        visibility_producer: SourceVisibilityProducer,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _ROW_PRODUCER_SEAL:
            raise TypeError(
                "ScheduleRowVerticalPlacementProducer must be obtained from "
                "from_source_visibility_producer()"
            )
        if type(visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("visibility_producer must be producer-owned")
        self._visibility_producer = visibility_producer
        self._results: dict[_RowKey, ScheduleRowVerticalPlacementResult] = {}

    @classmethod
    def from_source_visibility_producer(
        cls,
        visibility_producer: SourceVisibilityProducer,
    ) -> "ScheduleRowVerticalPlacementProducer":
        return cls(visibility_producer, _seal=_ROW_PRODUCER_SEAL)

    def publish_scope(
        self,
        selector: ScheduleRowVerticalPlacementSelector,
    ) -> ScheduleRowVerticalPlacementResult:
        if type(selector) is not ScheduleRowVerticalPlacementSelector:
            raise TypeError("selector must be ScheduleRowVerticalPlacementSelector")
        key = selector.key
        existing = self._results.get(key)
        if existing is not None:
            return existing

        published = self._visibility_producer.published_snapshot_for_revision(selector.revision_id)
        if (
            published is None
            or published.revision.document_id != selector.document_id
            or published.revision.source_sha256 != selector.source_sha256
            or published.snapshot.snapshot_id != selector.snapshot_id
        ):
            return self._store(
                key,
                _row_blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    ROW_VERTICAL_SOURCE_SCOPE_UNAVAILABLE,
                ),
            )
        if published.coverage.state != "complete" or published.coverage.failed_pages:
            return self._store(
                key,
                _row_blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    ROW_VERTICAL_PARTIAL_SOURCE_COVERAGE,
                ),
            )

        text_integrity = self._visibility_producer.text_integrity_authority()
        page_words: list[tuple[str, str, tuple[float, ...]]] = []
        for observation_id in published.text_observation_ids:
            resolved = text_integrity.resolve_text(
                ObservationSelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    observation_id=observation_id,
                )
            )
            if (
                resolved.status is not EvidenceResolutionStatus.CORROBORATED
                or resolved.trusted_text is None
                or resolved.receipt is None
                or resolved.receipt.page_id != selector.schedule_page_id
            ):
                continue
            page_words.append(
                (
                    observation_id,
                    resolved.trusted_text,
                    tuple(float(value) for value in resolved.receipt.geometry),
                )
            )

        page_rows = _row_groups_for_page(page_words)
        target_ids = tuple(sorted(selector.schedule_row_observation_ids))
        target_matches = [
            (index, row, tuple(ids))
            for index, (row, ids) in enumerate(page_rows)
            if tuple(sorted(ids)) == target_ids
        ]
        if not target_matches:
            return self._store(
                key,
                _row_blocked(EvidenceResolutionStatus.ABSTAINED, ROW_VERTICAL_ROW_UNAVAILABLE),
            )
        if len(target_matches) != 1:
            return self._store(
                key,
                _row_blocked(EvidenceResolutionStatus.CONFLICT, ROW_VERTICAL_ROW_AMBIGUOUS),
            )
        target_index, target_row, _ = target_matches[0]

        # Re-prove that the exact target row belongs to exactly one contiguous native
        # schedule region. Header words are reconstructed into logical source columns;
        # caller-authored text and remote notes are never accepted.
        header_candidates: list[
            tuple[int, dict[str, object], tuple[str, ...], tuple[_LogicalCell, ...]]
        ] = []
        for index, (row, ids) in enumerate(page_rows[:target_index]):
            logical_cells = _logical_header_cells(row)
            if not logical_cells:
                continue
            mapping = detect_header([cell[0] for cell in logical_cells])
            if "mark" not in mapping and "dims" not in mapping:
                continue
            contiguous = True
            previous_y = float(row.get("center_y", -math.inf))
            for candidate_row, _candidate_ids in page_rows[index + 1 : target_index + 1]:
                current_y = float(candidate_row.get("center_y", math.inf))
                if current_y - previous_y > 50.0:
                    contiguous = False
                    break
                previous_y = current_y
            if not contiguous:
                continue
            header_bounds = row.get("bounds", [])
            target_bounds = target_row.get("bounds", [])
            if header_bounds and target_bounds:
                header_min_x = header_bounds[0][0] - 20.0
                header_max_x = header_bounds[-1][1] + 20.0
                if target_bounds[-1][1] < header_min_x or target_bounds[0][0] > header_max_x:
                    continue
            header_candidates.append((index, row, tuple(ids), logical_cells))

        # If nested/duplicate headers can both govern this exact row, fail closed.
        if len(header_candidates) != 1:
            reason = ROW_VERTICAL_HEADER_UNAVAILABLE if not header_candidates else ROW_VERTICAL_ROW_AMBIGUOUS
            status = EvidenceResolutionStatus.ABSTAINED if not header_candidates else EvidenceResolutionStatus.CONFLICT
            return self._store(key, _row_blocked(status, reason))

        _header_index, header_row, header_ids, header_cells = header_candidates[0]
        semantic_columns: dict[str, list[int]] = {"bottom": [], "top": []}
        for index, (heading, _left, _right) in enumerate(header_cells):
            kind = _placement_kind(heading)
            if kind is not None:
                semantic_columns[kind].append(index)
        if len(semantic_columns["bottom"]) != 1 or len(semantic_columns["top"]) != 1:
            return self._store(
                key,
                _row_blocked(EvidenceResolutionStatus.ABSTAINED, ROW_VERTICAL_BASIS_UNPROVEN),
            )

        bottom_index = semantic_columns["bottom"][0]
        top_index = semantic_columns["top"][0]
        bottom_heading = header_cells[bottom_index][0]
        top_heading = header_cells[top_index][0]
        bottom_cell = _logical_column_text(target_row, header_cells, bottom_index)
        top_cell = _logical_column_text(target_row, header_cells, top_index)
        if not bottom_cell or not top_cell:
            return self._store(
                key,
                _row_blocked(EvidenceResolutionStatus.ABSTAINED, ROW_VERTICAL_FIELD_UNAVAILABLE),
            )

        bottom_reason, z0_mm, bottom_units = _parse_position_mm(
            bottom_heading, bottom_cell
        )
        top_reason, z1_mm, top_units = _parse_position_mm(
            top_heading, top_cell
        )
        if z0_mm is None:
            status = EvidenceResolutionStatus.CONFLICT if bottom_reason == ROW_VERTICAL_UNITS_CONFLICT else EvidenceResolutionStatus.ABSTAINED
            return self._store(key, _row_blocked(status, bottom_reason))
        if z1_mm is None:
            status = EvidenceResolutionStatus.CONFLICT if top_reason == ROW_VERTICAL_UNITS_CONFLICT else EvidenceResolutionStatus.ABSTAINED
            return self._store(key, _row_blocked(status, top_reason))
        if z1_mm <= z0_mm:
            return self._store(
                key,
                _row_blocked(EvidenceResolutionStatus.CONFLICT, ROW_VERTICAL_ORDER_INVALID),
            )

        evidence = ScheduleRowVerticalPlacementEvidence(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            schedule_page_id=selector.schedule_page_id,
            schedule_row_observation_ids=tuple(selector.schedule_row_observation_ids),
            header_observation_ids=header_ids,
            z0_mm=float(z0_mm),
            z1_mm=float(z1_mm),
            units="mm",
            bottom_source_units=str(bottom_units),
            top_source_units=str(top_units),
            bottom_basis_source=bottom_heading,
            top_basis_source=top_heading,
            raw_text=str(target_row.get("text", "")),
        )
        return self._store(
            key,
            ScheduleRowVerticalPlacementResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=frozenset([ROW_VERTICAL_PLACEMENT_RESOLVED]),
                evidence=evidence,
            ),
        )

    def _store(
        self,
        key: _RowKey,
        result: ScheduleRowVerticalPlacementResult,
    ) -> ScheduleRowVerticalPlacementResult:
        existing = self._results.get(key)
        if existing is not None and existing != result:
            raise RuntimeError("schedule-row vertical-placement producer equivocation")
        self._results[key] = result
        return result

    def authority(self) -> ScheduleRowVerticalPlacementAuthority:
        return ScheduleRowVerticalPlacementAuthority(
            MappingProxyType(dict(self._results)),
            _seal=_ROW_AUTHORITY_SEAL,
        )


@dataclasses.dataclass(frozen=True)
class OpeningVerticalPlacementSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    decision_scope_id: str
    opening_record_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "decision_scope_id",
            "opening_record_id",
        ):
            _require_nonempty(getattr(self, name), name)

    @property
    def key(self) -> _OpeningKey:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.decision_scope_id,
            self.opening_record_id,
        )


@dataclasses.dataclass(frozen=True)
class OpeningVerticalPlacementEvidence:
    opening_record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    decision_scope_id: str
    schedule_page_id: str
    schedule_row_observation_ids: tuple[str, ...]
    schedule_header_observation_ids: tuple[str, ...]
    z0_mm: float
    z1_mm: float
    units: str
    schema_version: str = VERTICAL_PLACEMENT_SCHEMA_VERSION


@dataclasses.dataclass(frozen=True)
class OpeningVerticalPlacementResult:
    status: EvidenceResolutionStatus
    reason_codes: frozenset[str]
    evidence: OpeningVerticalPlacementEvidence | None = None
    schema_version: str = VERTICAL_PLACEMENT_SCHEMA_VERSION


def _opening_blocked(
    status: EvidenceResolutionStatus,
    *reasons: str,
) -> OpeningVerticalPlacementResult:
    cleaned = frozenset(str(reason) for reason in reasons if str(reason))
    return OpeningVerticalPlacementResult(
        status=status,
        reason_codes=cleaned or frozenset(["opening_vertical_placement_unavailable"]),
        evidence=None,
    )


class OpeningVerticalPlacementAuthority:
    def __init__(
        self,
        results: Mapping[_OpeningKey, OpeningVerticalPlacementResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _OPENING_AUTHORITY_SEAL:
            raise ValueError("OpeningVerticalPlacementAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: OpeningVerticalPlacementSelector) -> OpeningVerticalPlacementResult:
        if type(selector) is not OpeningVerticalPlacementSelector:
            raise TypeError("selector must be OpeningVerticalPlacementSelector")
        result = self._results.get(selector.key)
        if result is not None:
            return result
        return _opening_blocked(
            EvidenceResolutionStatus.ABSTAINED,
            "opening_vertical_placement_no_evidence",
        )


class OpeningVerticalPlacementProducer:
    def __init__(
        self,
        binding_authority: ScheduleOpeningInstanceBindingAuthority,
        row_vertical_placement_authority: ScheduleRowVerticalPlacementAuthority,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _OPENING_PRODUCER_SEAL:
            raise TypeError(
                "OpeningVerticalPlacementProducer must be obtained from from_authorities()"
            )
        if type(binding_authority) is not ScheduleOpeningInstanceBindingAuthority:
            raise TypeError("binding_authority must be producer-owned")
        if type(row_vertical_placement_authority) is not ScheduleRowVerticalPlacementAuthority:
            raise TypeError("row_vertical_placement_authority must be producer-owned")
        self._binding_authority = binding_authority
        self._row_vertical_placement_authority = row_vertical_placement_authority
        self._results: dict[_OpeningKey, OpeningVerticalPlacementResult] = {}

    @classmethod
    def from_authorities(
        cls,
        binding_authority: ScheduleOpeningInstanceBindingAuthority,
        row_vertical_placement_authority: ScheduleRowVerticalPlacementAuthority,
    ) -> "OpeningVerticalPlacementProducer":
        return cls(
            binding_authority,
            row_vertical_placement_authority,
            _seal=_OPENING_PRODUCER_SEAL,
        )

    def publish_scope(
        self,
        selector: OpeningVerticalPlacementSelector,
    ) -> OpeningVerticalPlacementResult:
        if type(selector) is not OpeningVerticalPlacementSelector:
            raise TypeError("selector must be OpeningVerticalPlacementSelector")
        key = selector.key
        existing = self._results.get(key)
        if existing is not None:
            return existing

        binding_result = self._binding_authority.resolve(
            ScheduleOpeningInstanceBindingSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                decision_scope_id=selector.decision_scope_id,
                opening_record_id=selector.opening_record_id,
            )
        )
        if (
            binding_result.status is not EvidenceResolutionStatus.CORROBORATED
            or binding_result.record is None
        ):
            return self._store(
                key,
                _opening_blocked(binding_result.status, *binding_result.reason_codes),
            )
        binding = binding_result.record
        if (
            binding.document_id != selector.document_id
            or binding.revision_id != selector.revision_id
            or binding.source_sha256 != selector.source_sha256
            or binding.snapshot_id != selector.snapshot_id
            or binding.decision_scope_id != selector.decision_scope_id
            or binding.opening_record_id != selector.opening_record_id
        ):
            return self._store(
                key,
                _opening_blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    OPENING_VERTICAL_UPSTREAM_INCONSISTENT,
                ),
            )

        row_result = self._row_vertical_placement_authority.resolve(
            ScheduleRowVerticalPlacementSelector(
                document_id=binding.document_id,
                revision_id=binding.revision_id,
                source_sha256=binding.source_sha256,
                snapshot_id=binding.snapshot_id,
                schedule_page_id=binding.schedule_page_id,
                schedule_row_observation_ids=binding.schedule_row_observation_ids,
            )
        )
        if (
            row_result.status is not EvidenceResolutionStatus.CORROBORATED
            or row_result.evidence is None
        ):
            return self._store(
                key,
                _opening_blocked(row_result.status, *row_result.reason_codes),
            )
        row = row_result.evidence
        if (
            row.document_id != binding.document_id
            or row.revision_id != binding.revision_id
            or row.source_sha256 != binding.source_sha256
            or row.snapshot_id != binding.snapshot_id
            or row.schedule_page_id != binding.schedule_page_id
            or tuple(sorted(row.schedule_row_observation_ids))
            != tuple(sorted(binding.schedule_row_observation_ids))
            or row.units != "mm"
        ):
            return self._store(
                key,
                _opening_blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    OPENING_VERTICAL_UPSTREAM_INCONSISTENT,
                ),
            )

        result = OpeningVerticalPlacementResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=frozenset([OPENING_VERTICAL_PLACEMENT_RESOLVED]),
            evidence=OpeningVerticalPlacementEvidence(
                opening_record_id=binding.opening_record_id,
                document_id=binding.document_id,
                revision_id=binding.revision_id,
                source_sha256=binding.source_sha256,
                snapshot_id=binding.snapshot_id,
                decision_scope_id=binding.decision_scope_id,
                schedule_page_id=binding.schedule_page_id,
                schedule_row_observation_ids=row.schedule_row_observation_ids,
                schedule_header_observation_ids=row.header_observation_ids,
                z0_mm=row.z0_mm,
                z1_mm=row.z1_mm,
                units=row.units,
            ),
        )
        return self._store(key, result)

    def _store(
        self,
        key: _OpeningKey,
        result: OpeningVerticalPlacementResult,
    ) -> OpeningVerticalPlacementResult:
        existing = self._results.get(key)
        if existing is not None and existing != result:
            raise RuntimeError("opening vertical-placement producer equivocation")
        self._results[key] = result
        return result

    def authority(self) -> OpeningVerticalPlacementAuthority:
        return OpeningVerticalPlacementAuthority(
            MappingProxyType(dict(self._results)),
            _seal=_OPENING_AUTHORITY_SEAL,
        )


__all__ = [
    "OPENING_VERTICAL_PLACEMENT_RESOLVED",
    "OPENING_VERTICAL_UPSTREAM_INCONSISTENT",
    "OpeningVerticalPlacementAuthority",
    "OpeningVerticalPlacementEvidence",
    "OpeningVerticalPlacementProducer",
    "OpeningVerticalPlacementResult",
    "OpeningVerticalPlacementSelector",
    "ROW_VERTICAL_BASIS_UNPROVEN",
    "ROW_VERTICAL_FIELD_UNAVAILABLE",
    "ROW_VERTICAL_HEADER_UNAVAILABLE",
    "ROW_VERTICAL_ORDER_INVALID",
    "ROW_VERTICAL_PARTIAL_SOURCE_COVERAGE",
    "ROW_VERTICAL_PLACEMENT_RESOLVED",
    "ROW_VERTICAL_ROW_AMBIGUOUS",
    "ROW_VERTICAL_ROW_UNAVAILABLE",
    "ROW_VERTICAL_SOURCE_SCOPE_UNAVAILABLE",
    "ROW_VERTICAL_UNITS_CONFLICT",
    "ROW_VERTICAL_UNITS_UNPROVEN",
    "ScheduleRowVerticalPlacementAuthority",
    "ScheduleRowVerticalPlacementEvidence",
    "ScheduleRowVerticalPlacementProducer",
    "ScheduleRowVerticalPlacementResult",
    "ScheduleRowVerticalPlacementSelector",
    "VERTICAL_PLACEMENT_SCHEMA_VERSION",
]