"""Original physical G17 opening → exact authenticated two-flank ink ownership.

Consumes source-family geometry candidates from GPT2's original raster
parent/band shadows, but re-resolves EVERY opening-primitive observation from
the existing producer-owned SourceVisibilityAuthority. There is no substitute
source namespace, no geometric proximity guess, and no W4/host/FIRM grant.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from pb_gpt2_raster_opening_parent_source_shadow import (
    RasterOpeningParentSourceHandoff,
)
from pb_gpt2_raster_source_flank_band_shadow import (
    RasterSourceFlankBandResult,
    reconstruct_raster_source_flank_bands_shadow,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION,
    RASTER_FRAMED_WALL_BAND_INTERRUPTION,
    PhysicalOpeningAuthority,
    PhysicalOpeningExistenceRecord,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityAuthority


@dataclass(frozen=True)
class OriginalG17OpeningFlankOwnership:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    physical_opening_id: str
    source_sha256: str
    physical_source_observation_ids: tuple[str, ...] = ()
    authenticated_flank_end_parent_ids: tuple[str, ...] = ()
    authenticated_flank_source_visible_ids: tuple[str, ...] = ()
    authenticated_source_parent_ids: tuple[str, ...] = ()
    shadow_only: bool = True
    w4_wall_membership_granted: bool = False
    host_binding_granted: bool = False
    whole_wall_frame_granted: bool = False
    opening_count_granted: bool = False
    firm_area_granted: bool = False
    customer_publication_granted: bool = False


def _abstain(
    selector: ObservationSelector, code: str, *,
    physical_id: str = "",
) -> OriginalG17OpeningFlankOwnership:
    return OriginalG17OpeningFlankOwnership(
        EvidenceResolutionStatus.ABSTAINED, (code,), physical_id,
        selector.source_sha256,
    )


def bind_original_g17_flanks_to_physical_opening_shadow(
    authority: PhysicalOpeningAuthority, *,
    original_selector: ObservationSelector,
    parent_source: RasterOpeningParentSourceHandoff,
    source_bands: RasterSourceFlankBandResult,
) -> OriginalG17OpeningFlankOwnership:
    """Require one exact G17 physical owner of BOTH source band flanks.

    This proves original source support membership only. In particular, two
    geometrically closed source bands do not identify a W4 structural wall.
    """
    if type(authority) is not PhysicalOpeningAuthority:
        raise TypeError("PhysicalOpeningAuthority required")
    if type(original_selector) is not ObservationSelector:
        raise TypeError("original physical opening source selector required")
    if (type(parent_source) is not RasterOpeningParentSourceHandoff
            or type(source_bands) is not RasterSourceFlankBandResult):
        raise TypeError("typed source-backed GPT2 raster handoff required")

    original = authority.prove_existence(original_selector)
    record = original.existence_record

    def blocked(reason: str) -> OriginalG17OpeningFlankOwnership:
        # Physical source candidates must stay addressable when a later
        # receipt fails; an empty ID collapses independent G17 abstentions.
        physical_id = (
            record.record_id if type(record) is PhysicalOpeningExistenceRecord
            else ""
        )
        return _abstain(original_selector, reason, physical_id=physical_id)

    if (original.status is not EvidenceResolutionStatus.CORROBORATED
            or type(record) is not PhysicalOpeningExistenceRecord
            or record.status is not EvidenceResolutionStatus.CORROBORATED
            or record.proposition != PHYSICAL_OPENING_EXISTS):
        return blocked("physical_g17_existence_unproven")

    root = ("document_id", "revision_id", "source_sha256", "snapshot_id")
    if (any(getattr(record, field) != getattr(original_selector, field)
            for field in root)
            or type(record.record_id) is not str or not record.record_id
            or type(record.page_id) is not str or not record.page_id
            or record.viewport_id is not None
            or record.semantic_class != "opening"
            or record.structural_pattern not in (
                RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION,
                RASTER_FRAMED_WALL_BAND_INTERRUPTION,
            )
            or type(record.source_observation_ids) is not tuple
            or not record.source_observation_ids
            or original_selector.observation_id not in record.source_observation_ids
            or any(type(obs) is not str or not obs
                   for obs in record.source_observation_ids)
            or len(set(record.source_observation_ids))
            != len(record.source_observation_ids)):
        return blocked("physical_g17_source_root_conflict")

    if (parent_source.source_sha256 != original_selector.source_sha256
            or source_bands.source_sha256 != original_selector.source_sha256
            or parent_source.status != "SOURCE_ONLY_CANDIDATE"
            or parent_source.unresolved_parent_ids
            or not parent_source.shadow_only
            or parent_source.structural_host_granted
            or source_bands.status != "SOURCE_BAND_GEOMETRY_CANDIDATE"
            or not source_bands.shadow_only
            or source_bands.physical_wall_granted
            or source_bands.opening_host_granted
            or source_bands.opening_count_granted
            or source_bands.firm_quantity_granted
            or len(source_bands.candidates) != 2):
        return blocked("source_g17_flank_scope_or_count_unproven")

    # The upstream shadow is an address-only dataclass. Rebuild the same
    # geometry independently here; callers cannot swap in a forged candidate.
    if reconstruct_raster_source_flank_bands_shadow(parent_source) != source_bands:
        return blocked("source_g17_flank_geometry_mismatch")

    rows = parent_source.lines
    source_visible_ids = [line.visible_observation_id for line in rows]
    if (len(source_visible_ids) != len(set(source_visible_ids))
            or len({line.parent_observation_id for line in rows}) != len(rows)
            or any(line.page_id != record.page_id for line in rows)):
        return blocked("source_g17_flank_observation_identity_conflict")

    opening_observation_ids = set(record.source_observation_ids)
    if set(source_visible_ids) != opening_observation_ids:
        return blocked("source_g17_not_complete_physical_opening_support")

    # The original G17 producer independently issues this exact immutable
    # source-root set from each supporting visible observation's derivation
    # parent. Without the comparison, a caller could splice source-owned ink
    # from an entirely different opening under a valid physical opening ID.
    source_roots = tuple(sorted(line.parent_observation_id for line in rows))
    if (
        type(record.source_lineage_root_ids) is not tuple
        or not record.source_lineage_root_ids
        or len(set(record.source_lineage_root_ids)) != len(record.source_lineage_root_ids)
        or any(type(parent) is not str or not parent for parent in record.source_lineage_root_ids)
        or tuple(sorted(record.source_lineage_root_ids)) != source_roots
    ):
        return blocked("source_g17_original_parent_lineage_unbound")

    # Existing producer-owned typed reader must independently reauthenticate
    # every original source observation, not just the two end-line summaries.
    visibility = authority.source_visibility_authority()
    if type(visibility) is not SourceVisibilityAuthority:
        return blocked("source_g17_visibility_authority_unavailable")
    for line in rows:
        resolved = visibility.resolve_raster_opening_primitive(
            ObservationSelector(
                document_id=original_selector.document_id,
                revision_id=original_selector.revision_id,
                source_sha256=original_selector.source_sha256,
                snapshot_id=original_selector.snapshot_id,
                observation_id=line.visible_observation_id,
            )
        )
        source = resolved.observation
        if (resolved.status is not EvidenceResolutionStatus.CORROBORATED
                or source is None
                or source.observation_id != line.visible_observation_id
                or source.page_id != record.page_id
                or any(getattr(source, name) != getattr(original_selector, name)
                       for name in root)
                or source.observation_kind != line.observation_kind
                or source.source_primitive_ref != line.original_source_primitive_ref
                or source.derivation_parent_ids != (line.parent_observation_id,)
                or tuple(source.geometry) != line.geometry_pdf_points):
            return blocked("source_g17_original_primitive_receipt_unbound")

    expected_band_obs = {
        line.visible_observation_id
        for line in rows
        if line.observation_kind in ("raster_wall_band_face", "raster_wall_band_end")
    }
    actual_band_obs = [
        item for candidate in source_bands.candidates
        for item in candidate.original_source_visible_ids
    ]
    if (set(actual_band_obs) != expected_band_obs
            or len(set(actual_band_obs)) != len(actual_band_obs)
            or len({candidate.end_parent_id
                    for candidate in source_bands.candidates}) != 2
            or any(candidate.page_id != record.page_id
                   or candidate.host_binding_granted
                   or candidate.structural_wall_granted
                   or candidate.whole_wall_frame_granted
                   for candidate in source_bands.candidates)):
        return blocked("source_g17_band_ownership_conflict")

    return OriginalG17OpeningFlankOwnership(
        EvidenceResolutionStatus.CORROBORATED,
        ("physical_g17_two_source_flanks_owned_w4_unproven",),
        record.record_id, original_selector.source_sha256,
        tuple(sorted(opening_observation_ids)),
        tuple(sorted(candidate.end_parent_id
                     for candidate in source_bands.candidates)),
        tuple(sorted(expected_band_obs)),
        authenticated_source_parent_ids=source_roots,
    )


def quarantine_overlapping_g17_physical_source_claims_shadow(
    records: tuple[OriginalG17OpeningFlankOwnership, ...],
) -> tuple[OriginalG17OpeningFlankOwnership, ...]:
    """Never silently choose among TWO real physical openings owning G17 ink.

    A one-opening source proof does not certify whole-page physical-instance
    uniqueness. Compare the complete emitted original source observation
    ownership universe before any subsequent structural host claim.
    """
    if type(records) is not tuple or any(
        type(item) is not OriginalG17OpeningFlankOwnership for item in records
    ):
        raise TypeError("typed source-owned G17 physical claim tuple required")
    owners: dict[tuple[str, str], set[str]] = {}
    physically_repeated: set[tuple[str, str]] = set()
    seen_ids: set[tuple[str, str]] = set()
    for item in records:
        physical_key = (item.source_sha256, item.physical_opening_id)
        if item.physical_opening_id and physical_key in seen_ids:
            physically_repeated.add(physical_key)
        seen_ids.add(physical_key)
        if item.status is not EvidenceResolutionStatus.CORROBORATED:
            continue
        for original_id in (
            *item.physical_source_observation_ids,
            *item.authenticated_source_parent_ids,
            *item.authenticated_flank_end_parent_ids,
        ):
            key = (item.source_sha256, original_id)
            owners.setdefault(key, set()).add(item.physical_opening_id)
    contested: set[tuple[str, str]] = set(physically_repeated)
    for (original_sha, _original_id), owner_ids in owners.items():
        if len(owner_ids) > 1:
            contested.update((original_sha, physical_id)
                             for physical_id in owner_ids)
    output = []
    for item in records:
        if (item.source_sha256, item.physical_opening_id) in contested:
            output.append(replace(
                item, status=EvidenceResolutionStatus.CONFLICT,
                reason_codes=("source_g17_physical_instance_ownership_conflict",),
            ))
        else:
            output.append(item)
    return tuple(sorted(output, key=lambda item: (
        item.source_sha256, item.physical_opening_id,
        item.reason_codes,
    )))
