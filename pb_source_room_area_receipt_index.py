"""Fail-closed producer-local room-area receipt indexing.

Both cross-view and same-view source area result accessors must quarantine
competing source faces, physical rooms and figured evidence. A dict
comprehension must not choose an arbitrary winner before the production
source room area bridge checks authenticated lineage.

Do not infer metric quantities, room geometry, names or material finishes.
"""
from __future__ import annotations

from collections import Counter
from types import MappingProxyType
from typing import Mapping


def unique_source_room_area_evidence_by(
    records: tuple[object, ...],
    *,
    key: str,
) -> Mapping[str, object]:
    """One exact source face, physical room and figured evidence per owner.

    Same-view/cross-view priority is managed by the downstream producer; this
    method restricts each single producer's own original source universe.
    """
    if key not in ("physical_room_id", "source_room_face_record_id"):
        raise ValueError("unsupported original source room owner key")
    if not isinstance(records, tuple):
        raise TypeError("sealed producer result records must be a tuple")

    def valid(value: object) -> bool:
        return type(value) is str and bool(value) and value == value.strip()

    candidates: list[tuple[object,str,str,str]] = []
    for row in records:
        face = getattr(row,"source_room_face_record_id",None)
        physical = getattr(row,"physical_room_id",None)
        receipt = getattr(getattr(row,"area_evidence",None),"evidence_id",None)
        if not (valid(face) and valid(physical) and valid(receipt)):
            continue
        candidates.append((row,face,physical,receipt))
    face_counts = Counter(face for _,face,_,_ in candidates)
    physical_counts = Counter(physical for _,_,physical,_ in candidates)
    evidence_counts = Counter(receipt for _,_,_,receipt in candidates)

    # A wholly malformed address must not suppress an otherwise fully
    # producer-authenticated independent source room. A collision between two
    # correctly typed original addresses always suppresses both claimants.
    safe = {}
    for row,face,physical,receipt in candidates:
        if face_counts[face]!=1 or physical_counts[physical]!=1 or evidence_counts[receipt]!=1:
            continue
        address=physical if key=="physical_room_id" else face
        safe[address]=row.area_evidence
    return MappingProxyType(safe)
