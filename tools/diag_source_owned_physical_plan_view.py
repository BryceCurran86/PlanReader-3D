"""Replay a bounded F.07 source-view proof from immutable original PDF bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict
from pathlib import Path

import fitz

from pb_migration_provider_envelope import ProviderContext
from pb_native_page_frame import native_page_frame
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_migration_adapter import adapt_f07_viewport_to_migration
from pb_viewport_segmentation import (
    calibrate_viewport_layout,
    extract_vector_frames,
    is_authoritative_derived_viewport,
    segment_page_viewports,
    segment_source_page_viewports,
)


def _signature(views):
    return tuple(
        (
            v.view_id,
            v.view_type,
            v.status,
            v.title_bbox,
            v.bounding_box,
            v.scale_raw,
            v.scale_denominator,
            v.provenance,
        )
        for v in views
    )


def replay(data, *, page_number, raster_supports=False):
    digest = hashlib.sha256(data).hexdigest()
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall", producer_version="1"
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{digest[:32]}",
        source_bytes=data,
        source_locator="memory://original-source-view.pdf",
        page_ids=(str(page_number),),
    )
    if raster_supports:
        # Test preparation is explicit and source-owned. The viewport reader
        # itself NEVER augments a snapshot or accepts these as caller geometry.
        published = source.augment_with_raster_opening_primitives(
            published.revision.revision_id, page_ids=(str(page_number),)
        )
    with fitz.open(stream=data, filetype="pdf") as pdf:
        page = pdf[page_number - 1]
        frame = native_page_frame(page)
        baseline = segment_page_viewports(page, page_number=page_number)
        original_frames = extract_vector_frames(page, calibrate_viewport_layout(page))
    before = published
    views = segment_source_page_viewports(
        source,
        revision_id=published.revision.revision_id,
        page_id=str(page_number),
        physical_plan_view_shadow=True,
    )
    assert (
        source.published_snapshot_for_revision(published.revision.revision_id) == before
    )
    default_after = segment_source_page_viewports(
        source, revision_id=published.revision.revision_id, page_id=str(page_number)
    )
    assert _signature(default_after) == _signature(baseline)
    owned = tuple(v.view_id for v in views)
    context = ProviderContext(
        run_id="source-view-audit",
        workspace_id="audit",
        project_id="source-only",
        document_id=published.revision.document_id,
        source_sha256=digest,
        revision_id=published.revision.revision_id,
        current_revision_id=published.revision.revision_id,
        selected_pages=(page_number - 1,),
        owned_viewport_ids=owned,
        evidence_snapshot_id=published.snapshot.snapshot_id,
        owned_page_numbers=(page_number,),
        viewport_page_ownership=tuple((v, page_number) for v in owned),
    )
    products = []
    for view in views:
        raw = asdict(view)
        raw.pop("_producer_token")
        raw.pop("_producer_fingerprint")
        authoritative = is_authoritative_derived_viewport(view)
        migration = None
        if authoritative:
            adapted = adapt_f07_viewport_to_migration(
                views, viewport_id=view.view_id, context=context, page_no=page_number
            )
            assert adapted.viewport is not None and adapted.ownership_proof is not None
            assert not adapted.blocking_reasons
            migration = {
                "viewport_id": adapted.viewport.viewport_id,
                "ownership_id": adapted.ownership_proof.ownership_id,
                "blocking_reasons": adapted.blocking_reasons,
            }
        products.append(
            dict(raw, authoritative=authoritative, downstream_migration=migration)
        )
    return {
        "source_sha256": digest,
        "page_number": page_number,
        "native_frame": asdict(frame),
        "original_source_frames": original_frames,
        "revision_id": published.revision.revision_id,
        "snapshot_id": published.snapshot.snapshot_id,
        "default_segmentation_unchanged": True,
        "published_snapshot_unchanged": True,
        "viewports": products,
        "authoritative_plan_view_count": sum(r["authoritative"] for r in products),
        "metric_authority_granted": False,
        "published_quantities": [],
        "commercial_projection_allowed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--page", required=True, type=int)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--raster-supports", action="store_true")
    args = parser.parse_args()
    report = replay(
        args.pdf.read_bytes(),
        page_number=args.page,
        raster_supports=args.raster_supports,
    )
    report["producer_head_sha"] = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "source_view_proof.json").write_text(
        json.dumps(report, indent=2)
    )
    with fitz.open(args.pdf) as pdf:
        page = pdf[args.page - 1]
        for view in report["viewports"]:
            if view["authoritative"]:
                page.draw_rect(
                    fitz.Rect(view["bounding_box"]), color=(0.0, 0.65, 0.25), width=2.0
                )
                page.draw_rect(
                    fitz.Rect(view["title_bbox"]), color=(0.65, 0.0, 0.6), width=2.0
                )
        page.get_pixmap(matrix=fitz.Matrix(0.75, 0.75), alpha=False).save(
            args.output_dir / "source_view_overlay.png"
        )
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "source_sha256",
                    "page_number",
                    "authoritative_plan_view_count",
                    "default_segmentation_unchanged",
                    "published_snapshot_unchanged",
                    "metric_authority_granted",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
