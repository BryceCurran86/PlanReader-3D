"""pb_opening_schedule_count_authority.py -- Item 35 / Phase C support authority.

Producer-owned resolution of the EXPLICIT commercial count a door/window
schedule states for one normalized opening tag mark, in one decision scope.

This module does not parse schedule text and does not discover which rows
belong to which page -- callers supply already-parsed ScheduleEntry records
(pb_opening_schedule_v171.parse_schedule_rows) paired with the source
observation ids their own row discovery used, so this module never
duplicates that private row-grouping logic living in sibling authorities.

The only new fact this module establishes: whether the schedule explicitly,
unambiguously states a count for a mark. ScheduleEntry.count defaults to 1
both when a quantity column is absent AND when its value fails to parse --
count_explicit distinguishes a genuinely source-backed count from that
default, and this authority refuses to treat the default as evidence.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_opening_schedule_v171 import ScheduleEntry
from pb_opening_tag_normalization import normalize_opening_tag

OPENING_SCHEDULE_COUNT_SCHEMA_VERSION = "1.0.0"

SCHEDULE_COUNT_RESOLVED = "opening_schedule_count_resolved"
SCHEDULE_COUNT_NO_EXPLICIT_ROW = "opening_schedule_count_no_explicit_row"
SCHEDULE_COUNT_AMBIGUOUS_ROWS = "opening_schedule_count_ambiguous_rows"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RecordKey = tuple[str, str, str, str, str, str]


def _require_nonempty(value: object, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be a non-empty string")
    return clean


@dataclass(frozen=True)
class OpeningScheduleCountSelector:
    """Read-only lookup key supplied by ordinary consumers."""

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    decision_scope_id: str
    normalized_mark: str

    def __post_init__(self) -> None:
        for name in (
            "document_id", "revision_id", "source_sha256", "snapshot_id",
            "decision_scope_id", "normalized_mark",
        ):
            _require_nonempty(getattr(self, name), name)


@dataclass(frozen=True)
class OpeningScheduleCountRecord:
    """Immutable, producer-owned explicit schedule count for one mark."""

    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    decision_scope_id: str
    normalized_mark: str
    explicit_count: int
    schedule_page_id: str
    schedule_row_observation_ids: tuple[str, ...]
    count_source_kind: str
    schema_version: str = OPENING_SCHEDULE_COUNT_SCHEMA_VERSION


@dataclass(frozen=True)
class OpeningScheduleCountResult:
    """Fail-closed resolution result for one (scope, mark) selector."""

    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: OpeningScheduleCountRecord | None = None
    schema_version: str = OPENING_SCHEDULE_COUNT_SCHEMA_VERSION


def _record_key(
    document_id: str,
    revision_id: str,
    source_sha256: str,
    snapshot_id: str,
    decision_scope_id: str,
    normalized_mark: str,
) -> _RecordKey:
    return (
        str(document_id),
        str(revision_id),
        str(source_sha256),
        str(snapshot_id),
        str(decision_scope_id),
        str(normalized_mark),
    )


class OpeningScheduleCountAuthority:
    """Read-only selector resolver for producer-owned explicit count records."""

    def __init__(
        self,
        results: Mapping[_RecordKey, OpeningScheduleCountResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise ValueError(
                "OpeningScheduleCountAuthority must be obtained from "
                "OpeningScheduleCountProducer.authority()"
            )
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: OpeningScheduleCountSelector) -> OpeningScheduleCountResult:
        if not isinstance(selector, OpeningScheduleCountSelector):
            raise TypeError("selector must be OpeningScheduleCountSelector")
        key = _record_key(
            selector.document_id,
            selector.revision_id,
            selector.source_sha256,
            selector.snapshot_id,
            selector.decision_scope_id,
            selector.normalized_mark,
        )
        result = self._results.get(key)
        if result is not None:
            return result
        return OpeningScheduleCountResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(SCHEDULE_COUNT_NO_EXPLICIT_ROW,),
        )


class OpeningScheduleCountProducer:
    """Trusted writer reconciling already-parsed schedule rows into one
    explicit-count-or-nothing proposition per (scope, normalized mark)."""

    def __init__(self, *, _seal: object = None) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "OpeningScheduleCountProducer must be obtained from create()"
            )
        self._results: dict[_RecordKey, OpeningScheduleCountResult] = {}

    @classmethod
    def create(cls) -> OpeningScheduleCountProducer:
        return cls(_seal=_PRODUCER_SEAL)

    def publish_scope(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        snapshot_id: str,
        decision_scope_id: str,
        schedule_rows: Sequence[tuple[ScheduleEntry, Sequence[str]]],
    ) -> tuple[OpeningScheduleCountResult, ...]:
        """Publish one result per normalized mark discovered across
        `schedule_rows` -- (ScheduleEntry, that row's source observation ids)
        pairs, exactly as the caller's own (pre-existing, public) row
        discovery produced them. Rows with count_explicit=False never
        contribute -- the historical default-1 is invisible to this authority.
        """
        by_mark: dict[str, dict[int, tuple[ScheduleEntry, tuple[str, ...]]]] = {}
        for entry, ids in schedule_rows:
            if not entry.count_explicit:
                continue
            normalized = normalize_opening_tag(entry.type_mark)
            if normalized is None:
                continue
            # Dedupe on count alone: this authority's sole published fact is
            # the explicit count, so two rows agreeing on count are
            # corroborating, not ambiguous, even if their (unrelated,
            # unpublished-by-this-module) width/height parsed differently or
            # not at all. Folding dimensions into the ambiguity key would
            # manufacture a false CONFLICT out of a dimension-parsing hiccup
            # that has nothing to do with the count this module states.
            mark_rows = by_mark.setdefault(normalized.tag, {})
            if entry.count not in mark_rows:
                mark_rows[entry.count] = (entry, tuple(sorted(str(i) for i in ids)))

        produced: list[OpeningScheduleCountResult] = []
        for mark in sorted(by_mark):
            distinct = by_mark[mark]
            record_key = _record_key(
                document_id, revision_id, source_sha256, snapshot_id,
                decision_scope_id, mark,
            )
            if len(distinct) > 1:
                result = OpeningScheduleCountResult(
                    status=EvidenceResolutionStatus.CONFLICT,
                    reason_codes=(SCHEDULE_COUNT_AMBIGUOUS_ROWS,),
                )
            else:
                ((entry, ids),) = distinct.values()
                payload = {
                    "schema_version": OPENING_SCHEDULE_COUNT_SCHEMA_VERSION,
                    "document_id": document_id,
                    "revision_id": revision_id,
                    "source_sha256": source_sha256,
                    "snapshot_id": snapshot_id,
                    "decision_scope_id": decision_scope_id,
                    "normalized_mark": mark,
                    "explicit_count": entry.count,
                    "schedule_page_id": str(entry.page_no),
                    "schedule_row_observation_ids": list(ids),
                }
                record = OpeningScheduleCountRecord(
                    record_id=stable_contract_id(
                        "opening_schedule_count", payload, digest_chars=32
                    ),
                    document_id=document_id,
                    revision_id=revision_id,
                    source_sha256=source_sha256,
                    snapshot_id=snapshot_id,
                    decision_scope_id=decision_scope_id,
                    normalized_mark=mark,
                    explicit_count=entry.count,
                    schedule_page_id=str(entry.page_no),
                    schedule_row_observation_ids=ids,
                    count_source_kind="schedule_entry_explicit_count",
                )
                result = OpeningScheduleCountResult(
                    status=EvidenceResolutionStatus.CORROBORATED,
                    reason_codes=(SCHEDULE_COUNT_RESOLVED,),
                    record=record,
                )
            existing = self._results.get(record_key)
            if existing is not None and existing != result:
                raise RuntimeError("opening schedule count producer equivocation")
            self._results[record_key] = result
            produced.append(result)
        return tuple(produced)

    def authority(self) -> OpeningScheduleCountAuthority:
        return OpeningScheduleCountAuthority(
            MappingProxyType(dict(self._results)), _seal=_AUTHORITY_SEAL
        )


__all__ = [
    "OPENING_SCHEDULE_COUNT_SCHEMA_VERSION",
    "SCHEDULE_COUNT_AMBIGUOUS_ROWS",
    "SCHEDULE_COUNT_NO_EXPLICIT_ROW",
    "SCHEDULE_COUNT_RESOLVED",
    "OpeningScheduleCountAuthority",
    "OpeningScheduleCountProducer",
    "OpeningScheduleCountRecord",
    "OpeningScheduleCountResult",
    "OpeningScheduleCountSelector",
]
