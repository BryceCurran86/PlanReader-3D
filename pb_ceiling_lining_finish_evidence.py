"""C15 unscoped ceiling-finish candidate collection.

Collection produces *candidate* evidence only. It never accepts a caller
room/scope id as proof of ownership. Scope binding is a separate binder
(``pb_ceiling_lining_scope_binder``).

Preserved ownership fields when known:
- document_id
- source_sha256
- revision_id
- page_id / page_no
- viewport_id (only when independently known)
- text geometry / bbox when available
- source method / raw text provenance
"""
from __future__ import annotations

from typing import Mapping, Optional, Sequence

from pb_ceiling_lining_quantity import (
    explicit_ceiling_finish_descriptor,
    iter_explicit_ceiling_finish_matches,
)
from pb_migration_contracts import EvidenceAtom, EvidenceResolutionStatus, stable_contract_id

UNSCOPED_FINISH_KIND = "ceiling_finish"
UNSCOPED_FINISH_CANDIDATE_TYPE = "unscoped_ceiling_finish_candidate"


def _clean(value: object) -> str:
    return str(value if value is not None else "").strip()


def collect_unscoped_ceiling_finish_candidates(
    *,
    page_text: str,
    document_id: str,
    source_sha256: str,
    revision_id: str,
    page_id: str,
    page_no: int,
    viewport_id: Optional[str] = None,
    text_geometry: Optional[Sequence[Mapping[str, object]]] = None,
    method: str = "native_pdf_text",
    confidence: float = 0.95,
) -> tuple[EvidenceAtom, ...]:
    """Collect unscoped explicit ceiling-finish candidates from page text.

    ``scope_entity_id`` is intentionally absent from this API. Passing a room
    id here is not supported and cannot create scope authority.
    """
    doc_id = _clean(document_id)
    page = _clean(page_id)
    source = _clean(source_sha256).lower()
    revision = _clean(revision_id)
    if not doc_id or not page or not source or not revision:
        return ()

    geometry_by_raw: dict[str, tuple[float, float, float, float]] = {}
    for item in text_geometry or ():
        if not isinstance(item, Mapping):
            continue
        raw = _clean(item.get("raw_text") or item.get("text"))
        bbox = item.get("bbox")
        if not raw or not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue
        try:
            geometry_by_raw[raw] = (
                float(bbox[0]),
                float(bbox[1]),
                float(bbox[2]),
                float(bbox[3]),
            )
        except (TypeError, ValueError):
            continue

    viewport = _clean(viewport_id) or None
    atoms: list[EvidenceAtom] = []
    for raw in iter_explicit_ceiling_finish_matches(page_text):
        descriptor = explicit_ceiling_finish_descriptor(raw)
        if descriptor is None:
            continue
        bbox = geometry_by_raw.get(raw)
        payload = {
            "kind": UNSCOPED_FINISH_KIND,
            "candidate_type": UNSCOPED_FINISH_CANDIDATE_TYPE,
            "document_id": doc_id,
            "source_sha256": source,
            "revision_id": revision,
            "page_id": page,
            "page_no": int(page_no),
            "viewport_id": viewport,
            "method": method,
            "descriptor": descriptor,
            "raw_text": raw,
            "bbox": list(bbox) if bbox is not None else None,
        }
        evidence_id = stable_contract_id("ev", payload)
        metadata = {
            "unscoped": True,
            "candidate_type": UNSCOPED_FINISH_CANDIDATE_TYPE,
            "source_sha256": source,
            "revision_id": revision,
            "page_no": int(page_no),
            "finish_descriptor": descriptor,
            # Explicitly absent: scope_entity_id is not proven at collection.
        }
        if viewport is not None:
            metadata["viewport_id"] = viewport
        atoms.append(
            EvidenceAtom(
                evidence_id=evidence_id,
                document_id=doc_id,
                page_id=page,
                kind=UNSCOPED_FINISH_KIND,
                method=method,
                viewport_id=viewport,
                raw_text=raw,
                confidence=float(confidence),
                status=EvidenceResolutionStatus.RAW,
                bbox=bbox,
                metadata=metadata,
            )
        )
    return tuple(atoms)
