"""Document-scoped source authority for universal joinery head-height notes.

Architectural drawing sets sometimes state a global note such as "JOINERY
HEIGHTS TO BE 2100 AFL U.N.O.".  This module authenticates that source claim
as a document/revision-scoped joinery HEAD height above finished level.

It deliberately does not turn the note into an opening height by itself:
windows may have non-zero sill levels and raised openings may exist.  Any
downstream conversion from head height to physical opening height must prove
the opening base/vertical placement separately.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from types import MappingProxyType
from typing import Mapping, Optional

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


JOINERY_HEAD_HEIGHT_SCHEMA_VERSION = "1.0.0"
JOINERY_HEAD_HEIGHT_RESOLVED = "document_joinery_head_height_resolved"
JOINERY_HEAD_HEIGHT_UNAVAILABLE = "document_joinery_head_height_unavailable"
JOINERY_HEAD_HEIGHT_CONFLICT = "document_joinery_head_height_conflict"
JOINERY_HEAD_HEIGHT_SOURCE_SCOPE_UNAVAILABLE = (
    "document_joinery_head_height_source_scope_unavailable"
)

_MIN_HEAD_HEIGHT_MM = 1200.0
_MAX_HEAD_HEIGHT_MM = 3600.0
_NOTE_RE = re.compile(
    r"\bJOINERY\s+HEIGHTS?\s+TO\s+BE\s+(?P<value>\d{3,4})\s*"
    r"(?:MM\s*)?A\s*F\s*L\s+U\s*N\s*O\b",
    re.IGNORECASE,
)

_Key = tuple[str, str, str, str]


@dataclass(frozen=True)
class DocumentJoineryHeadHeightEvidence:
    evidence_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    head_height_mm: float
    source_page_ids: tuple[str, ...]
    source_text_observation_ids: tuple[str, ...]
    raw_texts: tuple[str, ...]
    units: str = "mm"
    datum: str = "AFL"
    scope: str = "document_joinery_uno"
    schema_version: str = JOINERY_HEAD_HEIGHT_SCHEMA_VERSION


@dataclass(frozen=True)
class DocumentJoineryHeadHeightResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    evidence: Optional[DocumentJoineryHeadHeightEvidence] = None
    schema_version: str = JOINERY_HEAD_HEIGHT_SCHEMA_VERSION


def _blocked(
    status: EvidenceResolutionStatus,
    *reasons: str,
) -> DocumentJoineryHeadHeightResult:
    return DocumentJoineryHeadHeightResult(
        status=status,
        reason_codes=tuple(dict.fromkeys(reason for reason in reasons if reason))
        or (JOINERY_HEAD_HEIGHT_UNAVAILABLE,),
    )


def _normalize_note_text(text: str) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", str(text or "").upper()).strip()


def _parse_joinery_head_height_mm(text: str) -> Optional[float]:
    normalized = _normalize_note_text(text)
    match = _NOTE_RE.search(normalized)
    if match is None:
        return None
    try:
        value = float(match.group("value"))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    if not (_MIN_HEAD_HEIGHT_MM <= value <= _MAX_HEAD_HEIGHT_MM):
        return None
    return value


class DocumentJoineryHeadHeightProducer:
    def __init__(
        self,
        source_visibility_producer: SourceVisibilityProducer,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "DocumentJoineryHeadHeightProducer must be obtained from "
                "from_source_visibility_producer()"
            )
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned")
        self._source = source_visibility_producer
        self._results: dict[_Key, DocumentJoineryHeadHeightResult] = {}

    @classmethod
    def from_source_visibility_producer(
        cls,
        source_visibility_producer: SourceVisibilityProducer,
    ) -> "DocumentJoineryHeadHeightProducer":
        return cls(source_visibility_producer, _seal=_PRODUCER_SEAL)

    def publish_revision(
        self,
        revision_id: str,
    ) -> DocumentJoineryHeadHeightResult:
        published = self._source.published_snapshot_for_revision(str(revision_id))
        if published is None:
            return _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                JOINERY_HEAD_HEIGHT_SOURCE_SCOPE_UNAVAILABLE,
            )
        key = (
            published.revision.document_id,
            published.revision.revision_id,
            published.revision.source_sha256,
            published.snapshot.snapshot_id,
        )
        prior = self._results.get(key)
        if prior is not None:
            return prior

        integrity = self._source.text_integrity_authority()
        grouped: dict[
            tuple[str, object, object],
            list[tuple[int, str, str]],
        ] = {}
        for observation_id in published.text_observation_ids:
            resolved = integrity.resolve_text(
                ObservationSelector(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    observation_id=observation_id,
                )
            )
            if (
                resolved.status is not EvidenceResolutionStatus.CORROBORATED
                or resolved.trusted_text is None
                or resolved.receipt is None
            ):
                continue
            receipt = resolved.receipt
            page_id = str(receipt.page_id)
            if receipt.block_no is None or receipt.line_no is None:
                group_key = (page_id, "observation", observation_id)
                order = 0
            else:
                group_key = (page_id, int(receipt.block_no), int(receipt.line_no))
                order = int(receipt.word_no or 0)
            grouped.setdefault(group_key, []).append(
                (order, observation_id, resolved.trusted_text)
            )

        matches: list[tuple[float, str, tuple[str, ...], str]] = []
        for (page_id, _block, _line), rows in grouped.items():
            rows.sort(key=lambda item: (item[0], item[1]))
            text_value = " ".join(row[2] for row in rows)
            height_mm = _parse_joinery_head_height_mm(text_value)
            if height_mm is None:
                continue
            matches.append(
                (
                    height_mm,
                    page_id,
                    tuple(row[1] for row in rows),
                    text_value,
                )
            )

        if not matches:
            return self._store(
                key,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    JOINERY_HEAD_HEIGHT_UNAVAILABLE,
                ),
            )

        distinct_values = {round(match[0], 6) for match in matches}
        if len(distinct_values) != 1:
            return self._store(
                key,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    JOINERY_HEAD_HEIGHT_CONFLICT,
                ),
            )

        height_mm = float(matches[0][0])
        page_ids = tuple(sorted({match[1] for match in matches}))
        observation_ids = tuple(
            sorted(
                {
                    observation_id
                    for _height, _page, ids, _text in matches
                    for observation_id in ids
                }
            )
        )
        raw_texts = tuple(sorted({match[3] for match in matches}))
        payload = {
            "schema_version": JOINERY_HEAD_HEIGHT_SCHEMA_VERSION,
            "document_id": published.revision.document_id,
            "revision_id": published.revision.revision_id,
            "source_sha256": published.revision.source_sha256,
            "snapshot_id": published.snapshot.snapshot_id,
            "head_height_mm": height_mm,
            "source_page_ids": page_ids,
            "source_text_observation_ids": observation_ids,
        }
        evidence = DocumentJoineryHeadHeightEvidence(
            evidence_id=stable_contract_id(
                "document_joinery_head_height",
                payload,
                digest_chars=32,
            ),
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            head_height_mm=height_mm,
            source_page_ids=page_ids,
            source_text_observation_ids=observation_ids,
            raw_texts=raw_texts,
        )
        return self._store(
            key,
            DocumentJoineryHeadHeightResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(JOINERY_HEAD_HEIGHT_RESOLVED,),
                evidence=evidence,
            ),
        )

    def _store(
        self,
        key: _Key,
        result: DocumentJoineryHeadHeightResult,
    ) -> DocumentJoineryHeadHeightResult:
        existing = self._results.get(key)
        if existing is not None and existing != result:
            raise RuntimeError("document joinery head-height producer equivocation")
        self._results[key] = result
        return result

    def authority(self) -> "DocumentJoineryHeadHeightAuthority":
        return DocumentJoineryHeadHeightAuthority(
            MappingProxyType(dict(self._results)),
            _seal=_AUTHORITY_SEAL,
        )


class DocumentJoineryHeadHeightAuthority:
    def __init__(
        self,
        results: Mapping[_Key, DocumentJoineryHeadHeightResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("DocumentJoineryHeadHeightAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        snapshot_id: str,
    ) -> DocumentJoineryHeadHeightResult:
        key = (
            str(document_id),
            str(revision_id),
            str(source_sha256),
            str(snapshot_id),
        )
        return self._results.get(
            key,
            _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                JOINERY_HEAD_HEIGHT_UNAVAILABLE,
            ),
        )


_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()


__all__ = [
    "DocumentJoineryHeadHeightAuthority",
    "DocumentJoineryHeadHeightEvidence",
    "DocumentJoineryHeadHeightProducer",
    "DocumentJoineryHeadHeightResult",
    "JOINERY_HEAD_HEIGHT_CONFLICT",
    "JOINERY_HEAD_HEIGHT_RESOLVED",
    "JOINERY_HEAD_HEIGHT_SCHEMA_VERSION",
    "JOINERY_HEAD_HEIGHT_SOURCE_SCOPE_UNAVAILABLE",
    "JOINERY_HEAD_HEIGHT_UNAVAILABLE",
    "_parse_joinery_head_height_mm",
]
