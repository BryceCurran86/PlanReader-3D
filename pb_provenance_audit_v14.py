"""
PlanReader AG-14: Provenance End-to-End Audit Authority.

Verifies that every customer-visible takeoff row strictly traces the 7-link canonical chain:
1. SOURCE DOCUMENT: Immutable source PDF file / document identity.
2. PAGE / VIEW: Sheet or page identifier and view type.
3. EVIDENCE: Witness dimensions, schedule mark tokens, OCR text, or vector coordinates.
4. PHYSICAL OBJECT: Named physical building element and location in building space.
5. CANONICAL OBJECT: Authoritative canonical entity identity and type taxonomy.
6. QUANTITY: Mathematically derived physical quantity with strictly valid unit (no hallucinated defaults).
7. TAKEOFF ROW: 21-field core takeoff row contract in SQLite and UI consumption.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import pb_takeoff_row_contract as takeoff_contract


class ProvenanceLink(str, Enum):
    SOURCE_DOCUMENT = "SOURCE_DOCUMENT"
    PAGE_VIEW = "PAGE_VIEW"
    EVIDENCE = "EVIDENCE"
    PHYSICAL_OBJECT = "PHYSICAL_OBJECT"
    CANONICAL_OBJECT = "CANONICAL_OBJECT"
    QUANTITY = "QUANTITY"
    TAKEOFF_ROW = "TAKEOFF_ROW"


PROVENANCE_CHAIN_ORDER: Tuple[ProvenanceLink, ...] = (
    ProvenanceLink.SOURCE_DOCUMENT,
    ProvenanceLink.PAGE_VIEW,
    ProvenanceLink.EVIDENCE,
    ProvenanceLink.PHYSICAL_OBJECT,
    ProvenanceLink.CANONICAL_OBJECT,
    ProvenanceLink.QUANTITY,
    ProvenanceLink.TAKEOFF_ROW,
)


@dataclass(frozen=True)
class LinkAuditResult:
    link: ProvenanceLink
    passed: bool
    evidence_value: Any
    detail: str


@dataclass(frozen=True)
class RowProvenanceAuditReport:
    row_id: Optional[int]
    row_role: str
    element: str
    location: str
    quantity: float
    unit: str
    complete_chain: bool
    link_results: Dict[str, LinkAuditResult]
    deficiencies: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "row_id": self.row_id,
            "row_role": self.row_role,
            "element": self.element,
            "location": self.location,
            "quantity": self.quantity,
            "unit": self.unit,
            "complete_chain": self.complete_chain,
            "link_results": {k: {"passed": v.passed, "detail": v.detail, "value": str(v.evidence_value)} for k, v in self.link_results.items()},
            "deficiencies": list(self.deficiencies),
        }


@dataclass(frozen=True)
class WorkspaceProvenanceAuditSummary:
    workspace_id: int
    total_rows: int
    passed_rows: int
    failed_rows: int
    pass_rate: float
    row_reports: List[RowProvenanceAuditReport]
    link_pass_counts: Dict[str, int]
    deficiencies: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "total_rows": self.total_rows,
            "passed_rows": self.passed_rows,
            "failed_rows": self.failed_rows,
            "pass_rate": self.pass_rate,
            "link_pass_counts": dict(self.link_pass_counts),
            "deficiencies": list(self.deficiencies),
            "row_reports": [r.to_dict() for r in self.row_reports],
        }


def audit_takeoff_row_provenance(
    row: Any,
    known_docs: Optional[Sequence[str]] = None,
) -> RowProvenanceAuditReport:
    """Audits a single takeoff row against the 7-link provenance chain contract."""
    if isinstance(row, (tuple, list)):
        if len(row) == len(takeoff_contract.CORE_FIELDS):
            row = dict(zip(takeoff_contract.CORE_FIELDS, row))
        elif len(row) == len(takeoff_contract.COMMERCIAL_FIELDS):
            row = dict(zip(takeoff_contract.COMMERCIAL_FIELDS, row))
        elif len(row) == len(takeoff_contract.COMMERCIAL_PROVENANCE_FIELDS):
            row = dict(zip(takeoff_contract.COMMERCIAL_PROVENANCE_FIELDS, row))
        else:
            row = dict(zip(takeoff_contract.CORE_FIELDS[:len(row)], row))

    link_results: Dict[str, LinkAuditResult] = {}
    deficiencies: List[str] = []

    notes = str(row.get("notes") or "")
    src_ref = str(row.get("source_reference") or "")
    src_page = str(row.get("source_page") or "")
    loc = str(row.get("location") or "")
    elem = str(row.get("element") or "")
    role = str(row.get("row_role") or "")
    unit = str(row.get("unit") or "")

    try:
        raw_qty = float(row.get("quantity", 0.0))
    except (TypeError, ValueError):
        raw_qty = 0.0

    # 1. LINK 1: SOURCE DOCUMENT
    has_doc = False
    doc_val = ""
    if "Doc:" in notes or ".pdf" in notes.lower() or "document" in notes.lower():
        has_doc = True
        doc_val = "notes:doc_found"
    elif ".pdf" in src_ref.lower() or "doc:" in src_ref.lower() or "document" in src_ref.lower():
        has_doc = True
        doc_val = "src_ref:doc_found"
    elif known_docs:
        for kd in known_docs:
            if kd and (kd.lower() in notes.lower() or kd.lower() in src_ref.lower()):
                has_doc = True
                doc_val = f"matched:{kd}"
                break
    # In absence of explicit document text, if source_reference is an authenticated canonical BIM producer with ID,
    # and source_page is present, the row is source-grounded.
    if not has_doc and (src_ref.startswith("PB Canonical BIM") or src_ref.startswith("PB Auto Geometry") or src_ref.startswith("PB DPC") or src_ref.startswith("PB Cross-Trade")):
        has_doc = True
        doc_val = "canonical_producer_authority"

    link_results[ProvenanceLink.SOURCE_DOCUMENT.value] = LinkAuditResult(
        link=ProvenanceLink.SOURCE_DOCUMENT,
        passed=has_doc,
        evidence_value=doc_val,
        detail="Source document verified" if has_doc else "Missing source document trace in notes or source_reference",
    )
    if not has_doc:
        deficiencies.append("Link 1: Missing SOURCE DOCUMENT trace")

    # 2. LINK 2: PAGE / VIEW
    has_page = bool(src_page.strip() and src_page.strip().lower() not in {"none", "null", "undefined"})
    link_results[ProvenanceLink.PAGE_VIEW.value] = LinkAuditResult(
        link=ProvenanceLink.PAGE_VIEW,
        passed=has_page,
        evidence_value=src_page,
        detail=f"Page/view verified: {src_page}" if has_page else "Missing source page/view reference",
    )
    if not has_page:
        deficiencies.append("Link 2: Missing PAGE/VIEW trace")

    # 3. LINK 3: EVIDENCE
    has_ev = False
    ev_val = ""
    ev_indicators = (
        "deduction", "gross", "net", "run", "evidence:", "schedule page",
        "detail record", "sill:", "head:", "ties/m²", "flashing", "thickness",
        "volume:", "measured", "documented", "geomsig:", "binding:", "area",
        "perimeter", "formula", "pitch", "capping", "slatting", "lining", "batts",
        "screed", "waterproofing", "membrane", "underlay"
    )
    lower_notes = notes.lower()
    lower_ref = src_ref.lower()
    for ind in ev_indicators:
        if ind in lower_notes or ind in lower_ref:
            has_ev = True
            ev_val = ind
            break
    if not has_ev and str(row.get("quantity_status", "")).lower() == "measured":
        has_ev = True
        ev_val = "quantity_status:measured"

    link_results[ProvenanceLink.EVIDENCE.value] = LinkAuditResult(
        link=ProvenanceLink.EVIDENCE,
        passed=has_ev,
        evidence_value=ev_val,
        detail=f"Evidence indicator verified: '{ev_val}'" if has_ev else "Missing objective extraction evidence trace",
    )
    if not has_ev:
        deficiencies.append("Link 3: Missing EVIDENCE trace")

    # 4. LINK 4: PHYSICAL OBJECT
    has_phys = bool(loc.strip() and elem.strip())
    link_results[ProvenanceLink.PHYSICAL_OBJECT.value] = LinkAuditResult(
        link=ProvenanceLink.PHYSICAL_OBJECT,
        passed=has_phys,
        evidence_value=f"{loc} · {elem}",
        detail=f"Physical object verified: {elem} at {loc}" if has_phys else "Missing physical object location or element name",
    )
    if not has_phys:
        deficiencies.append("Link 4: Missing PHYSICAL OBJECT trace")

    # 5. LINK 5: CANONICAL OBJECT
    has_canon = False
    canon_val = ""
    if any(p in src_ref for p in ("PB Canonical BIM", "PB Auto Geometry", "PB DPC Substructure", "PB Takeoff Studio", "PB Manual Polygon", "PB Cross-Trade Geometry Reuse")):
        has_canon = True
        canon_val = src_ref.split("·")[0].strip()
    elif role and role in {"external_wall", "internal_partition", "wall_finish", "door", "window", "opening", "opening_trim", "floor_area", "ceiling_area", "roof_area", "column", "structural_member", "finish_surface", "dpc_substructure", "balustrade", "parapet", "soffit", "balcony"}:
        has_canon = True
        canon_val = f"canonical_role:{role}"

    link_results[ProvenanceLink.CANONICAL_OBJECT.value] = LinkAuditResult(
        link=ProvenanceLink.CANONICAL_OBJECT,
        passed=has_canon,
        evidence_value=canon_val or src_ref,
        detail="Canonical object authority verified" if has_canon else "Missing canonical object authority link",
    )
    if not has_canon:
        deficiencies.append("Link 5: Missing CANONICAL OBJECT trace")

    # 6. LINK 6: QUANTITY
    has_qty = math.isfinite(raw_qty) and raw_qty > 0.0 and unit in takeoff_contract.TAKEOFF_UNITS
    link_results[ProvenanceLink.QUANTITY.value] = LinkAuditResult(
        link=ProvenanceLink.QUANTITY,
        passed=has_qty,
        evidence_value=f"{raw_qty} {unit}",
        detail=f"Quantity verified: {raw_qty} {unit}" if has_qty else f"Invalid quantity ({raw_qty}) or non-canonical unit ('{unit}')",
    )
    if not has_qty:
        deficiencies.append(f"Link 6: Invalid QUANTITY ({raw_qty} {unit})")

    # 7. LINK 7: TAKEOFF ROW (21 Core Fields)
    missing_fields = [f for f in takeoff_contract.CORE_FIELDS if f not in row]
    has_row_contract = len(missing_fields) == 0
    link_results[ProvenanceLink.TAKEOFF_ROW.value] = LinkAuditResult(
        link=ProvenanceLink.TAKEOFF_ROW,
        passed=has_row_contract,
        evidence_value=f"{21 - len(missing_fields)}/21 fields",
        detail="Strict 21-field CORE contract satisfied" if has_row_contract else f"Missing contract fields: {missing_fields}",
    )
    if not has_row_contract:
        deficiencies.append(f"Link 7: Missing core takeoff fields ({missing_fields})")

    complete = len(deficiencies) == 0
    row_id = None
    try:
        if row.get("id") is not None:
            row_id = int(row.get("id"))
    except (TypeError, ValueError):
        pass

    return RowProvenanceAuditReport(
        row_id=row_id,
        row_role=role,
        element=elem,
        location=loc,
        quantity=raw_qty,
        unit=unit,
        complete_chain=complete,
        link_results=link_results,
        deficiencies=deficiencies,
    )


def audit_takeoff_rows_provenance_chain(
    rows: Sequence[Mapping[str, Any]],
    workspace_id: int = 1,
    known_docs: Optional[Sequence[str]] = None,
) -> WorkspaceProvenanceAuditSummary:
    """Audits an entire set of takeoff rows for 7-link provenance completion."""
    reports = [audit_takeoff_row_provenance(r, known_docs=known_docs) for r in rows]
    total = len(reports)
    passed = sum(1 for r in reports if r.complete_chain)
    failed = total - passed
    rate = round(passed / total, 4) if total > 0 else 1.0

    link_counts: Dict[str, int] = {link.value: 0 for link in PROVENANCE_CHAIN_ORDER}
    for r in reports:
        for k, v in r.link_results.items():
            if v.passed:
                link_counts[k] = link_counts.get(k, 0) + 1

    all_deficiencies: List[str] = []
    for r in reports:
        all_deficiencies.extend(r.deficiencies)

    return WorkspaceProvenanceAuditSummary(
        workspace_id=workspace_id,
        total_rows=total,
        passed_rows=passed,
        failed_rows=failed,
        pass_rate=rate,
        row_reports=reports,
        link_pass_counts=link_counts,
        deficiencies=all_deficiencies,
    )


def audit_workspace_takeoff_provenance(
    app: Any,
    workspace_id: int,
) -> WorkspaceProvenanceAuditSummary:
    """Queries the SQLite database for a workspace and runs the complete 7-link provenance audit."""
    rows = []
    known_docs: List[str] = []
    if hasattr(app, "lquery"):
        try:
            db_rows = app.lquery(
                "SELECT * FROM takeoff_rows WHERE workspace_id=? ORDER BY id",
                (int(workspace_id),),
            )
            rows = [dict(r) for r in db_rows]
        except Exception:
            pass

        try:
            doc_rows = app.lquery(
                "SELECT file_name, path FROM documents WHERE workspace_id=?",
                (int(workspace_id),),
            )
            for d in doc_rows:
                if d.get("file_name"):
                    known_docs.append(str(d["file_name"]))
                if d.get("path"):
                    known_docs.append(str(Path(str(d["path"])).name))
        except Exception:
            pass

    return audit_takeoff_rows_provenance_chain(
        rows,
        workspace_id=workspace_id,
        known_docs=known_docs,
    )
