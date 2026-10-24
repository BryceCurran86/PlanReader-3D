"""Index producer-owned visible / raster_segment geometries (shadow).

Previous Lot16 censuses counted ``published.snapshot.visible_observation_ids``,
which is not the producer list. This module reads
``PublishedVisibleSourceSnapshot.visible_observation_ids`` and authenticates
each via ``resolve_visible``. Never grants host.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from pb_migration_contracts import EvidenceResolutionStatus
from pb_segment_w4_exact_geometry_identity_shadow import _finite_line
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    RASTER_PDF_SEGMENT,
    RASTER_PDF_VISIBLE_SEGMENT,
    SourceVisibilityAuthority,
)


def _clean(value: object) -> str:
    return str(value or "").strip()


def _strip_visible(ref: str) -> str:
    text = _clean(ref)
    return text[len("visible:"):] if text.startswith("visible:") else text


def index_published_visible_segment_geometries_shadow(
    *,
    visibility: SourceVisibilityAuthority,
    published: object,
) -> dict[str, Any]:
    """Map source_primitive_ref → authenticated visible-segment geometry."""
    if type(visibility) is not SourceVisibilityAuthority:
        raise TypeError("SourceVisibilityAuthority required")
    revision = published.revision
    snapshot = published.snapshot
    visible_ids = tuple(
        str(x) for x in (getattr(published, "visible_observation_ids", ()) or ())
        if str(x).strip()
    )
    snapshot_visible = tuple(
        str(x) for x in (getattr(snapshot, "visible_observation_ids", ()) or ())
        if str(x).strip()
    )
    by_ref: dict[str, dict[str, Any]] = {}
    kind_counts: Counter[str] = Counter()
    unresolved = 0
    non_line = 0
    for oid in visible_ids:
        res = visibility.resolve_visible(ObservationSelector(
            document_id=revision.document_id,
            revision_id=revision.revision_id,
            source_sha256=revision.source_sha256,
            snapshot_id=snapshot.snapshot_id,
            observation_id=oid,
        ))
        if res.status is not EvidenceResolutionStatus.CORROBORATED or res.observation is None:
            unresolved += 1
            continue
        obs = res.observation
        kind = str(obs.observation_kind or "")
        kind_counts[kind] += 1
        line = _finite_line(obs.geometry)
        if line is None:
            non_line += 1
            continue
        ref = _clean(obs.source_primitive_ref)
        stripped = _strip_visible(ref)
        row = {
            "observation_id": oid,
            "observation_kind": kind,
            "source_primitive_ref": ref,
            "stripped_ref": stripped,
            "line_pt": list(line),
            "page_id": str(obs.page_id),
        }
        for key in (ref, stripped, oid):
            if key and key not in by_ref:
                by_ref[key] = row
        parent_ids = tuple(obs.derivation_parent_ids or ())
        for pid in parent_ids:
            parent = visibility._source_authority.resolve(ObservationSelector(
                document_id=revision.document_id,
                revision_id=revision.revision_id,
                source_sha256=revision.source_sha256,
                snapshot_id=snapshot.snapshot_id,
                observation_id=str(pid),
            ))
            if (
                parent.status is not EvidenceResolutionStatus.CORROBORATED
                or parent.observation is None
            ):
                continue
            pobs = parent.observation
            pref = _clean(pobs.source_primitive_ref)
            pkind = str(pobs.observation_kind or "")
            kind_counts[f"parent:{pkind}"] += 1
            pline = _finite_line(pobs.geometry) or line
            prow = {
                "observation_id": str(pid),
                "observation_kind": pkind,
                "source_primitive_ref": pref,
                "stripped_ref": _strip_visible(pref),
                "line_pt": list(pline),
                "page_id": str(pobs.page_id),
            }
            for key in (pref, _strip_visible(pref), str(pid)):
                if key and key not in by_ref:
                    by_ref[key] = prow

    return {
        "status": "UNPUBLISHED_W4_RASTER_SEGMENT_GEOMETRY_INDEX",
        "producer_visible_observation_id_count": len(visible_ids),
        "snapshot_visible_observation_id_count": len(snapshot_visible),
        "indexed_ref_count": len(by_ref),
        "kind_counts": dict(sorted(kind_counts.items())),
        "unresolved_visible_count": unresolved,
        "non_line_geometry_count": non_line,
        "raster_pdf_visible_segment_kind": RASTER_PDF_VISIBLE_SEGMENT,
        "raster_pdf_segment_kind": RASTER_PDF_SEGMENT,
        "geometries_by_ref": by_ref,
        "host_granted": False,
        "shadow_only": True,
    }


def lookup_w4_primitive_geometries(
    *,
    w4_source_primitive_ids: Sequence[str],
    geometries_by_ref: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    hits = []
    missing = 0
    for raw in w4_source_primitive_ids:
        text = _clean(raw)
        if not text:
            continue
        row = geometries_by_ref.get(text) or geometries_by_ref.get(_strip_visible(text))
        if row is None:
            missing += 1
            continue
        hits.append({
            "w4_source_primitive_id": text,
            "indexed_observation_id": row["observation_id"],
            "indexed_kind": row["observation_kind"],
            "line_pt": list(row["line_pt"]),
        })
    return {
        "matched_w4_primitive_geometry_count": len(hits),
        "unmatched_w4_primitive_count": missing,
        "hits": hits,
        "host_granted": False,
        "shadow_only": True,
    }
