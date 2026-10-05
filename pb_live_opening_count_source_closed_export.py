"""Benchmark-neutral source-closed export for authenticated opening counts.

This module seals only count QuantityEvidence already produced by the live
source-authenticated opening-count authority. It does not discover openings,
group benchmark objects, infer marks/counts, or read benchmark truth.

A positive trace re-proves that every quantity member is one exact canonical /
physical opening from the live claim, that all members share current document
lineage, and that the quantity cites each member's source observations.
Multi-opening claims use a deterministic aggregate spatial trace whose member
pages/viewports are retained explicitly in trace metadata.
"""
from __future__ import annotations

import math
from types import MappingProxyType
from typing import Mapping

from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
from pb_migration_contracts import QuantityEvidence, stable_contract_id
from pb_opening_tag_normalization import normalize_opening_tag
from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace
from pb_source_closed_run_export import (
    SealedSourceClosedRun,
    SourceClosedRunConflictError,
    seal_source_closed_run,
)


LIVE_OPENING_COUNT_SOURCE_CLOSED_SCHEMA_VERSION = "1.0.0"


def _clean(value: object) -> str:
    return str(value if value is not None else "").strip()


def _opening_by_identity(claim: LivePhysicalNetWallClaim) -> Mapping[str, object]:
    by_id: dict[str, object] = {}
    for opening in claim.canonical_openings:
        canonical_id = _clean(opening.canonical_opening_id)
        physical_id = _clean(opening.physical_opening_id)
        if not canonical_id or canonical_id != physical_id:
            raise SourceClosedRunConflictError(
                "opening-count sealing requires canonical/physical identity equality"
            )
        if canonical_id in by_id:
            raise SourceClosedRunConflictError(
                f"duplicate canonical opening identity: {canonical_id}"
            )
        by_id[canonical_id] = opening
    return MappingProxyType(by_id)


def _validated_count_quantities(
    claim: LivePhysicalNetWallClaim,
) -> tuple[QuantityEvidence, ...]:
    quantities: list[QuantityEvidence] = []
    seen: set[str] = set()
    for quantity in claim.opening_count_quantity_evidence:
        if not isinstance(quantity, QuantityEvidence):
            raise TypeError(
                "opening_count_quantity_evidence must contain QuantityEvidence"
            )
        if quantity.family != "opening_count":
            continue
        if quantity.abstained or quantity.value is None:
            continue
        if quantity.blocking_reasons:
            continue
        if quantity.quantity_id in seen:
            raise SourceClosedRunConflictError(
                f"duplicate opening-count quantity id: {quantity.quantity_id}"
            )
        seen.add(quantity.quantity_id)
        quantities.append(quantity)
    return tuple(sorted(quantities, key=lambda item: item.quantity_id))


