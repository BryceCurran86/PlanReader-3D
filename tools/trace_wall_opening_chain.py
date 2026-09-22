from __future__ import annotations

import argparse
import json
from pathlib import Path

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_host_binding_authority import (
    OpeningHostBindingProducer,
    OpeningHostWallUniverseProducer,
    OpeningHostWallUniverseSelector,
)
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
    _PRODUCER_SEAL as WALL_PRODUCER_SEAL,
    _ScopeKey,
    _build_scope_result,
    _decision_scope_id,
)
from pb_semantic_opening_enumeration_authority import (
    SemanticOpeningEnumerationProducer,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _lineage(obj):
    if obj is None:
        return None
    keys = (
        "document_id",
        "revision_id",
        "source_sha256",
        "snapshot_id",
        "page_id",
        "decision_scope_id",
        "viewport_id",
    )
    return {key: getattr(obj, key, None) for key in keys if hasattr(obj, key)}


def _status(value):
    if isinstance(value, EvidenceResolutionStatus):
        return value.value
    return getattr(value, "value", value)


def _emit(stage, **payload):
    print(json.dumps({"stage": stage, **payload}, sort_keys=True, default=str))


def trace(pdf_path: Path, *, document_id: str, page_id: str) -> int:
    raw = pdf_path.read_bytes()
    source = SourceVisibilityProducer(
        producer_method="wall-opening-live-trace-v1",
        producer_version="1",
    )
    ingested = source.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=raw,
        source_locator=str(pdf_path),
    )
    published = source.published_snapshot_for_revision(ingested.revision.revision_id)
    if published is None:
        _emit("source_evidence", status="abstained", reason_codes=["snapshot_unavailable"])
        return 2

    _emit(
        "source_evidence",
        status="corroborated",
        reason_codes=[],
        record_present=True,
        record_id=published.snapshot.snapshot_id,
        input_lineage=None,
        output_lineage={
            "document_id": published.revision.document_id,
            "revision_id": published.revision.revision_id,
            "source_sha256": published.revision.source_sha256,
            "snapshot_id": published.snapshot.snapshot_id,
            "page_id": page_id,
        },
        visible_observation_count=len(published.visible_observation_ids),
        coverage_state=str(published.coverage.state),
    )

    scope_id = _decision_scope_id(page_id)
    # Diagnostic-only exact-page construction: preserve the registered source
    # bytes/SHA and use the production page builder, but do not build wall
    # candidates for unrelated pages in this trace job.
    wall_scope = _build_scope_result(
        source_producer=source,
        published=published,
        source_bytes=raw,
        page_id=page_id,
    )
    wall_key = _ScopeKey(
        document_id=wall_scope.document_id,
        revision_id=wall_scope.revision_id,
        source_sha256=wall_scope.source_sha256,
        snapshot_id=wall_scope.snapshot_id,
        page_id=wall_scope.page_id,
        decision_scope_id=wall_scope.decision_scope_id,
    )
    wall_producer = PhysicalWallCandidateProducer(
        {wall_key: wall_scope},
        _seal=WALL_PRODUCER_SEAL,
    )
    wall_authority = wall_producer.authority()
    wall_selector = PhysicalWallCandidateSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=page_id,
        decision_scope_id=scope_id,
    )
    wall_result = wall_authority.resolve_scope(wall_selector)
    wall_records = tuple(wall_result.records or ())
    _emit(
        "physical_wall_candidate",
        file="pb_physical_wall_candidate_authority.py",
        class_function="PhysicalWallCandidateAuthority.resolve_scope",
        status=_status(wall_result.status),
        reason_codes=list(wall_result.reason_codes or ()),
        record_present=bool(wall_records),
        record_id=[r.wall_candidate_id for r in wall_records],
        input_lineage=_lineage(wall_selector),
        output_lineage=_lineage(wall_result),
        scope_complete=wall_result.scope_complete,
        wall_count=len(wall_records),
        wall_identities=[
            {
                "wall_candidate_id": r.wall_candidate_id,
                "candidate_identity_id": getattr(r.physical_identity, "candidate_identity_id", None),
                "status": _status(getattr(r.physical_identity, "status", None)),
                "source_primitive_ids": list(getattr(r.physical_identity, "source_primitive_ids", ()) or ()),
                "edge_ids": list(getattr(r.physical_identity, "edge_ids", ()) or ()),
            }
            for r in wall_records
        ],
    )

    semantic = SemanticOpeningEnumerationProducer.from_source_visibility_producer(source)
    semantic_result = semantic.publish_page_scope(
        revision_id=published.revision.revision_id,
        decision_scope_id=scope_id,
        page_ids=(page_id,),
    )
    sem_record = semantic_result.record
    _emit(
        "physical_opening",
        file="pb_semantic_opening_enumeration_authority.py + pb_physical_opening_authority.py",
        class_function="SemanticOpeningEnumerationProducer.publish_page_scope",
        status=_status(semantic_result.status),
        reason_codes=list(semantic_result.reason_codes or ()),
        record_present=sem_record is not None,
        record_id=getattr(sem_record, "record_id", None),
        input_lineage={
            "document_id": published.revision.document_id,
            "revision_id": published.revision.revision_id,
            "source_sha256": published.revision.source_sha256,
            "snapshot_id": published.snapshot.snapshot_id,
            "page_id": page_id,
            "decision_scope_id": scope_id,
        },
        output_lineage=_lineage(sem_record),
        structural_enumeration_complete=getattr(sem_record, "structural_enumeration_complete", None),
        physical_opening_universe_complete=getattr(sem_record, "physical_opening_universe_complete", None),
        physical_opening_record_ids=list(getattr(sem_record, "physical_opening_record_ids", ()) or ()),
        representative_observation_ids=list(getattr(sem_record, "representative_observation_ids", ()) or ()),
        residual_visible_observation_count=len(getattr(sem_record, "residual_visible_observation_ids", ()) or ()),
        conflict_observation_count=len(getattr(sem_record, "conflict_observation_ids", ()) or ()),
    )

    physical = PhysicalOpeningAuthority(source.authority())
    host_universe = OpeningHostWallUniverseProducer.from_physical_wall_candidate_authority(
        wall_authority
    ).authority()
    host_universe_selector = OpeningHostWallUniverseSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=page_id,
        decision_scope_id=scope_id,
    )
    host_universe_result = host_universe.resolve_scope(host_universe_selector)
    _emit(
        "physical_wall_identity",
        file="pb_opening_host_binding_authority.py",
        class_function="OpeningHostWallUniverseAuthority.resolve_scope",
        status=_status(host_universe_result.status),
        reason_codes=list(host_universe_result.reason_codes or ()),
        record_present=bool(host_universe_result.records),
        record_id=[r.wall_candidate_id for r in tuple(host_universe_result.records or ())],
        input_lineage=_lineage(host_universe_selector),
        output_lineage=_lineage(host_universe_result),
        scope_complete=host_universe_result.scope_complete,
        wall_count=len(tuple(host_universe_result.records or ())),
    )

    if sem_record is None:
        _emit(
            "opening_host_binding",
            file="pb_opening_host_binding_authority.py",
            class_function="OpeningHostBindingProducer.publish",
            status="abstained",
            reason_codes=["semantic_opening_inventory_unavailable"],
            record_present=False,
            record_id=None,
            input_lineage=_lineage(host_universe_selector),
            output_lineage=None,
        )
        return 0

    host_producer = OpeningHostBindingProducer.from_authorities(
        physical_opening_authority=physical,
        host_wall_universe_authority=host_universe,
    )
    pairs = list(
        zip(
            sem_record.physical_opening_record_ids,
            sem_record.representative_observation_ids,
            strict=True,
        )
    )
    if not pairs:
        _emit(
            "opening_host_binding",
            file="pb_opening_host_binding_authority.py",
            class_function="OpeningHostBindingProducer.publish",
            status="abstained",
            reason_codes=["no_physical_openings_in_semantic_inventory"],
            record_present=False,
            record_id=None,
            input_lineage=_lineage(host_universe_selector),
            output_lineage=None,
        )
        return 0

    for opening_record_id, observation_id in pairs:
        obs_selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        existence = physical.prove_existence(obs_selector)
        _emit(
            "physical_opening_identity",
            file="pb_physical_opening_authority.py",
            class_function="PhysicalOpeningAuthority.prove_existence",
            status=_status(existence.status),
            reason_codes=list(existence.reason_codes or ()),
            record_present=existence.existence_record is not None,
            record_id=getattr(existence.existence_record, "record_id", None),
            input_lineage={
                "document_id": obs_selector.document_id,
                "revision_id": obs_selector.revision_id,
                "source_sha256": obs_selector.source_sha256,
                "snapshot_id": obs_selector.snapshot_id,
                "page_id": page_id,
                "decision_scope_id": scope_id,
                "observation_id": observation_id,
            },
            output_lineage=_lineage(existence.existence_record),
            semantic_inventory_record_id=opening_record_id,
        )
        binding = host_producer.publish(
            opening_left_selector=obs_selector,
            opening_right_selector=obs_selector,
            host_universe_selector=host_universe_selector,
        )
        _emit(
            "opening_host_binding",
            file="pb_opening_host_binding_authority.py",
            class_function="OpeningHostBindingProducer.publish",
            status=_status(binding.status),
            reason_codes=list(binding.reason_codes or ()),
            record_present=binding.record is not None,
            record_id=getattr(binding.record, "record_id", None),
            input_lineage={
                "document_id": obs_selector.document_id,
                "revision_id": obs_selector.revision_id,
                "source_sha256": obs_selector.source_sha256,
                "snapshot_id": obs_selector.snapshot_id,
                "page_id": page_id,
                "decision_scope_id": scope_id,
                "opening_identity_id": opening_record_id,
                "observation_id": observation_id,
            },
            output_lineage=_lineage(binding.record),
            host_wall_id=getattr(binding.record, "host_wall_id", None),
            member_wall_candidate_ids=list(
                getattr(binding.record, "member_wall_candidate_ids", ()) or ()
            ),
        )

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--page-id", required=True)
    args = parser.parse_args()
    return trace(args.pdf, document_id=args.document_id, page_id=args.page_id)


if __name__ == "__main__":
    raise SystemExit(main())
