"""On-demand, source-owned room/opening review for original PlanReader.

Only reads original PDF paths + printed room words and existing hosted opening
receipts. No inferred wall geometry, scale, finish or customer area is emitted.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re
from typing import Any

from pb_three_laurel_floor_opening_correspondence_shadow import (
    FloorOpeningBoundaryWitness,
    SourceOpening,
    match_source_exterior_openings_to_floor_wall_gaps,
)
from pb_three_laurel_floor_wall_face_correspondence_shadow import (
    build_floor_to_physical_wall_candidate_receipt,
)
from pb_source_room_gap_audit import (
    SourceRoomGapAudit,
    audit_source_room_outline_remaining_gaps,
)
from pb_source_painted_wall_corner_witness import (
    SourcePaintedWallCornerReview,
    review_source_painted_wall_corners,
)

_SINGLE_ROOM_WORDS = frozenset({
    "LIVING", "MEDIA", "KITCHEN", "DINING", "MEALS", "GARAGE",
    "BATH", "BATHROOM", "ENS", "ENSUITE", "LAUNDRY",
    "OFFICE", "STUDY", "ENTRY", "HALL", "STORE", "WIR", "WIP",
})


def printed_room_names(words: Sequence[Sequence[Any]]) -> tuple[str, ...]:
    """Extract candidate printed labels, not room geometry or semantic authority."""
    names: dict[str, None] = {}
    for i, word in enumerate(words):
        if not isinstance(word, (tuple, list)) or len(word) < 8:
            continue
        token = re.sub(r"[^A-Z0-9]", "", str(word[4]).upper())
        if token in _SINGLE_ROOM_WORDS:
            names[token] = None
        elif token in ("BED", "BEDROOM"):
            name = token
            if i + 1 < len(words):
                next_word = words[i + 1]
                if (
                    isinstance(next_word, (tuple, list))
                    and len(next_word) >= 8
                    and (word[5], word[6]) == (next_word[5], next_word[6])
                    and re.fullmatch(r"[0-9]{1,2}", str(next_word[4]))
                    and 0 <= float(next_word[0]) - float(word[2]) <= 20
                ):
                    name = f"{token} {next_word[4]}"
            names[name] = None
    return tuple(names)


@dataclass(frozen=True)
class SourceRoomOpeningReview:
    page_index: int
    status: str
    reason: str
    labels_checked: int
    floor_candidates: int
    witnesses: tuple[FloorOpeningBoundaryWitness, ...] = ()
    ambiguous_opening_count: int = 0
    shared_source_floor_outline_labels: tuple[tuple[int, tuple[str, ...]], ...] = ()
    room_gap_audits: tuple[SourceRoomGapAudit, ...] = ()
    painted_corner_reviews: tuple[SourcePaintedWallCornerReview, ...] = ()
    physical_wall_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "page_index": self.page_index,
            "status": self.status,
            "reason": self.reason,
            "labels_checked": self.labels_checked,
            "floor_candidates": self.floor_candidates,
            "witness_count": len(self.witnesses),
            "witnesses": [w.to_dict() for w in self.witnesses],
            "ambiguous_opening_count": self.ambiguous_opening_count,
            "shared_source_floor_outline_labels": [
                {"source_floor_path_id": path, "printed_labels": list(names)}
                for path, names in self.shared_source_floor_outline_labels
            ],
            "room_gap_audits": [a.to_dict() for a in self.room_gap_audits],
            "painted_corner_reviews": [
                a.to_dict() for a in self.painted_corner_reviews
            ],
            "physical_wall_authenticated": False,
            "measurement_authorized": False,
        }


def review_source_room_opening_gaps(
    drawings: Sequence[Mapping[str, Any] | object],
    words: Sequence[Sequence[Any]],
    openings: Sequence[SourceOpening],
    *,
    page_index: int,
    source_sha256: str,
    max_labels: int = 64,
) -> SourceRoomOpeningReview:
    """Match existing hosted openings to independently painted room-side walls."""
    invalid = (
        type(page_index) is not int or page_index < 0
        or not re.fullmatch(r"[0-9a-f]{64}", source_sha256)
        or len(drawings) > 20_000
    )
    if invalid:
        return SourceRoomOpeningReview(
            page_index, "ABSTAINED", "original_source_scope_invalid", 0, 0,
        )
    labels = printed_room_names(words)
    if len(labels) > max_labels or max_labels < 1:
        return SourceRoomOpeningReview(
            page_index, "ABSTAINED", "native_room_label_budget_exceeded", 0, 0,
        )
    hits: list[FloorOpeningBoundaryWitness] = []
    source_floor_receipts = []
    floor_label_groups: dict[int, list[str]] = {}
    candidates = 0
    for label in labels:
        receipt = build_floor_to_physical_wall_candidate_receipt(
            drawings, words, label,
            page_index=page_index, source_sha256=source_sha256,
        )
        if receipt.floor_candidate_native_path_id is None:
            continue
        candidates += 1
        source_floor_receipts.append(receipt)
        floor_label_groups.setdefault(receipt.floor_candidate_native_path_id, []).append(label)
        hits.extend(match_source_exterior_openings_to_floor_wall_gaps(
            receipt, openings,
        ))
    # A printed room name can be only a SECTION label within a larger open
    # floor candidate. A single source-owned window/door may therefore be
    # claimed by multiple room names (or sides) from the same floor drawing.
    # NEVER choose the nearest label and quietly duplicate an opening.
    claims: dict[tuple[object, ...], list[FloorOpeningBoundaryWitness]] = {}
    for hit in hits:
        opening_key = (
            hit.opening_kind,
            hit.source_page_index,
            tuple(sorted(hit.opening_host_path_ids)),
            hit.opening_source_path_ids,
        )
        claims.setdefault(opening_key, []).append(hit)
    accepted: list[FloorOpeningBoundaryWitness] = []
    ambiguous = 0
    for group in claims.values():
        distinct_owners = {
            (
                h.floor_candidate_path_id,
                h.room_label,
                h.room_side,
                h.supported_gap_interval_pdf_pts,
            )
            for h in group
        }
        if len(distinct_owners) != 1:
            ambiguous += 1
            continue
        accepted.append(group[0])

    # Labels pointing at one original Finish_Floor path are only different
    # names/sections of the SAME source floor outline until independent wall
    # partitions prove otherwise. Never split them into measured rooms.
    shared_labels = tuple(
        (path, tuple(names))
        for path, names in sorted(floor_label_groups.items())
        if len(names) > 1
    )
    audits = []
    corner_reviews = []
    for receipt in source_floor_receipts:
        path_id = receipt.floor_candidate_native_path_id
        if len(floor_label_groups[path_id]) != 1:
            continue
        audit = audit_source_room_outline_remaining_gaps(
            receipt,
            [w for w in accepted if w.room_label == receipt.label],
        )
        if audit is not None:
            audits.append(audit)
        corners = review_source_painted_wall_corners(drawings, receipt)
        if corners is not None:
            corner_reviews.append(corners)

    # Separate source receipts only; no category is ever a customer wall
    # or finish quantity, even with every opening or side accounted for.
    return SourceRoomOpeningReview(
        page_index=page_index,
        status="CANDIDATE" if accepted else "ABSTAINED",
        reason="source_room_opening_witnesses_noncommercial"
        if accepted else "no_unique_source_owned_room_opening_correspondence",
        labels_checked=len(labels),
        floor_candidates=candidates,
        witnesses=tuple(accepted),
        ambiguous_opening_count=ambiguous,
        shared_source_floor_outline_labels=shared_labels,
        room_gap_audits=tuple(sorted(
            audits, key=lambda a: (a.remaining_unproved_pdf_pt, a.room_label),
        )),
        painted_corner_reviews=tuple(sorted(
            corner_reviews, key=lambda a: (a.source_floor_path_id, a.source_page_index),
        )),
    )
