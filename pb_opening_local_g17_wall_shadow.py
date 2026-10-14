"""Producer-owned isolated G17 source candidates, never a host universe.

No augmentation, consumer geometry or serialized diagnostic proof enters this
boundary. Original source primitives retain their namespace through W2/W4.
All outputs remain shadow candidates pending structural role and equivalence.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import cv2
import numpy as np

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateRecord, PhysicalWallSourceEdgeFragment,
    _assemble_source_owned_w4_identities_or_unavailable,
)
from pb_raster_g17_source_shadow import (
    authenticated_one_end_g17_paint_shadow, source_only_closed_flanks,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    RASTER_OPENING_PRIMITIVE_RENDER_DPI, SourceVisibilityProducer,
)
from pb_wall_room_topology_junction_classifier import classify_junctions
from pb_wall_room_topology_primitive_lineage import LINEAGE_KEY
from pb_wall_room_topology_stage_a import (
    DEFAULT_GAP_SNAP_TOLERANCE_PT, build_wall_graph_for_viewport,
)


@dataclass(frozen=True)
class G17FlankWallShadow:
    source_observation_ids: tuple[str, ...]
    source_parent_ids: tuple[str, ...]
    source_ink_supported: bool
    reason_codes: tuple[str, ...]
    default_records: tuple[PhysicalWallCandidateRecord, ...] = ()
    exact_coordinate_records: tuple[PhysicalWallCandidateRecord, ...] = ()
    default_snap_collapsed_count: int = 0
    default_junction_types: tuple[str, ...] = ()
    exact_junction_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class OpeningLocalG17WallShadow:
    source_selector: ObservationSelector
    physical_opening_id: str | None
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    flanks: tuple[G17FlankWallShadow, ...] = ()
    scope_complete: bool = False
    physical_wall_role_granted: bool = False
    opening_host_granted: bool = False
    metric_quantity_granted: bool = False


def _graph_records(segments, opening, side, tolerance):
    scope_id = stable_contract_id("g17-wall-source-shadow", {
        "document_id": opening.document_id, "source_sha256": opening.source_sha256,
        "revision_id": opening.revision_id, "snapshot_id": opening.snapshot_id,
        "page_id": opening.page_id, "physical_opening_id": opening.record_id,
        "side": side, "snap_tolerance_pt": tolerance,
    })
    graph = build_wall_graph_for_viewport(
        segments, gap_snap_tolerance_pt=tolerance,
        exact_endpoint_index_shadow=(tolerance == 0.0),
        exact_split_parent_lineage_shadow=True,
    )
    junctions, relationships = classify_junctions(
        graph, document_id=opening.document_id,
        page_id=opening.page_id, viewport_id=scope_id,
    )
    assembled = _assemble_source_owned_w4_identities_or_unavailable(
        graph=graph, junctions=junctions, relationships=relationships,
        scope_id=scope_id,
    )
    if assembled is None:
        return (), len(graph["snap_collapsed_fragments"]), (), ("physical_wall_candidate_identity_unresolved",)
    walls, _, identities = assembled
    edges = {str(e["id"]): e for e in graph["edges"]}
    records = tuple(PhysicalWallCandidateRecord(
        wall_candidate_id=wall.candidate_id, wall_candidate=wall,
        physical_identity=identities[wall.candidate_id],
        source_edge_fragments=tuple(PhysicalWallSourceEdgeFragment(
            edge_id=eid,
            geometry=tuple(float(edges[eid][k]) for k in ("x1", "y1", "x2", "y2")),
            source_primitive_ids=tuple(sorted(edges[eid][LINEAGE_KEY]["source_primitive_ids"])),
        ) for eid in sorted(identities[wall.candidate_id].edge_ids)),
    ) for wall in sorted(walls, key=lambda w: w.candidate_id))
    return (records, len(graph["snap_collapsed_fragments"]),
            tuple(sorted(j.junction_type.value for j in junctions)), ())


def build_opening_local_g17_wall_shadow(
    source: SourceVisibilityProducer, selector: ObservationSelector,
) -> OpeningLocalG17WallShadow:
    """Address one original opening; never accept source/candidate bodies.

    This deliberately cannot be passed to the sealed physical-wall or host
    universe authorities. A source-owned candidate identity is not a wall role.
    """
    if type(source) is not SourceVisibilityProducer or type(selector) is not ObservationSelector:
        raise TypeError("actual source producer and observation selector required")
    published = source.published_snapshot_for_revision(selector.revision_id)
    if published is None or any((
        selector.document_id != published.revision.document_id,
        selector.source_sha256 != published.revision.source_sha256,
        selector.snapshot_id != published.snapshot.snapshot_id,
    )):
        raise ValueError("original source selector is foreign or stale")
    blocked = OpeningLocalG17WallShadow(
        selector, None, EvidenceResolutionStatus.ABSTAINED,
        ("g17_structural_wall_role_and_equivalence_unproven",),
    )
    authority = source.physical_opening_authority()
    existence = authority.prove_existence(selector)
    opening = existence.existence_record
    if (existence.status is not EvidenceResolutionStatus.CORROBORATED
            or existence.proposition != PHYSICAL_OPENING_EXISTS or opening is None):
        return replace(blocked, reason_codes=tuple(existence.reason_codes))
    blocked = replace(blocked, physical_opening_id=opening.record_id)
    visibility = source.authority()
    support = {}
    rows = []
    for oid in sorted(opening.source_observation_ids):
        address = replace(selector, observation_id=oid)
        result = visibility.resolve_raster_opening_primitive(address)
        observation = result.observation
        if (result.status is not EvidenceResolutionStatus.CORROBORATED
                or observation is None or observation.page_id != opening.page_id):
            return replace(blocked, reason_codes=("g17_original_source_support_unavailable",))
        support[oid] = observation
        rows.append({
            "observation_id": oid, "observation_kind": observation.observation_kind,
            "geometry_pdf_pts": list(observation.geometry),
            "authenticated_source_parents": [
                {"observation_id": pid} for pid in observation.derivation_parent_ids],
        })
    nomination = source_only_closed_flanks({
        "source_sha256": opening.source_sha256, "physical_opening_id": opening.record_id,
        "host_status": "abstained", "host_granted": False,
        "metric_quantity_granted": False, "source_g17_observations": rows,
    })
    if not nomination["closed_source_flank_nomination"]:
        return replace(blocked, reason_codes=("g17_original_face_end_scope_incomplete",))
    dpi = RASTER_OPENING_PRIMITIVE_RENDER_DPI
    args = {k: getattr(opening, k) for k in (
        "document_id", "revision_id", "source_sha256", "snapshot_id", "page_id")}
    image_png, iparent, iframe = source._producer.render_native_page_png(
        **args, dpi=float(dpi), include_native_frame=True, images_only=True)
    full_png, fparent, fframe = source._producer.render_native_page_png(
        **args, dpi=float(dpi), include_native_frame=True)
    registration = source.raster_opening_registration_scale(opening.revision_id, opening.page_id)
    if (iparent != fparent or iframe != fframe or iframe.rotation != 0
            or registration != (1.0, 1.0)):
        return replace(blocked, reason_codes=("g17_original_render_frame_unproven",))
    def rgb(png):
        decoded = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
        if decoded is None:
            raise ValueError("original source render unavailable")
        return cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)
    image, full = rgb(image_png), rgb(full_png)
    regions = source._producer.native_page_image_regions(**args)
    flanks = []
    for flank in nomination["source_flank_boxes"]:
        ids = tuple(sorted(flank["source_observation_ids"]))
        parents = tuple(sorted(pid for oid in ids for pid in support[oid].derivation_parent_ids))
        paint = authenticated_one_end_g17_paint_shadow(
            image, full, flank, dpi=dpi, image_regions=regions)
        if not paint["source_one_end_shadow_eligible"]:
            flanks.append(G17FlankWallShadow(ids, parents, False,
                                           (paint["source_shadow_first_failure"],)))
            continue
        segments = []
        for oid in ids:
            observation = support[oid]
            if not observation.source_primitive_ref.startswith("visible:raster_opening_primitive:"):
                raise ValueError("original G17 primitive namespace unavailable")
            # Preserve the raw primitive address, not a generated graph alias.
            primitive = observation.source_primitive_ref[len("visible:"):]
            x1, y1, x2, y2 = observation.geometry
            segments.append({
                "id": primitive, "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "document_id": opening.document_id, "page_id": opening.page_id,
                "kind": "line", "kind_present": True,
                "width": 0.0, "width_present": False, "layer": "", "dashes": "",
            })
        default, collapsed, junctions, reasons = _graph_records(
            segments, opening, flank["side_in_original_source_order"], DEFAULT_GAP_SNAP_TOLERANCE_PT)
        exact, _, exact_junctions, exact_reasons = _graph_records(
            segments, opening, flank["side_in_original_source_order"], 0.0)
        if collapsed:
            reasons = (*reasons, "g17_default_w2_source_jamb_snap_collapsed")
        flanks.append(G17FlankWallShadow(
            ids, parents, True, tuple(dict.fromkeys((*reasons, *exact_reasons))),
            default, exact, collapsed, junctions, exact_junctions,
        ))
    if source.published_snapshot_for_revision(selector.revision_id) != published:
        raise RuntimeError("G17 wall shadow changed published source snapshot")
    return replace(blocked, flanks=tuple(flanks))
