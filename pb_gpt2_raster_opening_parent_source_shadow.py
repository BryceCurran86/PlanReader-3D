"""Source-owned raster-opening primitive parent LINE handoff for GPT MAX.

The producer's 300-DPI raster-opening primitive family is not the ordinary
144-DPI raster_pdf_visible_segment family. Consume its dedicated authentic
visibility receipt. Never relabel primitive ink as a structural W4 wall.
Shadow only: grants no host, frame, opening count or FIRM quantity.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    RASTER_OPENING_VISIBLE_PRIMITIVE_KINDS,
    RASTER_OPENING_VISIBLE_PRIMITIVE_ORIGIN_KIND,
    SourceVisibilityProducer,
)


@dataclass(frozen=True)
class AuthenticatedRasterOpeningParentLine:
    parent_observation_id: str
    visible_observation_id: str
    observation_kind: str
    original_source_primitive_ref: str
    page_id: str
    geometry_pdf_points: tuple[float, float, float, float]
    w4_wall_identity_granted: bool = False
    host_binding_granted: bool = False
    opening_count_granted: bool = False


@dataclass(frozen=True)
class RasterOpeningParentSourceHandoff:
    status: str
    source_sha256: str
    requested_parent_ids: tuple[str, ...]
    lines: tuple[AuthenticatedRasterOpeningParentLine, ...]
    unresolved_parent_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    shadow_only: bool = True
    structural_host_granted: bool = False
    whole_wall_frame_granted: bool = False
    metric_quantity_granted: bool = False
    customer_publication_granted: bool = False


def _source_line(record, *, parent_id: str, root: tuple[str, str, str, str], page_id: str):
    """Recheck source ancestry already authenticated by the producer reader."""
    document_id, revision_id, sha256, snapshot_id = root
    if (
        record is None
        or record.document_id != document_id
        or record.revision_id != revision_id
        or record.source_sha256 != sha256
        or record.snapshot_id != snapshot_id
        or record.page_id != page_id
        or record.viewport_id is not None
        or record.observation_kind not in RASTER_OPENING_VISIBLE_PRIMITIVE_KINDS
        or record.origin_kind != RASTER_OPENING_VISIBLE_PRIMITIVE_ORIGIN_KIND
        or type(record.derivation_parent_ids) is not tuple
        or record.derivation_parent_ids != (parent_id,)
        or type(record.source_primitive_ref) is not str
        or not record.source_primitive_ref.startswith("visible:raster_opening_primitive:")
        or type(record.raw_text) is not str or record.raw_text
        or type(record.geometry) is not tuple or len(record.geometry) != 4
        or any(type(v) not in (float, int) or not math.isfinite(float(v))
               for v in record.geometry)
    ):
        return None
    values = tuple(float(v) for v in record.geometry)
    if values[:2] == values[2:]:
        return None
    if type(record.observation_id) is not str or not record.observation_id:
        return None
    return AuthenticatedRasterOpeningParentLine(
        parent_observation_id=parent_id,
        visible_observation_id=record.observation_id,
        observation_kind=record.observation_kind,
        original_source_primitive_ref=record.source_primitive_ref,
        page_id=page_id,
        geometry_pdf_points=values,
    )


def recover_original_raster_opening_parent_lines_shadow(
    source: SourceVisibilityProducer, *,
    revision_id: str,
    snapshot_id: str,
    page_id: str,
    required_parent_ids: Sequence[str],
) -> RasterOpeningParentSourceHandoff:
    """Reauthenticate parent ink, preserving ambiguity and W4 host abstention."""
    if type(source) is not SourceVisibilityProducer:
        raise TypeError("source must be original SourceVisibilityProducer")
    if (
        type(revision_id) is not str or not revision_id
        or type(snapshot_id) is not str or not snapshot_id
        or type(page_id) is not str or not page_id.isdecimal()
        or int(page_id) < 1 or str(int(page_id)) != page_id
        or type(required_parent_ids) not in (list, tuple)
        or not required_parent_ids
        or any(type(v) is not str or not v or v != v.strip()
               for v in required_parent_ids)
        or len(set(required_parent_ids)) != len(required_parent_ids)
    ):
        raise ValueError("exact nonduplicate original source parent and page scope required")
    published = source.published_snapshot_for_revision(revision_id)
    if published is None or published.snapshot.snapshot_id != snapshot_id:
        raise ValueError("original source snapshot unavailable or stale")
    revision = published.revision
    if revision.revision_id != revision_id or not revision.document_id:
        raise ValueError("original source revision conflict")
    sha = revision.source_sha256
    if type(sha) is not str or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("original source SHA identity unavailable")
    root = (revision.document_id, revision_id, sha, snapshot_id)
    requested = tuple(sorted(required_parent_ids))
    sought = set(requested)
    found: dict[str, list[AuthenticatedRasterOpeningParentLine]] = {
        key: [] for key in requested
    }
    # Addressing only: every visible opening primitive must be resolved with
    # the EXISTING producer-owned parent/page/render/visibility receipt.
    for visible_id in sorted(source.raster_opening_primitive_observation_ids_for_snapshot(snapshot_id)):
        selector = ObservationSelector(
            document_id=root[0], revision_id=root[1],
            source_sha256=root[2], snapshot_id=root[3], observation_id=visible_id,
        )
        result = source.resolve_raster_opening_primitive(selector)
        if result.status is not EvidenceResolutionStatus.CORROBORATED:
            continue
        record = result.observation
        if record is None or len(record.derivation_parent_ids) != 1:
            continue
        parent_id = record.derivation_parent_ids[0]
        if parent_id not in sought:
            continue
        line = _source_line(record, parent_id=parent_id, root=root, page_id=page_id)
        if line is not None:
            found[parent_id].append(line)
    verified, blocked = [], []
    for parent_id in requested:
        matches = found[parent_id]
        if len(matches) == 1:
            verified.append(matches[0])
        else:
            blocked.append(parent_id)
    reasons = (
        ("original_raster_opening_parent_lines_partially_authenticated",)
        if blocked and verified else
        ("original_raster_opening_parent_line_unavailable_or_ambiguous",)
        if blocked else
        ("original_raster_opening_source_lines_authenticated_not_w4",)
    )
    return RasterOpeningParentSourceHandoff(
        status="SOURCE_ONLY_CANDIDATE" if not blocked else "PARTIAL_ABSTAIN",
        source_sha256=sha,
        requested_parent_ids=requested,
        lines=tuple(verified),
        unresolved_parent_ids=tuple(blocked),
        reason_codes=reasons,
    )
