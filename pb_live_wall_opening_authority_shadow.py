"""Extractor diagnostic shadow for the source-owned WALL -> OPENING chain.

This module executes the production authority composition against immutable PDF
bytes and serializes lineage/status only. It never mutates extractor
predictions, never supplies caller-authored geometry or completeness claims,
and never unlocks commercial publication.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from pb_live_wall_opening_authority_composition import (
    LiveWallOpeningAuthorityComposition,
    compose_live_wall_opening_authority,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer


SHADOW_SCHEMA_VERSION = "1.0.0"
PHYSICAL_OPENING_VOID_NOT_COMPOSED = "live_physical_opening_void_not_composed"


def empty_wall_opening_authority_shadow(*, reason: str = "not_collected") -> dict[str, Any]:
    return {
        "schema_version": SHADOW_SCHEMA_VERSION,
        "status": "abstained",
        "reason": str(reason),
        "first_causal_failure": None,
        "stages": [],
    }


def _status(value: EvidenceResolutionStatus) -> str:
    return str(value.value)


def _lineage(*, document_id: str, revision_id: str, source_sha256: str, snapshot_id: str, page_id: str | None = None) -> dict[str, str]:
    result = {
        "document_id": document_id,
        "revision_id": revision_id,
        "source_sha256": source_sha256,
        "snapshot_id": snapshot_id,
    }
    if page_id is not None:
        result["page_id"] = str(page_id)
    return result


def _stage(
    *,
    file: str,
    function: str,
    status: str,
    reason_codes: Sequence[str],
    record_id: str | None,
    input_lineage: dict[str, str],
    output_lineage: dict[str, str],
    record_present: bool | None = None,
) -> dict[str, Any]:
    return {
        "FILE": file,
        "CLASS/FUNCTION": function,
        "STATUS": status,
        "REASON_CODES": tuple(dict.fromkeys(str(code) for code in reason_codes if str(code))),
        "RECORD PRESENT": bool(record_id) if record_present is None else bool(record_present),
        "RECORD ID": record_id,
        "INPUT LINEAGE": dict(input_lineage),
        "OUTPUT LINEAGE": dict(output_lineage),
    }


def _serialize_composition(
    composition: LiveWallOpeningAuthorityComposition,
    *,
    document_id: str,
    source_sha256: str,
    snapshot_id: str,
) -> dict[str, Any]:
    root_lineage = _lineage(
        document_id=document_id,
        revision_id=composition.revision_id,
        source_sha256=source_sha256,
        snapshot_id=snapshot_id,
    )
    stages: list[dict[str, Any]] = []

    semantic = composition.semantic_enumeration_result
    semantic_record = semantic.record
    stages.append(
        _stage(
            file="pb_semantic_opening_enumeration_authority.py",
            function="SemanticOpeningEnumerationProducer.publish_page_scope",
            status=_status(semantic.status),
            reason_codes=semantic.reason_codes,
            record_id=semantic_record.record_id if semantic_record is not None else None,
            input_lineage=root_lineage,
            output_lineage=root_lineage,
        )
    )

    universe = composition.opening_universe_result
    universe_record = universe.record
    stages.append(
        _stage(
            file="pb_opening_universe_completeness_source_adapter.py",
            function="build_semantic_opening_inventory_completeness",
            status=_status(universe.status),
            reason_codes=universe.reason_codes,
            record_id=universe_record.record_id if universe_record is not None else None,
            input_lineage=root_lineage,
            output_lineage=root_lineage,
            record_present=(
                universe_record is not None
                and bool(universe.decision_scope_complete)
            ),
        )
    )

    for trace in composition.wall_scopes:
        lineage = _lineage(
            document_id=document_id,
            revision_id=composition.revision_id,
            source_sha256=source_sha256,
            snapshot_id=snapshot_id,
            page_id=trace.page_id,
        )
        stages.append(
            _stage(
                file="pb_physical_wall_candidate_authority.py",
                function="PhysicalWallCandidateAuthority.resolve_scope",
                status=_status(trace.status),
                reason_codes=trace.reason_codes,
                record_id=(trace.wall_candidate_ids[0] if len(trace.wall_candidate_ids) == 1 else None),
                input_lineage=lineage,
                output_lineage=lineage,
                record_present=bool(trace.scope_complete and trace.wall_candidate_ids),
            )
        )

    if semantic_record is not None:
        for opening_id, observation_id in zip(
            semantic_record.physical_opening_record_ids,
            semantic_record.representative_observation_ids,
        ):
            stages.append(
                _stage(
                    file="pb_physical_opening_authority.py",
                    function="PhysicalOpeningAuthority.prove_existence",
                    status=EvidenceResolutionStatus.CORROBORATED.value,
                    reason_codes=("physical_opening_exists",),
                    record_id=opening_id,
                    input_lineage={**root_lineage, "observation_id": observation_id},
                    output_lineage=root_lineage,
                )
            )

    for trace in composition.opening_bindings:
        page_lineage = _lineage(
            document_id=document_id,
            revision_id=composition.revision_id,
            source_sha256=source_sha256,
            snapshot_id=snapshot_id,
            page_id=trace.page_id,
        ) if trace.page_id is not None else root_lineage
        stages.append(
            _stage(
                file="pb_opening_host_binding_authority.py",
                function="OpeningHostBindingProducer.publish",
                status=_status(trace.status),
                reason_codes=trace.reason_codes,
                record_id=trace.record_id,
                input_lineage={
                    **page_lineage,
                    "opening_identity_id": str(trace.opening_identity_id or ""),
                },
                output_lineage={
                    **page_lineage,
                    "host_wall_id": str(trace.host_wall_id or ""),
                },
            )
        )

    for trace in composition.host_frames:
        stages.append(
            _stage(
                file="pb_opening_host_frame_authority.py",
                function="OpeningHostFrameProducer.publish",
                status=_status(trace.status),
                reason_codes=trace.reason_codes,
                record_id=trace.record_id,
                input_lineage={
                    **root_lineage,
                    "opening_identity_id": trace.opening_identity_id,
                },
                output_lineage={
                    **root_lineage,
                    "host_wall_id": str(trace.host_wall_id or ""),
                },
            )
        )

    stages.append(
        _stage(
            file="pb_physical_opening_void_authority.py",
            function="PhysicalOpeningVoidProducer.publish",
            status="not_composed",
            reason_codes=(PHYSICAL_OPENING_VOID_NOT_COMPOSED,),
            record_id=None,
            input_lineage=root_lineage,
            output_lineage=root_lineage,
            record_present=False,
        )
    )

    first_failure = next(
        (
            stage
            for stage in stages
            if stage["STATUS"] not in {
                EvidenceResolutionStatus.CORROBORATED.value,
            }
            or not stage["RECORD PRESENT"]
        ),
        None,
    )
    return {
        "schema_version": SHADOW_SCHEMA_VERSION,
        "status": _status(composition.status),
        "reason_codes": tuple(composition.reason_codes),
        "page_ids": tuple(composition.page_ids),
        "first_causal_failure": first_failure,
        "stages": stages,
    }


def collect_live_wall_opening_authority_shadow(
    pdf_path: Path | str,
    *,
    document_id: str,
    page_indexes: Sequence[int],
) -> dict[str, Any]:
    """Execute the source-owned wall/opening composition without publication."""
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    cleaned_indexes = tuple(sorted({int(index) for index in page_indexes if int(index) >= 0}))
    if not cleaned_indexes:
        return empty_wall_opening_authority_shadow(reason="no_selected_drawing_pages")

    source = SourceVisibilityProducer(
        producer_method="live_wall_opening_authority_shadow",
        producer_version=SHADOW_SCHEMA_VERSION,
    )
    published = source.ingest_native_pdf_bytes(
        document_id=str(document_id),
        source_bytes=path.read_bytes(),
        source_locator=str(path),
    )
    valid_indexes = tuple(
        index for index in cleaned_indexes if index < int(published.coverage.total_pages)
    )
    if not valid_indexes:
        return empty_wall_opening_authority_shadow(reason="selected_pages_out_of_range")

    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=tuple(str(index + 1) for index in valid_indexes),
    )
    return _serialize_composition(
        composition,
        document_id=published.revision.document_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
    )


__all__ = [
    "PHYSICAL_OPENING_VOID_NOT_COMPOSED",
    "SHADOW_SCHEMA_VERSION",
    "collect_live_wall_opening_authority_shadow",
    "empty_wall_opening_authority_shadow",
]
