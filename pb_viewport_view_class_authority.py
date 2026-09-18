"""Producer-owned viewport view-class authority (Item 23 dependency).

Establishes whether a viewport is a floor-plan (or other) view class from
producer-owned evidence only. Caller-supplied viewport IDs, names, or keyword
guesses never establish view class.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Optional

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

VIEWPORT_VIEW_CLASS_SCHEMA_VERSION = "1.0.0"

VIEWPORT_VIEW_CLASS_RESOLVED = "viewport_view_class_resolved"
VIEWPORT_VIEW_CLASS_UNAVAILABLE = "viewport_view_class_unavailable"
VIEWPORT_VIEW_CLASS_UNKNOWN = "viewport_view_class_unknown"

VIEW_KIND_FLOOR_PLAN = "floor_plan"
VIEW_KIND_ELEVATION = "elevation"
VIEW_KIND_SECTION = "section"
VIEW_KIND_DETAIL = "detail"
VIEW_KIND_SCHEDULE = "schedule"
VIEW_KIND_UNKNOWN = "unknown"

_ALLOWED_VIEW_KINDS = frozenset(
    {
        VIEW_KIND_FLOOR_PLAN,
        VIEW_KIND_ELEVATION,
        VIEW_KIND_SECTION,
        VIEW_KIND_DETAIL,
        VIEW_KIND_SCHEDULE,
        VIEW_KIND_UNKNOWN,
    }
)

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()

_Key = tuple[str, str, str, str, str]


def _require_nonempty(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be a non-empty string")
    return text


@dataclass(frozen=True)
class ViewportViewClassSelector:
    """Address-only lookup: never a caller-authored view class."""

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    viewport_id: str

    def __post_init__(self) -> None:
        _require_nonempty(self.document_id, "document_id")
        _require_nonempty(self.revision_id, "revision_id")
        _require_nonempty(self.source_sha256, "source_sha256")
        _require_nonempty(self.snapshot_id, "snapshot_id")
        _require_nonempty(self.viewport_id, "viewport_id")

    @property
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.viewport_id,
        )


@dataclass(frozen=True)
class ViewportViewClassRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    viewport_id: str
    view_kind: str
    evidence_observation_ids: tuple[str, ...]
    schema_version: str = VIEWPORT_VIEW_CLASS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_nonempty(self.record_id, "record_id")
        _require_nonempty(self.document_id, "document_id")
        _require_nonempty(self.revision_id, "revision_id")
        _require_nonempty(self.source_sha256, "source_sha256")
        _require_nonempty(self.snapshot_id, "snapshot_id")
        _require_nonempty(self.viewport_id, "viewport_id")
        kind = str(self.view_kind or "").strip().lower()
        if kind not in _ALLOWED_VIEW_KINDS:
            raise ValueError(
                "view_kind must be one of: " + ", ".join(sorted(_ALLOWED_VIEW_KINDS))
            )
        object.__setattr__(self, "view_kind", kind)
        if not self.evidence_observation_ids:
            raise ValueError("evidence_observation_ids must be non-empty")
        if len(set(self.evidence_observation_ids)) != len(self.evidence_observation_ids):
            raise ValueError("evidence_observation_ids must be unique")


@dataclass(frozen=True)
class ViewportViewClassResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: Optional[ViewportViewClassRecord] = None
    schema_version: str = VIEWPORT_VIEW_CLASS_SCHEMA_VERSION


def _blocked(
    status: EvidenceResolutionStatus,
    reason: str,
    *extra: str,
) -> ViewportViewClassResult:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    return ViewportViewClassResult(
        status=status,
        reason_codes=tuple(dict.fromkeys([reason, *(r for r in extra if r)])),
        record=None,
    )


class ViewportViewClassAuthority:
    """Read-only producer-owned viewport view-class lookup."""

    def __init__(
        self,
        results: Mapping[_Key, ViewportViewClassResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("ViewportViewClassAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: ViewportViewClassSelector) -> ViewportViewClassResult:
        if type(selector) is not ViewportViewClassSelector:
            raise TypeError("selector must be ViewportViewClassSelector")
        return self._results.get(
            selector.key,
            _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                VIEWPORT_VIEW_CLASS_UNAVAILABLE,
            ),
        )


class ViewportViewClassProducer:
    """Trusted boundary publishing viewport view-class propositions."""

    def __init__(self, *, _seal: object = None) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "ViewportViewClassProducer must be obtained from create()"
            )
        self._results: dict[_Key, ViewportViewClassResult] = {}

    @classmethod
    def create(cls) -> "ViewportViewClassProducer":
        return cls(_seal=_PRODUCER_SEAL)

    def authority(self) -> ViewportViewClassAuthority:
        return ViewportViewClassAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def publish(
        self,
        selector: ViewportViewClassSelector,
        *,
        view_kind: str,
        evidence_observation_ids: tuple[str, ...],
    ) -> ViewportViewClassResult:
        """Publish a producer-owned view class for an exact viewport selector.

        ``view_kind`` must already be established by upstream producer evidence;
        this method does not classify from viewport name strings.
        """
        if type(selector) is not ViewportViewClassSelector:
            raise TypeError("selector must be ViewportViewClassSelector")
        kind = str(view_kind or "").strip().lower()
        if kind not in _ALLOWED_VIEW_KINDS:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    VIEWPORT_VIEW_CLASS_UNKNOWN,
                ),
            )
        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "viewport_id": selector.viewport_id,
            "view_kind": kind,
            "evidence_observation_ids": tuple(evidence_observation_ids),
        }
        record = ViewportViewClassRecord(
            record_id=stable_contract_id(
                "viewport_view_class", payload, digest_chars=32
            ),
            **payload,
        )
        if kind == VIEW_KIND_UNKNOWN:
            return self._store(
                selector,
                ViewportViewClassResult(
                    status=EvidenceResolutionStatus.ABSTAINED,
                    reason_codes=(VIEWPORT_VIEW_CLASS_UNKNOWN,),
                    record=None,
                ),
            )
        return self._store(
            selector,
            ViewportViewClassResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(VIEWPORT_VIEW_CLASS_RESOLVED,),
                record=record,
            ),
        )

    def _store(
        self,
        selector: ViewportViewClassSelector,
        result: ViewportViewClassResult,
    ) -> ViewportViewClassResult:
        self._results[selector.key] = result
        return result


__all__ = [
    "VIEWPORT_VIEW_CLASS_RESOLVED",
    "VIEWPORT_VIEW_CLASS_SCHEMA_VERSION",
    "VIEWPORT_VIEW_CLASS_UNAVAILABLE",
    "VIEWPORT_VIEW_CLASS_UNKNOWN",
    "VIEW_KIND_DETAIL",
    "VIEW_KIND_ELEVATION",
    "VIEW_KIND_FLOOR_PLAN",
    "VIEW_KIND_SCHEDULE",
    "VIEW_KIND_SECTION",
    "VIEW_KIND_UNKNOWN",
    "ViewportViewClassAuthority",
    "ViewportViewClassProducer",
    "ViewportViewClassRecord",
    "ViewportViewClassResult",
    "ViewportViewClassSelector",
    "_AUTHORITY_SEAL",
]
