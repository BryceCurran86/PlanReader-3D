"""Trace the live source-authenticated wall/opening authority seam on a real PDF.

This is a diagnostic executable for the wall -> opening -> net-wall accuracy lane.
It never reads benchmark expected quantities and never mutates commercial outputs.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

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
)
from pb_semantic_opening_enumeration_authority import (
    SemanticOpeningEnumerationProducer,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _enum(value: Any) -> Any:
    return getattr(value, "value", value)


def _serial(value: Any) -> Any:
    if is_dataclass(value):
        return {k: _serial(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _serial(v) for k, v in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_serial(v) for v in value]
    return _enum(value)


def _record_id(record: Any) -> str | None:
    return getattr(record, "record_id", None)


def _lineage(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    fields = (
        "document_id",
        "revision_id",
        "source_sha256",
        "snapshot_id",
        "page_id",
        "decision_scope_id",
        "viewport_id",
        "opening_identity_id",
        "physical_wall_id",
        "host_wall_id",
        "wall_candidate_id",
        "candidate_identity_id",
    )
    return {
        name: _serial(getattr(obj, name))
        for name in fields
        if getattr(obj, name, None) is not None
    }


def _entry(
    *,
    file: str,
    function: str,
    status: Any,
    reason_codes: Any = (),
    record: Any = None,
    input_lineage: dict[str, Any] | None = None,
    output_lineage: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = {
        "FILE": file,
        "CLASS_FUNCTION": function,
        "STATUS": _serial(status),
        "REASON_CODES": _serial(reason_codes or ()),
        "RECORD_PRESENT": record is not None,
        "RECORD_ID": _record_id(record),
        "INPUT_LINEAGE": input_lineage or {},
        "OUTPUT_LINEAGE": output_lineage or _lineage(record),
    }
    if extra:
        out["EXTRA"] = _serial(extra)
    return out


def trace(pdf_path: Path, *, document_id: str, page_id: str) -> dict[str, Any]:
    source = SourceVisibilityProducer(
        producer_method="wall-opening-net-trace",
        producer_version="1",
    )
    source_bytes = pdf_path.read_bytes()
    published = source.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=source_bytes,
        source_locator=str(pdf_path),
    )
    scope_id = f"wall-source:page-{page_id}"

    trace_rows: list[dict[str, Any]] = []
    trace_rows.append(
        _entry(
            file="pb_source_visibility_authority.py",
            function="SourceVisibilityProducer.ingest_native_pdf_bytes",
            status=published.coverage.state,
            reason_codes=(),
            record=published.revision,
            input_lineage={"document_id": document_id, "page_id": page_id},
            output_lineage={
                "document_id": published.revision.document_id,
                "revision_id": published.revision.revision_id,
                "source_sha256": published.revision.source_sha256,
                "snapshot_id": published.snapshot.snapshot_id,
                "page_id": page_id,
            },
            extra={
                "decoded_pages": list(published.coverage.decoded_pages),
                "failed_pages": list(published.coverage.failed_pages),
                "visible_observation_count": len(published.visible_observation_ids),
                "text_observation_count": len(published.text_observation_ids),
            },
        )
    )

    wall_authority = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source
    ).authority()
    wall_selector = PhysicalWallCandidateSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=page_id,
        decision_scope_id=scope_id,
    )
    wall_result = wall_authority.resolve_scope(wall_selector)
    trace_rows.append(
        _entry(
            file="pb_physical_wall_candidate_authority.py",
            function="PhysicalWallCandidateAuthority.resolve_scope",
            status=wall_result.status,
            reason_codes=wall_result.reason_codes,
            record=None,
            input_lineage=_lineage(wall_selector),
            output_lineage={
                "document_id": wall_result.document_id,
                "revision_id": wall_result.revision_id,
                "source_sha256": wall_result.source_sha256,
                "snapshot_id": wall_result.snapshot_id,
                "page_id": wall_result.page_id,
                "decision_scope_id": wall_result.decision_scope_id,
            },
            extra={
                "scope_complete": wall_result.scope_complete,
                "record_count": len(wall_result.records),
                "source_observation_count": len(wall_result.source_observation_ids),
            },
        )
    )

    wall_identity_rows: list[dict[str, Any]] = []
    for wall_record in wall_result.records:
        identity = wall_record.physical_identity
        row = _entry(
            file="pb_physical_wall_identity.py",
            function="resolve_physical_wall_identity / published sidecar",
            status=identity.status,
            reason_codes=identity.blocking_reasons,
            record=None,
            input_lineage={
                "wall_candidate_id": wall_record.wall_candidate_id,
                "page_id": page_id,
                "decision_scope_id": scope_id,
            },
            output_lineage={
                "wall_candidate_id": identity.wall_candidate_id,
                "candidate_identity_id": identity.candidate_identity_id,
                "viewport_id": identity.viewport_id,
            },
            extra={
                "usable": identity.usable,
                "source_primitive_ids": identity.source_primitive_ids,
                "edge_ids": identity.edge_ids,
                "path_fingerprint": identity.path_fingerprint,
            },
        )
        row["RECORD_PRESENT"] = True
        row["RECORD_ID"] = identity.candidate_identity_id
        wall_identity_rows.append(row)

    semantic = SemanticOpeningEnumerationProducer.from_source_visibility_producer(
        source
    )
    semantic_result = semantic.publish_page_scope(
        revision_id=published.revision.revision_id,
        decision_scope_id=scope_id,
        page_ids=(page_id,),
    )
    semantic_record = semantic_result.record
    trace_rows.append(
        _entry(
            file="pb_semantic_opening_enumeration_authority.py",
            function="SemanticOpeningEnumerationProducer.publish_page_scope",
            status=semantic_result.status,
            reason_codes=semantic_result.reason_codes,
            record=semantic_record,
            input_lineage={
                "document_id": published.revision.document_id,
                "revision_id": published.revision.revision_id,
                "source_sha256": published.revision.source_sha256,
                "snapshot_id": published.snapshot.snapshot_id,
                "page_id": page_id,
                "decision_scope_id": scope_id,
            },
            output_lineage=_lineage(semantic_record),
            extra=(
                {
                    "structural_enumeration_complete": semantic_record.structural_enumeration_complete,
                    "physical_opening_universe_complete": semantic_record.physical_opening_universe_complete,
                    "physical_opening_count": len(semantic_record.physical_opening_record_ids),
                    "residual_visible_observation_count": len(semantic_record.residual_visible_observation_ids),
                    "conflict_observation_count": len(semantic_record.conflict_observation_ids),
                }
                if semantic_record is not None
                else {}
            ),
        )
    )

    host_universe_authority = (
        OpeningHostWallUniverseProducer.from_physical_wall_candidate_authority(
            wall_authority
        ).authority()
    )
    host_universe_selector = OpeningHostWallUniverseSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=page_id,
        decision_scope_id=scope_id,
    )
    host_universe_result = host_universe_authority.resolve_scope(
        host_universe_selector
    )
    trace_rows.append(
        _entry(
            file="pb_opening_host_binding_authority.py",
            function="OpeningHostWallUniverseAuthority.resolve_scope",
            status=host_universe_result.status,
            reason_codes=host_universe_result.reason_codes,
            record=None,
            input_lineage=_lineage(host_universe_selector),
            output_lineage={
                "document_id": host_universe_result.document_id,
                "revision_id": host_universe_result.revision_id,
                "source_sha256": host_universe_result.source_sha256,
                "snapshot_id": host_universe_result.snapshot_id,
                "page_id": host_universe_result.page_id,
                "decision_scope_id": host_universe_result.decision_scope_id,
            },
            extra={
                "scope_complete": host_universe_result.scope_complete,
                "record_count": len(host_universe_result.records),
                "equivalence_present": host_universe_result.equivalence is not None,
            },
        )
    )

    physical = PhysicalOpeningAuthority(source.authority())
    host_producer = OpeningHostBindingProducer.from_authorities(
        physical_opening_authority=physical,
        host_wall_universe_authority=host_universe_authority,
    )

    physical_rows: list[dict[str, Any]] = []
    host_rows: list[dict[str, Any]] = []
    if semantic_record is not None:
        for opening_id, observation_id in zip(
            semantic_record.physical_opening_record_ids,
            semantic_record.representative_observation_ids,
        ):
            observation_selector = ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
            proof = physical.prove_existence(observation_selector)
            existence = proof.existence_record
            physical_rows.append(
                _entry(
                    file="pb_physical_opening_authority.py",
                    function="PhysicalOpeningAuthority.prove_existence",
                    status=proof.status,
                    reason_codes=proof.reason_codes,
                    record=existence,
                    input_lineage={
                        **_lineage(observation_selector),
                        "observation_id": observation_id,
                        "semantic_opening_record_id": opening_id,
                    },
                    output_lineage=_lineage(existence),
                    extra={
                        "proposition": proof.proposition,
                        "physical_opening_existence": proof.physical_opening_existence,
                        "semantic_record_matches_proof": (
                            existence is not None
                            and existence.record_id == opening_id
                        ),
                    },
                )
            )
            host_result = host_producer.publish(
                opening_left_selector=observation_selector,
                opening_right_selector=observation_selector,
                host_universe_selector=host_universe_selector,
            )
            host_rows.append(
                _entry(
                    file="pb_opening_host_binding_authority.py",
                    function="OpeningHostBindingProducer.publish",
                    status=host_result.status,
                    reason_codes=host_result.reason_codes,
                    record=host_result.record,
                    input_lineage={
                        "document_id": published.revision.document_id,
                        "revision_id": published.revision.revision_id,
                        "source_sha256": published.revision.source_sha256,
                        "snapshot_id": published.snapshot.snapshot_id,
                        "page_id": page_id,
                        "decision_scope_id": scope_id,
                        "opening_identity_id": (
                            existence.record_id if existence is not None else opening_id
                        ),
                        "observation_id": observation_id,
                    },
                    output_lineage=_lineage(host_result.record),
                    extra={
                        "host_wall_id": host_result.host_wall_id,
                    },
                )
            )

    first_failure = None
    ordered = [
        *trace_rows[:2],
        *wall_identity_rows,
        trace_rows[2],
        *physical_rows,
        trace_rows[3],
        *host_rows,
    ]
    for row in ordered:
        status = str(row["STATUS"]).lower()
        if status not in {
            EvidenceResolutionStatus.CORROBORATED.value,
            "complete",
        }:
            first_failure = {
                "FILE": row["FILE"],
                "CLASS_FUNCTION": row["CLASS_FUNCTION"],
                "STATUS": row["STATUS"],
                "REASON_CODES": row["REASON_CODES"],
                "RECORD_ID": row["RECORD_ID"],
            }
            break

    return {
        "document_id": document_id,
        "page_id": page_id,
        "decision_scope_id": scope_id,
        "source_sha256": published.revision.source_sha256,
        "trace": ordered,
        "FIRST_CAUSAL_FAILURE": first_failure,
        "wall_candidate_count": len(wall_result.records),
        "physical_opening_count": len(physical_rows),
        "host_binding_resolved_count": sum(
            1
            for row in host_rows
            if str(row["STATUS"]).lower()
            == EvidenceResolutionStatus.CORROBORATED.value
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--page-id", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = trace(
        args.pdf,
        document_id=args.document_id,
        page_id=str(args.page_id),
    )
    payload = json.dumps(result, indent=2, sort_keys=True)
    print(payload)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
