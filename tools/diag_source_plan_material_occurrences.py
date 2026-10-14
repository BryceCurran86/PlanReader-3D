"""Replay source-owned bounded material marks without physical-floor promotion."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import fitz
import pb_source_material_semantic_authority as material_module

from pb_cross_view_floor_finish_authority import _occurrences_on_page
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_material_semantic_authority import (
    SourceMaterialDefinitionSelector,
    SourceMaterialSemanticProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import segment_source_page_viewports
from tools.diag_source_owned_physical_plan_view import _signature


def replay(data: bytes, *, page_number: int, raster_supports: bool = False):
    """All prediction inputs are original bytes and an explicit source page."""
    sha = hashlib.sha256(data).hexdigest()
    source = SourceVisibilityProducer(
        producer_method="live-source-plan-material-shadow", producer_version="1"
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{sha[:32]}",
        source_bytes=data,
        source_locator="memory://original-source.pdf",
        page_ids=(str(page_number),),
    )
    if raster_supports:
        published = source.augment_with_raster_opening_primitives(
            published.revision.revision_id, page_ids=(str(page_number),)
        )
    revision = published.revision.revision_id
    ordinary_views_before = segment_source_page_viewports(
        source, revision_id=revision, page_id=str(page_number)
    )
    native_recovery = []
    original_recover = material_module._recover_native_material_block
    phase = "ordinary"

    def observed_recovery(**kwargs):
        recovered = original_recover(**kwargs)
        if kwargs["source"] is source and recovered:
            candidate = material_module._material_definition_candidate(
                kwargs["block_words"]
            )
            native_recovery.append(
                {
                    "phase": phase,
                    "page_id": recovered[0].page_id,
                    "source_partition_id": recovered[0].source_partition_id,
                    "block_no": recovered[0].block_no,
                    "candidate_code": candidate[0] if candidate else "",
                    "word_count": len(recovered),
                    "trusted_word_count": sum(w.trusted for w in recovered),
                    "unresolved_words": [asdict(w) for w in recovered if not w.trusted],
                }
            )
        return recovered

    # A read-only observer: delegate exactly once, return the original result,
    # restore even on failure. No receipt, cache or decision is substituted.
    material_module._recover_native_material_block = observed_recovery
    try:
        default = SourceMaterialSemanticProducer.from_source_visibility_producer(source)
        default_authority = default.publish(revision)
        default_scopes_before = default.published_occurrence_results()
        phase = "physical_plan_shadow"
        producer = SourceMaterialSemanticProducer.for_physical_plan_view_shadow(
            source, page_ids=(str(page_number),)
        )
        authority = producer.publish(revision)
    finally:
        material_module._recover_native_material_block = original_recover
    views = producer.published_plan_viewports()
    scopes = producer.published_occurrence_results()
    records = tuple(record for scope in scopes for record in scope.records)
    assert source.published_snapshot_for_revision(revision) == published
    assert _signature(
        segment_source_page_viewports(
            source, revision_id=revision, page_id=str(page_number)
        )
    ) == _signature(ordinary_views_before)
    assert default.published_occurrence_results() == default_scopes_before
    definition_checks = []
    nominated_definition_checks = {}
    codes = {record.code for record in records} | {
        r["candidate_code"] for r in native_recovery if r["candidate_code"]
    }
    for code in sorted(codes):
        selector = SourceMaterialDefinitionSelector(
            published.revision.document_id,
            revision,
            sha,
            published.snapshot.snapshot_id,
            code,
        )
        baseline = default_authority.resolve_definition(selector)
        actual = authority.resolve_definition(selector)
        assert actual == baseline
        nominated_definition_checks[code] = asdict(actual)
        if any(record.code == code for record in records):
            assert (
                actual.status is EvidenceResolutionStatus.CORROBORATED
                and actual.record is not None
            )
            definition_checks.append(asdict(actual))
    by_id = {view.view_id: view for view in views}
    for scope in scopes:
        for record in scope.records:
            view = by_id[record.viewport_id]
            assert (
                scope.source_viewport_ownership_id
                and record.source_text_observation_ids
            )
            assert fitz.Rect(view.bounding_box).contains(fitz.Rect(record.bbox_pdf_pts))
            assert (
                record.document_id,
                record.revision_id,
                record.source_sha256,
                record.snapshot_id,
            ) == (
                published.revision.document_id,
                revision,
                sha,
                published.snapshot.snapshot_id,
            )
        if not scope.scope_complete:
            assert scope.status is EvidenceResolutionStatus.ABSTAINED
    incomplete_scopes = tuple(scope for scope in scopes if not scope.scope_complete)
    assert _occurrences_on_page(incomplete_scopes, page_id=str(page_number)) == ()
    serialized_views = []
    for view in views:
        raw = asdict(view)
        raw.pop("_producer_token")
        raw.pop("_producer_fingerprint")
        assert raw["provenance"]["metric_authority_granted"] is False
        assert raw["provenance"]["whole_sheet_plan_universe_proven"] is False
        serialized_views.append(raw)
    return {
        "source_sha256": sha,
        "page_number": page_number,
        "revision_id": revision,
        "snapshot_id": published.snapshot.snapshot_id,
        "source_owned_plan_views": serialized_views,
        "material_occurrence_scopes": [asdict(scope) for scope in scopes],
        "fixed_original_text_corroboration_results": [
            asdict(r) for r in producer.published_plan_text_corroboration_results()
        ],
        "unchanged_authenticated_definition_checks": definition_checks,
        "unchanged_nominated_definition_results": nominated_definition_checks,
        "original_native_material_block_recovery": native_recovery,
        "default_occurrence_results_unchanged": True,
        "default_segmentation_unchanged": True,
        "published_snapshot_unchanged": True,
        "incomplete_scopes_rejected_by_existing_floor_consumer": True,
        "bounded_plan_view_count": len(views),
        "positive_material_occurrence_count": len(records),
        "scope_complete_count": sum(scope.scope_complete for scope in scopes),
        "whole_sheet_plan_universe_proven": False,
        "physical_floor_identity_granted": False,
        "metric_authority_granted": False,
        "commercial_projection_allowed": False,
        "published_quantities": [],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raster-supports", action="store_true")
    args = parser.parse_args()
    result = replay(
        args.pdf.read_bytes(),
        page_number=args.page,
        raster_supports=args.raster_supports,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2))
    print(
        json.dumps({k: v for k, v in result.items() if not isinstance(v, (list, dict))})
    )


if __name__ == "__main__":
    main()
