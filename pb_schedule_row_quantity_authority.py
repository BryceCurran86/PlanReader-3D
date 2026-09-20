"""Producer-owned schedule-row quantity authority (Item 23 dependency).

Authenticates a declared schedule quantity for exact schedule-row observation
IDs. Caller-supplied mark→count maps never establish schedule quantity.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Optional

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

SCHEDULE_ROW_QUANTITY_SCHEMA_VERSION = "1.0.0"

SCHEDULE_ROW_QTY_RESOLVED = "schedule_row_quantity_resolved"
SCHEDULE_ROW_QTY_UNAVAILABLE = "schedule_row_quantity_unavailable"
SCHEDULE_ROW_QTY_LINEAGE_MISMATCH = "schedule_row_quantity_lineage_mismatch"
SCHEDULE_ROW_QTY_INCOMPLETE = "schedule_row_quantity_incomplete"
SCHEDULE_ROW_QTY_INVALID = "schedule_row_quantity_invalid"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_AUTHENTICATED_BINDING_SEAL = object()

_Key = tuple[str, str, str, str, str, tuple[str, ...]]


def _require_nonempty(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be a non-empty string")
    return text


@dataclass(frozen=True)
class ScheduleRowQuantitySelector:
    """Address-only lookup keyed by exact schedule-row observation IDs."""

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
        if len(set(self.schedule_row_observation_ids)) != len(
            self.schedule_row_observation_ids
        ):
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


@dataclass(frozen=True)
class ScheduleRowQuantityRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    schedule_page_id: str
    schedule_row_observation_ids: tuple[str, ...]
    type_mark: Optional[str]
    declared_count: int
    universe_complete: bool
    schema_version: str = SCHEDULE_ROW_QUANTITY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_nonempty(self.record_id, "record_id")
        _require_nonempty(self.document_id, "document_id")
        _require_nonempty(self.revision_id, "revision_id")
        _require_nonempty(self.source_sha256, "source_sha256")
        _require_nonempty(self.snapshot_id, "snapshot_id")
        _require_nonempty(self.schedule_page_id, "schedule_page_id")
        if self.declared_count < 0:
            raise ValueError("declared_count must be non-negative")
        if not self.schedule_row_observation_ids:
            raise ValueError("schedule_row_observation_ids must be non-empty")
        if self.type_mark is not None:
            mark = str(self.type_mark).strip().upper()
            if not mark:
                raise ValueError("type_mark cannot be empty when provided")
            object.__setattr__(self, "type_mark", mark)


@dataclass(frozen=True)
class ScheduleRowQuantityResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: Optional[ScheduleRowQuantityRecord] = None
    schema_version: str = SCHEDULE_ROW_QUANTITY_SCHEMA_VERSION


def _blocked(
    status: EvidenceResolutionStatus,
    reason: str,
    *extra: str,
) -> ScheduleRowQuantityResult:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    return ScheduleRowQuantityResult(
        status=status,
        reason_codes=tuple(dict.fromkeys([reason, *(r for r in extra if r)])),
        record=None,
    )


class ScheduleRowQuantityAuthority:
    """Read-only producer-owned schedule-row quantity lookup."""

    def __init__(
        self,
        results: Mapping[_Key, ScheduleRowQuantityResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("ScheduleRowQuantityAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(
        self, selector: ScheduleRowQuantitySelector
    ) -> ScheduleRowQuantityResult:
        if type(selector) is not ScheduleRowQuantitySelector:
            raise TypeError("selector must be ScheduleRowQuantitySelector")
        return self._results.get(
            selector.key,
            _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                SCHEDULE_ROW_QTY_UNAVAILABLE,
            ),
        )


class ScheduleRowQuantityProducer:
    """Trusted boundary publishing authenticated schedule-row quantities."""

    def __init__(self, *, _seal: object = None) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "ScheduleRowQuantityProducer must be obtained from create()"
            )
        self._results: dict[_Key, ScheduleRowQuantityResult] = {}

    @classmethod
    def create(cls) -> "ScheduleRowQuantityProducer":
        return cls(_seal=_PRODUCER_SEAL)

    def authority(self) -> ScheduleRowQuantityAuthority:
        return ScheduleRowQuantityAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def publish(self, *args, **kwargs) -> ScheduleRowQuantityResult:
        """Reject legacy raw quantity publication.

        A caller-supplied declared_count or universe_complete boolean is not
        schedule authority. Positive schedule quantities must be republished
        through the source-authenticated binding adapter.
        """
        raise TypeError(
            "raw schedule quantity publication is not an authority path; "
            "resolve ScheduleOpeningInstanceBindingAuthority first"
        )

    def _publish_from_authenticated_binding(
        self,
        selector: ScheduleRowQuantitySelector,
        *,
        declared_count: int,
        type_mark: Optional[str],
        _seal: object = None,
    ) -> ScheduleRowQuantityResult:
        """Internal positive path used only after producer-owned binding resolution."""
        if _seal is not _AUTHENTICATED_BINDING_SEAL:
            raise TypeError(
                "schedule quantity must originate from authenticated binding resolution"
            )
        if type(selector) is not ScheduleRowQuantitySelector:
            raise TypeError("selector must be ScheduleRowQuantitySelector")
        if not isinstance(declared_count, int) or declared_count < 1:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    SCHEDULE_ROW_QTY_INVALID,
                ),
            )
        mark = None if type_mark is None else str(type_mark).strip().upper()
        if not mark:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    SCHEDULE_ROW_QTY_INCOMPLETE,
                    "schedule_row_type_mark_missing",
                ),
            )
        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "schedule_page_id": selector.schedule_page_id,
            "schedule_row_observation_ids": tuple(
                sorted(selector.schedule_row_observation_ids)
            ),
            "type_mark": mark,
            "declared_count": declared_count,
            # A positive ScheduleOpeningInstanceBindingAuthority result is
            # already derived from complete source coverage and exhaustive
            # matching-row discovery. This is producer-derived, not a caller
            # boolean.
            "universe_complete": True,
        }
        record = ScheduleRowQuantityRecord(
            record_id=stable_contract_id(
                "schedule_row_quantity", payload, digest_chars=32
            ),
            **payload,
        )
        return self._store(
            selector,
            ScheduleRowQuantityResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(SCHEDULE_ROW_QTY_RESOLVED,),
                record=record,
            ),
        )

    def _store(
        self,
        selector: ScheduleRowQuantitySelector,
        result: ScheduleRowQuantityResult,
    ) -> ScheduleRowQuantityResult:
        prior = self._results.get(selector.key)
        if prior is not None and prior != result:
            raise RuntimeError("schedule row quantity producer equivocation")
        self._results[selector.key] = result
        return result


__all__ = [
    "SCHEDULE_ROW_QUANTITY_SCHEMA_VERSION",
    "SCHEDULE_ROW_QTY_INCOMPLETE",
    "SCHEDULE_ROW_QTY_INVALID",
    "SCHEDULE_ROW_QTY_LINEAGE_MISMATCH",
    "SCHEDULE_ROW_QTY_RESOLVED",
    "SCHEDULE_ROW_QTY_UNAVAILABLE",
    "ScheduleRowQuantityAuthority",
    "ScheduleRowQuantityProducer",
    "ScheduleRowQuantityRecord",
    "ScheduleRowQuantityResult",
    "ScheduleRowQuantitySelector",
    "_AUTHORITY_SEAL",
]
