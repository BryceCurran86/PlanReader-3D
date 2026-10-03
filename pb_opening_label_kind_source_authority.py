"""Source-owned semantic label evidence for proven physical openings.

This module never creates an opening and never decides final kind. It only
authenticates semantic label evidence owned by an already-proven physical
opening. Final reconciliation remains in pb_opening_kind_authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_opening_label_dimension_authority import (
    _TrustedTextLine,
    _bbox_union,
    _gap_span,
    _label_matches_gap,
)
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

OPENING_LABEL_KIND_SCHEMA_VERSION = "1.0.0"
OPENING_LABEL_KIND_RESOLVED = "opening_label_kind_resolved"
OPENING_LABEL_KIND_UNAVAILABLE = "opening_label_kind_unavailable"
OPENING_LABEL_KIND_CONFLICT = "opening_label_kind_conflict"

_CODE_RE = re.compile(r"^[A-Z][A-Z0-9._/+-]{1,14}$", re.I)
_WINDOW_RE = re.compile(r"\\bWINDOWS?\\b", re.I)
_DOOR_RE = re.compile(r"\\bDOORS?\\b", re.I)
_TOKEN_RE = re.compile(r"[A-Z][A-Z0-9._/+-]{1,14}", re.I)


@dataclass(frozen=True)
class OpeningLabelKindEvidence:
    evidence_id: str
    opening_record_id: str
    page_id: str
    opening_kind: str
    label_observation_ids: tuple[str, ...]
    definition_observation_ids: tuple[str, ...]
    raw_label_text: str
    basis: str
    schema_version: str = OPENING_LABEL_KIND_SCHEMA_VERSION


@dataclass(frozen=True)
class OpeningLabelKindResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    evidence: Optional[OpeningLabelKindEvidence] = None


def _phrase_kind(text: str) -> Optional[str]:
    has_window = _WINDOW_RE.search(text or "") is not None
    has_door = _DOOR_RE.search(text or "") is not None
    if has_window == has_door:
        return None
    return "window" if has_window else "door"


def _trusted_lines(source, opening):
    published = source.published_snapshot_for_revision(opening.revision_id)
    if published is None or published.snapshot.snapshot_id != opening.snapshot_id:
        return ()
    integrity = source.text_integrity_authority()
    grouped = {}
    for observation_id in published.text_observation_ids:
        resolved = integrity.resolve_text(
            ObservationSelector(
                document_id=opening.document_id,
                revision_id=opening.revision_id,
                source_sha256=opening.source_sha256,
                snapshot_id=opening.snapshot_id,
                observation_id=observation_id,
            )
        )
        receipt = resolved.receipt
        if (
            resolved.status is not EvidenceResolutionStatus.CORROBORATED
            or resolved.trusted_text is None
            or receipt is None
            or str(receipt.page_id) != str(opening.page_id)
        ):
            continue
        block_no = int(receipt.block_no) if receipt.block_no is not None else None
        line_no = int(receipt.line_no) if receipt.line_no is not None else None
        key = (block_no, line_no) if block_no is not None and line_no is not None else (observation_id,)
        grouped.setdefault(key, []).append((
            int(receipt.word_no or 0),
            observation_id,
            resolved.trusted_text,
            tuple(float(value) for value in receipt.geometry),
            block_no,
            line_no,
        ))
    out = []
    for rows in grouped.values():
        ordered = sorted(rows, key=lambda item: (item[0], item[1]))
        bbox = _bbox_union([row[3] for row in ordered])
        if bbox is None:
            continue
        out.append((
            ordered[0][4],
            ordered[0][5],
            _TrustedTextLine(
                observation_ids=tuple(row[1] for row in ordered),
                text=" ".join(row[2] for row in ordered),
                bbox=bbox,
            ),
        ))
    return tuple(sorted(out, key=lambda item: (
        item[0] if item[0] is not None else 10**9,
        item[1] if item[1] is not None else 10**9,
        item[2].bbox[1],
        item[2].bbox[0],
    )))


def _legend_map(lines):
    by_block = {}
    for block_no, line_no, line in lines:
        if block_no is None or line_no is None:
            continue
        by_block.setdefault(block_no, {})[line_no] = line
    candidates = {}
    for block in by_block.values():
        for line_no, code_line in block.items():
            code = code_line.text.strip().upper()
            if _CODE_RE.fullmatch(code) is None:
                continue
            desc = block.get(line_no + 1)
            if desc is None:
                continue
            kind = _phrase_kind(desc.text)
            if kind is None:
                continue
            ids = tuple(sorted({*code_line.observation_ids, *desc.observation_ids}))
            candidates.setdefault(code, []).append((kind, ids))
    resolved = {}
    conflicted = set()
    for code, values in candidates.items():
        kinds = {kind for kind, _ids in values}
        if len(kinds) != 1:
            conflicted.add(code)
            continue
        kind = next(iter(kinds))
        ids = tuple(sorted({eid for _kind, value_ids in values for eid in value_ids}))
        resolved[code] = (kind, ids)
    return resolved, conflicted


class OpeningLabelKindProducer:
    def __init__(self, source: SourceVisibilityProducer) -> None:
        if type(source) is not SourceVisibilityProducer:
            raise TypeError("source must be producer-owned")
        self._source = source
        self._physical = source.physical_opening_authority()

    @classmethod
    def from_source_visibility_producer(cls, source):
        return cls(source)

    def publish_scope(self, selector: ObservationSelector) -> OpeningLabelKindResult:
        physical = self._physical.prove_existence(selector)
        opening = physical.existence_record
        if (
            physical.status is not EvidenceResolutionStatus.CORROBORATED
            or physical.proposition != PHYSICAL_OPENING_EXISTS
            or opening is None
        ):
            return OpeningLabelKindResult(
                EvidenceResolutionStatus.ABSTAINED,
                (OPENING_LABEL_KIND_UNAVAILABLE,),
            )

        visibility = self._source.authority()
        source_records = []
        for observation_id in opening.source_observation_ids:
            resolved = visibility.resolve_visible(ObservationSelector(
                document_id=opening.document_id,
                revision_id=opening.revision_id,
                source_sha256=opening.source_sha256,
                snapshot_id=opening.snapshot_id,
                observation_id=observation_id,
            ))
            if resolved.status is not EvidenceResolutionStatus.CORROBORATED or resolved.observation is None:
                return OpeningLabelKindResult(EvidenceResolutionStatus.ABSTAINED, (OPENING_LABEL_KIND_UNAVAILABLE,))
            source_records.append(resolved.observation)
        gap = _gap_span(source_records)
        if gap is None:
            return OpeningLabelKindResult(EvidenceResolutionStatus.ABSTAINED, (OPENING_LABEL_KIND_UNAVAILABLE,))

        lines = _trusted_lines(self._source, opening)
        legend, conflicted = _legend_map(lines)
        candidates = []
        saw_conflict = False
        for _block_no, _line_no, label in lines:
            if not _label_matches_gap(label, gap):
                continue
            direct = _phrase_kind(label.text)
            if direct is not None:
                candidates.append((direct, label, (), "explicit_phrase"))
            for token in (value.upper() for value in _TOKEN_RE.findall(label.text)):
                if token in conflicted:
                    saw_conflict = True
                    continue
                mapped = legend.get(token)
                if mapped is not None:
                    candidates.append((mapped[0], label, mapped[1], "source_legend"))

        kinds = {kind for kind, _label, _ids, _basis in candidates}
        if saw_conflict or len(kinds) > 1:
            return OpeningLabelKindResult(EvidenceResolutionStatus.CONFLICT, (OPENING_LABEL_KIND_CONFLICT,))
        if not candidates:
            return OpeningLabelKindResult(EvidenceResolutionStatus.ABSTAINED, (OPENING_LABEL_KIND_UNAVAILABLE,))

        kind = next(iter(kinds))
        label_ids = tuple(sorted({eid for k, label, _ids, _basis in candidates if k == kind for eid in label.observation_ids}))
        definition_ids = tuple(sorted({eid for k, _label, ids, _basis in candidates if k == kind for eid in ids}))
        labels = sorted({label.text for k, label, _ids, _basis in candidates if k == kind})
        bases = sorted({basis for k, _label, _ids, basis in candidates if k == kind})
        payload = {
            "opening_record_id": opening.record_id,
            "page_id": opening.page_id,
            "opening_kind": kind,
            "label_observation_ids": label_ids,
            "definition_observation_ids": definition_ids,
            "labels": labels,
            "bases": bases,
        }
        evidence = OpeningLabelKindEvidence(
            evidence_id=stable_contract_id("opening_label_kind", payload, digest_chars=32),
            opening_record_id=opening.record_id,
            page_id=opening.page_id,
            opening_kind=kind,
            label_observation_ids=label_ids,
            definition_observation_ids=definition_ids,
            raw_label_text=" | ".join(labels),
            basis="+".join(bases),
        )
        return OpeningLabelKindResult(
            EvidenceResolutionStatus.CORROBORATED,
            (OPENING_LABEL_KIND_RESOLVED,),
            evidence,
        )


__all__ = [
    "OPENING_LABEL_KIND_CONFLICT",
    "OPENING_LABEL_KIND_RESOLVED",
    "OPENING_LABEL_KIND_UNAVAILABLE",
    "OpeningLabelKindEvidence",
    "OpeningLabelKindProducer",
    "OpeningLabelKindResult",
]