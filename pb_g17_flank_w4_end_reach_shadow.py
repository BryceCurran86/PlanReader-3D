"""Shadow ledger: G17 solid-flank FACE/END → local W4 end-reach (never a host).

OBSERVED production seam: ``_resolve_raster_source_band_host_from_records`` in
``pb_opening_host_binding_authority`` emits either
``raster_source_band_{side}_source_primitive_unmapped`` (no W4 parent in the
authenticated solid flank) or
``raster_source_band_{side}_local_wall_owner_unmapped`` (parent exists on a
remote fragment of a longer source line whose own chain does not reach the
flank end).

This module re-observes that classification for diagnostics and GPT MAX
lineage handoff. It retains every plausible owner and never:

- selects nearest/first/smallest
- normalizes physical equivalence into a published host band
- grants host, frame, kind, metric, count, customer, or benchmark authority
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_host_binding_authority import (
    _COORD_TOL,
    _OpeningGeometry,
    _RASTER_WHOLE_WALL_CENTER_TOL_PT,
    _raster_source_band_flanks,
    _source_line_axis_data,
)
from pb_physical_wall_candidate_authority import PhysicalWallCandidateRecord
from pb_source_observation_authority import SourceObservationRecord
from pb_wall_room_topology_stage_a import DEFAULT_GAP_SNAP_TOLERANCE_PT


_ROLES = ("left", "right")


def _candidate_usable(record: PhysicalWallCandidateRecord) -> bool:
    identity = record.physical_identity
    wall = record.wall_candidate
    return bool(
        identity.usable
        and identity.candidate_identity_id
        and not wall.is_curved
        and "non_simple_chain_topology_fallback_ordering" not in wall.reason_codes
    )


def _local_chain_reaches_flank_end(
    record: PhysicalWallCandidateRecord,
    opening: _OpeningGeometry,
    *,
    role: str,
    edge: float,
    cross_lo: float,
    cross_hi: float,
    parent_lo: float,
    parent_hi: float,
    snap_tol: float,
    pixel_tol: float,
) -> bool:
    """True only when a W4 centerline segment itself meets the sealed flank end."""
    points = record.wall_candidate.centerline_pts
    for start, end in zip(points, points[1:]):
        local = _source_line_axis_data((*start, *end), opening)
        if local is None:
            continue
        s_lo, s_hi, s_offset = local
        s_edge = s_hi if role == "left" else s_lo
        if (
            abs(s_edge - edge) <= snap_tol
            and cross_lo - snap_tol <= s_offset <= cross_hi + snap_tol
            and min(s_hi, parent_hi) - max(s_lo, parent_lo) > pixel_tol
        ):
            return True
    return False


def build_g17_flank_w4_end_reach_ledger(
    support: Sequence[SourceObservationRecord],
    records: Sequence[PhysicalWallCandidateRecord],
    opening: _OpeningGeometry,
    source_lines_by_primitive: Mapping[str, Sequence[float]],
) -> dict[str, Any]:
    """Classify each sealed solid flank's first W4 membership gate without hosting.

    Returns a stable sorted ledger. ``host_granted`` is always False. A unique
    local end-reach observation is reported as diagnostic only — it does not
    publish ``OpeningHostBinding`` or alter live composition.
    """
    if type(opening) is not _OpeningGeometry:
        raise TypeError("producer opening geometry required")
    if not isinstance(source_lines_by_primitive, Mapping):
        raise TypeError("source line mapping required")

    flanks = _raster_source_band_flanks(support, opening)
    pixel_tol = _RASTER_WHOLE_WALL_CENTER_TOL_PT + _COORD_TOL
    snap_tol = DEFAULT_GAP_SNAP_TOLERANCE_PT + _COORD_TOL

    role_rows: list[dict[str, Any]] = []
    if flanks is None:
        return {
            "status": EvidenceResolutionStatus.ABSTAINED.value,
            "reason_codes": ("exact_original_g17_face_end_closure_unavailable",),
            "flanks": (),
            "host_granted": False,
            "frame_granted": False,
            "opening_filling_kind_granted": False,
            "metric_quantity_granted": False,
            "customer_publication_granted": False,
            "benchmark_score_granted": False,
            "shadow_only": True,
        }

    for role in _ROLES:
        lo, hi, cross_lo, cross_hi, edge = flanks[role]
        remote_only: list[dict[str, Any]] = []
        local_owners: list[dict[str, Any]] = []
        conflicting_parents: list[dict[str, Any]] = []
        source_member_count = 0
        skipped: list[dict[str, Any]] = []

        for record in records:
            if not _candidate_usable(record):
                skipped.append({
                    "wall_candidate_id": record.wall_candidate_id,
                    "skip_reason": "unusable_or_non_simple_or_curved",
                })
                continue
            identity = record.physical_identity
            # A single W4 candidate may carry MULTIPLE original source
            # primitives reaching this flank. Never silently choose the first
            # parent: different owned source spans may disagree on whether the
            # local W4 centerline reaches the sealed G17 end.
            matches: list[dict[str, Any]] = []
            for primitive_id in identity.source_primitive_ids:
                line = source_lines_by_primitive.get(str(primitive_id))
                data = None if line is None else _source_line_axis_data(line, opening)
                if data is None:
                    continue
                p_lo, p_hi, offset = data
                endpoint = p_hi if role == "left" else p_lo
                if (
                    abs(endpoint - edge) > snap_tol
                    or offset < cross_lo - pixel_tol
                    or offset > cross_hi + pixel_tol
                    or min(p_hi, hi) - max(p_lo, lo) <= pixel_tol
                ):
                    continue
                reaches = _local_chain_reaches_flank_end(
                    record,
                    opening,
                    role=role,
                    edge=edge,
                    cross_lo=cross_lo,
                    cross_hi=cross_hi,
                    parent_lo=p_lo,
                    parent_hi=p_hi,
                    snap_tol=snap_tol,
                    pixel_tol=pixel_tol,
                )
                matches.append({
                    "source_primitive_id": str(primitive_id),
                    "local_chain_reaches_flank_end": reaches,
                })
            if not matches:
                continue
            if len({x["source_primitive_id"] for x in matches}) != len(matches):
                raise ValueError("duplicate W4 source primitive parent identity")
            matches.sort(key=lambda row: row["source_primitive_id"])
            source_member_count += 1
            statuses = {x["local_chain_reaches_flank_end"] for x in matches}
            row = {
                "wall_candidate_id": record.wall_candidate_id,
                "candidate_identity_id": identity.candidate_identity_id,
                # Preserve the older single-parent receipt without falsely
                # electing an arbitrary first source parent for multi-parent.
                "matched_source_primitive_id": (
                    matches[0]["source_primitive_id"] if len(matches) == 1 else None
                ),
                "matched_source_primitive_ids": [
                    x["source_primitive_id"] for x in matches
                ],
                "source_parent_end_reach": matches,
                "local_chain_reaches_flank_end": (
                    next(iter(statuses)) if len(statuses) == 1 else None
                ),
                "host_publication_allowed": False,
            }
            if statuses == {True}:
                local_owners.append(row)
            elif statuses == {False}:
                remote_only.append(row)
            else:
                conflicting_parents.append(row)

        if source_member_count == 0:
            disposition = f"raster_source_band_{role}_source_primitive_unmapped"
        elif conflicting_parents:
            # Source ancestry itself is in conflict; no unique role can be
            # inferred even if a different W4 record has a positive parent.
            disposition = f"raster_source_band_{role}_source_parent_end_reach_conflict_abstained"
        elif not local_owners:
            disposition = f"raster_source_band_{role}_local_wall_owner_unmapped"
        elif len(local_owners) > 1:
            disposition = f"raster_source_band_{role}_multiple_local_w4_end_reach_retained"
        else:
            disposition = f"raster_source_band_{role}_unique_local_w4_end_reach_observed"

        role_rows.append({
            "role": role,
            "flank_axis_span_pt": [lo, hi],
            "flank_cross_band_pt": [cross_lo, cross_hi],
            "flank_end_axis_pt": edge,
            "disposition": disposition,
            "source_member_count": source_member_count,
            "local_end_reach_candidates": sorted(
                local_owners, key=lambda r: r["wall_candidate_id"]
            ),
            "remote_ancestry_only_candidates": sorted(
                remote_only, key=lambda r: r["wall_candidate_id"]
            ),
            "conflicting_source_parent_candidates": sorted(
                conflicting_parents, key=lambda r: r["wall_candidate_id"]
            ),
            "skipped_candidates": sorted(
                skipped, key=lambda r: r["wall_candidate_id"]
            ),
            "host_granted": False,
        })

    return {
        "status": EvidenceResolutionStatus.CORROBORATED.value,
        "reason_codes": tuple(row["disposition"] for row in role_rows),
        "flanks": tuple(role_rows),
        "host_granted": False,
        "frame_granted": False,
        "opening_filling_kind_granted": False,
        "metric_quantity_granted": False,
        "customer_publication_granted": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }
