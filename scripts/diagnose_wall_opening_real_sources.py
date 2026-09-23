from __future__ import annotations

from collections import Counter
from dataclasses import asdict, is_dataclass
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import fitz

from pb_live_wall_opening_authority_composition import (
    compose_live_wall_opening_authority,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    SourceVisibilityProducer,
    classify_native_segment_visibility,
)
from pb_vector_geometry_v130 import extract_native_page


CASES = (
    {
        "name": "KSTVET",
        "path": Path("benchmarks/sources/1727358888238-bq-nd-drawing.pdf"),
        "sha256": "6856bfa739aa136dd8e0bf17cb25fd43d0d31c9c3dfe3252525454f09d8fa4dc",
        "page": 54,
    },
    {
        "name": "LAMU",
        "path": Path("benchmarks/sources/lamu-ishakani-ecd-classrooms-boq.pdf"),
        "sha256": "fa53c9b72fd35189f11848f9a26ccc3512c8c03b5316e78cad6a4d55c09330f2",
        "page": 41,
    },
)


def _status(value: Any) -> str:
    raw = getattr(value, "value", value)
    return str(raw)


def _ids(value: Any, *, limit: int = 20) -> dict[str, Any]:
    if value is None:
        return {}
    if is_dataclass(value):
        value = asdict(value)
    found: dict[str, Any] = {}

    def walk(node: Any, prefix: str = "") -> None:
        if len(found) >= limit:
            return
        if isinstance(node, dict):
            for key, item in node.items():
                key_s = str(key)
                child = f"{prefix}.{key_s}" if prefix else key_s
                if (
                    key_s.endswith("_id")
                    or key_s.endswith("_ids")
                    or "lineage" in key_s
                    or "parent" in key_s
                    or "evidence" in key_s
                ):
                    if isinstance(item, (str, int, float, bool)) or item is None:
                        found[child] = item
                    elif isinstance(item, (list, tuple)):
                        found[child] = list(item[:10])
                walk(item, child)
        elif isinstance(node, (list, tuple)):
            for index, item in enumerate(node[:10]):
                walk(item, f"{prefix}[{index}]")

    walk(value)
    return found


def _record_id(value: Any) -> Any:
    if value is None:
        return None
    for name in (
        "record_id",
        "physical_wall_id",
        "wall_identity_id",
        "wall_candidate_id",
        "opening_identity_id",
        "observation_id",
        "identity_id",
    ):
        candidate = getattr(value, name, None)
        if candidate not in (None, ""):
            return candidate
    fields = _ids(value, limit=10)
    return next(iter(fields.values()), None)


def _emit(
    *,
    project: str,
    stage: str,
    file: str,
    class_function: str,
    status: Any,
    reason_codes: Any,
    record_present: bool,
    record_id: Any,
    input_lineage: Any,
    output_lineage: Any,
) -> None:
    payload = {
        "PROJECT": project,
        "STAGE": stage,
        "FILE": file,
        "CLASS/FUNCTION": class_function,
        "STATUS": _status(status),
        "REASON_CODES": list(reason_codes or ()),
        "RECORD PRESENT": bool(record_present),
        "RECORD ID": record_id,
        "INPUT LINEAGE": input_lineage,
        "OUTPUT LINEAGE": output_lineage,
    }
    print("AUTHORITY_TRACE " + json.dumps(payload, sort_keys=True, default=str), flush=True)


def _is_corrob(status: Any) -> bool:
    return status is EvidenceResolutionStatus.CORROBORATED


