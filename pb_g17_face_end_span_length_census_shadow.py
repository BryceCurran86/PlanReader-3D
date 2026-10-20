"""FACE/END geometry span-length census for unhosted G17 supports (shadow)."""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from math import hypot
from typing import Any

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityAuthority


def _span_length(geometry: object) -> float | None:
    if not isinstance(geometry, (list, tuple)) or len(geometry) != 4:
        return None
    try:
        x0, y0, x1, y1 = (float(v) for v in geometry)
    except (TypeError, ValueError):
        return None
    if not all(v == v and abs(v) != float("inf") for v in (x0, y0, x1, y1)):
        return None
    length = hypot(x1 - x0, y1 - y0)
    return length if length > 0 else None


def census_g17_face_end_span_lengths_shadow(
    *,
    composition: object,
    published: object,
    physical_opening_ids: Sequence[str],
) -> dict[str, Any]:
    revision = published.revision
    snapshot = published.snapshot
    opening_authority = composition.physical_opening_authority
    visibility = opening_authority.source_visibility_authority()
    if type(visibility) is not SourceVisibilityAuthority:
        raise TypeError("SourceVisibilityAuthority required")

    kind_spans: dict[str, list[float]] = {}
    openings: list[dict[str, Any]] = []
    for oid in sorted({str(x).strip() for x in physical_opening_ids if str(x).strip()}):
        trace = next(
            (r for r in composition.opening_bindings if r.opening_identity_id == oid),
            None,
        )
        if trace is None or trace.status is not EvidenceResolutionStatus.ABSTAINED:
            raise ValueError(f"unhosted abstained opening required: {oid}")
        existence = opening_authority.prove_existence(ObservationSelector(
            document_id=revision.document_id,
            revision_id=revision.revision_id,
            source_sha256=revision.source_sha256,
            snapshot_id=snapshot.snapshot_id,
            observation_id=trace.representative_observation_id,
        ))
        opening = existence.existence_record
        if existence.status is not EvidenceResolutionStatus.CORROBORATED or opening is None:
            raise RuntimeError("existence lost")
        per_kind: Counter[str] = Counter()
        spans: list[dict[str, Any]] = []
        for observation_id in opening.source_observation_ids:
            res = visibility.resolve_raster_opening_primitive(ObservationSelector(
                document_id=opening.document_id,
                revision_id=opening.revision_id,
                source_sha256=opening.source_sha256,
                snapshot_id=opening.snapshot_id,
                observation_id=observation_id,
            ))
            if res.status is not EvidenceResolutionStatus.CORROBORATED or res.observation is None:
                raise RuntimeError("support observation unverified")
            kind = str(res.observation.observation_kind or "")
            length = _span_length(res.observation.geometry)
            per_kind[kind] += 1
            if length is not None:
                kind_spans.setdefault(kind, []).append(length)
                spans.append({
                    "observation_id": observation_id,
                    "observation_kind": kind,
                    "span_length_pdf_pts": length,
                })
            else:
                spans.append({
                    "observation_id": observation_id,
                    "observation_kind": kind,
                    "span_length_pdf_pts": None,
                    "blocker": "nonfinite_or_point_geometry",
                })
        openings.append({
            "physical_opening_id": oid,
            "support_kind_counts": dict(sorted(per_kind.items())),
            "spans": spans,
            "host_granted": False,
        })

    summary = {}
    for kind, lengths in sorted(kind_spans.items()):
        summary[kind] = {
            "count": len(lengths),
            "min_pdf_pts": min(lengths),
            "max_pdf_pts": max(lengths),
            "mean_pdf_pts": sum(lengths) / len(lengths),
        }
    return {
        "status": "UNPUBLISHED_G17_FACE_END_SPAN_LENGTH_CENSUS",
        "opening_count": len(openings),
        "span_summary_by_kind": summary,
        "openings": openings,
        "host_granted": False,
        "nearest_wins_applied": False,
        "measurement_published": False,
        "shadow_only": True,
    }


def geometric_proximity_abstain_shadow(
    *,
    candidate_distances_pdf_pts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Prove proximity lists are retained without selecting a nearest host."""
    rows = []
    for row in candidate_distances_pdf_pts:
        if not isinstance(row, Mapping):
            raise TypeError("candidate distance row must be a mapping")
        wid = str(row.get("wall_candidate_id") or "").strip()
        dist = row.get("distance_pdf_pts")
        if not wid:
            raise ValueError("wall_candidate_id required")
        if type(dist) not in (float, int) or float(dist) < 0:
            raise ValueError("non-negative distance required")
        rows.append({"wall_candidate_id": wid, "distance_pdf_pts": float(dist)})
    sorted_rows = sorted(rows, key=lambda r: (r["distance_pdf_pts"], r["wall_candidate_id"]))
    return {
        "status": "UNPUBLISHED_GEOMETRIC_PROXIMITY_ABSTAIN",
        "candidate_count": len(sorted_rows),
        "candidates_retained_sorted_diagnostic_only": sorted_rows,
        "selected_wall_candidate_id": None,
        "nearest_wins_applied": False,
        "first_remaining_gate": (
            "geometric_proximity_ambiguous_abstain"
            if len(sorted_rows) != 1
            else "single_proximity_candidate_still_review_only"
        ),
        "host_granted": False,
        "shadow_only": True,
    }
