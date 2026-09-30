"""Producer-owned structural definition compilation from trusted source text.

Shadow only: this module can discover source-owned structural definitions.
It cannot create physical member instances, prove view completeness, or publish
a structural quantity.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Mapping, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_structural_member_authority import StructuralMemberSelector
from pb_structural_member_definition_producer import (
    ParsedStructuralDefinition,
    SourceStructuralTextBlock,
    parse_structural_member_definitions,
)

STRUCTURAL_DEFINITION_SOURCE_SHADOW_SCHEMA_VERSION = "1.0.0"
STRUCTURAL_DEFINITION_SOURCE_SHADOW_RESOLVED = (
    "structural_definition_source_shadow_resolved"
)
STRUCTURAL_DEFINITION_SOURCE_SHADOW_EMPTY = (
    "structural_definition_source_shadow_empty"
)
STRUCTURAL_DEFINITION_SOURCE_SHADOW_SCOPE_MISMATCH = (
    "structural_definition_source_shadow_scope_mismatch"
)
STRUCTURAL_DEFINITION_SOURCE_SHADOW_PAGE_UNAVAILABLE = (
    "structural_definition_source_shadow_page_unavailable"
)
STRUCTURAL_DEFINITION_SOURCE_SHADOW_TEXT_INCOMPLETE = (
    "structural_definition_source_shadow_text_incomplete"
)


@dataclass(frozen=True)
class StructuralDefinitionSourceShadowResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    selector: StructuralMemberSelector
    blocks: tuple[SourceStructuralTextBlock, ...]
    definitions: tuple[ParsedStructuralDefinition, ...]
    trusted_text_observation_ids: tuple[str, ...]
    schema_version: str = STRUCTURAL_DEFINITION_SOURCE_SHADOW_SCHEMA_VERSION


def _blocked(
    selector: StructuralMemberSelector,
    status: EvidenceResolutionStatus,
    *reasons: str,
) -> StructuralDefinitionSourceShadowResult:
    return StructuralDefinitionSourceShadowResult(
        status=status,
        reason_codes=tuple(dict.fromkeys(str(reason) for reason in reasons if str(reason))),
        selector=selector,
        blocks=(),
        definitions=(),
        trusted_text_observation_ids=(),
    )


def _selector_matches_snapshot(selector: StructuralMemberSelector, published) -> bool:
    return (
        str(published.revision.document_id) == str(selector.document_id)
        and str(published.revision.revision_id) == str(selector.revision_id)
        and str(published.revision.source_sha256) == str(selector.source_sha256)
        and str(published.snapshot.snapshot_id) == str(selector.snapshot_id)
    )



_STANDALONE_DECORATIVE_MARKERS = frozenset({"-", "–", "—", "•", "·", "▪", "◦"})


def _is_ignorable_standalone_untrusted_marker(
    receipt,
    line_counts: Mapping[tuple[str, int, int], int],
) -> bool:
    """Allow omission only for a source-isolated decorative marker line.

    Structural definition parsing consumes semantic words. A marker can be
    omitted without inventing text only when the producer proves it is a
    standalone first token on its own line. Any token sharing a line, any
    alphanumeric token, or any receipt without complete line coordinates
    remains completeness-blocking.
    """

    if (
        receipt.block_no is None
        or receipt.line_no is None
        or receipt.word_no is None
        or int(receipt.word_no) != 0
        or str(receipt.raw_text or "").strip() not in _STANDALONE_DECORATIVE_MARKERS
    ):
        return False
    key = (
        str(receipt.page_id),
        int(receipt.block_no),
        int(receipt.line_no),
    )
    return int(line_counts.get(key, 0)) == 1


def compile_structural_definition_source_shadow(
    *,
    selector: StructuralMemberSelector,
    source_visibility_producer: SourceVisibilityProducer,
    page_ids: Sequence[str] | None = None,
) -> StructuralDefinitionSourceShadowResult:
    """Compile count-free structural definitions from producer-trusted PDF words.

    Page-scoped pseudo-view ids deliberately say unscoped. Native source words
    do not own a viewport, and this adapter never manufactures one.
    """
    if type(selector) is not StructuralMemberSelector:
        raise TypeError("selector must be StructuralMemberSelector")
    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError(
            "source_visibility_producer must be producer-owned "
            "SourceVisibilityProducer"
        )

    published = source_visibility_producer.published_snapshot_for_revision(
        selector.revision_id
    )
    if published is None:
        return _blocked(
            selector,
            EvidenceResolutionStatus.ABSTAINED,
            STRUCTURAL_DEFINITION_SOURCE_SHADOW_PAGE_UNAVAILABLE,
        )
    if not _selector_matches_snapshot(selector, published):
        return _blocked(
            selector,
            EvidenceResolutionStatus.CONFLICT,
            STRUCTURAL_DEFINITION_SOURCE_SHADOW_SCOPE_MISMATCH,
        )

    decoded_pages = {str(int(page)) for page in published.coverage.decoded_pages}
    if page_ids is None:
        selected_pages = decoded_pages
    else:
        selected_pages = {
            str(page).strip()
            for page in page_ids
            if str(page).strip()
        }
        if not selected_pages or not selected_pages <= decoded_pages:
            return _blocked(
                selector,
                EvidenceResolutionStatus.ABSTAINED,
                STRUCTURAL_DEFINITION_SOURCE_SHADOW_PAGE_UNAVAILABLE,
            )

    text_authority = source_visibility_producer.text_integrity_authority()
    groups: dict[
        tuple[str, int],
        list[tuple[int, int, str, str, tuple[float, ...]]],
    ] = {}
    trusted_ids: list[str] = []
    blocked_blocks: set[tuple[str, int]] = set()
    incomplete_block = False

    resolved_rows = []
    for observation_id in published.text_observation_ids:
        result = text_authority.resolve_text(
            ObservationSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                observation_id=observation_id,
            )
        )
        receipt = result.receipt
        if receipt is None or str(receipt.page_id) not in selected_pages:
            continue
        resolved_rows.append((str(observation_id), result, receipt))

    line_counts: Counter[tuple[str, int, int]] = Counter()
    for _observation_id, _result, receipt in resolved_rows:
        if receipt.block_no is None or receipt.line_no is None:
            continue
        line_counts[
            (
                str(receipt.page_id),
                int(receipt.block_no),
                int(receipt.line_no),
            )
        ] += 1

    for observation_id, result, receipt in resolved_rows:
        if receipt.block_no is None:
            incomplete_block = True
            continue
        block_key = (str(receipt.page_id), int(receipt.block_no))
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or result.trusted_text is None
            or receipt.line_no is None
            or receipt.word_no is None
            or len(receipt.geometry) < 4
        ):
            if _is_ignorable_standalone_untrusted_marker(receipt, line_counts):
                continue
            incomplete_block = True
            blocked_blocks.add(block_key)
            continue
        groups.setdefault(
            block_key,
            [],
        ).append(
            (
                int(receipt.line_no),
                int(receipt.word_no),
                observation_id,
                str(result.trusted_text),
                tuple(float(value) for value in receipt.geometry[:4]),
            )
        )
        trusted_ids.append(observation_id)

    blocks: list[SourceStructuralTextBlock] = []
    for (page_id, block_no), rows in sorted(groups.items()):
        if (page_id, block_no) in blocked_blocks:
            continue
        ordered = sorted(rows, key=lambda row: (row[0], row[1], row[2]))
        word_ids = tuple(row[2] for row in ordered)
        text = " ".join(row[3] for row in ordered if row[3].strip()).strip()
        if not text:
            continue
        x0 = min(row[4][0] for row in ordered)
        y0 = min(row[4][1] for row in ordered)
        x1 = max(row[4][2] for row in ordered)
        y1 = max(row[4][3] for row in ordered)
        scope_id = f"source-page:{page_id}:unscoped"
        block_id = stable_contract_id(
            "structural_source_text_block_v1",
            {
                "document_id": selector.document_id,
                "revision_id": selector.revision_id,
                "source_sha256": selector.source_sha256,
                "snapshot_id": selector.snapshot_id,
                "page_id": page_id,
                "block_no": block_no,
                "word_observation_ids": word_ids,
            },
            digest_chars=32,
        )
        blocks.append(
            SourceStructuralTextBlock(
                page_id=page_id,
                view_id=scope_id,
                block_id=block_id,
                reading_order=block_no,
                bbox=(x0, y0, x1, y1),
                text=text,
                scope_id=scope_id,
            )
        )

    definitions = parse_structural_member_definitions(
        selector=selector,
        blocks=tuple(blocks),
    )
    reasons = []
    if incomplete_block:
        reasons.append(STRUCTURAL_DEFINITION_SOURCE_SHADOW_TEXT_INCOMPLETE)
    reasons.append(
        STRUCTURAL_DEFINITION_SOURCE_SHADOW_RESOLVED
        if definitions
        else STRUCTURAL_DEFINITION_SOURCE_SHADOW_EMPTY
    )
    return StructuralDefinitionSourceShadowResult(
        status=(
            EvidenceResolutionStatus.CORROBORATED
            if definitions
            else EvidenceResolutionStatus.ABSTAINED
        ),
        reason_codes=tuple(reasons),
        selector=selector,
        blocks=tuple(blocks),
        definitions=definitions,
        trusted_text_observation_ids=tuple(sorted(set(trusted_ids))),
    )


__all__ = [
    "STRUCTURAL_DEFINITION_SOURCE_SHADOW_SCHEMA_VERSION",
    "STRUCTURAL_DEFINITION_SOURCE_SHADOW_RESOLVED",
    "STRUCTURAL_DEFINITION_SOURCE_SHADOW_EMPTY",
    "STRUCTURAL_DEFINITION_SOURCE_SHADOW_SCOPE_MISMATCH",
    "STRUCTURAL_DEFINITION_SOURCE_SHADOW_PAGE_UNAVAILABLE",
    "STRUCTURAL_DEFINITION_SOURCE_SHADOW_TEXT_INCOMPLETE",
    "StructuralDefinitionSourceShadowResult",
    "_is_ignorable_standalone_untrusted_marker",
    "compile_structural_definition_source_shadow",
]
