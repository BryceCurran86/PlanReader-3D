"""Typed census: why G17 derivation parents yield empty authenticated raster lines.

Explains ``authenticated_raster_parent_lines_empty`` without inventing hosts or
lines. Counts parent observation kinds and ``visible:`` primitive-ref outcomes.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    RASTER_PDF_VISIBLE_SEGMENT,
    SourceVisibilityAuthority,
)


def census_unhosted_parent_line_kinds(
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
        raise TypeError("producer SourceVisibilityAuthority required")

    openings: list[dict[str, Any]] = []
    kind_counts: Counter[str] = Counter()
    outcome_counts: Counter[str] = Counter()

    for oid in sorted({str(x).strip() for x in physical_opening_ids if str(x).strip()}):
        trace = next(
            (
                row for row in composition.opening_bindings
                if row.opening_identity_id == oid
            ),
            None,
        )
        if trace is None:
            raise ValueError(f"opening binding missing: {oid}")
        if trace.status is not EvidenceResolutionStatus.ABSTAINED or trace.host_wall_id:
            raise ValueError(f"not unhosted abstained: {oid}")

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
            or opening_record.record_id != oid
        ):
            raise RuntimeError("unhosted opening lost authenticated existence")

        parents: list[dict[str, Any]] = []
        for observation_id in opening_record.source_observation_ids:
            support = visibility.resolve_raster_opening_primitive(ObservationSelector(
                document_id=opening_record.document_id,
                revision_id=opening_record.revision_id,
                source_sha256=opening_record.source_sha256,
                snapshot_id=opening_record.snapshot_id,
                observation_id=observation_id,
            ))
            if support.status is not EvidenceResolutionStatus.CORROBORATED or support.observation is None:
                raise RuntimeError("G17 support observation unverified")
            for parent_id in support.observation.derivation_parent_ids:
                parent_sel = ObservationSelector(
                    document_id=opening_record.document_id,
                    revision_id=opening_record.revision_id,
                    source_sha256=opening_record.source_sha256,
                    snapshot_id=opening_record.snapshot_id,
                    observation_id=str(parent_id),
                )
                parent_res = visibility._source_authority.resolve(parent_sel)
                parent = parent_res.observation
                if (
                    parent_res.status is not EvidenceResolutionStatus.CORROBORATED
                    or parent is None
                ):
                    outcome = "parent_resolve_unauthenticated"
                    kind = None
                    pref = None
                else:
                    kind = str(parent.observation_kind or "")
                    pref = str(parent.source_primitive_ref or "")
                    kind_counts[kind or "<empty_kind>"] += 1
                    if kind != RASTER_PDF_VISIBLE_SEGMENT:
                        outcome = "parent_kind_not_raster_pdf_visible_segment"
                    elif not pref.startswith("visible:"):
                        outcome = "parent_primitive_ref_not_visible_prefix"
                    elif str(parent.page_id) != str(opening_record.page_id):
                        outcome = "parent_page_mismatch"
                    else:
                        outcome = "parent_would_authenticate_as_raster_line"
                outcome_counts[outcome] += 1
                parents.append({
                    "parent_observation_id": str(parent_id),
                    "observation_kind": kind,
                    "source_primitive_ref": pref,
                    "line_auth_outcome": outcome,
                })

        openings.append({
            "physical_opening_id": oid,
            "g17_support_observation_count": len(opening_record.source_observation_ids),
            "derivation_parent_count": len(parents),
            "parents": parents,
            "host_granted": False,
        })

    return {
        "status": "UNPUBLISHED_UNHOSTED_PARENT_LINE_KIND_CENSUS",
        "opening_count": len(openings),
        "parent_observation_kind_counts": dict(sorted(kind_counts.items())),
        "line_auth_outcome_counts": dict(sorted(outcome_counts.items())),
        "openings": openings,
        "host_granted": False,
        "measurement_published": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }
