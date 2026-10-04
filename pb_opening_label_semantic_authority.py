"""Authenticated semantic label evidence for proven physical openings."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_opening_label_dimension_authority import (
    _TrustedTextLine,
    _bbox_overlap_fraction,
    _bbox_union,
    _gap_span,
    _label_matches_gap,
)
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

OPENING_LABEL_SEMANTIC_SCHEMA_VERSION = "1.0.0"
OPENING_LABEL_SEMANTIC_RESOLVED = "opening_label_semantic_resolved"
OPENING_LABEL_SEMANTIC_UNAVAILABLE = "opening_label_semantic_unavailable"
OPENING_LABEL_SEMANTIC_CONFLICT = "opening_label_semantic_conflict"

_LEGEND_HEADER_RE = re.compile(r"\b(?:LEGEND|ABBREVIATIONS?)\b", re.I)
_LEGEND_CODE_RE = re.compile(r"^[A-Z][A-Z0-9._/+\-]{1,14}$", re.I)
_LABEL_CODE_TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9._/+\-]{1,14}\b", re.I)
_EXPLICIT_WINDOW_WORD_RE = re.compile(r"\bWINDOWS?\b", re.I)
_EXPLICIT_DOOR_WORD_RE = re.compile(r"\bDOORS?\b", re.I)
_EXPLICIT_DOOR_PHRASE_RE = re.compile(
    r"\b(?:STACKER|STACKING\s+DOOR|PANEL[\s-]+LIFT(?:\s+DOOR)?)\b",
    re.I,
)


@dataclass(frozen=True)
class OpeningLabelSemanticEvidence:
    evidence_id: str
    opening_record_id: str
    page_id: str
    semantic_kind: str
    source_text_observation_ids: tuple[str, ...]
    legend_observation_ids: tuple[str, ...]
    raw_texts: tuple[str, ...]
    schema_version: str = OPENING_LABEL_SEMANTIC_SCHEMA_VERSION


@dataclass(frozen=True)
class OpeningLabelSemanticResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    evidence: Optional[OpeningLabelSemanticEvidence] = None


def _explicit_word_kind(text: str) -> tuple[Optional[str], bool]:
    has_window = _EXPLICIT_WINDOW_WORD_RE.search(text or "") is not None
    has_door = (
        _EXPLICIT_DOOR_WORD_RE.search(text or "") is not None
        or _EXPLICIT_DOOR_PHRASE_RE.search(text or "") is not None
    )
    if has_window and has_door:
        return None, True
    if has_window:
        return "window", False
    if has_door:
        return "door", False
    return None, False


def _trusted_native_lines(source: SourceVisibilityProducer, opening):
    published = source.published_snapshot_for_revision(opening.revision_id)
    if published is None or published.snapshot.snapshot_id != opening.snapshot_id:
        return ()
    integrity = source.text_integrity_authority()
    grouped = {}
    for observation_id in published.text_observation_ids:
        resolved = integrity.resolve_text(ObservationSelector(
            document_id=opening.document_id,
            revision_id=opening.revision_id,
            source_sha256=opening.source_sha256,
            snapshot_id=opening.snapshot_id,
            observation_id=observation_id,
        ))
        receipt = getattr(resolved, "receipt", None)
        if (
            resolved.status is not EvidenceResolutionStatus.CORROBORATED
            or resolved.trusted_text is None
            or receipt is None
            or str(receipt.page_id) != str(opening.page_id)
        ):
            continue
        block_no = int(receipt.block_no) if receipt.block_no is not None else None
        line_no = int(receipt.line_no) if receipt.line_no is not None else None
        if block_no is not None and line_no is not None:
            key = ("native", block_no, line_no)
            order = int(receipt.word_no or 0)
        else:
            key = ("obs", observation_id)
            order = 0
        grouped.setdefault(key, []).append((
            order,
            observation_id,
            resolved.trusted_text,
            tuple(float(v) for v in receipt.geometry),
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
                text=" ".join(row[2] for row in ordered).strip(),
                bbox=bbox,
            ),
        ))
    return tuple(out)


def _legend_semantics(lines):
    # A legend heading may be emitted as a separate native text block from the
    # table it governs. Gate semantics at page scope, but still require each
    # code/definition pair to share one producer-owned block and align.
    has_legend_header = any(
        _LEGEND_HEADER_RE.search(line.text or "") is not None
        for _block_no, _line_no, line in lines
    )
    if not has_legend_header:
        return {}, set()

    resolved = {}
    conflicted = set()

    # Some PDF producers keep code + definition on one native line.
    for block_no, _line_no, line in lines:
        if block_no is None:
            continue
        parts = line.text.strip().split(maxsplit=1)
        if len(parts) != 2:
            continue
        code = parts[0].upper()
        if _LEGEND_CODE_RE.fullmatch(code) is None:
            continue
        kind, conflict = _explicit_word_kind(parts[1])
        if conflict:
            conflicted.add(code)
            resolved.pop(code, None)
            continue
        if kind is None:
            continue
        prior = resolved.get(code)
        if prior is not None and prior[0] != kind:
            conflicted.add(code)
            resolved.pop(code, None)
            continue
        resolved[code] = (kind, tuple(sorted(line.observation_ids)))

    for block_no, _line_no, code_line in lines:
        if block_no is None:
            continue
        code = code_line.text.strip().upper()
        if _LEGEND_CODE_RE.fullmatch(code) is None:
            continue
        candidates = []
        for other_block, _other_line_no, desc_line in lines:
            if other_block != block_no or desc_line is code_line:
                continue
            if desc_line.bbox[0] <= code_line.bbox[2]:
                continue
            overlap = _bbox_overlap_fraction(
                code_line.bbox[1], code_line.bbox[3],
                desc_line.bbox[1], desc_line.bbox[3],
            )
            if overlap < 0.5:
                continue
            kind, conflict = _explicit_word_kind(desc_line.text)
            if conflict:
                conflicted.add(code)
                continue
            if kind is not None:
                candidates.append((kind, desc_line.observation_ids))
        kinds = {kind for kind, _ids in candidates}
        if len(kinds) > 1:
            conflicted.add(code)
            resolved.pop(code, None)
            continue
        if len(kinds) != 1 or code in conflicted:
            continue
        kind = next(iter(kinds))
        ids = tuple(sorted({
            *code_line.observation_ids,
            *(eid for candidate_kind, value_ids in candidates if candidate_kind == kind for eid in value_ids),
        }))
        prior = resolved.get(code)
        if prior is not None and prior[0] != kind:
            conflicted.add(code)
            resolved.pop(code, None)
            continue
        resolved[code] = (kind, ids)
    for code in conflicted:
        resolved.pop(code, None)
    return resolved, conflicted


class OpeningLabelSemanticProducer:
    def __init__(self, source: SourceVisibilityProducer) -> None:
        if type(source) is not SourceVisibilityProducer:
            raise TypeError("source must be producer-owned")
        self._source = source
        self._physical = source.physical_opening_authority()

    @classmethod
    def from_source_visibility_producer(cls, source):
        return cls(source)

    def publish_scope(self, selector: ObservationSelector) -> OpeningLabelSemanticResult:
        physical = self._physical.prove_existence(selector)
        opening = physical.existence_record
        if (
            physical.status is not EvidenceResolutionStatus.CORROBORATED
            or physical.proposition != PHYSICAL_OPENING_EXISTS
            or opening is None
        ):
            return OpeningLabelSemanticResult(
                EvidenceResolutionStatus.ABSTAINED,
                (OPENING_LABEL_SEMANTIC_UNAVAILABLE,),
            )
        visibility = self._source.authority()
        source_records = []
        for observation_id in opening.source_observation_ids:
            result = visibility.resolve_visible(ObservationSelector(
                document_id=opening.document_id,
                revision_id=opening.revision_id,
                source_sha256=opening.source_sha256,
                snapshot_id=opening.snapshot_id,
                observation_id=observation_id,
            ))
            if result.status is not EvidenceResolutionStatus.CORROBORATED or result.observation is None:
                return OpeningLabelSemanticResult(EvidenceResolutionStatus.ABSTAINED, (OPENING_LABEL_SEMANTIC_UNAVAILABLE,))
            source_records.append(result.observation)
        gap = _gap_span(source_records)
        if gap is None:
            return OpeningLabelSemanticResult(EvidenceResolutionStatus.ABSTAINED, (OPENING_LABEL_SEMANTIC_UNAVAILABLE,))

        lines = _trusted_native_lines(self._source, opening)
        legend, legend_conflicts = _legend_semantics(lines)
        candidates = []
        for _block_no, _line_no, line in lines:
            if not _label_matches_gap(line, gap):
                continue
            direct_kind, direct_conflict = _explicit_word_kind(line.text)
            if direct_conflict:
                return OpeningLabelSemanticResult(EvidenceResolutionStatus.CONFLICT, (OPENING_LABEL_SEMANTIC_CONFLICT,))
            if direct_kind is not None:
                candidates.append((direct_kind, line, (), "explicit_phrase"))
            tokens = {m.group(0).upper() for m in _LABEL_CODE_TOKEN_RE.finditer(line.text or "")}
            if tokens & legend_conflicts:
                return OpeningLabelSemanticResult(EvidenceResolutionStatus.CONFLICT, (OPENING_LABEL_SEMANTIC_CONFLICT,))
            for token in sorted(tokens):
                definition = legend.get(token)
                if definition is not None:
                    candidates.append((definition[0], line, definition[1], "source_legend"))

        kinds = {kind for kind, _line, _ids, _basis in candidates}
        if len(kinds) > 1:
            return OpeningLabelSemanticResult(EvidenceResolutionStatus.CONFLICT, (OPENING_LABEL_SEMANTIC_CONFLICT,))
        if not kinds:
            return OpeningLabelSemanticResult(EvidenceResolutionStatus.ABSTAINED, (OPENING_LABEL_SEMANTIC_UNAVAILABLE,))
        kind = next(iter(kinds))
        label_ids = tuple(sorted({eid for k, line, _ids, _basis in candidates if k == kind for eid in line.observation_ids}))
        legend_ids = tuple(sorted({eid for k, _line, ids, _basis in candidates if k == kind for eid in ids}))
        raw_texts = tuple(sorted({line.text for k, line, _ids, _basis in candidates if k == kind}))
        payload = {
            "opening_record_id": opening.record_id,
            "page_id": opening.page_id,
            "semantic_kind": kind,
            "source_text_observation_ids": label_ids,
            "legend_observation_ids": legend_ids,
            "raw_texts": raw_texts,
        }
        evidence = OpeningLabelSemanticEvidence(
            evidence_id=stable_contract_id("opening_label_semantic", payload, digest_chars=32),
            opening_record_id=opening.record_id,
            page_id=opening.page_id,
            semantic_kind=kind,
            source_text_observation_ids=label_ids,
            legend_observation_ids=legend_ids,
            raw_texts=raw_texts,
        )
        return OpeningLabelSemanticResult(
            EvidenceResolutionStatus.CORROBORATED,
            (OPENING_LABEL_SEMANTIC_RESOLVED,),
            evidence,
        )


__all__ = [
    "OPENING_LABEL_SEMANTIC_CONFLICT",
    "OPENING_LABEL_SEMANTIC_RESOLVED",
    "OPENING_LABEL_SEMANTIC_UNAVAILABLE",
    "OpeningLabelSemanticEvidence",
    "OpeningLabelSemanticProducer",
    "OpeningLabelSemanticResult",
]