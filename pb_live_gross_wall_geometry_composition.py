"""Live source-owned gross-wall geometry composition.

Composes existing producer-owned page, cross-sheet, scale, wall-height, and
whole-wall-frame authorities into GrossWallGeometryAuthority for the exact
physical host walls already proven by the physical-opening-void chain.

Target sheets are never supplied by the caller. The producer searches the
complete decoded page universe from the immutable source snapshot. If expanding
wall-candidate materialization adds raster evidence and advances the source
snapshot, this layer fails closed and requires the upstream opening chain to be
recomposed on that stabilized snapshot rather than mixing lineages.

No default height, inferred height, scalar area, caller polygon, expected
benchmark quantity, or commercial publication enters this boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from pb_cross_sheet_registration_authority import (
    CrossSheetRegistrationAuthority,
    CrossSheetRegistrationProducer,
    CrossSheetRegistrationSelector,
)
from pb_geometry_takeoff_model import AuthorityStatus
from pb_gross_wall_geometry_authority import (
    GrossWallGeometryAuthority,
    GrossWallGeometryProducer,
    GrossWallGeometrySelector,
)
from pb_live_physical_opening_void_composition import (
    LivePhysicalOpeningVoidComposition,
)
from pb_live_wall_opening_authority_composition import (
    LiveWallOpeningAuthorityComposition,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_host_frame_authority import OpeningHostFrameSelector
from pb_physical_scale_authority import (
    PhysicalScaleAuthority,
    PhysicalScaleProducer,
    PhysicalScaleSelector,
)
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_height_authority import (
    WallHeightAuthority,
    WallHeightProducer,
    WallHeightSelector,
)
from pb_zero_opening_wall_frame_authority import (
    ZeroOpeningWallFrameProducer,
    ZeroOpeningWallFrameSelector,
    combine_zero_opening_wall_frame_authorities,
)


LIVE_GROSS_WALL_SCHEMA_VERSION = "1.0.0"
LIVE_GROSS_WALL_RESOLVED = "live_gross_wall_geometry_composition_resolved"
LIVE_GROSS_WALL_PARTIAL = "live_gross_wall_geometry_composition_partial"
LIVE_GROSS_WALL_UNAVAILABLE = "live_gross_wall_geometry_composition_unavailable"
LIVE_GROSS_WALL_SOURCE_SNAPSHOT_ADVANCED = (
    "live_gross_wall_geometry_source_snapshot_advanced"
)
LIVE_GROSS_WALL_UPSTREAM_INCOMPLETE = (
    "live_gross_wall_geometry_upstream_incomplete"
)
LIVE_GROSS_WALL_COVERAGE_INCOMPLETE = (
    "live_gross_wall_geometry_wall_coverage_incomplete"
)


@dataclass(frozen=True)
class LiveGrossWallTrace:
    physical_wall_id: str
    page_id: str
    decision_scope_id: str
    registration_target_page_ids: tuple[str, ...]
    registration_record_ids: tuple[str, ...]
    height_status: str
    height_m: float | None
    height_reason_codes: tuple[str, ...]
    scale_status: EvidenceResolutionStatus
    scale_record_id: str | None
    scale_reason_codes: tuple[str, ...]
    gross_status: EvidenceResolutionStatus
    gross_record_id: str | None
    gross_reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class LiveGrossWallGeometryComposition:
    revision_id: str
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    traces: tuple[LiveGrossWallTrace, ...]
    physical_wall_candidate_authority: PhysicalWallCandidateAuthority | None
    cross_sheet_registration_authority: CrossSheetRegistrationAuthority | None
    physical_scale_authority: PhysicalScaleAuthority | None
    wall_height_authority: WallHeightAuthority | None
    gross_wall_geometry_authority: GrossWallGeometryAuthority | None
    gross_selectors: Mapping[str, GrossWallGeometrySelector]
    schema_version: str = LIVE_GROSS_WALL_SCHEMA_VERSION


def _reasons(values) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


def _blocked(
    *,
    revision_id: str,
    reason_codes: tuple[str, ...],
) -> LiveGrossWallGeometryComposition:
    return LiveGrossWallGeometryComposition(
        revision_id=revision_id,
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=_reasons(reason_codes),
        traces=(),
        physical_wall_candidate_authority=None,
        cross_sheet_registration_authority=None,
        physical_scale_authority=None,
        wall_height_authority=None,
        gross_wall_geometry_authority=None,
        gross_selectors=MappingProxyType({}),
    )


def compose_live_gross_wall_geometry(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    wall_opening_composition: LiveWallOpeningAuthorityComposition,
    physical_void_composition: LivePhysicalOpeningVoidComposition,
) -> LiveGrossWallGeometryComposition:
    """Compose authenticated gross wall geometry for proven opening host walls."""
    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError("source_visibility_producer must be producer-owned")
    if type(wall_opening_composition) is not LiveWallOpeningAuthorityComposition:
        raise TypeError(
            "wall_opening_composition must be LiveWallOpeningAuthorityComposition"
        )
    if type(physical_void_composition) is not LivePhysicalOpeningVoidComposition:
        raise TypeError(
            "physical_void_composition must be LivePhysicalOpeningVoidComposition"
        )

    revision_id = wall_opening_composition.revision_id
    if physical_void_composition.revision_id != revision_id:
        return _blocked(
            revision_id=revision_id,
            reason_codes=(LIVE_GROSS_WALL_UPSTREAM_INCOMPLETE,),
        )

    published_before = source_visibility_producer.published_snapshot_for_revision(
        revision_id
    )
    if published_before is None:
        return _blocked(
            revision_id=revision_id,
            reason_codes=(LIVE_GROSS_WALL_UNAVAILABLE,),
        )

    # Build the complete decoded-page candidate universe. This may add
    # producer-owned raster evidence on pages that had no usable native vectors.
    # Never mix a newly advanced snapshot with already-sealed opening records.
    wall_candidate_producer = (
        PhysicalWallCandidateProducer.from_source_visibility_producer(
            source_visibility_producer
        )
    )
    published_after = source_visibility_producer.published_snapshot_for_revision(
        revision_id
    )
    if published_after is None:
        return _blocked(
            revision_id=revision_id,
            reason_codes=(LIVE_GROSS_WALL_UNAVAILABLE,),
        )
    if (
        published_after.snapshot.snapshot_id
        != published_before.snapshot.snapshot_id
    ):
        return _blocked(
            revision_id=revision_id,
            reason_codes=(LIVE_GROSS_WALL_SOURCE_SNAPSHOT_ADVANCED,),
        )
    if (
        published_after.revision.document_id
        != published_before.revision.document_id
        or published_after.revision.source_sha256
        != published_before.revision.source_sha256
    ):
        return _blocked(
            revision_id=revision_id,
            reason_codes=(LIVE_GROSS_WALL_UPSTREAM_INCOMPLETE,),
        )

    wall_candidate_authority = wall_candidate_producer.authority()

    # Build the complete wall-equivalence universe for the exact source pages
    # selected by the upstream live wall/opening composition. A downstream
    # gross/net composition may not call itself complete merely because every
    # opening-host wall resolved; zero-opening walls must remain visible as an
    # explicit coverage blocker until they have their own authenticated frame.
    required_wall_classes: list[tuple[str, str, frozenset[str]]] = []
    ambiguous_wall_ids_by_page: dict[str, set[str]] = {}
    coverage_equivalence_unavailable = False
    for page_id in wall_opening_composition.page_ids:
        scope_selector = PhysicalWallCandidateSelector(
            document_id=published_after.revision.document_id,
            revision_id=published_after.revision.revision_id,
            source_sha256=published_after.revision.source_sha256,
            snapshot_id=published_after.snapshot.snapshot_id,
            page_id=page_id,
            decision_scope_id=f"wall-source:page-{page_id}",
        )
        scope_result = wall_candidate_authority.resolve_scope(scope_selector)
        if (
            scope_result.status is not EvidenceResolutionStatus.CORROBORATED
            or not scope_result.scope_complete
            or scope_result.document_id != published_after.revision.document_id
            or scope_result.revision_id != published_after.revision.revision_id
            or scope_result.source_sha256 != published_after.revision.source_sha256
            or scope_result.snapshot_id != published_after.snapshot.snapshot_id
            or scope_result.page_id != page_id
        ):
            return _blocked(
                revision_id=revision_id,
                reason_codes=(
                    LIVE_GROSS_WALL_UPSTREAM_INCOMPLETE,
                    LIVE_GROSS_WALL_COVERAGE_INCOMPLETE,
                ),
            )

        equivalence = scope_result.equivalence
        if equivalence is None:
            coverage_equivalence_unavailable = True
            for record in scope_result.records:
                required_wall_classes.append(
                    (
                        page_id,
                        record.wall_candidate_id,
                        frozenset((record.wall_candidate_id,)),
                    )
                )
            continue

        # abstained_wall_ids also contains ordinary non-representatives of
        # proven SAME groups, so it cannot by itself mean coverage is unknown.
        # Track only genuinely ambiguous candidate identities. A later sealed
        # whole-wall host frame may independently account for those members.
        if tuple(equivalence.ambiguous_wall_ids):
            ambiguous_wall_ids_by_page.setdefault(page_id, set()).update(
                str(wall_id)
                for wall_id in equivalence.ambiguous_wall_ids
                if str(wall_id)
            )

        groups = tuple(
            frozenset(str(member_id) for member_id in group if str(member_id))
            for group in equivalence.equivalence_groups
            if group
        )
        for representative_id in equivalence.representative_wall_ids:
            representative_id = str(representative_id)
            wall_class = next(
                (group for group in groups if representative_id in group),
                frozenset((representative_id,)),
            )
            required_wall_classes.append(
                (page_id, representative_id, wall_class)
            )

    # Whole walls are discovered only by replaying producer-owned physical void
    # records and their sealed whole-wall host frames. OpeningHostBindingRecord
    # host_wall_id is deliberately opening-scoped; it must never become the
    # downstream physical-wall identity. The shared whole_wall_frame_id is the
    # canonical address, while its authenticated candidate members are retained
    # only for lower-level cross-sheet registration and wall-height proof.
    host_walls: dict[tuple[str, str, str], tuple[str, ...]] = {}
    frame_authority = wall_opening_composition.opening_host_frame_authority
    if frame_authority is None:
        return _blocked(
            revision_id=revision_id,
            reason_codes=(LIVE_GROSS_WALL_UPSTREAM_INCOMPLETE,),
        )

    for opening_id, selector in physical_void_composition.void_selectors.items():
        authority = physical_void_composition.physical_opening_void_authorities.get(
            selector.page_id
        )
        if authority is None:
            continue
        result = authority.resolve(selector)
        record = result.record
        if not (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and record is not None
            and record.opening_identity_id == opening_id
            and record.document_id == published_after.revision.document_id
            and record.revision_id == published_after.revision.revision_id
            and record.source_sha256 == published_after.revision.source_sha256
            and record.snapshot_id == published_after.snapshot.snapshot_id
        ):
            continue

        frame_result = frame_authority.resolve(
            OpeningHostFrameSelector(
                document_id=record.document_id,
                revision_id=record.revision_id,
                source_sha256=record.source_sha256,
                snapshot_id=record.snapshot_id,
                page_id=record.page_id,
                decision_scope_id=record.decision_scope_id,
                opening_identity_id=record.opening_identity_id,
            )
        )
        frame = frame_result.evidence
        if not (
            frame_result.status is EvidenceResolutionStatus.CORROBORATED
            and frame is not None
            and frame.whole_wall_frame_id == record.wall_local_frame_id
            and frame.host_wall_id == record.host_wall_id
            and frame.opening_identity_id == record.opening_identity_id
        ):
            continue

        member_ids = tuple(
            sorted(
                dict.fromkeys(
                    str(member_id)
                    for member_id in frame.whole_wall_candidate_ids
                    if str(member_id)
                )
            )
        )
        if not member_ids:
            continue

        key = (
            record.page_id,
            record.decision_scope_id,
            frame.whole_wall_frame_id,
        )
        existing = host_walls.get(key)
        if existing is not None and existing != member_ids:
            return _blocked(
                revision_id=revision_id,
                reason_codes=(LIVE_GROSS_WALL_UPSTREAM_INCOMPLETE,),
            )
        host_walls[key] = member_ids

    covered_member_ids_by_page: dict[str, set[str]] = {}
    for (page_id, _decision_scope_id, _frame_id), member_ids in host_walls.items():
        covered_member_ids_by_page.setdefault(page_id, set()).update(member_ids)

    uncovered_wall_classes = tuple(
        (page_id, representative_id, wall_class)
        for page_id, representative_id, wall_class in required_wall_classes
        if not (
            wall_class
            & covered_member_ids_by_page.get(page_id, set())
        )
    )

    # A wall class absent from the opening-host inventory is not assumed to
    # have zero openings. Re-prove that proposition through exact page opening
    # completeness + every sealed opening host frame, then mint a producer-owned
    # source-space frame only for a genuinely unopened wall.
    zero_walls: dict[tuple[str, str, str], tuple[str, ...]] = {}
    zero_frame_authorities = []
    physical_opening_authority = (
        wall_opening_composition.physical_opening_authority
    )
    for page_id, representative_id, wall_class in uncovered_wall_classes:
        opening_completeness_authority = (
            wall_opening_composition.opening_universe_completeness_authorities.get(
                page_id
            )
        )
        if (
            physical_opening_authority is None
            or opening_completeness_authority is None
        ):
            continue

        zero_producer = ZeroOpeningWallFrameProducer.from_authorities(
            physical_wall_candidate_authority=wall_candidate_authority,
            physical_opening_authority=physical_opening_authority,
            opening_universe_completeness_authority=(
                opening_completeness_authority
            ),
            opening_host_frame_authority=frame_authority,
        )
        zero_selector = ZeroOpeningWallFrameSelector(
            document_id=published_after.revision.document_id,
            revision_id=published_after.revision.revision_id,
            source_sha256=published_after.revision.source_sha256,
            snapshot_id=published_after.snapshot.snapshot_id,
            page_id=page_id,
            decision_scope_id=f"wall-source:page-{page_id}",
            physical_wall_id=representative_id,
        )
        zero_result = zero_producer.publish(zero_selector)
        zero_frame_authorities.append(zero_producer.authority())
        zero_record = zero_result.record
        if (
            zero_result.status is EvidenceResolutionStatus.CORROBORATED
            and zero_record is not None
            and zero_record.physical_wall_id == representative_id
            and frozenset(zero_record.member_wall_candidate_ids) == wall_class
        ):
            zero_walls[
                (
                    page_id,
                    f"wall-source:page-{page_id}",
                    representative_id,
                )
            ] = tuple(zero_record.member_wall_candidate_ids)

    zero_frame_authority = (
        combine_zero_opening_wall_frame_authorities(
            tuple(zero_frame_authorities)
        )
        if zero_frame_authorities
        else None
    )

    wall_targets = dict(host_walls)
    for key, member_ids in zero_walls.items():
        existing = wall_targets.get(key)
        if existing is not None and existing != member_ids:
            return _blocked(
                revision_id=revision_id,
                reason_codes=(LIVE_GROSS_WALL_UPSTREAM_INCOMPLETE,),
            )
        wall_targets[key] = member_ids

    covered_member_ids_by_page = {}
    for (page_id, _decision_scope_id, _wall_id), member_ids in wall_targets.items():
        covered_member_ids_by_page.setdefault(page_id, set()).update(member_ids)

    remaining_uncovered_wall_classes = tuple(
        (page_id, representative_id, wall_class)
        for page_id, representative_id, wall_class in required_wall_classes
        if not (
            wall_class
            & covered_member_ids_by_page.get(page_id, set())
        )
    )
    remaining_uncovered_ambiguous_ids = tuple(
        (page_id, wall_id)
        for page_id, wall_ids in sorted(ambiguous_wall_ids_by_page.items())
        for wall_id in sorted(wall_ids)
        if wall_id not in covered_member_ids_by_page.get(page_id, set())
    )
    coverage_incomplete = bool(
        coverage_equivalence_unavailable
        or remaining_uncovered_wall_classes
        or remaining_uncovered_ambiguous_ids
    )

    if not wall_targets:
        return LiveGrossWallGeometryComposition(
            revision_id=revision_id,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(
                LIVE_GROSS_WALL_UNAVAILABLE,
                LIVE_GROSS_WALL_UPSTREAM_INCOMPLETE,
                LIVE_GROSS_WALL_COVERAGE_INCOMPLETE,
            ),
            traces=(),
            physical_wall_candidate_authority=wall_candidate_authority,
            cross_sheet_registration_authority=None,
            physical_scale_authority=None,
            wall_height_authority=None,
            gross_wall_geometry_authority=None,
            gross_selectors=MappingProxyType({}),
        )

    decoded_pages = tuple(
        sorted(
            {
                str(int(page_number))
                for page_number in published_after.coverage.decoded_pages
            },
            key=int,
        )
    )

    registration_producer = CrossSheetRegistrationProducer.from_authorities(
        physical_wall_candidate_authority=wall_candidate_authority,
        source_visibility_producer=source_visibility_producer,
    )
    registration_results: dict[
        tuple[str, str, str], list[tuple[str, str, object]]
    ] = {key: [] for key in wall_targets}

    for key in sorted(wall_targets):
        page_id, decision_scope_id, whole_wall_frame_id = key
        for member_id in wall_targets[key]:
            for target_page_id in decoded_pages:
                if target_page_id == page_id:
                    continue
                selector = CrossSheetRegistrationSelector(
                    document_id=published_after.revision.document_id,
                    revision_id=published_after.revision.revision_id,
                    source_sha256=published_after.revision.source_sha256,
                    snapshot_id=published_after.snapshot.snapshot_id,
                    source_page_id=page_id,
                    target_page_id=target_page_id,
                    physical_element_id=member_id,
                )
                result = registration_producer.publish(selector)
                registration_results[key].append(
                    (member_id, target_page_id, result)
                )

    registration_authority = registration_producer.authority()

    height_producer = WallHeightProducer.from_authorities(
        source_visibility_producer,
        cross_sheet_registration_authority=registration_authority,
        physical_wall_candidate_authority=wall_candidate_authority,
    )
    height_results = {}
    for key in sorted(wall_targets):
        page_id, decision_scope_id, _whole_wall_frame_id = key
        member_heights = []
        for member_id in wall_targets[key]:
            selector = WallHeightSelector(
                document_id=published_after.revision.document_id,
                revision_id=published_after.revision.revision_id,
                source_sha256=published_after.revision.source_sha256,
                snapshot_id=published_after.snapshot.snapshot_id,
                page_id=page_id,
                decision_scope_id=decision_scope_id,
                physical_wall_id=member_id,
            )
            member_heights.append(
                (member_id, height_producer.publish_scope(selector))
            )

        resolved_heights = [
            (member_id, quantity)
            for member_id, quantity in member_heights
            if (
                not getattr(quantity, "abstained", True)
                and getattr(quantity, "value", None) is not None
                and getattr(quantity, "status", None) == AuthorityStatus.FIRM.value
            )
        ]
        if resolved_heights:
            height_results[key] = sorted(
                resolved_heights, key=lambda item: item[0]
            )[0][1]
        elif member_heights:
            height_results[key] = sorted(
                member_heights, key=lambda item: item[0]
            )[0][1]
    height_authority = height_producer.authority()

    scale_producer = PhysicalScaleProducer.from_source_visibility_producer(
        source_visibility_producer
    )
    scale_results = {}
    for page_id in sorted({key[0] for key in wall_targets}, key=int):
        selector = PhysicalScaleSelector(
            document_id=published_after.revision.document_id,
            revision_id=published_after.revision.revision_id,
            source_sha256=published_after.revision.source_sha256,
            snapshot_id=published_after.snapshot.snapshot_id,
            page_id=page_id,
            viewport_id=None,
        )
        scale_results[page_id] = scale_producer.publish_scope(selector)
    scale_authority = scale_producer.authority()

    gross_producer = GrossWallGeometryProducer.from_authorities(
        physical_wall_candidate_authority=wall_candidate_authority,
        host_frame_authority=wall_opening_composition.opening_host_frame_authority,
        physical_scale_authority=scale_authority,
        wall_height_authority=height_authority,
        zero_opening_wall_frame_authority=zero_frame_authority,
    )
    gross_results = {}
    gross_selectors: dict[str, GrossWallGeometrySelector] = {}
    for page_id, decision_scope_id, physical_wall_id in sorted(wall_targets):
        selector = GrossWallGeometrySelector(
            document_id=published_after.revision.document_id,
            revision_id=published_after.revision.revision_id,
            source_sha256=published_after.revision.source_sha256,
            snapshot_id=published_after.snapshot.snapshot_id,
            page_id=page_id,
            decision_scope_id=decision_scope_id,
            physical_wall_id=physical_wall_id,
        )
        gross_selectors[physical_wall_id] = selector
        gross_results[(page_id, decision_scope_id, physical_wall_id)] = (
            gross_producer.publish(selector)
        )
    gross_authority = gross_producer.authority()

    traces: list[LiveGrossWallTrace] = []
    for key in sorted(wall_targets):
        page_id, decision_scope_id, physical_wall_id = key
        registrations = registration_results.get(key, [])
        resolved_registrations = [
            (target_page_id, result.record.record_id)
            for _member_id, target_page_id, result in registrations
            if (
                result.status is EvidenceResolutionStatus.CORROBORATED
                and result.record is not None
            )
        ]
        height = height_results.get(key)
        scale = scale_results.get(page_id)
        gross = gross_results[key]
        scale_evidence = getattr(scale, "evidence", None)
        gross_record = gross.record
        traces.append(
            LiveGrossWallTrace(
                physical_wall_id=physical_wall_id,
                page_id=page_id,
                decision_scope_id=decision_scope_id,
                registration_target_page_ids=tuple(
                    target for target, _ in resolved_registrations
                ),
                registration_record_ids=tuple(
                    record_id for _, record_id in resolved_registrations
                ),
                height_status=(
                    str(height.status)
                    if height is not None
                    else str(AuthorityStatus.BLOCKED.value)
                ),
                height_m=(
                    float(height.value)
                    if height is not None and height.value is not None
                    else None
                ),
                height_reason_codes=_reasons(
                    (
                        getattr(height, "reason_codes", ())
                        or getattr(height, "blocking_reasons", ())
                    )
                    if height is not None
                    else ("wall_height_unavailable",)
                ),
                scale_status=(
                    scale.status
                    if scale is not None
                    else EvidenceResolutionStatus.ABSTAINED
                ),
                scale_record_id=getattr(scale_evidence, "record_id", None),
                scale_reason_codes=_reasons(
                    getattr(scale, "reason_codes", ())
                    if scale is not None
                    else ("physical_scale_unavailable",)
                ),
                gross_status=gross.status,
                gross_record_id=(
                    gross_record.record_id if gross_record is not None else None
                ),
                gross_reason_codes=_reasons(gross.reason_codes),
            )
        )

    all_resolved = bool(traces) and all(
        trace.gross_status is EvidenceResolutionStatus.CORROBORATED
        and trace.gross_record_id is not None
        for trace in traces
    )
    any_conflict = any(
        trace.gross_status is EvidenceResolutionStatus.CONFLICT
        or trace.scale_status is EvidenceResolutionStatus.CONFLICT
        for trace in traces
    )
    if any_conflict:
        status = EvidenceResolutionStatus.CONFLICT
        reasons = (
            LIVE_GROSS_WALL_PARTIAL,
            *(
                (LIVE_GROSS_WALL_COVERAGE_INCOMPLETE,)
                if coverage_incomplete
                else ()
            ),
            *(reason for trace in traces for reason in trace.gross_reason_codes),
        )
    elif coverage_incomplete:
        status = EvidenceResolutionStatus.ABSTAINED
        reasons = (
            LIVE_GROSS_WALL_PARTIAL,
            LIVE_GROSS_WALL_COVERAGE_INCOMPLETE,
            *(reason for trace in traces for reason in trace.gross_reason_codes),
        )
    elif all_resolved:
        status = EvidenceResolutionStatus.CORROBORATED
        reasons = (LIVE_GROSS_WALL_RESOLVED,)
    else:
        status = EvidenceResolutionStatus.ABSTAINED
        reasons = (
            LIVE_GROSS_WALL_PARTIAL,
            *(reason for trace in traces for reason in trace.gross_reason_codes),
        )

    return LiveGrossWallGeometryComposition(
        revision_id=revision_id,
        status=status,
        reason_codes=_reasons(reasons),
        traces=tuple(traces),
        physical_wall_candidate_authority=wall_candidate_authority,
        cross_sheet_registration_authority=registration_authority,
        physical_scale_authority=scale_authority,
        wall_height_authority=height_authority,
        gross_wall_geometry_authority=gross_authority,
        gross_selectors=MappingProxyType(dict(gross_selectors)),
    )


__all__ = [
    "LIVE_GROSS_WALL_COVERAGE_INCOMPLETE",
    "LIVE_GROSS_WALL_PARTIAL",
    "LIVE_GROSS_WALL_RESOLVED",
    "LIVE_GROSS_WALL_SCHEMA_VERSION",
    "LIVE_GROSS_WALL_SOURCE_SNAPSHOT_ADVANCED",
    "LIVE_GROSS_WALL_UNAVAILABLE",
    "LIVE_GROSS_WALL_UPSTREAM_INCOMPLETE",
    "LiveGrossWallGeometryComposition",
    "LiveGrossWallTrace",
    "compose_live_gross_wall_geometry",
]