def build_live_opening_count_source_traces(
    claim: LivePhysicalNetWallClaim,
    *,
    workspace_id: int,
    project_id: str,
) -> Mapping[str, CommercialTakeoffSourceTrace]:
    """Build exact aggregate source traces for live authenticated counts."""
    if type(claim) is not LivePhysicalNetWallClaim:
        raise TypeError("claim must be LivePhysicalNetWallClaim")

    openings = _opening_by_identity(claim)
    traces: dict[str, CommercialTakeoffSourceTrace] = {}

    for quantity in _validated_count_quantities(claim):
        identities = tuple(_clean(v) for v in quantity.input_entity_ids if _clean(v))
        if not identities or len(identities) != len(set(identities)):
            raise SourceClosedRunConflictError(
                "opening-count quantity requires unique physical member identities"
            )
        try:
            count_value = float(quantity.value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise SourceClosedRunConflictError(
                "opening-count quantity value must be numeric"
            ) from exc
        if (
            not math.isfinite(count_value)
            or count_value < 0
            or abs(count_value - round(count_value)) > 1e-9
            or int(round(count_value)) != len(identities)
        ):
            raise SourceClosedRunConflictError(
                "opening-count quantity must equal its authenticated physical member count"
            )

        metadata = quantity.metadata if isinstance(quantity.metadata, Mapping) else {}
        if metadata.get("schedule_corroborated") is not True:
            raise SourceClosedRunConflictError(
                "opening-count sealing requires source schedule corroboration"
            )
        raw_mark = _clean(metadata.get("opening_mark"))
        normalized_mark = normalize_opening_tag(raw_mark)
        if normalized_mark is None:
            raise SourceClosedRunConflictError(
                "opening-count quantity requires an authenticated opening mark"
            )

        members = []
        physical_evidence: set[str] = set()
        for identity in identities:
            opening = openings.get(identity)
            if opening is None:
                raise SourceClosedRunConflictError(
                    f"opening-count quantity references unknown physical identity: {identity}"
                )
            member_mark = normalize_opening_tag(_clean(opening.type_mark))
            if member_mark is None or member_mark.tag != normalized_mark.tag:
                raise SourceClosedRunConflictError(
                    f"opening-count member {identity} does not match authenticated mark"
                )
            if not _clean(opening.viewport_id):
                raise SourceClosedRunConflictError(
                    f"opening-count member {identity} lacks owned viewport"
                )
            physical_evidence.update(
                _clean(value)
                for value in opening.source_observation_ids
                if _clean(value)
            )
            members.append(opening)

        first = members[0]
        for member in members[1:]:
            if (
                member.document_id != first.document_id
                or member.revision_id != first.revision_id
                or member.source_sha256 != first.source_sha256
                or member.snapshot_id != first.snapshot_id
            ):
                raise SourceClosedRunConflictError(
                    "opening-count members do not share exact source lineage"
                )

        missing_physical_evidence = physical_evidence - set(quantity.evidence_ids)
        if missing_physical_evidence:
            raise SourceClosedRunConflictError(
                "opening-count quantity omits physical member evidence: "
                + ", ".join(sorted(missing_physical_evidence))
            )

        pages = tuple(sorted({_clean(member.page_id) for member in members}))
        viewports = tuple(
            sorted({_clean(member.viewport_id) for member in members if _clean(member.viewport_id)})
        )
        if not pages or not viewports:
            raise SourceClosedRunConflictError(
                "opening-count aggregate trace requires member pages and viewports"
            )

        aggregate_viewport_id = stable_contract_id(
            "opening_count_spatial_scope",
            {
                "document_id": first.document_id,
                "revision_id": first.revision_id,
                "source_sha256": first.source_sha256,
                "snapshot_id": first.snapshot_id,
                "pages": pages,
                "viewport_ids": viewports,
                "physical_opening_ids": tuple(sorted(identities)),
            },
            digest_chars=24,
        )
        trace = CommercialTakeoffSourceTrace(
            workspace_id=workspace_id,
            project_id=project_id,
            document_id=first.document_id,
            source_sha256=first.source_sha256,
            source_page="aggregate:" + ",".join(pages),
            viewport_id=aggregate_viewport_id,
            revision_id=first.revision_id,
            current_revision_id=first.revision_id,
            evidence_ids=tuple(quantity.evidence_ids),
            canonical_entity_ids=identities,
            metadata={
                "family": quantity.family,
                "opening_mark": normalized_mark.tag,
                "opening_family": metadata.get("opening_family"),
                "aggregate_source_trace": True,
                "member_pages": pages,
                "member_viewport_ids": viewports,
                "member_opening_ids": tuple(sorted(identities)),
                "source_snapshot_id": first.snapshot_id,
            },
        )
        if quantity.quantity_id in traces:
            raise SourceClosedRunConflictError(
                f"duplicate opening-count quantity id: {quantity.quantity_id}"
            )
        traces[quantity.quantity_id] = trace

    return MappingProxyType(traces)


def seal_live_opening_count_run(
    claim: LivePhysicalNetWallClaim,
    *,
    workspace_id: int,
    project_id: str,
) -> SealedSourceClosedRun:
    """Seal all currently authenticated opening-count quantities."""
    quantities = _validated_count_quantities(claim)
    traces = build_live_opening_count_source_traces(
        claim,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    return seal_source_closed_run(
        quantities,
        project_id=project_id,
        traces_by_quantity_id=traces,
    )


__all__ = [
    "LIVE_OPENING_COUNT_SOURCE_CLOSED_SCHEMA_VERSION",
    "build_live_opening_count_source_traces",
    "seal_live_opening_count_run",
]
