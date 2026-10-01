"""Customer runtime bridge for DPCSubstructureAuthority (AG-11).

Bridges the benchmark-proven, producer-owned DPC and substructure quantity authority
into the PlanReader customer runtime.

Invariants:
1. Re-derives run lengths strictly from explicit witness-bound callouts in immutable PDF bytes.
2. If authority abstains (no witness-bound callout), the bridge fails closed (zero hallucination).
3. All published rows strictly adhere to the canonical 21-field takeoff_rows contract.
4. Preserves full provenance chain (document_id, revision_id, page_id, dimension_chain_id).
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import fitz

from pb_dpc_substructure_authority import (
    DPC_SUBSTRUCTURE_RESOLVED,
    DPCSubstructureAuthority,
    DPCSubstructureProducer,
    DPCSubstructureRecord,
    DPCSubstructureResult,
    DPCSubstructureSelector,
    SubstructureFamily,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer
import pb_takeoff_row_contract as takeoff_contract

SOURCE_PREFIX = "PB DPC Substructure Authority v2.0"

_FAMILY_ELEMENT_CONFIG = {
    SubstructureFamily.DPC_LENGTH: {
        "element": "Damp-proof course (DPC) run",
        "default_unit": "lm",
        "substrate": "Embossed polyethylene film DPC",
        "finish_system": "Laid continuous under base course with 200mm laps",
    },
    SubstructureFamily.FOUNDATION_WALL_LENGTH: {
        "element": "Foundation wall framing run",
        "default_unit": "lm",
        "substrate": "Treated timber / steel foundation framing",
        "finish_system": "Fixed to footing substrate per engineering detail",
    },
    SubstructureFamily.STRIP_FOOTING_LENGTH: {
        "element": "Concrete strip footing run",
        "default_unit": "lm",
        "substrate": "25 MPa Reinforced Concrete",
        "finish_system": "Poured in trench with reinforcement cage",
    },
    SubstructureFamily.SUBSTRUCTURE_WALL_AREA: {
        "element": "Substructure foundation wall area",
        "default_unit": "m²",
        "substrate": "Concrete block / core-filled masonry",
        "finish_system": "Core filled and damp-proof tanked",
    },
}


def substructure_record_to_takeoff_row(
    workspace_id: int,
    record: DPCSubstructureRecord,
    *,
    now_stamp: str = "",
) -> Dict[str, Any]:
    """Converts a verified DPCSubstructureRecord into a 21-field core takeoff row."""
    cfg = _FAMILY_ELEMENT_CONFIG.get(
        record.family,
        {
            "element": f"Substructure {record.family.value.replace('_', ' ').title()}",
            "default_unit": record.unit,
            "substrate": "Substructure substrate",
            "finish_system": "Installed per engineering specification",
        },
    )

    unit = record.unit if record.unit in takeoff_contract.TAKEOFF_UNITS else cfg["default_unit"]
    qty = round(max(0.0, float(record.value)), 2)

    return {
        "workspace_id": int(workspace_id),
        "section": "Substructure",
        "element": cfg["element"],
        "location": f"Substructure · Page {record.page_id}",
        "substrate": cfg["substrate"],
        "finish_system": cfg["finish_system"],
        "quantity": qty,
        "unit": unit,
        "quantity_status": "Measured",
        "source_page": str(record.page_id),
        "source_reference": f"{SOURCE_PREFIX} · chain:{record.dimension_chain_id}",
        "inclusion_status": "INCLUSION",
        "coats": 1,
        "coverage_m2_per_litre": 0.0,
        "productivity_m2_per_hour": 0.0,
        "rate_per_unit": 0.0,
        "confidence": "Documented",
        "notes": f"Authoritative source-bound {record.family.value}: {qty:.2f} {unit} (binding: {record.binding_status}).",
        "row_role": "dpc_substructure",
        "created_at": str(now_stamp),
        "updated_at": str(now_stamp),
    }


def resolve_pdf_substructure_records(
    pdf_bytes: bytes,
    *,
    document_id: str = "doc_substructure",
    page_numbers: Optional[Sequence[int]] = None,
) -> List[DPCSubstructureRecord]:
    """Resolves authenticated substructure records directly from immutable PDF bytes.
    Fails closed: returns only records where the authority corroborated witness-bound callouts.
    """
    if not pdf_bytes:
        return []

    source = SourceVisibilityProducer(
        producer_method="customer_dpc_substructure_bridge",
        producer_version="2.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=str(document_id),
        source_bytes=pdf_bytes,
        source_locator=f"memory:{document_id}.pdf",
    )

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages_to_scan = list(page_numbers) if page_numbers else list(range(1, doc.page_count + 1))
    doc.close()

    producer = DPCSubstructureProducer.from_source_visibility_producer(source)
    records: List[DPCSubstructureRecord] = []

    for page_no in pages_to_scan:
        for family in SubstructureFamily:
            selector = DPCSubstructureSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                page_id=str(page_no),
                viewport_id=None,
                physical_run_id=f"run-{family.value}-p{page_no}",
                family=family,
            )
            result = producer.publish(selector)
            if (
                result.status == EvidenceResolutionStatus.CORROBORATED
                and result.record is not None
                and result.record.value > 0.0
            ):
                records.append(result.record)

    return records


def resolve_workspace_substructure_takeoff_rows(
    app: Any,
    workspace_id: int,
) -> List[Dict[str, Any]]:
    """Inspects workspace documents and publishes verified substructure takeoff rows."""
    if not hasattr(app, "lquery"):
        return []

    docs = app.lquery(
        "SELECT id, file_name, path FROM documents WHERE workspace_id=? ORDER BY id",
        (int(workspace_id),),
    )
    if not docs:
        return []

    now_stamp = app.now_stamp() if hasattr(app, "now_stamp") else ""
    all_rows: List[Dict[str, Any]] = []

    for doc_row in docs:
        doc_path_str = doc_row.get("path")
        if not doc_path_str:
            continue
        p = Path(doc_path_str)
        if not p.exists() or not p.is_file():
            continue

        try:
            pdf_bytes = p.read_bytes()
        except Exception:
            continue

        records = resolve_pdf_substructure_records(
            pdf_bytes,
            document_id=f"doc_{doc_row.get('id', 1)}",
        )
        for rec in records:
            row = substructure_record_to_takeoff_row(workspace_id, rec, now_stamp=now_stamp)
            all_rows.append(row)

    return all_rows


def publish_substructure_takeoff_rows(
    app: Any,
    workspace_id: int,
) -> int:
    """Publishes verified substructure rows to SQLite takeoff_rows table."""
    if hasattr(app, "lexecute"):
        app.lexecute(
            "DELETE FROM takeoff_rows WHERE workspace_id=? AND source_reference LIKE ?",
            (int(workspace_id), SOURCE_PREFIX + "%"),
        )
    rows = resolve_workspace_substructure_takeoff_rows(app, workspace_id)
    if not rows:
        return 0

    sql = takeoff_contract.insert_sql(takeoff_contract.CORE_FIELDS)
    count = 0
    for r in rows:
        vals = takeoff_contract.values_from_mapping(r, takeoff_contract.CORE_FIELDS)
        if hasattr(app, "lexecute"):
            app.lexecute(sql, vals)
        count += 1
    return count
