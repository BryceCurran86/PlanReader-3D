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
    record_type: type,
) -> Mapping[str, object]:
    """One exact source face, physical room and figured evidence per owner.

    Same-view/cross-view priority is managed by the downstream producer; this
    method restricts each single producer's own original source universe.
    """
    if key not in ("physical_room_id", "source_room_face_record_id"):
        raise ValueError("unsupported original source room owner key")
    if not isinstance(records, tuple) or not isinstance(record_type, type):
        raise TypeError("sealed producer records and class type required")

    def valid(value: object) -> bool:
        return type(value) is str and bool(value) and value == value.strip()

    # A malformed second receipt for an otherwise real physical room cannot
    # make the first one appear unique. Count *all* producer-owned claims
    # with valid addresses before rejecting malformed evidence IDs.
    candidates: list[tuple[object,str | None,str | None,str | None]] = []
    for row in records:
        if type(row) is not record_type:
            raise TypeError("foreign or fabricated room-area producer record")
        raw_face = getattr(row,"source_room_face_record_id",None)
        raw_physical = getattr(row,"physical_room_id",None)
        raw_receipt = getattr(getattr(row,"area_evidence",None),"evidence_id",None)
        candidates.append((
            row,
            raw_face if valid(raw_face) else None,
            raw_physical if valid(raw_physical) else None,
            raw_receipt if valid(raw_receipt) else None,
        ))
    face_counts = Counter(face for _,face,_,_ in candidates if face is not None)
    physical_counts = Counter(physical for _,_,physical,_ in candidates
                              if physical is not None)
    evidence_counts = Counter(receipt for _,_,_,receipt in candidates
                              if receipt is not None)

    # A wholly malformed address must not suppress an otherwise fully
    # producer-authenticated independent source room. A collision between two
    # correctly typed original addresses always suppresses both claimants.
    safe = {}
    for row,face,physical,receipt in candidates:
        if (face is None or physical is None or receipt is None
                or face_counts[face]!=1 or physical_counts[physical]!=1
                or evidence_counts[receipt]!=1):
            continue
        address=physical if key=="physical_room_id" else face
        safe[address]=row.area_evidence
    return MappingProxyType(safe)