def diagnose(case: dict[str, Any]) -> None:
    name = str(case["name"])
    path: Path = case["path"]
    page_number = int(case["page"])
    source_bytes = path.read_bytes()
    actual_sha = hashlib.sha256(source_bytes).hexdigest()
    if actual_sha != case["sha256"]:
        raise SystemExit(
            f"{name}: source SHA mismatch: expected {case['sha256']} got {actual_sha}"
        )

    pdf = fitz.open(stream=source_bytes, filetype="pdf")
    try:
        page = pdf.load_page(page_number - 1)
        native = extract_native_page(page)
    finally:
        pdf.close()

    segments = list(native.get("segments") or ())
    decisions = [classify_native_segment_visibility(segment) for segment in segments]
    visible_segments = [
        segment for segment, decision in zip(segments, decisions) if decision.visible
    ]
    reason_counts = Counter(
        reason
        for decision in decisions
        for reason in decision.reason_codes
    )
    _emit(
        project=name,
        stage="SOURCE_VISIBILITY",
        file="pb_source_visibility_authority.py",
        class_function="classify_native_segment_visibility",
        status=(
            EvidenceResolutionStatus.CORROBORATED
            if visible_segments
            else EvidenceResolutionStatus.ABSTAINED
        ),
        reason_codes=tuple(sorted(reason_counts)),
        record_present=bool(visible_segments),
        record_id=(
            str(visible_segments[0].get("id")) if visible_segments else None
        ),
        input_lineage={
            "source_sha256": actual_sha,
            "page_id": str(page_number),
            "native_segment_count": len(segments),
            "clip_known_count": sum(
                1 for segment in segments if segment.get("clip_known") is True
            ),
            "clip_present_count": sum(
                1 for segment in segments if segment.get("clip_present") is True
            ),
            "clip_shape_known_count": sum(
                1 for segment in segments if segment.get("clip_shape_known") is True
            ),
            "clip_exact_rect_count": sum(
                1 for segment in segments if segment.get("clip_exact_rect") is not None
            ),
        },
        output_lineage={
            "visible_segment_count": len(visible_segments),
            "reason_counts": dict(sorted(reason_counts.items())),
            "sample_visible_segment_ids": [
                str(segment.get("id")) for segment in visible_segments[:20]
            ],
        },
    )

    if os.environ.get("VISIBILITY_ONLY") == "1":
        print(
            "VISIBILITY_ONLY_COMPLETE "
            + json.dumps(
                {
                    "PROJECT": name,
                    "PAGE": page_number,
                    "NATIVE_SEGMENTS": len(segments),
                    "VISIBLE_SEGMENTS": len(visible_segments),
                    "REASON_COUNTS": dict(sorted(reason_counts.items())),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return

    producer = SourceVisibilityProducer(
        producer_method="wall-opening-real-source-diagnostic",
        producer_version="1.0",
    )
    ingest_started = time.perf_counter()
    published = producer.ingest_native_pdf_bytes(
        document_id=f"diagnostic:{name.lower()}",
        source_bytes=source_bytes,
        source_locator=str(path),
    )
    ingest_seconds = time.perf_counter() - ingest_started
    print(
        "SOURCE_VISIBILITY_INGEST_COMPLETE "
        + json.dumps(
            {
                "PROJECT": name,
                "SECONDS": round(ingest_seconds, 3),
                "VISIBLE_OBSERVATIONS": len(published.visible_observation_ids),
                "TEXT_OBSERVATIONS": len(published.text_observation_ids),
                "SNAPSHOT_ID": published.snapshot.snapshot_id,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    if os.environ.get("INGEST_ONLY") == "1":
        return

    composition_started = time.perf_counter()
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=producer,
        revision_id=published.revision.revision_id,
        page_ids=(str(page_number),),
    )
    composition_seconds = time.perf_counter() - composition_started
    print(
        "WALL_OPENING_COMPOSITION_COMPLETE "
        + json.dumps(
            {
                "PROJECT": name,
                "SECONDS": round(composition_seconds, 3),
                "STATUS": _status(composition.status),
                "REASON_CODES": list(composition.reason_codes),
            },
            sort_keys=True,
        ),
        flush=True,
    )

    wall_selector = PhysicalWallCandidateSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=str(page_number),
        decision_scope_id=f"wall-source:page-{page_number}",
    )
    wall_result = composition.physical_wall_candidate_authority.resolve_scope(
        wall_selector
    )
    wall_ids = [record.wall_candidate_id for record in wall_result.records]
    _emit(
        project=name,
        stage="PHYSICAL_WALL_CANDIDATE",
        file="pb_physical_wall_candidate_authority.py",
        class_function="PhysicalWallCandidateAuthority.resolve_scope",
        status=wall_result.status,
        reason_codes=wall_result.reason_codes,
        record_present=bool(wall_result.records),
        record_id=(wall_ids[0] if wall_ids else None),
        input_lineage={
            "source_observation_count": len(wall_result.source_observation_ids),
            "sample_source_observation_ids": list(
                wall_result.source_observation_ids[:20]
            ),
            "decision_scope_id": wall_result.decision_scope_id,
            "scope_complete": wall_result.scope_complete,
        },
        output_lineage={
            "wall_candidate_count": len(wall_result.records),
            "sample_wall_candidate_ids": wall_ids[:20],
        },
    )

    identity_records = [
        record.physical_identity
        for record in wall_result.records
        if record.physical_identity is not None
    ]
    _emit(
        project=name,
        stage="PHYSICAL_WALL_IDENTITY",
        file="pb_physical_wall_candidate_authority.py",
        class_function="PhysicalWallCandidateRecord.physical_identity",
        status=(
            EvidenceResolutionStatus.CORROBORATED
            if identity_records and len(identity_records) == len(wall_result.records)
            else EvidenceResolutionStatus.ABSTAINED
        ),
        reason_codes=(
            ()
            if identity_records and len(identity_records) == len(wall_result.records)
            else ("physical_wall_candidate_identity_unresolved",)
        ),
        record_present=bool(identity_records),
        record_id=(_record_id(identity_records[0]) if identity_records else None),
        input_lineage={
            "wall_candidate_count": len(wall_result.records),
            "sample_wall_candidate_ids": wall_ids[:20],
        },
        output_lineage={
            "physical_identity_count": len(identity_records),
            "sample_identity_lineage": [
                _ids(identity, limit=12) for identity in identity_records[:10]
            ],
        },
    )

    semantic = composition.semantic_enumeration_result
    semantic_record = semantic.record
    representative_ids = (
        tuple(semantic_record.representative_observation_ids)
        if semantic_record is not None
        else ()
    )
    opening_results: list[tuple[str, Any]] = []
    for observation_id in representative_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        opening_results.append(
            (
                observation_id,
                composition.physical_opening_authority.prove_existence(selector),
            )
        )

    physical_opening_records = [
        result.existence_record
        for _, result in opening_results
        if result.existence_record is not None
    ]
    opening_reasons = tuple(
        dict.fromkeys(
            reason
            for _, result in opening_results
            for reason in result.reason_codes
        )
    )
    physical_opening_ok = bool(opening_results) and all(
        _is_corrob(result.status) and result.existence_record is not None
        for _, result in opening_results
    )
    _emit(
        project=name,
        stage="PHYSICAL_OPENING",
        file="pb_physical_opening_authority.py",
        class_function="PhysicalOpeningAuthority.prove_existence",
        status=(
            EvidenceResolutionStatus.CORROBORATED
            if physical_opening_ok
            else (
                semantic.status
                if not opening_results
                else EvidenceResolutionStatus.ABSTAINED
            )
        ),
        reason_codes=(
            opening_reasons
            if opening_results
            else tuple(semantic.reason_codes)
        ),
        record_present=bool(physical_opening_records),
        record_id=(
            _record_id(physical_opening_records[0])
            if physical_opening_records
            else None
        ),
        input_lineage={
            "semantic_status": _status(semantic.status),
            "semantic_reason_codes": list(semantic.reason_codes),
            "representative_observation_count": len(representative_ids),
            "sample_representative_observation_ids": list(representative_ids[:20]),
        },
        output_lineage={
            "physical_opening_record_count": len(physical_opening_records),
            "sample_opening_record_lineage": [
                _ids(record, limit=12) for record in physical_opening_records[:10]
            ],
        },
    )

    bindings = tuple(composition.opening_bindings)
    binding_ok = bool(bindings) and all(
        _is_corrob(trace.status) and trace.record_id is not None for trace in bindings
    )
    binding_reasons = tuple(
        dict.fromkeys(reason for trace in bindings for reason in trace.reason_codes)
    )
    _emit(
        project=name,
        stage="OPENING_HOST_BINDING",
        file="pb_opening_host_binding_authority.py",
        class_function="OpeningHostBindingProducer.publish",
        status=(
            EvidenceResolutionStatus.CORROBORATED
            if binding_ok
            else EvidenceResolutionStatus.ABSTAINED
        ),
        reason_codes=binding_reasons,
        record_present=any(trace.record_id is not None for trace in bindings),
        record_id=next(
            (trace.record_id for trace in bindings if trace.record_id is not None),
            None,
        ),
        input_lineage={
            "opening_identity_count": len(bindings),
            "sample_opening_identity_ids": [
                trace.opening_identity_id for trace in bindings[:20]
            ],
        },
        output_lineage={
            "binding_count": len(bindings),
            "sample_bindings": [
                {
                    "record_id": trace.record_id,
                    "opening_identity_id": trace.opening_identity_id,
                    "host_wall_id": trace.host_wall_id,
                    "member_wall_candidate_ids": list(
                        trace.member_wall_candidate_ids[:10]
                    ),
                }
                for trace in bindings[:10]
            ],
        },
    )

    frames = tuple(composition.host_frames)
    frame_ok = bool(frames) and all(
        _is_corrob(trace.status) and trace.record_id is not None for trace in frames
    )
    frame_reasons = tuple(
        dict.fromkeys(reason for trace in frames for reason in trace.reason_codes)
    )
    _emit(
        project=name,
        stage="OPENING_HOST_FRAME",
        file="pb_opening_host_frame_authority.py",
        class_function="OpeningHostFrameProducer.publish",
        status=(
            EvidenceResolutionStatus.CORROBORATED
            if frame_ok
            else EvidenceResolutionStatus.ABSTAINED
        ),
        reason_codes=frame_reasons,
        record_present=any(trace.record_id is not None for trace in frames),
        record_id=next(
            (trace.record_id for trace in frames if trace.record_id is not None),
            None,
        ),
        input_lineage={
            "binding_count": len(bindings),
            "sample_binding_record_ids": [
                trace.record_id for trace in bindings[:20]
            ],
        },
        output_lineage={
            "host_frame_count": len(frames),
            "sample_host_frames": [
                {
                    "record_id": trace.record_id,
                    "opening_identity_id": trace.opening_identity_id,
                    "host_wall_id": trace.host_wall_id,
                    "whole_wall_candidate_ids": list(
                        trace.whole_wall_candidate_ids[:10]
                    ),
                }
                for trace in frames[:10]
            ],
        },
    )

    if not visible_segments:
        first_failure = "SOURCE_VISIBILITY"
    elif (
        not _is_corrob(wall_result.status)
        or not wall_result.scope_complete
        or not wall_result.records
    ):
        first_failure = "PHYSICAL_WALL_CANDIDATE"
    elif len(identity_records) != len(wall_result.records) or not identity_records:
        first_failure = "PHYSICAL_WALL_IDENTITY"
    elif not physical_opening_ok:
        first_failure = "PHYSICAL_OPENING"
    elif not binding_ok:
        first_failure = "OPENING_HOST_BINDING"
    elif not frame_ok:
        first_failure = "OPENING_HOST_FRAME"
    else:
        first_failure = "DOWNSTREAM_AFTER_OPENING_HOST_FRAME"

    print(
        "FIRST_CAUSAL_FAILURE "
        + json.dumps(
            {
                "PROJECT": name,
                "STAGE": first_failure,
                "COMPOSITION_STATUS": _status(composition.status),
                "COMPOSITION_REASON_CODES": list(composition.reason_codes),
            },
            sort_keys=True,
        )
    )


def main() -> int:
    project_filter = str(os.environ.get("PROJECT_FILTER") or "").strip().upper()
    selected = tuple(
        case
        for case in CASES
        if not project_filter or str(case["name"]).upper() == project_filter
    )
    if not selected:
        raise SystemExit(f"unknown PROJECT_FILTER={project_filter!r}")
    for case in selected:
        diagnose(case)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
