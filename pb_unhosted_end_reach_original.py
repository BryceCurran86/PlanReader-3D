"""Build G17→W4 end-reach ledgers for unhosted openings from live producers.

Mirrors the support/line assembly used by
``_resolve_raster_source_band_host`` but never publishes a host band.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pb_g17_flank_w4_end_reach_shadow import build_g17_flank_w4_end_reach_ledger
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_host_binding_authority import (
    _authenticated_raster_source_lines,
    _opening_geometry,
)
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
from pb_source_observation_authority import ObservationSelector


def build_unhosted_end_reach_ledger_for_opening(
    *,
    composition: object,
    published: object,
    physical_opening_id: str,
) -> dict[str, Any]:
    revision = published.revision
    snapshot = published.snapshot
    opening_authority = composition.physical_opening_authority
    wall_authority = composition.physical_wall_candidate_authority

    trace = next(
        (
            row for row in composition.opening_bindings
            if row.opening_identity_id == physical_opening_id
        ),
        None,
    )
    if trace is None:
        raise ValueError("opening binding trace missing")
    if trace.status is not EvidenceResolutionStatus.ABSTAINED or trace.host_wall_id:
        raise ValueError("target is not an unhosted abstained opening")

    selector = ObservationSelector(
        document_id=revision.document_id,
        revision_id=revision.revision_id,
        source_sha256=revision.source_sha256,
        snapshot_id=snapshot.snapshot_id,
        observation_id=trace.representative_observation_id,
    )
    existence = opening_authority.prove_existence(selector)
    opening_record = existence.existence_record
    if (
        existence.status is not EvidenceResolutionStatus.CORROBORATED
        or opening_record is None
        or opening_record.record_id != physical_opening_id
    ):
        raise RuntimeError("unhosted opening lost authenticated existence")

    geometry = _opening_geometry(opening_authority, opening_record)
    if geometry is None:
        return {
            "physical_opening_id": physical_opening_id,
            "first_remaining_gate": "opening_geometry_unavailable_for_end_reach",
            "end_reach_ledger": None,
            "host_granted": False,
            "shadow_only": True,
        }

    visibility = opening_authority.source_visibility_authority()
    support = []
    parent_ids: list[str] = []
    for observation_id in opening_record.source_observation_ids:
        result = visibility.resolve_raster_opening_primitive(ObservationSelector(
            document_id=opening_record.document_id,
            revision_id=opening_record.revision_id,
            source_sha256=opening_record.source_sha256,
            snapshot_id=opening_record.snapshot_id,
            observation_id=observation_id,
        ))
        if result.status is not EvidenceResolutionStatus.CORROBORATED or result.observation is None:
            return {
                "physical_opening_id": physical_opening_id,
                "first_remaining_gate": "raster_source_band_support_unavailable",
                "end_reach_ledger": None,
                "host_granted": False,
                "shadow_only": True,
            }
        support.append(result.observation)
        parent_ids.extend(str(pid) for pid in result.observation.derivation_parent_ids)

    wall_scope = wall_authority.resolve_scope(PhysicalWallCandidateSelector(
        document_id=revision.document_id,
        revision_id=revision.revision_id,
        source_sha256=revision.source_sha256,
        snapshot_id=snapshot.snapshot_id,
        page_id=str(opening_record.page_id),
        decision_scope_id=f"wall-source:page-{opening_record.page_id}",
    ))
    if wall_scope.status is not EvidenceResolutionStatus.CORROBORATED:
        return {
            "physical_opening_id": physical_opening_id,
            "first_remaining_gate": "wall_scope_unavailable_for_end_reach",
            "end_reach_ledger": None,
            "host_granted": False,
            "shadow_only": True,
        }

    unique_parents = tuple(sorted(set(parent_ids)))
    lines = _authenticated_raster_source_lines(
        opening_authority, opening_record, unique_parents,
    )
    w4_primitive_ids: set[str] = set()
    for record in wall_scope.records:
        identity = record.physical_identity
        if not identity.usable:
            continue
        for pid in identity.source_primitive_ids:
            text = str(pid).strip()
            if text:
                w4_primitive_ids.add(text)
    line_keys = set(lines.keys())
    intersection = sorted(line_keys & w4_primitive_ids)
    if not unique_parents:
        line_gate = "g17_derivation_parent_ids_absent"
    elif not line_keys:
        line_gate = "authenticated_raster_parent_lines_empty"
    elif not intersection:
        line_gate = "parent_lines_disjoint_from_w4_source_primitives"
    else:
        line_gate = "parent_lines_intersect_w4_source_primitives"
    ledger = build_g17_flank_w4_end_reach_ledger(
        support, wall_scope.records, geometry, lines,
    )
    if ledger.get("host_granted") is not False:
        raise RuntimeError("end-reach ledger attempted host grant")
    return {
        "physical_opening_id": physical_opening_id,
        "first_remaining_gate": "g17_flank_w4_end_reach_shadow_attached",
        "source_line_census": {
            "g17_support_observation_count": len(support),
            "derivation_parent_id_count": len(unique_parents),
            "authenticated_raster_line_count": len(line_keys),
            "usable_w4_source_primitive_count": len(w4_primitive_ids),
            "parent_line_w4_intersection_count": len(intersection),
            "source_line_first_gate": line_gate,
        },
        "end_reach_ledger": ledger,
        "flank_dispositions": [
            row["disposition"] for row in ledger.get("flanks") or ()
        ],
        "host_granted": False,
        "shadow_only": True,
    }


def attach_end_reach_to_unhosted_openings(
    *,
    composition: object,
    published: object,
    physical_opening_ids: Sequence[str],
) -> dict[str, Any]:
    rows = []
    disposition_counts: dict[str, int] = {}
    for oid in sorted({str(x).strip() for x in physical_opening_ids if str(x).strip()}):
        row = build_unhosted_end_reach_ledger_for_opening(
            composition=composition,
            published=published,
            physical_opening_id=oid,
        )
        for disp in row.get("flank_dispositions") or ():
            disposition_counts[disp] = disposition_counts.get(disp, 0) + 1
        if row.get("first_remaining_gate") and not row.get("flank_dispositions"):
            gate = row["first_remaining_gate"]
            disposition_counts[gate] = disposition_counts.get(gate, 0) + 1
        rows.append(row)
    return {
        "status": "UNPUBLISHED_UNHOSTED_END_REACH_ORIGINAL_ATTACH",
        "opening_count": len(rows),
        "flank_disposition_counts": dict(sorted(disposition_counts.items())),
        "openings": rows,
        "host_granted": False,
        "measurement_published": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }
