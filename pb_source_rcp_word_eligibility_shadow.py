"""Producer-Owned RCP Word and Viewport Scope Eligibility Shadow Authority.

Workstream B Item 16 / GPT2 PR #3469 & Issue #2843:
Classifies native PDF text words on reflected ceiling plans (e.g. Page 9) to
determine geometric and syntactic eligibility for ceiling material mark candidacy.
Disambiguates authentic in-plan room ceiling callouts (e.g. IPF1, GRID / 2400 CLG, CL03)
from tabular schedule cells, multi-word general specification prose, and
out-of-viewport annotations without project-specific hardcoding.

Non-negotiable invariants:
- Shadow mode: candidate status only, non-publishing, zero commercial projection.
- Fails closed on prose blocks, schedule cells, and out-of-viewport words.
- Preserves 2.5 pt snap tolerance and byte-for-byte customer retention.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)


class RcpWordRole(str, Enum):
    IN_PLAN_CEILING_ANNOTATION = "IN_PLAN_CEILING_ANNOTATION"
    NON_CEILING_LABEL = "NON_CEILING_LABEL"
    OTHER_PLAN_TEXT = "OTHER_PLAN_TEXT"
    SCHEDULE_TABLE_CELL = "SCHEDULE_TABLE_CELL"
    GENERAL_NOTE_PROSE = "GENERAL_NOTE_PROSE"
    TITLE_BLOCK_METADATA = "TITLE_BLOCK_METADATA"
    OUT_OF_VIEWPORT = "OUT_OF_VIEWPORT"


@dataclass(frozen=True)
class RcpWordEvidence:
    word_id: str
    text: str
    bbox_pdf_pts: Tuple[float, float, float, float]
    block_index: int
    line_index: int
    word_index: int
    role: RcpWordRole
    is_eligible_for_ceiling_mark: bool
    status: EvidenceResolutionStatus
    notes: str
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "word_id": self.word_id,
            "text": self.text,
            "bbox_pdf_pts": list(self.bbox_pdf_pts),
            "block_index": self.block_index,
            "line_index": self.line_index,
            "word_index": self.word_index,
            "role": self.role.value,
            "is_eligible_for_ceiling_mark": self.is_eligible_for_ceiling_mark,
            "status": self.status.value,
            "notes": self.notes,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


def _bbox_inside(
    inner: Tuple[float, float, float, float],
    outer: Tuple[float, float, float, float],
    margin: float = 1.0,
) -> bool:
    """Check if inner bbox is geometrically contained within outer bbox."""
    return (
        inner[0] >= outer[0] - margin
        and inner[1] >= outer[1] - margin
        and inner[2] <= outer[2] + margin
        and inner[3] <= outer[3] + margin
    )


class SourceRcpWordEligibilityShadowAuthority:
    """Evaluates text word tokens for reflected ceiling plan mark eligibility."""

    def classify_word(
        self,
        *,
        document_id: str,
        page_id: str,
        word_text: str,
        word_bbox: Tuple[float, float, float, float],
        block_text: str,
        block_index: int = 0,
        line_index: int = 0,
        word_index: int = 0,
        plan_viewport_bbox: Optional[Tuple[float, float, float, float]] = None,
        schedule_table_bboxes: Sequence[Tuple[float, float, float, float]] = (),
        title_block_bboxes: Sequence[Tuple[float, float, float, float]] = (),
        source_defined_ceiling_codes: Sequence[str] = (),
    ) -> RcpWordEvidence:
        """Classifies a single word token for ceiling mark eligibility."""
        clean_text = word_text.strip()
        wb = (float(word_bbox[0]), float(word_bbox[1]), float(word_bbox[2]), float(word_bbox[3]))

        # Never feed malformed PDF coordinates to stable_contract_id:
        # non-finite floats cannot be normalized as source ID ingredients.
        # An unusable geometry token gets a deterministic negative receipt
        # with a JSON-safe empty bbox, not a CANDIDATE or an exception.
        if not all(math.isfinite(value) for value in wb):
            return RcpWordEvidence(
                word_id=stable_contract_id(
                    "RCP_WORD_INVALID_BBOX",
                    (document_id, page_id, clean_text, block_index, line_index, word_index),
                ),
                text=clean_text,
                bbox_pdf_pts=(0.0, 0.0, 0.0, 0.0),
                block_index=block_index,
                line_index=line_index,
                word_index=word_index,
                role=RcpWordRole.OUT_OF_VIEWPORT,
                is_eligible_for_ceiling_mark=False,
                status=EvidenceResolutionStatus.ABSTAINED,
                notes="Non-finite original PDF word bounding box; no source geometry authority.",
            )

        word_id = stable_contract_id(
            "RCP_WORD",
            (document_id, page_id, clean_text, wb, block_index, line_index, word_index),
        )

        if not clean_text or wb[0] >= wb[2] or wb[1] >= wb[3]:
            return RcpWordEvidence(
                word_id=word_id,
                text=clean_text,
                bbox_pdf_pts=wb,
                block_index=block_index,
                line_index=line_index,
                word_index=word_index,
                role=RcpWordRole.OUT_OF_VIEWPORT,
                is_eligible_for_ceiling_mark=False,
                status=EvidenceResolutionStatus.ABSTAINED,
                notes="Degenerate or empty word bounding box.",
            )

        # 1. Schedule table check (takes priority over general viewport check)
        for tbl_bbox in schedule_table_bboxes:
            if _bbox_inside(wb, tbl_bbox):
                return RcpWordEvidence(
                    word_id=word_id,
                    text=clean_text,
                    bbox_pdf_pts=wb,
                    block_index=block_index,
                    line_index=line_index,
                    word_index=word_index,
                    role=RcpWordRole.SCHEDULE_TABLE_CELL,
                    is_eligible_for_ceiling_mark=False,
                    status=EvidenceResolutionStatus.ABSTAINED,
                    notes="Word is located inside a schedule/legend table.",
                )

        # 2. Title block check
        for tb_bbox in title_block_bboxes:
            if _bbox_inside(wb, tb_bbox):
                return RcpWordEvidence(
                    word_id=word_id,
                    text=clean_text,
                    bbox_pdf_pts=wb,
                    block_index=block_index,
                    line_index=line_index,
                    word_index=word_index,
                    role=RcpWordRole.TITLE_BLOCK_METADATA,
                    is_eligible_for_ceiling_mark=False,
                    status=EvidenceResolutionStatus.ABSTAINED,
                    notes="Word is located inside sheet title block or revision block.",
                )

        # 3. Viewport boundary check. The bbox is only a caller-supplied
        # candidate: even when present it cannot CORROBORATE original paint,
        # typed plan viewport, material or physical ceiling-zone ownership.
        if plan_viewport_bbox is None or not _bbox_inside(wb, plan_viewport_bbox):
            return RcpWordEvidence(
                word_id=word_id,
                text=clean_text,
                bbox_pdf_pts=wb,
                block_index=block_index,
                line_index=line_index,
                word_index=word_index,
                role=RcpWordRole.OUT_OF_VIEWPORT,
                is_eligible_for_ceiling_mark=False,
                status=EvidenceResolutionStatus.ABSTAINED,
                notes="Word bbox is outside designated plan drawing viewport.",
            )

        # 4. A source-visible word is not a ceiling code merely because its
        # spelling looks familiar. Require a caller-provided original schedule
        # code universe, and keep the whole native source block's rivals.
        # These caller scopes are only candidates, never source-producer trust.
        defined=frozenset(
            code.strip().upper() for code in source_defined_ceiling_codes
            if type(code) is str and code.strip()
        )
        tokens=tuple(part.upper() for part in block_text.strip().split())
        upper=clean_text.upper()
        # Multiword original coordination notes (including the four-word
        # OFFICE warning) are not material even when their PDF text is legible.
        if (len(tokens)>6 or len(block_text.strip())>35
                or (len(tokens)>=3 and upper not in defined)):
            return RcpWordEvidence(
                word_id=word_id,text=clean_text,bbox_pdf_pts=wb,
                block_index=block_index,line_index=line_index,
                word_index=word_index,role=RcpWordRole.GENERAL_NOTE_PROSE,
                is_eligible_for_ceiling_mark=False,
                status=EvidenceResolutionStatus.ABSTAINED,
                notes=f"Word is part of a general note prose block ({len(tokens)} words).",
            )
        if upper not in defined and defined:
            return RcpWordEvidence(
                word_id=word_id,text=clean_text,bbox_pdf_pts=wb,
                block_index=block_index,line_index=line_index,
                word_index=word_index,role=RcpWordRole.NON_CEILING_LABEL,
                is_eligible_for_ceiling_mark=False,
                status=EvidenceResolutionStatus.ABSTAINED,
                notes="Word is not an original schedule-defined ceiling material code.",
            )
        if not schedule_table_bboxes or not defined:
            return RcpWordEvidence(
                word_id=word_id,text=clean_text,bbox_pdf_pts=wb,
                block_index=block_index,line_index=line_index,
                word_index=word_index,role=RcpWordRole.OUT_OF_VIEWPORT,
                is_eligible_for_ceiling_mark=False,
                status=EvidenceResolutionStatus.ABSTAINED,
                notes="Complete original schedule/ceiling code scope is not issued.",
            )
        # Native sibling text must corroborate ONE code, not allow a same
        # block to mint two material occurrences, borrow a room label or use
        # a note/device word as a ceiling role. Pure height/CLG support only.
        in_block_codes=tuple(token for token in tokens if token in defined)
        support=frozenset(("CLG","/","AFFL","FFL","A.F.F.L","CEILING"))
        unsupported=tuple(
            token for token in tokens
            if token not in defined and token not in support
            and not re.fullmatch(r"[0-9]+(?:[.]?[0-9]+)?(?:MM|M)?",token)
        )
        if in_block_codes != (upper,) or unsupported:
            role=(
                RcpWordRole.GENERAL_NOTE_PROSE
                if unsupported and len(tokens)>=3
                else RcpWordRole.OTHER_PLAN_TEXT
            )
            return RcpWordEvidence(
                word_id=word_id,text=clean_text,bbox_pdf_pts=wb,
                block_index=block_index,line_index=line_index,
                word_index=word_index,role=role,
                is_eligible_for_ceiling_mark=False,
                status=EvidenceResolutionStatus.ABSTAINED,
                notes="Competing code or unsupported sibling original source text.",
            )

        # 6. Lexically plausible ceiling callout CANDIDATE only.
        # Complete real source PDF/snapshot/viewport/W4 zone and material
        # definition must be proved by independent typed authorities.
        return RcpWordEvidence(
            word_id=word_id,
            text=clean_text,
            bbox_pdf_pts=wb,
            block_index=block_index,
            line_index=line_index,
            word_index=word_index,
            role=RcpWordRole.IN_PLAN_CEILING_ANNOTATION,
            is_eligible_for_ceiling_mark=True,
            status=EvidenceResolutionStatus.CANDIDATE,
            notes="Lexical RCP candidate only: original source, viewport and ceiling zone unproved.",
        )
