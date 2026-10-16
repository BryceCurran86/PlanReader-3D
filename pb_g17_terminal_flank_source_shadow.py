"""Read a contained original terminal after a whole G17 flank fails paint.

Original primitives and their negative receipts remain unchanged. These
source-addressed CANDIDATE atoms have no structural or commercial authority.
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import math

import cv2
import numpy as np

from pb_migration_contracts import EvidenceAtom, EvidenceResolutionStatus, stable_contract_id
from pb_opening_local_g17_wall_shadow import build_opening_local_g17_wall_shadow
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS
from pb_physical_wall_candidate_authority import MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS
from pb_raster_g17_source_shadow import (
    authenticated_one_end_g17_paint_shadow, source_only_closed_flanks,
)
from pb_raster_opening_source_primitives import MASS_THRESHOLD
from pb_raster_visible_segment_detector import _MIN_LINE_LENGTH_PT
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    RASTER_OPENING_PRIMITIVE_RENDER_DPI, SourceVisibilityProducer,
)
from pb_wall_room_topology_typed_negative_evidence import KIND_UNKNOWN, POLARITY_UNKNOWN


def _inventory(source, pub, selector):
    ids = pub.raster_opening_primitive_observation_ids
    if len(ids) > MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS:
        raise ValueError("original G17 source cap exceeded")
    data = source._producer._store.source_bytes_by_revision.get(selector.revision_id)
    if data is None or sha256(data).hexdigest() != selector.source_sha256:
        raise RuntimeError("original terminal source bytes changed")
    observations = {}
    original_page_renders = {}
    visibility = source.authority()
    for oid in sorted(ids):
        proof = visibility.resolve_raster_opening_primitive(replace(selector, observation_id=oid))
        if proof.status is not EvidenceResolutionStatus.CORROBORATED or proof.observation is None:
            raise RuntimeError("original terminal source inventory unavailable")
        receipt = source._raster_opening_primitive_receipts.get((selector.snapshot_id, oid))
        if (receipt is None or receipt.dpi != RASTER_OPENING_PRIMITIVE_RENDER_DPI
                or len(receipt.pixel_geometry) != 4
                or not proof.observation.source_primitive_ref.startswith("visible:raster_opening_primitive:")
                or not all(type(p) in (int, float) and math.isfinite(p)
                    and math.isclose(p, float(g)*receipt.dpi/72., rel_tol=0, abs_tol=1e-6)
                    for p, g in zip(receipt.pixel_geometry, proof.observation.geometry))):
            raise RuntimeError("original terminal pixel coordinate receipt unproven")
        page_id = proof.observation.page_id
        if page_id not in original_page_renders:
            png, parent, _ = source._producer.render_native_page_png(
                document_id=selector.document_id, revision_id=selector.revision_id,
                source_sha256=selector.source_sha256, snapshot_id=selector.snapshot_id,
                page_id=page_id, dpi=float(RASTER_OPENING_PRIMITIVE_RENDER_DPI),
                include_native_frame=True, images_only=True)
            original_page_renders[page_id] = (sha256(png).hexdigest(), parent.observation_id)
        if original_page_renders[page_id] != (receipt.render_sha256, receipt.page_parent_observation_id):
            raise RuntimeError("original terminal source render receipt unproven")
        observations[oid] = proof.observation
    return observations


def _rgb(png):
    decoded = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    if decoded is None:
        raise ValueError("original terminal render unavailable")
    return cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)


def _terminal(image, full, flank, original, *, dpi, regions, root, parents):
    box = original["original_pixel_bbox_inclusive"]
    row = dict(
        side_in_original_source_order=flank["side_in_original_source_order"],
        original_source_bbox_pdf_pts=list(flank["source_bbox_pdf_pts"]),
        source_observation_ids=list(flank["source_observation_ids"]),
        original_full_flank_source_supported=original["source_one_end_shadow_eligible"],
        original_full_flank_paint_proof=original,
        unchanged_minimum_line_length_pt=_MIN_LINE_LENGTH_PT,
        terminal_contiguous_original_cells=0, terminal_endpoint_span_pt=0.,
        derived_terminal_paint_proof=None, derived_terminal_bbox_pdf_pts=None,
        unconsumed_original_pixel_bbox_inclusive=list(box),
        derived_outer_end_cap_assumed=False, terminal_source_atom=None,
        reason_codes=["original_full_flank_retained"],
    )
    if original["source_one_end_shadow_eligible"]:
        return row
    x0, y0, x1, y1 = box
    a, b = image[y0:y1+1, x0:x1+1], full[y0:y1+1, x0:x1+1]
    valid = (cv2.cvtColor(a, cv2.COLOR_RGB2GRAY) < MASS_THRESHOLD) & np.all(a == b, axis=2)
    if flank["orientation"] == "vertical":
        valid = valid.T
    # Same inset cross rows AND complete central row(s), including the jamb
    # column. Never bridge the first failed column to a more favourable run.
    middle = (valid.shape[0]-1)/2
    center = valid[int(np.floor(middle)):int(np.ceil(middle))+1, :]
    columns = np.all(valid[1:-1, :], axis=0) & np.all(center, axis=0)
    first = flank["side_in_original_source_order"] == "first"
    ordered = columns[::-1] if first else columns
    failures = np.flatnonzero(~ordered)
    cells = int(failures[0]) if failures.size else len(ordered)
    span = max(0, cells-1)*72./dpi
    row.update(terminal_contiguous_original_cells=cells, terminal_endpoint_span_pt=span)
    if span < _MIN_LINE_LENGTH_PT:
        row["reason_codes"] = ["original_terminal_endpoint_span_below_unchanged_minimum"]
        return row
    derived = list(box)
    low, high = (0, 2) if flank["orientation"] == "horizontal" else (1, 3)
    remainder = list(box)
    if first:
        derived[low] = derived[high]-cells+1
        remainder[high] = derived[low]-1
    else:
        derived[high] = derived[low]+cells-1
        remainder[low] = derived[high]+1
    if derived == box:
        row["reason_codes"] = ["original_full_flank_negative_not_replaced"]
        return row
    bounds = [p*72./dpi for p in derived]
    proposal = dict(flank, source_bbox_pdf_pts=bounds)
    proof = authenticated_one_end_g17_paint_shadow(
        image, full, proposal, dpi=dpi, image_regions=regions,
    )
    row.update(derived_terminal_paint_proof=proof, derived_terminal_bbox_pdf_pts=bounds,
               unconsumed_original_pixel_bbox_inclusive=remainder)
    if not proof["source_one_end_shadow_eligible"]:
        row["reason_codes"] = [proof["source_shadow_first_failure"]]
        return row
    payload = dict(root, original_source_observation_ids=flank["source_observation_ids"],
        original_source_parent_ids=parents, original_source_pixel_bbox=box,
        terminal_pixel_bbox=derived, unchanged_minimum_line_length_pt=_MIN_LINE_LENGTH_PT)
    atom = EvidenceAtom(
        evidence_id=stable_contract_id("g17-original-terminal-paint", payload),
        document_id=root["document_id"], page_id=root["page_id"], kind=KIND_UNKNOWN,
        method="original_g17_contained_terminal_paint_shadow", bbox=tuple(bounds),
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=("original_terminal_paint_structural_role_unproven",),
        metadata=dict(payload, source_observation_ids=flank["source_observation_ids"],
            polarity=POLARITY_UNKNOWN, source_role="source_paint_undetermined",
            derived_outer_end_cap_assumed=False, original_full_flank_negative_preserved=True,
            host_granted=False, structural_wall_role_granted=False, metric_quantity_granted=False),
    )
    row.update(terminal_source_atom=atom.to_dict(),
               reason_codes=["original_terminal_paint_structural_role_unproven"])
    return row


def build_g17_terminal_flank_source_shadow(source, selector) -> dict:
    """Address actual immutable source; caller rectangles/diagnostics are rejected."""
    if type(source) is not SourceVisibilityProducer or type(selector) is not ObservationSelector:
        raise TypeError("actual source producer and observation selector required")
    pub = source.published_snapshot_for_revision(selector.revision_id)
    if pub is None or any((selector.document_id != pub.revision.document_id,
        selector.source_sha256 != pub.revision.source_sha256,
        selector.snapshot_id != pub.snapshot.snapshot_id)):
        raise ValueError("original terminal selector is foreign or stale")
    before = _inventory(source, pub, selector)
    if selector.observation_id not in before:
        raise ValueError("original G17 observation selector required")
    receipts = {oid: source._raster_opening_primitive_receipts.get((selector.snapshot_id, oid))
                for oid in pub.raster_opening_primitive_observation_ids}
    baseline = build_opening_local_g17_wall_shadow(source, selector)
    authority = source.physical_opening_authority()
    existence = authority.prove_existence(selector)
    opening = existence.existence_record
    result = dict(status=EvidenceResolutionStatus.ABSTAINED.value,
        reason_codes=["independent_structural_wall_role_equivalence_and_host_required"],
        physical_opening_id=baseline.physical_opening_id, flanks=[],
        scope_complete=False, host_granted=False, structural_wall_role_granted=False,
        metric_quantity_granted=False, original_source_snapshot_unchanged=True)
    if (existence.status is not EvidenceResolutionStatus.CORROBORATED
            or existence.proposition != PHYSICAL_OPENING_EXISTS or opening is None):
        result["reason_codes"] = list(existence.reason_codes)
    else:
        if opening.record_id != baseline.physical_opening_id:
            raise RuntimeError("original terminal opening proof changed")
        with source._native_dimension_source_proof_batch(pub, page_id=opening.page_id):
            rows = []
            for oid in sorted(opening.source_observation_ids):
                o = before[oid]
                rows.append(dict(observation_id=oid, observation_kind=o.observation_kind,
                    geometry_pdf_pts=list(o.geometry), authenticated_source_parents=[
                        dict(observation_id=pid) for pid in o.derivation_parent_ids]))
            nomination = source_only_closed_flanks(dict(source_sha256=opening.source_sha256,
                physical_opening_id=opening.record_id, host_status="abstained",
                host_granted=False, metric_quantity_granted=False, source_g17_observations=rows))
            if not nomination["closed_source_flank_nomination"]:
                result["reason_codes"] = [nomination["unresolved_reason"]]
            root = {k: getattr(opening, k) for k in
                    ("document_id", "revision_id", "source_sha256", "snapshot_id", "page_id")}
            args = {k: root[k] for k in root}
            dpi = RASTER_OPENING_PRIMITIVE_RENDER_DPI
            image_png, ip, iframe = source._producer.render_native_page_png(
                **args, dpi=float(dpi), include_native_frame=True, images_only=True)
            full_png, fp, fframe = source._producer.render_native_page_png(
                **args, dpi=float(dpi), include_native_frame=True)
            if ip != fp or iframe != fframe or iframe.rotation != 0:
                raise RuntimeError("original terminal render frame unproven")
            image, full = _rgb(image_png), _rgb(full_png)
            regions = source._producer.native_page_image_regions(**args)
            image_digest = sha256(image_png).hexdigest()
            for oid, observation in before.items():
                if (observation.page_id == opening.page_id
                        and receipts[oid].render_sha256 != image_digest):
                    raise RuntimeError("original terminal source render receipt changed")
            root.update(original_image_render_sha256=sha256(image_png).hexdigest(),
                        original_full_render_sha256=sha256(full_png).hexdigest(), dpi=dpi,
                        physical_opening_id=opening.record_id)
            result.update({k: root[k] for k in root})
            for flank in nomination["source_flank_boxes"]:
                original = authenticated_one_end_g17_paint_shadow(
                    image, full, flank, dpi=dpi, image_regions=regions)
                parents = sorted({pid for oid in flank["source_observation_ids"]
                                  for pid in before[oid].derivation_parent_ids})
                result["flanks"].append(_terminal(image, full, flank, original,
                    dpi=dpi, regions=regions, root=root, parents=parents))
            if authority.prove_existence(selector) != existence:
                raise RuntimeError("original terminal opening changed during read")
    if (source.published_snapshot_for_revision(selector.revision_id) != pub
            or _inventory(source, pub, selector) != before
            or receipts != {oid: source._raster_opening_primitive_receipts.get((selector.snapshot_id, oid))
                            for oid in pub.raster_opening_primitive_observation_ids}):
        raise RuntimeError("original terminal source changed during read")
    return result


def build_g17_terminal_flank_source_inventory_shadow(source, *, revision_id, page_id):
    """Retain every actual G17 opening on a page; no caller-selected winners."""
    if type(source) is not SourceVisibilityProducer:
        raise TypeError("actual source producer required")
    pub = source.published_snapshot_for_revision(revision_id)
    if pub is None:
        raise ValueError("current original source revision required")
    result = dict(status=EvidenceResolutionStatus.ABSTAINED.value,
        document_id=pub.revision.document_id, revision_id=revision_id,
        source_sha256=pub.revision.source_sha256, snapshot_id=pub.snapshot.snapshot_id,
        page_id=page_id, source_openings=[], scope_complete=False,
        host_granted=False, structural_wall_role_granted=False, metric_quantity_granted=False)
    ids = pub.raster_opening_primitive_observation_ids
    if not ids:
        return result
    selector = ObservationSelector(pub.revision.document_id, revision_id,
        pub.revision.source_sha256, pub.snapshot.snapshot_id, ids[0])
    observations = _inventory(source, pub, selector)
    authority = source.physical_opening_authority()
    addressed = {}
    for oid, observation in observations.items():
        if observation.page_id != page_id:
            continue
        address = replace(selector, observation_id=oid)
        proof = authority.prove_existence(address)
        opening = proof.existence_record
        if (proof.status is EvidenceResolutionStatus.CORROBORATED
                and proof.proposition == PHYSICAL_OPENING_EXISTS and opening is not None):
            previous = addressed.get(opening.record_id)
            if previous is not None and previous[0] != opening:
                raise RuntimeError("original terminal opening inventory conflict")
            addressed.setdefault(opening.record_id, (opening, address))
    for rid, (opening, address) in sorted(addressed.items()):
        row = build_g17_terminal_flank_source_shadow(source, address)
        if row["physical_opening_id"] != rid:
            raise RuntimeError("original terminal opening address changed")
        result["source_openings"].append(row)
    if (source.published_snapshot_for_revision(revision_id) != pub
            or _inventory(source, pub, selector) != observations):
        raise RuntimeError("original terminal page source changed during read")
    return result
