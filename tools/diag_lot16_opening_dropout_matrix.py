from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

import fitz

from pb_live_opening_area_quantity_publication import (
    publish_live_opening_area_quantities,
)
from pb_live_physical_opening_void_composition import (
    compose_live_physical_opening_voids,
)
from pb_live_wall_opening_authority_composition import (
    compose_live_wall_opening_authority,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_floor_plan_page_scope import source_floor_plan_topology_scope
from pb_source_visibility_authority import SourceVisibilityProducer


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"


def state(value) -> str:
    return str(getattr(value, "value", value))


def reasons(rows, attr: str) -> dict[str, int]:
    out = Counter()
    for row in rows:
        out.update(str(x) for x in getattr(row, attr, ()) if str(x))
    return dict(out.most_common())


def statuses(rows, attr: str) -> dict[str, int]:
    return dict(Counter(state(getattr(row, attr)) for row in rows).most_common())


def area_gate(opening) -> tuple[str, ...]:
    failed = []
    canonical_id = str(opening.canonical_opening_id or "").strip()
    physical_id = str(opening.physical_opening_id or "").strip()
    viewport_id = str(opening.viewport_id or "").strip()
    host_wall_id = str(opening.host_wall_id or "").strip()
    host_binding = str(opening.host_binding_record_id or "").strip()
    host_frame = str(opening.host_frame_record_id or "").strip()
    kind = str(opening.opening_kind or "").strip().lower()
    basis = str(opening.area_basis or "").strip()
    evidence_ids = {str(x).strip() for x in opening.evidence_ids if str(x).strip()}

    if not canonical_id:
        failed.append("canonical_id")
    if canonical_id != physical_id:
        failed.append("physical_identity")
    if not viewport_id:
        failed.append("viewport")
    if not host_wall_id:
        failed.append("host_wall")
    if not (host_binding or host_frame):
        failed.append("host_record")
    if kind not in {"door", "window"}:
        failed.append("opening_kind")
    if not basis:
        failed.append("area_basis")
    if opening.area_m2 is None:
        failed.append("area_value")
    if not evidence_ids:
        failed.append("evidence")

    if basis == "figured_opening_label":
        rid = str(opening.figured_area_record_id or "").strip()
        if not rid or rid not in evidence_ids:
            failed.append("figured_area_record")
    elif basis == "resolved_opening_geometry":
        rid = str(opening.opening_void_record_id or "").strip()
        if not rid or rid not in evidence_ids:
            failed.append("opening_void_record")
    elif basis == "authenticated_elevation_frame":
        rid = str(opening.figured_area_record_id or "").strip()
        if not rid or rid not in evidence_ids:
            failed.append("elevation_frame_record")
    elif basis == "authenticated_frame_schedule":
        rid = str(opening.schedule_binding_record_id or "").strip()
        if not rid or rid not in evidence_ids:
            failed.append("schedule_binding_record")
        if str(opening.schedule_row_dimension_basis or "").strip().lower() != "frame":
            failed.append("schedule_frame_basis")
    elif basis:
        failed.append("unknown_area_basis")

    return tuple(failed)


def main() -> None:
    source_bytes = PDF.read_bytes()
    actual_sha = hashlib.sha256(source_bytes).hexdigest()
    if actual_sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {actual_sha}")

    doc = fitz.open(stream=source_bytes, filetype="pdf")
    try:
        page_count = int(doc.page_count)
    finally:
        doc.close()
    all_indices = tuple(range(page_count))
    scope = source_floor_plan_topology_scope(PDF, all_indices)
    topology_indices = (
        tuple(scope.topology_page_indices() or ())
        if scope is not None
        else all_indices
    )
    topology_page_ids = tuple(str(i + 1) for i in topology_indices)
    all_page_ids = tuple(str(i + 1) for i in all_indices)
    evidence_page_ids = tuple(p for p in all_page_ids if p not in topology_page_ids)

    source = SourceVisibilityProducer(
        producer_method="diag_lot16_opening_dropout_matrix",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="diag-lot16-opening-dropout-matrix",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=all_page_ids,
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=topology_page_ids,
        evidence_page_ids=evidence_page_ids,
    )
    voids = compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )
    quantities = publish_live_opening_area_quantities(voids)

    semantic = wall_opening.semantic_enumeration_result
    semantic_record = semantic.record
    universe = wall_opening.opening_universe_result

    trace_stage = {}
    for stage in ("width", "schedule_binding", "height", "vertical", "scale", "void"):
        trace_stage[stage] = {
            "status": statuses(voids.traces, f"{stage}_status"),
            "reasons": reasons(voids.traces, f"{stage}_reason_codes"),
        }

    canonical = tuple(voids.canonical_openings)
    gate_combo = Counter()
    gate_individual = Counter()
    kind = Counter()
    pattern = Counter()
    area_basis = Counter()
    type_marks = Counter()
    presence = Counter()
    examples = []
    for opening in canonical:
        failures = area_gate(opening)
        gate_combo["|".join(failures) if failures else "ELIGIBLE"] += 1
        gate_individual.update(failures)
        kind[str(opening.opening_kind or "<none>")] += 1
        pattern[str(opening.structural_pattern or "<none>")] += 1
        area_basis[str(opening.area_basis or "<none>")] += 1
        type_marks[str(opening.type_mark or "<none>")] += 1
        for key, flag in {
            "host_wall": bool(opening.host_wall_id),
            "host_binding": bool(opening.host_binding_record_id),
            "host_frame": bool(opening.host_frame_record_id),
            "type_mark": bool(opening.type_mark),
            "schedule_binding": bool(opening.schedule_binding_record_id),
            "schedule_count_explicit": bool(opening.schedule_count_explicit),
            "width": opening.width_m is not None,
            "height": opening.height_m is not None,
            "area": opening.area_m2 is not None,
            "geometry_complete": bool(opening.geometry_complete),
            "scale": bool(opening.scale_record_id),
        }.items():
            if flag:
                presence[key] += 1
        if failures and len(examples) < 25:
            examples.append({
                "id": opening.canonical_opening_id,
                "pattern": opening.structural_pattern,
                "kind": opening.opening_kind,
                "type_mark": opening.type_mark,
                "host_wall_id": opening.host_wall_id,
                "host_binding_record_id": opening.host_binding_record_id,
                "host_frame_record_id": opening.host_frame_record_id,
                "width_m": opening.width_m,
                "height_m": opening.height_m,
                "area_m2": opening.area_m2,
                "area_basis": opening.area_basis,
                "schedule_binding_record_id": opening.schedule_binding_record_id,
                "schedule_declared_width_mm": opening.schedule_declared_width_mm,
                "schedule_declared_height_mm": opening.schedule_declared_height_mm,
                "schedule_declared_count": opening.schedule_declared_count,
                "schedule_count_explicit": opening.schedule_count_explicit,
                "geometry_complete": opening.geometry_complete,
                "failures": list(failures),
            })

    payload = {
        "source_sha256": actual_sha,
        "topology_page_ids": topology_page_ids,
        "evidence_page_count": len(evidence_page_ids),
        "wall_opening_status": state(wall_opening.status),
        "wall_opening_reason_codes": list(wall_opening.reason_codes),
        "semantic_status": state(semantic.status),
        "semantic_reason_codes": list(semantic.reason_codes),
        "semantic_physical_opening_universe_complete": (
            bool(semantic_record.physical_opening_universe_complete)
            if semantic_record is not None
            else None
        ),
        "semantic_physical_opening_count": (
            len(semantic_record.physical_opening_record_ids)
            if semantic_record is not None
            else 0
        ),
        "semantic_representative_count": (
            len(semantic_record.representative_observation_ids)
            if semantic_record is not None
            else 0
        ),
        "universe_status": state(universe.status),
        "universe_reason_codes": list(universe.reason_codes),
        "opening_bindings": {
            "count": len(wall_opening.opening_bindings),
            "status": statuses(wall_opening.opening_bindings, "status"),
            "reasons": reasons(wall_opening.opening_bindings, "reason_codes"),
            "with_host_wall": sum(bool(x.host_wall_id) for x in wall_opening.opening_bindings),
        },
        "host_frames": {
            "count": len(wall_opening.host_frames),
            "status": statuses(wall_opening.host_frames, "status"),
            "reasons": reasons(wall_opening.host_frames, "reason_codes"),
            "with_host_wall": sum(bool(x.host_wall_id) for x in wall_opening.host_frames),
        },
        "void_composition_status": state(voids.status),
        "void_composition_reason_codes": list(voids.reason_codes),
        "trace_count": len(voids.traces),
        "trace_stage": trace_stage,
        "canonical_count": len(canonical),
        "canonical_kind": dict(kind.most_common()),
        "canonical_structural_pattern": dict(pattern.most_common()),
        "canonical_area_basis": dict(area_basis.most_common()),
        "canonical_type_marks": dict(type_marks.most_common()),
        "canonical_presence": dict(presence),
        "area_gate_individual_failures": dict(gate_individual.most_common()),
        "area_gate_combinations": dict(gate_combo.most_common()),
        "published_area_quantity_count": len(quantities),
        "published_area_quantities": [
            {
                "quantity_id": q.quantity_id,
                "semantic_key": q.semantic_key,
                "value": q.value,
                "unit": q.unit,
                "authority": q.authority,
                "input_entity_ids": list(q.input_entity_ids),
            }
            for q in quantities
        ],
        "sample_failed_openings": examples,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
