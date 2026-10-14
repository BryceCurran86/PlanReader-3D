"""Fresh source-only raster flank / full-page paint comparison; never a host."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
import math
from pathlib import Path

import cv2
import fitz
import numpy as np

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_opening_host_binding_authority import _opening_geometry
from pb_physical_wall_candidate_authority import MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS
from pb_raster_opening_source_primitives import MASS_THRESHOLD
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from tools.diag_gptmax_raster_host_source_membership import nonpublishing_g17_support_receipts
from tools.diag_gptmax_required_flank_source import _reported_flanks


from pb_raster_g17_source_shadow import pixel_paint_profile


def _finite_box(box) -> tuple[float, ...]:
    if (len(box) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in box)
            or box[2] < box[0] or box[3] < box[1]):
        raise ValueError("invalid original paint bounds")
    return tuple(float(v) for v in box)


def intersecting_paint_commands(commands, query_box) -> list[dict]:
    """Retain every intersecting conservative renderer bound, never a cause."""
    q = _finite_box(query_box)
    if len(commands) > MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS:
        raise ValueError("paint command inventory exceeds unchanged safety cap")
    seen, rows = set(), []
    for command in commands:
        seq = command["seqno"]
        if type(seq) is not int or seq < 0 or seq in seen:
            raise ValueError("invalid or duplicate original paint command address")
        seen.add(seq)
        b = _finite_box(command["rendered_paint_bounds_pt"])
        if min(q[2], b[2]) > max(q[0], b[0]) and min(q[3], b[3]) > max(q[1], b[1]):
            # JSON copy avoids handing out mutable caller-owned graphic state.
            row = json.loads(json.dumps(command, allow_nan=False))
            rows.append({**row, "rendered_bounds_intersect_query": True,
                         "paint_causality_proven": False, "native_paint_role_authenticated": False,
                         "host_publication_allowed": False})
    return sorted(rows, key=lambda r: r["seqno"])


def _literal(value):
    if isinstance(value, (fitz.Point, fitz.Rect, fitz.Quad, tuple, list)):
        return [_literal(v) for v in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise ValueError("unsupported literal native graphic state")


def original_paint_commands(page) -> list[dict]:
    """Sequence-addressed original renderer bounds, including thin strokes."""
    drawings = {}
    for path_index, drawing in enumerate(page.get_drawings()):
        seq = drawing.get("seqno")
        if type(seq) is not int or seq in drawings:
            raise ValueError("unavailable or duplicate original path sequence")
        drawings[seq] = {"path_index": path_index, **{
            k: _literal(drawing[k]) for k in ("rect", "items", "type", "color", "fill", "width",
                "stroke_opacity", "fill_opacity", "dashes", "lineCap", "lineJoin", "layer") if k in drawing}}
    bounds_log = page.get_bboxlog()
    if max(len(drawings), len(bounds_log)) > MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS:
        raise ValueError("paint command inventory exceeds unchanged safety cap")
    return [{"seqno": seq, "original_paint_kind": kind,
             "rendered_paint_bounds_pt": list(_finite_box(bounds)),
             "literal_native_path": drawings.get(seq)}
            for seq, (kind, bounds) in enumerate(bounds_log)]


def _flank_box(opening, flank, dpi: int):
    points = [tuple(opening.origin[i]+along*opening.axis[i]+cross*opening.normal[i] for i in (0, 1))
              for along in flank["axis_span_pt"] for cross in flank["normal_span_pt"]]
    bounds = [min(p[0] for p in points), min(p[1] for p in points),
              max(p[0] for p in points), max(p[1] for p in points)]
    pixels = [v*dpi/72 for v in bounds]
    if any(not math.isclose(v, round(v), rel_tol=0, abs_tol=1e-6) for v in pixels):
        raise ValueError("authenticated flank not on original pixel grid")
    if abs(opening.axis[0]) == 1 and opening.axis[1] == 0:
        orientation = "horizontal"
    elif abs(opening.axis[1]) == 1 and opening.axis[0] == 0:
        orientation = "vertical"
    else:
        raise ValueError("authenticated flank axis unavailable")
    return [int(round(v)) for v in pixels], orientation


def original_flank_paint_report(source_bytes: bytes, *, page_id: str, expected_source_sha: str) -> dict:
    digest = sha256(source_bytes).hexdigest()
    if digest != expected_source_sha:
        raise ValueError("original PDF SHA mismatch")
    if not isinstance(page_id, str) or not page_id.isdigit() or int(page_id) < 1:
        raise ValueError("invalid source page")
    producer = SourceVisibilityProducer(producer_method="live-physical-net-wall",
                                       producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION)
    published = producer.ingest_native_pdf_bytes(document_id=f"live-source:{digest[:32]}",
        source_bytes=source_bytes, source_locator="memory://live-physical-net-wall-source.pdf", page_ids=(page_id,))
    composition = compose_live_wall_opening_authority(source_visibility_producer=producer,
        revision_id=published.revision.revision_id, page_ids=(page_id,))
    published = producer.published_snapshot_for_revision(published.revision.revision_id)
    if published is None:
        raise ValueError("current source snapshot unavailable")
    image_png, image_parent, frame, dpi = producer.render_raster_opening_source_page(published.revision.revision_id, page_id)
    full_png, full_parent, full_frame = producer._producer.render_native_page_png(
        document_id=published.revision.document_id, revision_id=published.revision.revision_id,
        source_sha256=digest, snapshot_id=published.snapshot.snapshot_id, page_id=page_id,
        dpi=dpi, include_native_frame=True, images_only=False)
    if image_parent != full_parent or frame != full_frame or frame.rotation != 0:
        raise ValueError("matched native render frame/parent unavailable")
    def rgb(png):
        decoded = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR)
        if decoded is None:
            raise ValueError("source render unavailable")
        return cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)
    image, full = rgb(image_png), rgb(full_png)
    if image.shape != full.shape:
        raise ValueError("source render extents mismatch")
    with fitz.open(stream=source_bytes, filetype="pdf") as pdf:
        commands = original_paint_commands(pdf[int(page_id)-1])
    scope = {"source_sha256": digest, "document_id": published.revision.document_id,
             "revision_id": published.revision.revision_id, "snapshot_id": published.snapshot.snapshot_id,
             "page_id": page_id}
    authority, rows = composition.physical_opening_authority, []
    for trace in composition.opening_bindings:
        if trace.host_wall_id or trace.page_id != page_id or not any("raster_source_band_" in r for r in trace.reason_codes):
            continue
        resolved = authority.prove_existence(ObservationSelector(**{k: scope[k] for k in
            ("document_id", "revision_id", "source_sha256", "snapshot_id")},
            observation_id=trace.representative_observation_id))
        opening = resolved.existence_record
        if resolved.status is not EvidenceResolutionStatus.CORROBORATED or opening is None:
            raise ValueError("current G17 existence unavailable")
        geometry = _opening_geometry(authority, opening)
        if geometry is None:
            raise ValueError("current sealed aperture geometry unavailable")
        support = nonpublishing_g17_support_receipts(authority, opening, geometry)
        for receipt in support:
            if (not receipt["source_receipt_authenticated"] or sha256(image_png).hexdigest() not in receipt["source_primitive_ref"]
                    or len(receipt["derivation_parent_ids"]) != 1):
                raise ValueError("G17 support does not own current source render")
            # Visible primitive -> raw raster primitive -> native page. The
            # immediate parent is deliberately NOT the native page itself.
            parent_result = producer._producer.authority().resolve(ObservationSelector(
                **{k: scope[k] for k in ("document_id", "revision_id", "source_sha256", "snapshot_id")},
                observation_id=receipt["derivation_parent_ids"][0]))
            parent = parent_result.observation
            if (parent_result.status is not EvidenceResolutionStatus.CORROBORATED or parent is None
                    or parent.page_id != page_id or parent.viewport_id is not None
                    or parent.source_partition_id != image_parent.source_partition_id
                    or parent.derivation_parent_ids != (image_parent.observation_id,)
                    or parent.source_primitive_ref != receipt["source_primitive_ref"].removeprefix("visible:")
                    or tuple(parent.geometry) != tuple(receipt["original_source_support_geometry_pt"])):
                raise ValueError("G17 raw primitive page/render ancestry mismatch")
            receipt["raw_raster_primitive_parent_payload_sha256"] = parent.observation_payload_sha256
            receipt["render_page_parent_observation_id"] = image_parent.observation_id
        flanks = _reported_flanks({"original_g17_support_receipts": support,
            "original_g17_support_observation_ids": list(opening.source_observation_ids)}, geometry, scope)
        if flanks is None:
            raise ValueError("current four-face/two-end flank proof unavailable")
        for role, flank in sorted(flanks.items()):
            box, orientation = _flank_box(geometry, flank, dpi)
            query = [box[0]*72/dpi, box[1]*72/dpi, (box[2]+1)*72/dpi, (box[3]+1)*72/dpi]
            row = {"opening_identity_id": trace.opening_identity_id, "role": role,
                   "original_binding_reason_codes": list(trace.reason_codes),
                   "original_g17_support_receipts": support, "original_flank_geometry": flank,
                   "pixel_cell_query_bbox_pt": query,
                   "paint_profile": pixel_paint_profile(image, full, box, orientation=orientation),
                   "intersecting_original_paint_commands": intersecting_paint_commands(commands, query),
                   "candidate_nomination_controlled_by_query": False,
                   "host_publication_allowed": False}
            row["audit_row_id"] = stable_contract_id("raster_flank_paint_audit", {**scope, **row})
            rows.append(row)
    if producer.published_snapshot_for_revision(published.revision.revision_id) != published:
        raise ValueError("paint audit mutated the producer snapshot")
    return {**scope, "viewport_id": None, "native_frame": asdict(frame), "render_dpi": dpi,
            "image_render_sha256": sha256(image_png).hexdigest(), "full_render_sha256": sha256(full_png).hexdigest(),
            "native_page_parent_observation_id": image_parent.observation_id,
            "original_pdf_reauthenticated": True, "producer_snapshot_unchanged": True,
            "primitive_safety_cap": MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS,
            "original_paint_command_count": len(commands), "rows": sorted(rows, key=lambda r: (r["opening_identity_id"], r["role"])),
            "opening_bindings": [asdict(t) for t in composition.opening_bindings],
            "host_frames": [asdict(t) for t in composition.host_frames],
            "source_universe_completeness_proven": False, "native_paint_role_authenticated": False,
            "physical_equivalence_proven": False, "host_publication_allowed": False,
            "opening_count_publication_allowed": False, "metric_quantity_publication_allowed": False,
            "benchmark_accuracy": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page-id", required=True)
    parser.add_argument("--expected-source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = original_flank_paint_report(args.pdf.read_bytes(), page_id=args.page_id, expected_source_sha=args.expected_source_sha)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False, default=lambda v: v.value)+"\n")
    print(json.dumps({"source_sha256": result["source_sha256"], "queried_flanks": len(result["rows"]),
                      "host_publication_allowed": False}))


if __name__ == "__main__":
    main()
