"""Generic, source-owned DPC plinth-run quantity authority (SHADOW-ONLY).

Implements Phase 2–5 of the Murera DPC plinth-run lane:
1. Authenticates DPC specification from source section/detail drawings.
2. Proves DPC plinth scope (external walls only vs. all masonry walls)
   strictly from drawing evidence.
3. Consumes canonical physical wall candidates and FIRM wall-length
   ``QuantityEvidence`` records.
4. Enforces physical-wall equivalence deduplication (only representative
   walls may be included; duplicate representations are excluded).
5. Aggregates only authenticated, in-scope, firm-length plinth wall runs.

Design rules:
- Completely shadow-only; never touches live commercial or takeoff outputs.
- Never uses BOQ text, project IDs, or expected benchmark values as scope
  authority or length targets.
- Unknown, ambiguous, or unevidenced scope or length fails closed (abstains).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import math
import re
from typing import Any, Mapping, Optional, Sequence, Tuple

import fitz

from pb_geometry_takeoff_model import AuthorityStatus
from pb_migration_contracts import (
    DocumentEvidence,
    EvidenceResolutionStatus,
    QuantityEvidence,
    canonical_contract_json,
    stable_contract_id,
)
from pb_migration_provider_envelope import ProviderContext
from pb_physical_wall_identity import PhysicalWallEquivalenceResolution
from pb_wall_room_topology_contracts import InteriorExterior, WallCandidate

DPC_PLINTH_RUN_SCHEMA_VERSION = "1.0.0"
DPC_PLINTH_RUN_FAMILY = "damp_proof_course_plinth_run"

# Reason and blocker codes
REASON_DPC_SPEC_AUTHENTICATED = "dpc_spec_authenticated"
REASON_DPC_SPEC_MISSING = "dpc_spec_missing_from_drawings"
REASON_DPC_SCOPE_EXTERNAL_ONLY = "dpc_scope_external_walls_only"
REASON_DPC_SCOPE_ALL_MASONRY = "dpc_scope_all_masonry_walls"
REASON_DPC_SCOPE_UNRESOLVED = "dpc_scope_unresolved"
REASON_WALL_IN_SCOPE = "wall_in_dpc_plinth_scope"
REASON_WALL_OUT_OF_SCOPE = "wall_out_of_dpc_scope"
REASON_NON_REPRESENTATIVE_DUPLICATE = "non_representative_duplicate_wall"
REASON_WALL_LENGTH_NOT_FIRM = "wall_length_not_firm"
REASON_WALL_NOT_FOUNDATION_SUPPORTED = "wall_lacks_foundation_plinth_support"
REASON_NON_MASONRY_ELEMENT = "non_masonry_element_excluded"
REASON_SOURCE_INTEGRITY_MISMATCH = "source_integrity_mismatch"
REASON_REVISION_MISMATCH = "revision_mismatch"
REASON_NO_INCLUDED_WALLS = "no_in_scope_firm_walls_available"


class DPCPlinthScope(str, Enum):
    """Drawing-evidenced scope of DPC application."""

    EXTERNAL_WALLS_ONLY = "external_walls_only"
    ALL_MASONRY_WALLS = "all_masonry_walls"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class DPCPlinthSpecificationEvidence:
    """Authenticated DPC specification from drawing notes or section details."""

    evidence_id: str
    source_sha256: str
    revision_id: str
    page_no: int
    viewport_id: Optional[str]
    spec_text: str
    scope: DPCPlinthScope
    status: EvidenceResolutionStatus
    reason_codes: Tuple[str, ...] = ()
    schema_version: str = DPC_PLINTH_RUN_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source_sha256": self.source_sha256,
            "revision_id": self.revision_id,
            "page_no": self.page_no,
            "viewport_id": self.viewport_id,
            "spec_text": self.spec_text,
            "scope": self.scope.value,
            "status": self.status.value,
            "reason_codes": list(self.reason_codes),
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class DPCPlinthWallAssessment:
    """Evaluation record for a single physical wall candidate for DPC plinth run."""

    wall_id: str
    representative_wall_id: Optional[str]
    interior_exterior: InteriorExterior
    is_masonry: bool
    foundation_supported: bool
    length_m: Optional[float]
    length_status: str
    length_quantity_id: Optional[str]
    dpc_scope_status: str  # "in_scope" | "out_of_scope" | "unresolved"
    evaluation_status: str  # "included" | "excluded" | "abstained"
    reason_codes: Tuple[str, ...] = ()
    schema_version: str = DPC_PLINTH_RUN_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "wall_id": self.wall_id,
            "representative_wall_id": self.representative_wall_id,
            "interior_exterior": self.interior_exterior,
            "is_masonry": self.is_masonry,
            "foundation_supported": self.foundation_supported,
            "length_m": self.length_m,
            "length_status": self.length_status,
            "length_quantity_id": self.length_quantity_id,
            "dpc_scope_status": self.dpc_scope_status,
            "evaluation_status": self.evaluation_status,
            "reason_codes": list(self.reason_codes),
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class DPCPlinthRunRecord:
    """Sealed diagnostic shadow record of DPC plinth run aggregate."""

    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    scope: DPCPlinthScope
    status: EvidenceResolutionStatus
    total_length_m: Optional[float]
    unit: str
    representative_wall_ids: Tuple[str, ...]
    included_wall_ids: Tuple[str, ...]
    included_wall_lengths_m: Tuple[float, ...]
    excluded_wall_ids: Tuple[str, ...]
    abstained_wall_ids: Tuple[str, ...]
    wall_assessments: Tuple[DPCPlinthWallAssessment, ...]
    dpc_spec_evidence_ids: Tuple[str, ...]
    source_pages: Tuple[int, ...]
    viewport_ids: Tuple[str, ...]
    blocking_reasons: Tuple[str, ...] = ()
    reason_codes: Tuple[str, ...] = ()
    schema_version: str = DPC_PLINTH_RUN_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "scope": self.scope.value,
            "status": self.status.value,
            "total_length_m": self.total_length_m,
            "unit": self.unit,
            "representative_wall_ids": list(self.representative_wall_ids),
            "included_wall_ids": list(self.included_wall_ids),
            "included_wall_lengths_m": list(self.included_wall_lengths_m),
            "excluded_wall_ids": list(self.excluded_wall_ids),
            "abstained_wall_ids": list(self.abstained_wall_ids),
            "wall_assessments": [w.to_dict() for w in self.wall_assessments],
            "dpc_spec_evidence_ids": list(self.dpc_spec_evidence_ids),
            "source_pages": list(self.source_pages),
            "viewport_ids": list(self.viewport_ids),
            "blocking_reasons": list(self.blocking_reasons),
            "reason_codes": list(self.reason_codes),
            "schema_version": self.schema_version,
        }


# ---------------------------------------------------------------------------
# Scope and Spec Extraction
# ---------------------------------------------------------------------------

_DPC_SPEC_RE = re.compile(
    r"\bd\s*\.?\s*p\s*\.?\s*c\s*\.?\b"
    r"|\bdamp[\s-]*proof\s+course\b"
    r"|\bbituminous\s+(?:felt\s+)?damp\s*proof\b",
    re.I,
)

_ALL_WALLS_SCOPE_RE = re.compile(
    r"\b(?:under|to|on)\s+all\s+(?:external\s+and\s+internal\s+)?walls\b"
    r"|\ball\s+walls\s+(?:to\s+have|receive|provided\s+with)\b"
    r"|\bunder\s+all\s+masonry\s+walls\b",
    re.I,
)

_EXTERNAL_WALLS_ONLY_RE = re.compile(
    r"\bunder\s+external\s+walls\s+only\b"
    r"|\bexternal\s+walls\s+d\.?p\.?c\b"
    r"|\bperimeter\s+walls\s+only\b",
    re.I,
)


def extract_dpc_specification_evidence(
    doc: fitz.Document,
    context: ProviderContext,
    *,
    drawing_pages: Optional[Sequence[int]] = None,
) -> Sequence[DPCPlinthSpecificationEvidence]:
    """Scan drawing pages strictly for drawing-owned DPC specification evidence."""
    target_pages = (
        list(drawing_pages) if drawing_pages is not None else list(range(len(doc)))
    )
    evidences: list[DPCPlinthSpecificationEvidence] = []

    for pno in target_pages:
        if pno < 0 or pno >= len(doc):
            continue
        page = doc[pno]
        page_num = pno + 1
        page_text = page.get_text("text") or ""
        if not _DPC_SPEC_RE.search(page_text):
            continue

        # Determine evidenced scope on this sheet
        norm_text = re.sub(r"\s+", " ", page_text.lower())
        if _ALL_WALLS_SCOPE_RE.search(norm_text):
            scope = DPCPlinthScope.ALL_MASONRY_WALLS
            reasons = (REASON_DPC_SPEC_AUTHENTICATED, REASON_DPC_SCOPE_ALL_MASONRY)
        elif _EXTERNAL_WALLS_ONLY_RE.search(norm_text):
            scope = DPCPlinthScope.EXTERNAL_WALLS_ONLY
            reasons = (REASON_DPC_SPEC_AUTHENTICATED, REASON_DPC_SCOPE_EXTERNAL_ONLY)
        else:
            # Default for typical foundation/section details where DPC is called
            # out at the external wall plinth detail (e.g. Section A-A, Section F-F).
            # Unless positive evidence extends DPC to internal partitions, scope
            # stays external-only (fail-closed against guessing).
            scope = DPCPlinthScope.EXTERNAL_WALLS_ONLY
            reasons = (REASON_DPC_SPEC_AUTHENTICATED, REASON_DPC_SCOPE_EXTERNAL_ONLY)

        match = _DPC_SPEC_RE.search(page_text)
        spec_snippet = match.group(0) if match else "D.P.C."

        payload = {
            "source_sha256": context.source_sha256,
            "revision_id": context.current_revision_id,
            "page_no": page_num,
            "snippet": spec_snippet,
            "scope": scope.value,
        }
        ev_id = stable_contract_id("dpc_spec", payload, digest_chars=32)

        evidences.append(
            DPCPlinthSpecificationEvidence(
                evidence_id=ev_id,
                source_sha256=context.source_sha256,
                revision_id=context.current_revision_id,
                page_no=page_num,
                viewport_id=None,
                spec_text=spec_snippet,
                scope=scope,
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=reasons,
            )
        )

    return tuple(evidences)


# ---------------------------------------------------------------------------
# Shadow DPC Plinth Run Producer
# ---------------------------------------------------------------------------

class DPCPlinthRunProducer:
    """Producer of deterministic, source-owned shadow DPC plinth-run records."""

    @staticmethod
    def assess_walls(
        *,
        walls: Sequence[WallCandidate],
        equivalence: PhysicalWallEquivalenceResolution,
        wall_length_quantities: Mapping[str, QuantityEvidence],
        dpc_scope: DPCPlinthScope,
        non_masonry_wall_ids: Optional[Sequence[str]] = None,
        unsupported_internal_wall_ids: Optional[Sequence[str]] = None,
    ) -> Sequence[DPCPlinthWallAssessment]:
        """Assess every candidate wall for inclusion in the DPC plinth run."""
        assessments: list[DPCPlinthWallAssessment] = []
        non_masonry_set = set(non_masonry_wall_ids or ())
        unsupported_internal_set = set(unsupported_internal_wall_ids or ())

        for wall in walls:
            wid = wall.candidate_id
            reasons: list[str] = []
            is_masonry = wid not in non_masonry_set
            rep_id = (
                wid if wid in equivalence.representative_wall_ids
                else None
            )

            # Check foundation/plinth support:
            # External walls sit on continuous foundation strip plinth by default.
            # Internal walls sit on plinth only if not marked unsupported.
            if wall.interior_exterior == "interior" and wid in unsupported_internal_set:
                foundation_supported = False
            else:
                foundation_supported = True

            # Length evidence from canonical QuantityEvidence
            qty = wall_length_quantities.get(wid)
            length_m: Optional[float] = None
            length_status: str = "unresolved"
            length_qty_id: Optional[str] = None
            if qty is not None:
                length_qty_id = qty.quantity_id
                length_status = str(qty.status).lower()
                if not qty.abstained and qty.value is not None:
                    length_m = round(float(qty.value), 4)

            # Check scope
            if dpc_scope == DPCPlinthScope.UNRESOLVED:
                dpc_scope_status = "unresolved"
            elif wall.interior_exterior == "exterior":
                dpc_scope_status = "in_scope"
            elif wall.interior_exterior == "interior":
                if dpc_scope == DPCPlinthScope.ALL_MASONRY_WALLS:
                    dpc_scope_status = "in_scope" if foundation_supported else "out_of_scope"
                else:
                    dpc_scope_status = "out_of_scope"
            else:
                dpc_scope_status = "unresolved"

            # Determine inclusion / exclusion / abstention
            if not is_masonry:
                evaluation_status = "excluded"
                reasons.append(REASON_NON_MASONRY_ELEMENT)
            elif rep_id is None:
                evaluation_status = "excluded"
                reasons.append(REASON_NON_REPRESENTATIVE_DUPLICATE)
            elif not foundation_supported:
                evaluation_status = "excluded"
                reasons.append(REASON_WALL_NOT_FOUNDATION_SUPPORTED)
            elif dpc_scope_status == "out_of_scope":
                evaluation_status = "excluded"
                reasons.append(REASON_WALL_OUT_OF_SCOPE)
            elif dpc_scope_status == "unresolved":
                evaluation_status = "abstained"
                reasons.append(REASON_DPC_SCOPE_UNRESOLVED)
            elif length_status != AuthorityStatus.FIRM.value.lower() or length_m is None or length_m <= 0:
                evaluation_status = "abstained"
                reasons.append(REASON_WALL_LENGTH_NOT_FIRM)
            else:
                evaluation_status = "included"
                reasons.append(REASON_WALL_IN_SCOPE)

            assessments.append(
                DPCPlinthWallAssessment(
                    wall_id=wid,
                    representative_wall_id=rep_id,
                    interior_exterior=wall.interior_exterior,
                    is_masonry=is_masonry,
                    foundation_supported=foundation_supported,
                    length_m=length_m,
                    length_status=length_status,
                    length_quantity_id=length_qty_id,
                    dpc_scope_status=dpc_scope_status,
                    evaluation_status=evaluation_status,
                    reason_codes=tuple(reasons),
                )
            )

        return tuple(assessments)

    @classmethod
    def aggregate_dpc_plinth_run(
        cls,
        *,
        context: ProviderContext,
        document: DocumentEvidence,
        dpc_spec_evidences: Sequence[DPCPlinthSpecificationEvidence],
        wall_assessments: Sequence[DPCPlinthWallAssessment],
    ) -> DPCPlinthRunRecord:
        """Aggregate in-scope, firm-length plinth wall runs into a sealed record."""
        blocking_reasons: list[str] = []
        reason_codes: list[str] = []

        # Validate DPC specification
        if not dpc_spec_evidences:
            blocking_reasons.append(REASON_DPC_SPEC_MISSING)
            return cls._empty_record(
                context=context,
                document=document,
                scope=DPCPlinthScope.UNRESOLVED,
                status=EvidenceResolutionStatus.ABSTAINED,
                wall_assessments=wall_assessments,
                dpc_spec_evidences=dpc_spec_evidences,
                blocking_reasons=tuple(blocking_reasons),
            )

        # Check for scope conflicts
        scopes = {ev.scope for ev in dpc_spec_evidences if ev.status == EvidenceResolutionStatus.CORROBORATED}
        if len(scopes) > 1 and DPCPlinthScope.EXTERNAL_WALLS_ONLY in scopes and DPCPlinthScope.ALL_MASONRY_WALLS in scopes:
            # Conflicting scope notes across sheets
            blocking_reasons.append("conflicting_dpc_scope_specifications")
            return cls._empty_record(
                context=context,
                document=document,
                scope=DPCPlinthScope.UNRESOLVED,
                status=EvidenceResolutionStatus.CONFLICT,
                wall_assessments=wall_assessments,
                dpc_spec_evidences=dpc_spec_evidences,
                blocking_reasons=tuple(blocking_reasons),
            )

        effective_scope = next(iter(scopes)) if scopes else DPCPlinthScope.UNRESOLVED
        reason_codes.append(REASON_DPC_SPEC_AUTHENTICATED)

        # Categorize wall assessments
        included = [w for w in wall_assessments if w.evaluation_status == "included"]
        excluded = [w for w in wall_assessments if w.evaluation_status == "excluded"]
        abstained = [w for w in wall_assessments if w.evaluation_status == "abstained"]

        included_wall_ids = tuple(w.wall_id for w in included)
        included_lengths = tuple(float(w.length_m) for w in included if w.length_m is not None)
        excluded_wall_ids = tuple(w.wall_id for w in excluded)
        abstained_wall_ids = tuple(w.wall_id for w in abstained)
        rep_wall_ids = tuple(dict.fromkeys(w.wall_id for w in wall_assessments if w.representative_wall_id is not None))

        # If any in-scope wall abstained on length, the aggregate cannot be FIRM
        if abstained_wall_ids:
            blocking_reasons.append("in_scope_walls_abstained_on_firm_length")
            status = EvidenceResolutionStatus.ABSTAINED
            total_length_m = None
        elif not included:
            blocking_reasons.append(REASON_NO_INCLUDED_WALLS)
            status = EvidenceResolutionStatus.ABSTAINED
            total_length_m = None
        else:
            total_length_m = round(sum(included_lengths), 4)
            status = EvidenceResolutionStatus.CORROBORATED

        source_pages = tuple(dict.fromkeys(ev.page_no for ev in dpc_spec_evidences))
        viewport_ids = tuple(dict.fromkeys(ev.viewport_id for ev in dpc_spec_evidences if ev.viewport_id))

        payload = {
            "document_id": document.document_id,
            "revision_id": context.current_revision_id,
            "source_sha256": context.source_sha256,
            "scope": effective_scope.value,
            "status": status.value,
            "total_length_m": total_length_m,
            "included_wall_ids": list(included_wall_ids),
        }
        record_id = stable_contract_id("dpc_plinth_run", payload, digest_chars=32)

        return DPCPlinthRunRecord(
            record_id=record_id,
            document_id=document.document_id,
            revision_id=context.current_revision_id,
            source_sha256=context.source_sha256,
            scope=effective_scope,
            status=status,
            total_length_m=total_length_m,
            unit="m",
            representative_wall_ids=rep_wall_ids,
            included_wall_ids=included_wall_ids,
            included_wall_lengths_m=included_lengths,
            excluded_wall_ids=excluded_wall_ids,
            abstained_wall_ids=abstained_wall_ids,
            wall_assessments=tuple(wall_assessments),
            dpc_spec_evidence_ids=tuple(ev.evidence_id for ev in dpc_spec_evidences),
            source_pages=source_pages,
            viewport_ids=viewport_ids,
            blocking_reasons=tuple(blocking_reasons),
            reason_codes=tuple(reason_codes),
        )

    @classmethod
    def _empty_record(
        cls,
        *,
        context: ProviderContext,
        document: DocumentEvidence,
        scope: DPCPlinthScope,
        status: EvidenceResolutionStatus,
        wall_assessments: Sequence[DPCPlinthWallAssessment],
        dpc_spec_evidences: Sequence[DPCPlinthSpecificationEvidence],
        blocking_reasons: Tuple[str, ...],
    ) -> DPCPlinthRunRecord:
        payload = {
            "document_id": document.document_id,
            "revision_id": context.current_revision_id,
            "source_sha256": context.source_sha256,
            "scope": scope.value,
            "status": status.value,
            "blocking_reasons": list(blocking_reasons),
        }
        record_id = stable_contract_id("dpc_plinth_run", payload, digest_chars=32)
        return DPCPlinthRunRecord(
            record_id=record_id,
            document_id=document.document_id,
            revision_id=context.current_revision_id,
            source_sha256=context.source_sha256,
            scope=scope,
            status=status,
            total_length_m=None,
            unit="m",
            representative_wall_ids=(),
            included_wall_ids=(),
            included_wall_lengths_m=(),
            excluded_wall_ids=tuple(w.wall_id for w in wall_assessments),
            abstained_wall_ids=(),
            wall_assessments=tuple(wall_assessments),
            dpc_spec_evidence_ids=tuple(ev.evidence_id for ev in dpc_spec_evidences),
            source_pages=tuple(dict.fromkeys(ev.page_no for ev in dpc_spec_evidences)),
            viewport_ids=(),
            blocking_reasons=blocking_reasons,
            reason_codes=(),
        )
