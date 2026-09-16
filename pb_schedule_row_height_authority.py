"""Producer-owned semantic height authority for an exact schedule row.

This module does not bind a schedule row to a physical opening.  That is the
separate responsibility of ``ScheduleOpeningInstanceBindingAuthority``.  It
proves only that one exact producer-owned schedule row carries an explicit
rough/structural-opening HEIGHT measurement with source-backed unit semantics.
"""
from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping, Sequence
from types import MappingProxyType

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_schedule_v171 import detect_header
from pb_schedule_opening_instance_binding_authority import (
    _row_groups_for_page,
    _schedule_entries_for_page,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

SCHEDULE_ROW_HEIGHT_SCHEMA_VERSION = "1.0.0"

HEIGHT_RESOLVED = "schedule_row_height_resolved"
HEIGHT_SOURCE_SCOPE_UNAVAILABLE = "schedule_row_height_source_scope_unavailable"
HEIGHT_PARTIAL_SOURCE_COVERAGE = "schedule_row_height_partial_source_coverage"
HEIGHT_ROW_UNAVAILABLE = "schedule_row_height_row_unavailable"
HEIGHT_ROW_AMBIGUOUS = "schedule_row_height_row_ambiguous"
HEIGHT_FIELD_UNAVAILABLE = "opening_height_missing_field"
HEIGHT_BASIS_UNPROVEN = "schedule_row_height_basis_unproven"
HEIGHT_UNITS_UNPROVEN = "schedule_row_height_units_unproven"
HEIGHT_UNITS_CONFLICT = "opening_height_ambiguous_units"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_Key = tuple[str, str, str, str, str, tuple[str, ...]]

_MM_RE = re.compile(r"(?:\bmm\b|millimet(?:er|re)s?)", re.IGNORECASE)
_M_RE = re.compile(r"(?:\bmet(?:er|re)s?\b|(?<![A-Za-z])m\b)", re.IGNORECASE)


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


@dataclasses.dataclass(frozen=True)
class ScheduleRowHeightSelector:
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
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.schedule_page_id,
            tuple(sorted(self.schedule_row_observation_ids)),
        )


@dataclasses.dataclass(frozen=True)
class ScheduleRowHeightEvidence:
    schedule_page_id: str
    schedule_row_observation_ids: tuple[str, ...]
    header_observation_ids: tuple[str, ...]
    height_mm: float
    raw_text: str
    units: str
    source_units: str
    dimension_basis: str
    basis_source: str
    schema_version: str = SCHEDULE_ROW_HEIGHT_SCHEMA_VERSION


@dataclasses.dataclass(frozen=True)
class ScheduleRowHeightResult:
    status: EvidenceResolutionStatus
    reason_codes: frozenset[str]
    evidence: ScheduleRowHeightEvidence | None = None
    schema_version: str = SCHEDULE_ROW_HEIGHT_SCHEMA_VERSION


def _blocked(status: EvidenceResolutionStatus, reason: str) -> ScheduleRowHeightResult:
    return ScheduleRowHeightResult(status=status, reason_codes=frozenset([reason]), evidence=None)


