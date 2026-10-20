"""Run end-reach using segment-parent line shadow (diagnostic; never hosts)."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pb_g17_flank_w4_end_reach_shadow import build_g17_flank_w4_end_reach_ledger
from pb_g17_segment_parent_line_shadow import (
    build_segment_parent_line_map_shadow,
    lines_mapping_from_shadow,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_host_binding_authority import _opening_geometry
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
from pb_segment_line_w4_id_intersection_shadow import (
    assess_segment_line_w4_id_intersection_shadow,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityAuthority


def build_unhosted_end_reach_with_segment_lines_shadow(
    *,
    composition: object,
    published: object,
    physical_opening_id: str,
) -> dict[str, Any]:
    revision = published.revision
    snapshot = published.snapshot
    opening_authority = composition.physical_opening_authority
    wall_authority = composition.physical_wall_candidate_authority
    visibility = opening_authority.source_visibility_authority()
    if type(visibility) is not SourceVisibilityAuthority:
        raise TypeError("producer SourceVisibilityAuthority required")

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

    existence = opening_authority.prove_existence(ObservationSelector(
        document_id=revision.document_id,
        revision_id=revision.revision_id,
        source_sha256=revision.source_sha256,
        snapshot_id=snapshot.snapshot_id,
        observation_id=trace.representative_observation_id,
    ))
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
            "first_remaining_gate": "opening_geometry_unavailable",
            "host_granted": False,
            "shadow_only": True,
        }

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
                "host_granted": False,
                "shadow_only": True,
            }
        support.append(result.observation)
        parent_ids.extend(str(pid) for pid in result.observation.derivation_parent_ids)

    line_shadow = build_segment_parent_line_map_shadow(
        visibility=visibility,
        opening_document_id=opening_record.document_id,
        opening_revision_id=opening_record.revision_id,
        opening_source_sha256=opening_record.source_sha256,
        opening_snapshot_id=opening_record.snapshot_id,
        opening_page_id=str(opening_record.page_id),
        parent_observation_ids=parent_ids,
    )
    lines = lines_mapping_from_shadow(line_shadow)

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
            "first_remaining_gate": "wall_scope_unavailable",
            "segment_line_shadow": line_shadow,
            "host_granted": False,
            "shadow_only": True,
        }

    w4_ids: list[str] = []
    for record in wall_scope.records:
        identity = record.physical_identity
        if not identity.usable:
            continue
        for pid in identity.source_primitive_ids:
            text = str(pid).strip()
            if text:
                w4_ids.append(text)
    id_gate = assess_segment_line_w4_id_intersection_shadow(
        physical_opening_id=physical_opening_id,
        segment_line_raw_ids=tuple(lines.keys()),
        usable_w4_source_primitive_ids=w4_ids,
    )
    ledger = build_g17_flank_w4_end_reach_ledger(
        support, wall_scope.records, geometry, lines,
    )
    if ledger.get("host_granted") is not False:
        raise RuntimeError("end-reach ledger attempted host grant")
    return {
        "physical_opening_id": physical_opening_id,
        "first_remaining_gate": "g17_segment_line_end_reach_shadow_attached",
        "segment_line_shadow": {
            "authenticated_segment_line_count": line_shadow[
                "authenticated_segment_line_count"],
            "outcome_counts": line_shadow["outcome_counts"],
        },
        "segment_w4_id_intersection": id_gate,
        "flank_dispositions": [row["disposition"] for row in ledger.get("flanks") or ()],
        "end_reach_ledger": ledger,
        "host_granted": False,
        "production_line_assembler_bypassed": True,
        "shadow_only": True,
    }


def attach_segment_line_end_reach_to_unhosted(
    *,
    composition: object,
    published: object,
    physical_opening_ids: Sequence[str],
) -> dict[str, Any]:
    rows = []
    disposition_counts: dict[str, int] = {}
    for oid in sorted({str(x).strip() for x in physical_opening_ids if str(x).strip()}):
        row = build_unhosted_end_reach_with_segment_lines_shadow(
            composition=composition,
            published=published,
            physical_opening_id=oid,
        )
        for disp in row.get("flank_dispositions") or ():
            disposition_counts[disp] = disposition_counts.get(disp, 0) + 1
        rows.append(row)
    return {
        "status": "UNPUBLISHED_UNHOSTED_SEGMENT_LINE_END_REACH_SHADOW",
        "opening_count": len(rows),
        "flank_disposition_counts": dict(sorted(disposition_counts.items())),
        "openings": rows,
        "host_granted": False,
        "measurement_published": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }
