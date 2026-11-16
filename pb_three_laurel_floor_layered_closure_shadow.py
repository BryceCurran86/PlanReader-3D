"""Candidate-only correspondences for EXISTING source room-ring doorway closures.

Consumes source-native LayeredDoorwayClosure rows created by PlanReader's
existing room-ring producer. It never redetects a door and never authenticates
physical wall, scale, customer floor finish or sealed room ownership.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pb_three_laurel_native_slider_wall_end_correspondence_shadow import (
    corroborate_native_wall_ends_at_existing_slider,
)

from pb_migration_contracts import EvidenceResolutionStatus
from pb_next_wall_ring_preview import (
    KIND_CAVITY_SLIDER,
    KIND_SLIDING_LEAF,
    LayeredRoomRingResult,
)
from pb_three_laurel_floor_wall_face_correspondence_shadow import (
    FloorWallCandidateReceipt,
)


@dataclass(frozen=True)
class FloorCandidateLayeredClosureMatch:
    room_label: str
    room_floor_candidate_path_id: int
    source_sha256: str
    source_page_index: int
    room_side: str
    producer_closure_id: str
    producer_kind: str
    original_native_path_ids: tuple[int, ...]
    original_wall_path_ids: tuple[int, ...]
    original_word_refs: tuple[str, ...]
    evidence_completeness: str
    room_gap_interval_pdf_pt: tuple[float, float]
    matched_span_pdf_pt: float
    independently_painted_wall_end_path_ids: tuple[int, int] | tuple[()] = ()
    measurement_authorized: bool = False
    physical_wall_authenticated: bool = False
    room_enclosure_authenticated: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "room_label": self.room_label,
            "room_floor_candidate_path_id": self.room_floor_candidate_path_id,
            "source_sha256": self.source_sha256,
            "source_page_index": self.source_page_index,
            "room_side": self.room_side,
            "producer_closure_id": self.producer_closure_id,
            "producer_kind": self.producer_kind,
            "original_native_path_ids": list(self.original_native_path_ids),
            "original_wall_path_ids": list(self.original_wall_path_ids),
            "original_word_refs": list(self.original_word_refs),
            "evidence_completeness": self.evidence_completeness,
            "room_gap_interval_pdf_pt": list(self.room_gap_interval_pdf_pt),
            "matched_span_pdf_pt": round(self.matched_span_pdf_pt, 3),
            "independently_painted_wall_end_path_ids": list(
                self.independently_painted_wall_end_path_ids
            ),
            "measurement_authorized": False,
            "physical_wall_authenticated": False,
            "room_enclosure_authenticated": False,
        }


def match_existing_room_ring_closure_candidates(
    receipt: FloorWallCandidateReceipt,
    original_producer: LayeredRoomRingResult,
    *,
    source_sha256: str,
    page_index: int,
    max_face_offset_pt: float = 0.75,
    original_source_drawings: Sequence[Mapping[str, Any] | object] | None = None,
) -> tuple[FloorCandidateLayeredClosureMatch, ...]:
    """Correlate CS/VSD candidate closure with still-uncovered native floor edge.

    This is only a diagnostic intersection. A CS text reference without
    native hosted geometry is tagged 'word_only_unhosted', never promoted.
    Missing source fingerprint, source page, typed ring producer or unique
    source match makes this routine fail closed.
    """
    if not isinstance(receipt, FloorWallCandidateReceipt):
        return ()
    if not isinstance(original_producer, LayeredRoomRingResult):
        return ()
    if original_producer.status != EvidenceResolutionStatus.CANDIDATE:
        return ()
    if (
        not isinstance(source_sha256, str)
        or len(source_sha256) != 64
        or any(ch not in "0123456789abcdef" for ch in source_sha256)
        or source_sha256 != receipt.source_sha256
        or page_index != receipt.page_index
        or page_index < 0
        or receipt.floor_candidate_native_path_id is None
    ):
        return ()
    if any(
        r.source_sha256 != source_sha256 or r.page_index != page_index
        for r in original_producer.rings
    ):
        return ()

    hits: list[FloorCandidateLayeredClosureMatch] = []
    for face in receipt.wall_face_candidates:
        if not face.uncovered_intervals_pdf_pt:
            continue
        a, b = face.from_pdf_pt, face.to_pdf_pt
        horizontal = abs(a[1] - b[1]) < 0.2 and abs(a[0] - b[0]) > 1.0
        vertical = abs(a[0] - b[0]) < 0.2 and abs(a[1] - b[1]) > 1.0
        if not (horizontal or vertical):
            continue
        wall_position = a[1] if horizontal else a[0]
        for closure in original_producer.closures:
            if closure.kind not in (KIND_CAVITY_SLIDER, KIND_SLIDING_LEAF):
                continue
            if closure.horizontal != horizontal:
                continue
            if not closure.native_path_indices and not closure.native_word_refs:
                continue
            if (
                len(closure.gap_interval) != 2
                or len(closure.band) != 2
                or closure.gap_interval[1] <= closure.gap_interval[0]
                or closure.band[1] <= closure.band[0]
            ):
                continue
            normal_distance = min(
                abs(wall_position - closure.band[0]),
                abs(wall_position - closure.band[1]),
            )
            if normal_distance > max_face_offset_pt:
                continue
            wall_ends = (
                corroborate_native_wall_ends_at_existing_slider(
                    closure,
                    original_source_drawings,
                    source_sha256=source_sha256,
                    page_index=page_index,
                )
                if original_source_drawings is not None
                else None
            )
            for start, end in face.uncovered_intervals_pdf_pt:
                lo = max(start, closure.gap_interval[0])
                hi = min(end, closure.gap_interval[1])
                if hi - lo < 0.5:
                    continue
                if not closure.native_path_indices:
                    completeness = "word_only_unhosted"
                elif not closure.wall_path_indices:
                    completeness = "native_leaf_without_host_wall_ids"
                else:
                    completeness = "source_paths_and_host_candidate"
                hits.append(
                    FloorCandidateLayeredClosureMatch(
                        room_label=receipt.label,
                        room_floor_candidate_path_id=receipt.floor_candidate_native_path_id,
                        source_sha256=source_sha256,
                        source_page_index=page_index,
                        room_side=face.side,
                        producer_closure_id=closure.closure_id,
                        producer_kind=closure.kind,
                        original_native_path_ids=closure.native_path_indices,
                        original_wall_path_ids=closure.wall_path_indices,
                        original_word_refs=closure.native_word_refs,
                        evidence_completeness=completeness,
                        room_gap_interval_pdf_pt=(lo, hi),
                        matched_span_pdf_pt=hi - lo,
                        independently_painted_wall_end_path_ids=(
                            wall_ends.wall_host_path_ids
                            if wall_ends is not None
                            else ()
                        ),
                    )
                )
    # Two different source closure ids claiming the same segment are
    # contradictory candidates: do not choose whichever came first.
    accepted = [
        hit
        for hit in hits
        if not any(
            other is not hit
            and other.room_side == hit.room_side
            and other.producer_closure_id != hit.producer_closure_id
            and min(hit.room_gap_interval_pdf_pt[1], other.room_gap_interval_pdf_pt[1])
            - max(hit.room_gap_interval_pdf_pt[0], other.room_gap_interval_pdf_pt[0])
            > 0.5
            for other in hits
        )
    ]
    unique = {
        (hit.producer_closure_id, hit.room_side, hit.room_gap_interval_pdf_pt): hit
        for hit in accepted
    }
    return tuple(
        sorted(
            unique.values(),
            key=lambda r: (
                r.room_side,
                r.room_gap_interval_pdf_pt,
                r.producer_closure_id,
            ),
        )
    )
