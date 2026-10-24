"""Shadow: assemble end-reach lines from G17 segment parents (not production).

Production ``_authenticated_raster_source_lines`` only accepts
``RASTER_PDF_VISIBLE_SEGMENT``. Lot16 unhosted parents are
``raster_opening_primitive_segment``. This module builds a diagnostic line map
from those segment geometries without granting host or changing production.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    RASTER_OPENING_PRIMITIVE_SEGMENT,
    SourceVisibilityAuthority,
)


def _finite_line(geometry: object) -> tuple[float, float, float, float] | None:
    if not isinstance(geometry, (list, tuple)) or len(geometry) != 4:
        return None
    try:
        vals = tuple(float(v) for v in geometry)
    except (TypeError, ValueError):
        return None
    if not all(v == v and abs(v) != float("inf") for v in vals):
        return None
    if vals[0] == vals[2] and vals[1] == vals[3]:
        return None
    return vals  # type: ignore[return-value]


def build_segment_parent_line_map_shadow(
    *,
    visibility: SourceVisibilityAuthority,
    opening_document_id: str,
    opening_revision_id: str,
    opening_source_sha256: str,
    opening_snapshot_id: str,
    opening_page_id: str,
    parent_observation_ids: Sequence[str],
) -> dict[str, Any]:
    """Map raw primitive ids → line coords from segment-parent observations only."""
    lines: dict[str, tuple[float, float, float, float]] = {}
    conflicted: set[str] = set()
    outcomes: dict[str, int] = {}
    rows: list[dict[str, Any]] = []

    for parent_id in sorted({str(p).strip() for p in parent_observation_ids if str(p).strip()}):
        result = visibility._source_authority.resolve(ObservationSelector(
            document_id=opening_document_id,
            revision_id=opening_revision_id,
            source_sha256=opening_source_sha256,
            snapshot_id=opening_snapshot_id,
            observation_id=parent_id,
        ))
        obs = result.observation
        if result.status is not EvidenceResolutionStatus.CORROBORATED or obs is None:
            outcomes["parent_unauthenticated"] = outcomes.get("parent_unauthenticated", 0) + 1
            rows.append({"parent_observation_id": parent_id, "outcome": "parent_unauthenticated"})
            continue
        kind = str(obs.observation_kind or "")
        if kind != RASTER_OPENING_PRIMITIVE_SEGMENT:
            outcomes[f"kind_not_segment:{kind or 'empty'}"] = (
                outcomes.get(f"kind_not_segment:{kind or 'empty'}", 0) + 1
            )
            rows.append({
                "parent_observation_id": parent_id,
                "outcome": "kind_not_segment",
                "observation_kind": kind,
            })
            continue
        if str(obs.page_id) != str(opening_page_id):
            outcomes["page_mismatch"] = outcomes.get("page_mismatch", 0) + 1
            rows.append({"parent_observation_id": parent_id, "outcome": "page_mismatch"})
            continue
        pref = str(obs.source_primitive_ref or "").strip()
        if not pref:
            outcomes["empty_primitive_ref"] = outcomes.get("empty_primitive_ref", 0) + 1
            rows.append({"parent_observation_id": parent_id, "outcome": "empty_primitive_ref"})
            continue
        # Segment refs may already be raw ids or visible-prefixed; normalize.
        raw_id = pref[len("visible:"):] if pref.startswith("visible:") else pref
        line = _finite_line(obs.geometry)
        if line is None:
            outcomes["nonfinite_or_degenerate_geometry"] = (
                outcomes.get("nonfinite_or_degenerate_geometry", 0) + 1
            )
            rows.append({"parent_observation_id": parent_id, "outcome": "bad_geometry"})
            continue
        prior = lines.get(raw_id)
        if prior is not None and prior != line:
            conflicted.add(raw_id)
            outcomes["conflicting_geometry"] = outcomes.get("conflicting_geometry", 0) + 1
            rows.append({
                "parent_observation_id": parent_id,
                "outcome": "conflicting_geometry",
                "raw_primitive_id": raw_id,
            })
            continue
        lines[raw_id] = line
        outcomes["segment_line_authenticated"] = (
            outcomes.get("segment_line_authenticated", 0) + 1
        )
        rows.append({
            "parent_observation_id": parent_id,
            "outcome": "segment_line_authenticated",
            "raw_primitive_id": raw_id,
            "line_pt": list(line),
        })

    for raw_id in conflicted:
        lines.pop(raw_id, None)

    return {
        "status": "UNPUBLISHED_G17_SEGMENT_PARENT_LINE_SHADOW",
        "authenticated_segment_line_count": len(lines),
        "outcome_counts": dict(sorted(outcomes.items())),
        "lines_by_raw_primitive_id": {k: list(v) for k, v in sorted(lines.items())},
        "parent_rows": rows,
        "host_granted": False,
        "production_authenticated_raster_source_lines_replaced": False,
        "shadow_only": True,
    }


def lines_mapping_from_shadow(report: Mapping[str, Any]) -> dict[str, tuple[float, float, float, float]]:
    raw = report.get("lines_by_raw_primitive_id") or {}
    out: dict[str, tuple[float, float, float, float]] = {}
    for key, coords in raw.items():
        line = _finite_line(coords)
        if line is not None:
            out[str(key)] = line
    return out
