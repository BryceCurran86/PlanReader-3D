from __future__ import annotations

import argparse
import hashlib
import json
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


def _status(value: Any) -> str:
    if value is None:
        return "NONE"
    raw = getattr(value, "value", value)
    return str(raw)


def _reason_codes(result: Any) -> list[str]:
    return [str(x) for x in tuple(getattr(result, "reason_codes", ()) or ())]


def _lineage(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    names = (
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
        "target_scope_id",
    )
    return {
        name: getattr(obj, name)
        for name in names
        if getattr(obj, name, None) is not None
    }


def _entry(
    *,
    stage: str,
    file: str,
    class_function: str,
    result: Any = None,
    record: Any = None,
    record_id: str | None = None,
    input_lineage: dict[str, Any] | None = None,
    output_lineage: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if record is None and result is not None:
        for attr in ("record", "existence_record"):
            candidate = getattr(result, attr, None)
            if candidate is not None:
                record = candidate
                break
    rid = record_id
    if rid is None and record is not None:
        rid = (
            getattr(record, "record_id", None)
            or getattr(record, "wall_candidate_id", None)
            or getattr(record, "candidate_identity_id", None)
        )
    payload = {
        "STAGE": stage,
        "FILE": file,
        "CLASS_FUNCTION": class_function,
        "STATUS": _status(getattr(result, "status", None)) if result is not None else "NOT_REACHED",
        "REASON_CODES": _reason_codes(result) if result is not None else [],
        "RECORD_PRESENT": record is not None,
        "RECORD_ID": rid,
        "INPUT_LINEAGE": input_lineage or {},
        "OUTPUT_LINEAGE": output_lineage if output_lineage is not None else _lineage(record),
    }
    if extra:
        payload.update(extra)
    return payload


def trace(pdf_path: Path, *, document_id: str, page_id: str) -> dict[str, Any]:
    raw = pdf_path.read_bytes()
    source_sha = hashlib.sha256(raw).hexdigest()
    source = SourceVisibilityProducer(
        producer_method="wall-net-authority-trace-v1",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=raw,
        source_locator=str(pdf_path),
    )

    report: dict[str, Any] = {
        "document_id": document_id,
        "page_id": page_id,
        "source_path": str(pdf_path),
        "source_sha256_actual": source_sha,
        "published_source_sha256": published.revision.source_sha256,
        "trace": [],
    }

    page_scope = f"wall-source:page-{page_id}"
    base_lineage = {
        "document_id": published.revision.document_id,
        "revision_id": published.revision.revision_id,
        "source_sha256": published.revision.source_sha256,
        "snapshot_id": published.snapshot.snapshot_id,
        "page_id": page_id,
        "decision_scope_id": page_scope,
    }

    report["trace"].append(
        {
            "STAGE": "source evidence",
            "FILE": "pb_source_visibility_authority.py",
            "CLASS_FUNCTION": "SourceVisibilityProducer.ingest_native_pdf_bytes",
            "STATUS": "corroborated",
            "REASON_CODES": [],
            "RECORD_PRESENT": True,
            "RECORD_ID": published.snapshot.snapshot_id,
            "INPUT_LINEAGE": {
                "document_id": document_id,
                "source_sha256": source_sha,
            },
            "OUTPUT_LINEAGE": {
                **base_lineage,
                "coverage_state": str(published.coverage.state),
                "decoded_pages": [int(x) for x in published.coverage.decoded_pages],
                "failed_pages": [int(x) for x in published.coverage.failed_pages],
            },
        }
    )

    # Producer-owned physical wall scope and identities.
    wall_producer = PhysicalWallCandidateProducer.from_source_visibility_producer_for_pages(
        source,
        page_ids=(page_id,),
    )
    wall_authority = wall_producer.authority()
    wall_selector = PhysicalWallCandidateSelector(**base_lineage)
    wall_result = wall_authority.resolve_scope(wall_selector)
    report["trace"].append(
        _entry(
            stage="physical wall candidate",
            file="pb_physical_wall_candidate_authority.py",
            class_function="PhysicalWallCandidateAuthority.resolve_scope",
            result=wall_result,
            input_lineage=base_lineage,
            output_lineage={
                **_lineage(wall_result),
                "scope_complete": bool(getattr(wall_result, "scope_complete", False)),
                "record_count": len(tuple(getattr(wall_result, "records", ()) or ())),
                "source_observation_count": len(
                    tuple(getattr(wall_result, "source_observation_ids", ()) or ())
                ),
            },
            extra={
                "RECORD_PRESENT": bool(tuple(getattr(wall_result, "records", ()) or ())),
                "RECORD_ID": None,
            },
        )
    )
    for record in tuple(getattr(wall_result, "records", ()) or ()):
        identity = getattr(record, "physical_identity", None)
        report["trace"].append(
            _entry(
                stage="physical wall identity",
                file="pb_physical_wall_candidate_authority.py / pb_physical_wall_identity.py",
                class_function="PhysicalWallCandidateRecord.physical_identity",
                result=identity,
                record=identity,
                record_id=getattr(identity, "candidate_identity_id", None),
                input_lineage=base_lineage,
                output_lineage={
                    **base_lineage,
                    "wall_candidate_id": getattr(record, "wall_candidate_id", None),
                    "candidate_identity_id": getattr(identity, "candidate_identity_id", None),
                    "viewport_id": getattr(identity, "viewport_id", None),
                    "source_primitive_ids": list(
                        tuple(getattr(identity, "source_primitive_ids", ()) or ())
                    ),
                    "edge_ids": list(tuple(getattr(identity, "edge_ids", ()) or ())),
                },
                extra={
                    "STATUS": _status(getattr(identity, "status", None)),
                    "REASON_CODES": [],
                    "RECORD_PRESENT": identity is not None,
                },
            )
        )

    # Producer-owned semantic physical-opening inventory for this exact page.
    semantic_producer = SemanticOpeningEnumerationProducer.from_source_visibility_producer(source)
    semantic = semantic_producer.publish_page_scope(
        revision_id=published.revision.revision_id,
        decision_scope_id=page_scope,
        page_ids=(page_id,),
    )
    semantic_record = getattr(semantic, "record", None)
    report["trace"].append(
        _entry(
            stage="physical opening universe discovery",
            file="pb_semantic_opening_enumeration_authority.py",
            class_function="SemanticOpeningEnumerationProducer.publish_page_scope",
            result=semantic,
            record=semantic_record,
            input_lineage=base_lineage,
            output_lineage={
                **_lineage(semantic_record),
                "physical_opening_universe_complete": bool(
                    getattr(semantic_record, "physical_opening_universe_complete", False)
                )
                if semantic_record is not None
                else None,
                "structural_enumeration_complete": bool(
                    getattr(semantic_record, "structural_enumeration_complete", False)
                )
                if semantic_record is not None
                else None,
                "physical_opening_count": len(
                    tuple(getattr(semantic_record, "physical_opening_record_ids", ()) or ())
                )
                if semantic_record is not None
                else 0,
                "residual_visible_observation_count": len(
                    tuple(getattr(semantic_record, "residual_visible_observation_ids", ()) or ())
                )
                if semantic_record is not None
                else 0,
            },
        )
    )

    physical_opening = PhysicalOpeningAuthority(source.authority())
    host_universe = OpeningHostWallUniverseProducer.from_physical_wall_candidate_authority(
        wall_authority
    ).authority()
    host_universe_selector = OpeningHostWallUniverseSelector(**base_lineage)
    host_universe_result = host_universe.resolve_scope(host_universe_selector)
    report["trace"].append(
        _entry(
            stage="opening host wall universe",
            file="pb_opening_host_binding_authority.py",
            class_function="OpeningHostWallUniverseAuthority.resolve_scope",
            result=host_universe_result,
            input_lineage=base_lineage,
            output_lineage={
                **_lineage(host_universe_result),
                "scope_complete": bool(getattr(host_universe_result, "scope_complete", False)),
                "record_count": len(
                    tuple(getattr(host_universe_result, "records", ()) or ())
                ),
            },
            extra={
                "RECORD_PRESENT": bool(
                    tuple(getattr(host_universe_result, "records", ()) or ())
                ),
                "RECORD_ID": None,
            },
        )
    )

    host_producer = OpeningHostBindingProducer.from_authorities(
        physical_opening_authority=physical_opening,
        host_wall_universe_authority=host_universe,
    )

    reps = (
        tuple(getattr(semantic_record, "representative_observation_ids", ()) or ())
        if semantic_record is not None
        else ()
    )
    expected_opening_ids = (
        tuple(getattr(semantic_record, "physical_opening_record_ids", ()) or ())
        if semantic_record is not None
        else ()
    )

    for index, observation_id in enumerate(reps):
        obs_selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=str(observation_id),
        )
        opening_result = physical_opening.prove_existence(obs_selector)
        opening_record = getattr(opening_result, "existence_record", None)
        report["trace"].append(
            _entry(
                stage="physical opening",
                file="pb_physical_opening_authority.py",
                class_function="PhysicalOpeningAuthority.prove_existence",
                result=opening_result,
                record=opening_record,
                input_lineage={
                    **base_lineage,
                    "observation_id": observation_id,
                    "semantic_opening_record_id": (
                        expected_opening_ids[index]
                        if index < len(expected_opening_ids)
                        else None
                    ),
                },
                output_lineage=_lineage(opening_record),
                extra={
                    "PROPOSITION": getattr(opening_result, "proposition", None),
                    "PHYSICAL_OPENING_EXISTENCE": bool(
                        getattr(opening_result, "physical_opening_existence", False)
                    ),
                },
            )
        )

        host_result = host_producer.publish(
            opening_left_selector=obs_selector,
            opening_right_selector=obs_selector,
            host_universe_selector=host_universe_selector,
        )
        host_record = getattr(host_result, "record", None)
        report["trace"].append(
            _entry(
                stage="opening host binding",
                file="pb_opening_host_binding_authority.py",
                class_function="OpeningHostBindingProducer.publish",
                result=host_result,
                record=host_record,
                input_lineage={
                    **base_lineage,
                    "opening_identity_id": (
                        getattr(opening_record, "record_id", None)
                        if opening_record is not None
                        else None
                    ),
                },
                output_lineage={
                    **_lineage(host_record),
                    "member_wall_candidate_ids": list(
                        tuple(
                            getattr(host_record, "member_wall_candidate_ids", ()) or ()
                        )
                    )
                    if host_record is not None
                    else [],
                    "member_candidate_identity_ids": list(
                        tuple(
                            getattr(host_record, "member_candidate_identity_ids", ()) or ()
                        )
                    )
                    if host_record is not None
                    else [],
                },
            )
        )

    # The current live extractor does not construct the downstream producer-owned
    # void/completeness/applicability/deduction/gross/net stack. We record that
    # composition boundary explicitly rather than inventing downstream authority.
    downstream = (
        ("physical opening void", "pb_physical_opening_void_authority.py", "PhysicalOpeningVoidProducer.publish"),
        ("opening universe completeness", "pb_opening_universe_completeness_authority.py", "OpeningUniverseCompletenessAuthority.resolve"),
        ("deduction applicability", "pb_opening_deduction_applicability_authority.py", "OpeningDeductionApplicabilityProducer.publish"),
        ("opening deduction", "pb_opening_deduction_authority.py", "OpeningDeductionProducer.publish"),
        ("gross wall geometry", "pb_gross_wall_geometry_authority.py", "GrossWallGeometryProducer.publish"),
        ("net wall boolean union", "pb_net_wall_boolean_union_authority.py", "NetWallBooleanUnionProducer.publish"),
        ("live commercial output", "pb_planreader_pdf_extractor.py", "GenericPlanReaderExtractor.extract_from_pdf"),
        ("finish assignment", "pb_wall_finish_propagation_authority.py", "WallFinishPropagationProducer.publish"),
    )
    for stage, file, fn in downstream:
        report["trace"].append(
            {
                "STAGE": stage,
                "FILE": file,
                "CLASS_FUNCTION": fn,
                "STATUS": "NOT_COMPOSED_BY_CURRENT_LIVE_EXTRACTOR",
                "REASON_CODES": ["live_authority_chain_not_composed"],
                "RECORD_PRESENT": False,
                "RECORD_ID": None,
                "INPUT_LINEAGE": base_lineage,
                "OUTPUT_LINEAGE": {},
            }
        )

    host_entries = [x for x in report["trace"] if x["STAGE"] == "opening host binding"]
    first_failure = None
    for item in report["trace"]:
        if item["STAGE"] in {
            "source evidence",
            "physical wall candidate",
            "physical wall identity",
            "physical opening universe discovery",
            "opening host wall universe",
            "physical opening",
            "opening host binding",
        }:
            status = str(item.get("STATUS", "")).lower()
            if status not in {"corroborated"}:
                first_failure = {
                    "STAGE": item["STAGE"],
                    "STATUS": item["STATUS"],
                    "REASON_CODES": item["REASON_CODES"],
                    "RECORD_ID": item["RECORD_ID"],
                }
                break

    if first_failure is None:
        if not host_entries:
            first_failure = {
                "STAGE": "physical opening",
                "STATUS": "ABSTAINED",
                "REASON_CODES": ["no_semantic_physical_openings_published"],
                "RECORD_ID": None,
            }
        else:
            first_failure = {
                "STAGE": "live authority composition",
                "STATUS": "NOT_COMPOSED_BY_CURRENT_LIVE_EXTRACTOR",
                "REASON_CODES": ["live_authority_chain_not_composed"],
                "RECORD_ID": None,
            }

    report["FIRST_CAUSAL_FAILURE"] = first_failure
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--page-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    report = trace(args.pdf, document_id=args.document_id, page_id=str(args.page_id))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