class ScheduleRowHeightAuthority:
    def __init__(self, results: Mapping[_Key, ScheduleRowHeightResult], *, _seal: object = None) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise ValueError("ScheduleRowHeightAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: ScheduleRowHeightSelector) -> ScheduleRowHeightResult:
        if type(selector) is not ScheduleRowHeightSelector:
            raise TypeError("selector must be ScheduleRowHeightSelector")
        result = self._results.get(selector.key)
        if result is not None:
            return result
        return _blocked(EvidenceResolutionStatus.ABSTAINED, HEIGHT_ROW_UNAVAILABLE)


class ScheduleRowHeightProducer:
    def __init__(self, visibility_producer: SourceVisibilityProducer, *, _seal: object = None) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("ScheduleRowHeightProducer must be obtained from from_source_visibility_producer()")
        if type(visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("visibility_producer must be producer-owned")
        self._visibility_producer = visibility_producer
        self._results: dict[_Key, ScheduleRowHeightResult] = {}

    @classmethod
    def from_source_visibility_producer(cls, visibility_producer: SourceVisibilityProducer) -> "ScheduleRowHeightProducer":
        return cls(visibility_producer, _seal=_PRODUCER_SEAL)

    def publish_scope(self, selector: ScheduleRowHeightSelector) -> ScheduleRowHeightResult:
        if type(selector) is not ScheduleRowHeightSelector:
            raise TypeError("selector must be ScheduleRowHeightSelector")
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
            return self._store(key, _blocked(EvidenceResolutionStatus.ABSTAINED, HEIGHT_SOURCE_SCOPE_UNAVAILABLE))
        if published.coverage.state != "complete" or published.coverage.failed_pages:
            return self._store(key, _blocked(EvidenceResolutionStatus.ABSTAINED, HEIGHT_PARTIAL_SOURCE_COVERAGE))

        text_integrity = self._visibility_producer.text_integrity_authority()
        page_words: list[tuple[str, str, tuple[float, ...]]] = []
        for observation_id in published.text_observation_ids:
            text_result = text_integrity.resolve_text(
                ObservationSelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    observation_id=observation_id,
                )
            )
            if (
                text_result.status is not EvidenceResolutionStatus.CORROBORATED
                or text_result.trusted_text is None
                or text_result.receipt is None
                or text_result.receipt.page_id != selector.schedule_page_id
            ):
                continue
            page_words.append((observation_id, text_result.trusted_text, tuple(float(value) for value in text_result.receipt.geometry)))

        page_rows = _row_groups_for_page(page_words)
        if not page_rows:
            return self._store(key, _blocked(EvidenceResolutionStatus.ABSTAINED, HEIGHT_ROW_UNAVAILABLE))
        try:
            page_no = int(selector.schedule_page_id)
        except (TypeError, ValueError):
            return self._store(key, _blocked(EvidenceResolutionStatus.ABSTAINED, HEIGHT_ROW_UNAVAILABLE))

        header_index = -1
        header_mapping: dict[str, object] = {}
        for index, (row, _ids) in enumerate(page_rows):
            cells = [cell.strip() for cell in str(row.get("text", "")).split("\t")]
            mapping = detect_header(cells)
            if "mark" in mapping or "dims" in mapping:
                header_index = index
                header_mapping = mapping
                break
        if header_index < 0:
            return self._store(key, _blocked(EvidenceResolutionStatus.ABSTAINED, HEIGHT_ROW_UNAVAILABLE))

        target_ids = tuple(sorted(selector.schedule_row_observation_ids))
        matches = [
            (entry, tuple(ids))
            for entry, ids in _schedule_entries_for_page(page_rows, page_no)
            if tuple(sorted(ids)) == target_ids
        ]
        if not matches:
            return self._store(key, _blocked(EvidenceResolutionStatus.ABSTAINED, HEIGHT_ROW_UNAVAILABLE))
        if len(matches) != 1:
            return self._store(key, _blocked(EvidenceResolutionStatus.CONFLICT, HEIGHT_ROW_AMBIGUOUS))

        entry, _entry_ids = matches[0]
        target_row: dict[str, object] | None = None
        for row, ids in page_rows[header_index + 1 :]:
            if tuple(sorted(ids)) == target_ids:
                target_row = row
                break
        if target_row is None:
            return self._store(key, _blocked(EvidenceResolutionStatus.ABSTAINED, HEIGHT_ROW_UNAVAILABLE))

        if entry.height_mm is None:
            return self._store(key, _blocked(EvidenceResolutionStatus.ABSTAINED, HEIGHT_FIELD_UNAVAILABLE))
        if entry.dimension_basis != "rough_opening" or not entry.basis_source:
            return self._store(key, _blocked(EvidenceResolutionStatus.ABSTAINED, HEIGHT_BASIS_UNPROVEN))
        if entry.parse_source not in {"header_separate", "header_dims"}:
            return self._store(key, _blocked(EvidenceResolutionStatus.ABSTAINED, HEIGHT_BASIS_UNPROVEN))

        header_row, header_ids = page_rows[header_index]
        header_cells = [cell.strip() for cell in str(header_row.get("text", "")).split("\t")]
        target_cells = [cell.strip() for cell in str(target_row.get("text", "")).split("\t")]
        if entry.parse_source == "header_separate":
            column_index = header_mapping.get("height")
        else:
            column_index = header_mapping.get("dims")
        if not isinstance(column_index, int):
            return self._store(key, _blocked(EvidenceResolutionStatus.ABSTAINED, HEIGHT_FIELD_UNAVAILABLE))
        if column_index >= len(header_cells) or column_index >= len(target_cells):
            return self._store(key, _blocked(EvidenceResolutionStatus.ABSTAINED, HEIGHT_FIELD_UNAVAILABLE))

        unit_tokens = set(_unit_tokens(header_cells[column_index]))
        unit_tokens.update(_unit_tokens(target_cells[column_index]))
        if not unit_tokens:
            return self._store(key, _blocked(EvidenceResolutionStatus.ABSTAINED, HEIGHT_UNITS_UNPROVEN))
        if len(unit_tokens) != 1:
            return self._store(key, _blocked(EvidenceResolutionStatus.CONFLICT, HEIGHT_UNITS_CONFLICT))
        source_units = next(iter(unit_tokens))

        evidence = ScheduleRowHeightEvidence(
            schedule_page_id=selector.schedule_page_id,
            schedule_row_observation_ids=tuple(selector.schedule_row_observation_ids),
            header_observation_ids=tuple(header_ids),
            height_mm=float(entry.height_mm),
            raw_text=str(target_row.get("text", "")),
            units="mm",
            source_units=source_units,
            dimension_basis=entry.dimension_basis,
            basis_source=entry.basis_source,
        )
        return self._store(
            key,
            ScheduleRowHeightResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=frozenset([HEIGHT_RESOLVED]),
                evidence=evidence,
            ),
        )

    def _store(self, key: _Key, result: ScheduleRowHeightResult) -> ScheduleRowHeightResult:
        existing = self._results.get(key)
        if existing is not None and existing != result:
            raise RuntimeError("schedule-row height producer equivocation")
        self._results[key] = result
        return result

    def authority(self) -> ScheduleRowHeightAuthority:
        return ScheduleRowHeightAuthority(MappingProxyType(dict(self._results)), _seal=_AUTHORITY_SEAL)


__all__ = [
    "HEIGHT_BASIS_UNPROVEN",
    "HEIGHT_FIELD_UNAVAILABLE",
    "HEIGHT_PARTIAL_SOURCE_COVERAGE",
    "HEIGHT_RESOLVED",
    "HEIGHT_ROW_AMBIGUOUS",
    "HEIGHT_ROW_UNAVAILABLE",
    "HEIGHT_SOURCE_SCOPE_UNAVAILABLE",
    "HEIGHT_UNITS_CONFLICT",
    "HEIGHT_UNITS_UNPROVEN",
    "SCHEDULE_ROW_HEIGHT_SCHEMA_VERSION",
    "ScheduleRowHeightAuthority",
    "ScheduleRowHeightEvidence",
    "ScheduleRowHeightProducer",
    "ScheduleRowHeightResult",
    "ScheduleRowHeightSelector",
]
