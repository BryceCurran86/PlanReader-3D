"""SHA-owned 3Laurel internal room-door area REVIEW, never a billable opening.

Matches source printed width separately to two source walls, jambs and leaf
geometry. Reads the 2100 AFL U.N.O. joinery note from BOTH native elevation
pages. It is an independent typed evidence packet; not a frozen benchmark
scorer, wall deduction, physical clearance approval or quantity issuer.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path

import fitz

from pb_source_internal_swing_room_barrier import detect_source_internal_swing_room_barriers
from pb_source_native_cavity_slider_jamb_shadow import match_source_native_cavity_sliders

_SOURCE_SHA = "014e9f68b377bef4fb556de61b83a94388792dfa4bfb8ea981644f9c323e9e2e"
_NOTE = "JOINERY HEIGHTS TO BE 2100 AFL U.N.O."


@dataclass(frozen=True)
class ThreeLaurelDoorSourceWitness:
    kind: str
    width_word_index: int
    width_mm: int
    plan_source_path_ids: tuple[int, ...]
    source_label_bbox_pdf_pts: tuple[float, float, float, float]
    joinery_height_note_pages: tuple[int, int] = (4, 5)
    noted_height_mm: int = 2100
    source_width_height_area_preview_m2: float = 0.
    commercial_quantity_authorized: bool = False
    physical_opening_authenticated: bool = False


@dataclass(frozen=True)
class ThreeLaurelDoorSourceReview:
    status: str
    reasons: tuple[str, ...]
    source_sha256: str = ""
    witnesses: tuple[ThreeLaurelDoorSourceWitness, ...] = ()
    frozen_score_updated: bool = False
    opening_area_customer_authorized: bool = False


def _abstain(reason: str) -> ThreeLaurelDoorSourceReview:
    return ThreeLaurelDoorSourceReview("ABSTAIN", (reason,))


def review_original_three_laurel_internal_door_source(
    pdf_path: str | Path,
) -> ThreeLaurelDoorSourceReview:
    """No review succeeds without the exact protected original and native words."""
    try:
        path = Path(pdf_path)
        if path.is_symlink() or not path.is_file():
            return _abstain("original_source_missing")
        raw = path.read_bytes()
    except (TypeError, ValueError, OSError):
        return _abstain("original_source_unavailable")
    if hashlib.sha256(raw).hexdigest() != _SOURCE_SHA:
        return _abstain("original_source_sha_mismatch")

    try:
        with fitz.open(stream=raw, filetype="pdf") as document:
            if document.page_count < 5:
                return _abstain("source_pages_missing")
            for idx in (3, 4):
                if _NOTE not in document[idx].get_text("text"):
                    return _abstain("joinery_height_source_not_authenticated")
            rows, words = tuple(document[2].get_drawings()), tuple(document[2].get_text("words"))
    except (RuntimeError, ValueError, OSError):
        return _abstain("original_pdf_read_failed")
    hinges = detect_source_internal_swing_room_barriers(rows, words, page_index=2)
    sliders = match_source_native_cavity_sliders(rows, words, page_index=2)
    if len(hinges) != 8 or len(sliders) != 6:
        return _abstain("original_door_topology_incomplete")

    witnesses = []
    used_labels = set()
    for door in hinges:
        box = door.bounds_pdf_pts
        cx,cy = (box[0]+box[2])/2,(box[1]+box[3])/2
        choices = []
        for idx,word in enumerate(words):
            text = str(word[4]).replace(",","").strip()
            if text not in ("720", "870"):
                continue
            x,y = (word[0]+word[2])/2,(word[1]+word[3])/2
            distance = math.hypot(x-cx,y-cy)
            if distance < 15:
                choices.append((distance,idx,int(text)))
        choices.sort()
        if (
            not choices or
            (len(choices)>1 and choices[1][0]-choices[0][0]<=2)
        ):
            return _abstain("hinged_door_width_word_ambiguous")
        _distance,word_idx,width = choices[0]
        if word_idx in used_labels:
            return _abstain("hinged_door_width_word_reused")
        used_labels.add(word_idx)
        ids = (door.swing_arc_path_id, door.first_host_path_id,
               door.second_host_path_id, *door.jamb_cap_path_ids)
        if len(set(ids)) != len(ids):
            return _abstain("hinged_source_geometry_conflict")
        witnesses.append(ThreeLaurelDoorSourceWitness(
            kind="hinged_swing", width_word_index=word_idx,width_mm=width,
            plan_source_path_ids=ids,
            source_label_bbox_pdf_pts=tuple(float(v) for v in words[word_idx][:4]),
            source_width_height_area_preview_m2=round(width*2100/1e6,6),
        ))
    for door in sliders:
        idx=door.width_word_index
        if idx in used_labels:
            return _abstain("cavity_door_width_word_reused")
        used_labels.add(idx)
        ids = (*door.host_path_ids, *door.jamb_path_ids,door.leaf_path_id)
        if len(set(ids)) != len(ids):
            return _abstain("cavity_source_geometry_conflict")
        witnesses.append(ThreeLaurelDoorSourceWitness(
            kind="cavity_slider",width_word_index=idx,
            width_mm=door.printed_width_mm,
            plan_source_path_ids=ids,
            source_label_bbox_pdf_pts=tuple(float(v) for v in words[idx][:4]),
            source_width_height_area_preview_m2=round(door.printed_width_mm*2100/1e6,6),
        ))
    if (
        len(witnesses)!=14
        or len(used_labels)!=14
        or sum(w.kind=="hinged_swing" for w in witnesses)!=8
        or sum(w.kind=="cavity_slider" for w in witnesses)!=6
    ):
        return _abstain("fourteen_door_witness_bijection_unavailable")
    return ThreeLaurelDoorSourceReview(
        "SOURCE_NATIVE_REVIEW_ONLY",
        ("native_hosts_widths_and_elevation_note_reconciled_not_billable",),
        _SOURCE_SHA,
        tuple(sorted(witnesses,key=lambda w:(w.kind,w.width_word_index))),
        frozen_score_updated=False,
        opening_area_customer_authorized=False,
    )
