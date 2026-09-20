"""Diagnostic-only Item 35 authority execution for the live PDF extractor.

This module makes the source-authenticated Item 35 chain execute on production
PDF bytes without changing any commercial prediction.  It intentionally
reports the current fail-closed state:

source PDF bytes
-> SourceVisibilityProducer
-> SemanticOpeningEnumerationAuthority
-> semantic inventory completeness adapter
-> GenericOpeningCountAuthority diagnostic resolve

The semantic completeness adapter is intentionally unsealed until a stronger
authority proves exhaustive physical-opening-universe coverage, so commercial
count publication remains blocked.  This module must never modify extractor
predictions, benchmark gold, or expected quantities.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from pb_generic_opening_count_authority import (
    GenericOpeningCountProducer,
    GenericOpeningCountSelector,
)
from pb_opening_universe_completeness_source_adapter import (
    build_semantic_opening_inventory_completeness,
)
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_semantic_opening_enumeration_authority import (
    SemanticOpeningEnumerationProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_view_class_authority import ViewportViewClassProducer


ITEM35_PRODUCTION_SHADOW_SCHEMA_VERSION = "1.1.0"


def empty_item35_authority_shadow(*, reason: str) -> dict[str, Any]:
    return {
        "schema_version": ITEM35_PRODUCTION_SHADOW_SCHEMA_VERSION,
        "status": "abstained",
        "reason": str(reason or "unavailable"),
        "document_id": None,
        "revision_id": None,
        "source_sha256": None,
        "snapshot_id": None,
        "visible_observation_count": 0,
        "semantic_opening_count": 0,
        "support_observation_count": 0,
        "residual_visible_observation_count": 0,
        "structural_enumeration_complete": False,
        "physical_opening_universe_complete": False,
        "semantic_reason_codes": [],
        "semantic_record_id": None,
        "semantic_opening_record_ids": [],
        "representative_observation_ids": [],
        "generic_count_status": "abstained",
        "generic_count_reason_codes": [],
        "commercial_count_unlocked": False,
    }


def collect_item35_authority_shadow(
    pdf_path: Path | str,
    *,
    document_id: str | None = None,
) -> dict[str, Any]:
    """Execute Item 35 authority infrastructure without publishing quantities."""

    path = Path(pdf_path)
    if not path.exists() or not path.is_file():
        return empty_item35_authority_shadow(reason="source_unavailable")

    payload = path.read_bytes()
    if not payload:
        return empty_item35_authority_shadow(reason="source_unavailable")

    doc_id = str(document_id or f"file:{path.name}").strip()
    if not doc_id:
        return empty_item35_authority_shadow(reason="document_id_unavailable")

    source = SourceVisibilityProducer(
        producer_method="planreader_live_item35_shadow",
        producer_version=ITEM35_PRODUCTION_SHADOW_SCHEMA_VERSION,
    )
    published = source.ingest_native_pdf_bytes(
        document_id=doc_id,
        source_bytes=payload,
        source_locator=str(path),
    )
    published = source.augment_with_raster_visible_segments(
        published.revision.revision_id
    )

    semantic_producer = (
        SemanticOpeningEnumerationProducer.from_source_visibility_producer(source)
    )
    decision_scope_id = f"item35:document:{published.revision.revision_id}"
    semantic = semantic_producer.publish_document_scope(
        revision_id=published.revision.revision_id,
        decision_scope_id=decision_scope_id,
    )

    shadow = empty_item35_authority_shadow(reason="semantic_inventory_unavailable")
    shadow.update(
        {
            "document_id": published.revision.document_id,
            "revision_id": published.revision.revision_id,
            "source_sha256": published.revision.source_sha256,
            "snapshot_id": published.snapshot.snapshot_id,
            "visible_observation_count": len(published.visible_observation_ids),
        }
    )

    if semantic.record is not None:
        record = semantic.record
        shadow.update(
            {
                "status": (
                    "conflict"
                    if str(semantic.status.value) == "conflict"
                    else "evidence_present"
                ),
                "reason": "semantic_inventory_resolved",
                "semantic_opening_count": len(record.physical_opening_record_ids),
                "support_observation_count": len(
                    record.opening_support_observation_ids
                ),
                "residual_visible_observation_count": len(
                    record.residual_visible_observation_ids
                ),
                "structural_enumeration_complete": bool(
                    record.structural_enumeration_complete
                ),
                "physical_opening_universe_complete": bool(
                    record.physical_opening_universe_complete
                ),
                "semantic_reason_codes": list(record.reason_codes),
                "semantic_record_id": record.record_id,
                "semantic_opening_record_ids": list(
                    record.physical_opening_record_ids
                ),
                "representative_observation_ids": list(
                    record.representative_observation_ids
                ),
            }
        )
    else:
        shadow["semantic_reason_codes"] = list(semantic.reason_codes)

    # Exercise the commercial count gate against the same real source-derived
    # evidence. The semantic adapter intentionally remains commercially
    # unsealed today, so the expected safe outcome is ABSTAINED.
    completeness = build_semantic_opening_inventory_completeness(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        decision_scope_id=decision_scope_id,
        optional_content_known_visible=False,
    )
    generic = GenericOpeningCountProducer.from_authorities(
        opening_universe_authority=completeness,
        physical_opening_authority=PhysicalOpeningAuthority(source.authority()),
        viewport_view_class_authority=ViewportViewClassProducer.create().authority(),
    )
    generic_result = generic.publish(
        GenericOpeningCountSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            decision_scope_id=decision_scope_id,
        )
    )
    shadow["generic_count_status"] = str(generic_result.status.value)
    shadow["generic_count_reason_codes"] = list(generic_result.reason_codes)
    shadow["commercial_count_unlocked"] = bool(generic_result.record is not None)
    return shadow


__all__ = [
    "ITEM35_PRODUCTION_SHADOW_SCHEMA_VERSION",
    "collect_item35_authority_shadow",
    "empty_item35_authority_shadow",
]
