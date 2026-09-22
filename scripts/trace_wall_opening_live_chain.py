"""Trace producer-owned wall/opening authority seams on one source page.

Diagnostic only: never publishes commercial quantities and never consumes
benchmark expected values.  It is intentionally CLI-driven so the same trace
can be run against any authenticated source/page.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_host_binding_authority import (
    OpeningHostBindingProducer,
    OpeningHostWallUniverseProducer,
    OpeningHostWallUniverseSelector,
)
from pb_opening_universe_completeness_authority import OpeningUniverseSelector
from pb_opening_universe_completeness_source_adapter import (
    build_semantic_opening_inventory_completeness,
)
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, PhysicalOpeningAuthority
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _status(value: Any) -> str:
    raw = getattr(value, "status", None)
    return str(getattr(raw, "value", raw))


def _reasons(value: Any) -> list[str]:
    return [str(item) for item in (getattr(value, "reason_codes", ()) or ())]


def _lineage(record: Any) -> dict[str, Any]:
    if record is None:
        return {}
    return {
        key: getattr(record, key, None)
        for key in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "decision_scope_id",
        )
        if hasattr(record, key)
    }


def _emit(
    *,
    stage: str,
    file: str,
    callable_name: str,
    result: Any,
    record: Any = None,
    record_id: Any = None,
    input_lineage: dict[str, Any] | None = None,
    output_lineage: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    if record_id is None and record is not None:
        record_id = getattr(record, "record_id", None)
    payload = {
        "STAGE": stage,
        "FILE": file,
        "CLASS_FUNCTION": callable_name,
        "STATUS": _status(result),
        "REASON_CODES": _reasons(result),
        "RECORD_PRESENT": record is not None,
        "RECORD_ID": record_id,
        "INPUT_LINEAGE": input_lineage or {},
        "OUTPUT_LINEAGE": output_lineage if output_lineage is not None else _lineage(record),
    }
    if extra:
        payload.update(extra)
    print("TRACE " + json.dumps(payload, sort_keys=True, default=str))


def trace(pdf_path: Path, page_id: str) -> None:
    raw = pdf_path.read_bytes()
    source = SourceVisibilityProducer(
        producer_method="wall-opening-live-chain-trace",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"trace:{pdf_path.stem}",
        source_bytes=raw,
        source_locator=str(pdf_path),
    )
    published = source.augment_with_raster_visible_segments(
        published.revision.revision_id,
        page_ids=(page_id,),
    )
    source_lineage = {
        "document_id": published.revision.document_id,
        "revision_id": published.revision.revision_id,
        "source_sha256": published.revision.source_sha256,
        "snapshot_id": published.snapshot.snapshot_id,
        "page_id": page_id,
    }
    print(
        "TRACE "
        + json.dumps(
            {
                "STAGE": "source_evidence",
                "FILE": "pb_source_visibility_authority.py",
                "CLASS_FUNCTION": "SourceVisibilityProducer.ingest_native_pdf_bytes",
                "STATUS": EvidenceResolutionStatus.CORROBORATED.value,
                "REASON_CODES": [],
                "RECORD_PRESENT": True,
                "RECORD_ID": published.snapshot.snapshot_id,
                "INPUT_LINEAGE": {
                    "source_locator": str(pdf_path),
                    "page_id": page_id,
                },
                "OUTPUT_LINEAGE": source_lineage,
                "visible_observation_count": len(published.visible_observation_ids),
            },
            sort_keys=True,
        )
    )

    scope_id = f"wall-source:page-{page_id}"
    wall_producer = PhysicalWallCandidateProducer.from_source_visibility_producer(source)
    wall_authority = wall_producer.authority()
    wall_selector = PhysicalWallCandidateSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=page_id,
        decision_scope_id=scope_id,
    )
    wall = wall_authority.resolve_scope(wall_selector)
    wall_records = tuple(getattr(wall, "records", ()) or ())
    wall_ids = tuple(getattr(item, "wall_candidate_id", None) for item in wall_records)
    _emit(
        stage="physical_wall_candidate",
        file="pb_physical_wall_candidate_authority.py",
        callable_name="PhysicalWallCandidateAuthority.resolve_scope",
        result=wall,
        record=wall if wall_records else None,
        record_id=wall_ids,
        input_lineage=source_lineage,
        output_lineage={
            **source_lineage,
            "decision_scope_id": scope_id,
        },
        extra={
            "scope_complete": bool(getattr(wall, "scope_complete", False)),
            "candidate_count": len(wall_records),
            "candidate_ids": wall_ids,
            "candidate_identity_ids": tuple(
                getattr(getattr(item, "physical_identity", None), "candidate_identity_id", None)
                for item in wall_records
            ),
        },
    )

    completeness = build_semantic_opening_inventory_completeness(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        decision_scope_id=scope_id,
        page_ids=(page_id,),
    )
    universe_selector = OpeningUniverseSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        decision_scope_id=scope_id,
    )
    universe = completeness.resolve(universe_selector)
    universe_record = getattr(universe, "record", None)
    _emit(
        stage="opening_universe_completeness",
        file="pb_opening_universe_completeness_source_adapter.py",
        callable_name="build_semantic_opening_inventory_completeness/OpeningUniverseCompletenessAuthority.resolve",
        result=universe,
        record=universe_record,
        input_lineage={**source_lineage, "decision_scope_id": scope_id},
        extra={
            "decision_scope_complete": bool(
                getattr(universe, "decision_scope_complete", False)
            ),
            "accounted_member_ids": tuple(
                getattr(universe_record, "accounted_member_ids", ()) or ()
            ),
            "accounted_source_observation_ids": tuple(
                getattr(universe_record, "accounted_source_observation_ids", ()) or ()
            ),
        },
    )

    representative_ids = tuple(
        getattr(universe_record, "accounted_source_observation_ids", ()) or ()
    )
    physical = PhysicalOpeningAuthority(source.authority())
    opening_selectors: dict[str, ObservationSelector] = {}
    opening_records: dict[str, Any] = {}
    for observation_id in representative_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = physical.prove_existence(selector)
        record = getattr(result, "existence_record", None)
        _emit(
            stage="physical_opening",
            file="pb_physical_opening_authority.py",
            callable_name="PhysicalOpeningAuthority.prove_existence",
            result=result,
            record=record,
            input_lineage={
                **source_lineage,
                "observation_id": observation_id,
                "decision_scope_id": scope_id,
            },
            extra={"proposition": getattr(result, "proposition", None)},
        )
        if (
            getattr(result, "proposition", None) == PHYSICAL_OPENING_EXISTS
            and record is not None
        ):
            opening_selectors.setdefault(record.record_id, selector)
            opening_records.setdefault(record.record_id, record)

    host_universe = OpeningHostWallUniverseProducer.from_physical_wall_candidate_authority(
        wall_authority
    ).authority()
    host_scope = OpeningHostWallUniverseSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=page_id,
        decision_scope_id=scope_id,
    )
    host_scope_result = host_universe.resolve_scope(host_scope)
    _emit(
        stage="physical_wall_identity",
        file="pb_opening_host_binding_authority.py",
        callable_name="OpeningHostWallUniverseAuthority.resolve_scope",
        result=host_scope_result,
        record=host_scope_result if getattr(host_scope_result, "records", ()) else None,
        record_id=tuple(
            getattr(item, "wall_candidate_id", None)
            for item in (getattr(host_scope_result, "records", ()) or ())
        ),
        input_lineage={**source_lineage, "decision_scope_id": scope_id},
        output_lineage={**source_lineage, "decision_scope_id": scope_id},
        extra={
            "scope_complete": bool(getattr(host_scope_result, "scope_complete", False)),
            "ambiguous_wall_ids": tuple(
                getattr(getattr(host_scope_result, "equivalence", None), "ambiguous_wall_ids", ())
                or ()
            ),
        },
    )

    host_producer = OpeningHostBindingProducer.from_authorities(
        physical_opening_authority=physical,
        host_wall_universe_authority=host_universe,
    )
    for opening_id, selector in opening_selectors.items():
        host = host_producer.publish(
            opening_left_selector=selector,
            opening_right_selector=selector,
            host_universe_selector=host_scope,
        )
        record = getattr(host, "record", None)
        _emit(
            stage="opening_host_binding",
            file="pb_opening_host_binding_authority.py",
            callable_name="OpeningHostBindingProducer.publish",
            result=host,
            record=record,
            input_lineage={
                **source_lineage,
                "decision_scope_id": scope_id,
                "opening_identity_id": opening_id,
            },
            extra={
                "host_wall_id": getattr(record, "host_wall_id", None),
                "member_wall_candidate_ids": tuple(
                    getattr(record, "member_wall_candidate_ids", ()) or ()
                ),
                "host_id_is_raw_candidate_id": bool(
                    record is not None
                    and getattr(record, "host_wall_id", None) in set(wall_ids)
                ),
            },
        )

    if not opening_selectors:
        print(
            "TRACE "
            + json.dumps(
                {
                    "STAGE": "opening_host_binding",
                    "FILE": "pb_opening_host_binding_authority.py",
                    "CLASS_FUNCTION": "OpeningHostBindingProducer.publish",
                    "STATUS": "not_invoked_no_authenticated_physical_opening",
                    "REASON_CODES": ["authenticated_physical_opening_identity_required"],
                    "RECORD_PRESENT": False,
                    "RECORD_ID": None,
                    "INPUT_LINEAGE": {**source_lineage, "decision_scope_id": scope_id},
                    "OUTPUT_LINEAGE": {},
                },
                sort_keys=True,
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--page", required=True)
    args = parser.parse_args()
    trace(args.pdf, str(args.page))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
