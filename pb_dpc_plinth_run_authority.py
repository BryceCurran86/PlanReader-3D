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
- Unknown material status fails closed (abstains); absence of negative
  evidence does not prove masonry.
- Foundation/plinth relationship must be positive source-owned evidence;
  exterior role alone does not prove foundation support.
- All consumed QuantityEvidence records are strictly revalidated against
  source, revision, entity identity, equivalence, unit, and family before use.
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
REASON_FOUNDATION_SUPPORT_UNRESOLVED = "foundation_support_unresolved"
REASON_NON_MASONRY_ELEMENT = "non_masonry_element_excluded"
REASON_WALL_MATERIAL_UNRESOLVED = "wall_material_unresolved"
REASON_SOURCE_INTEGRITY_MISMATCH = "source_integrity_mismatch"
REASON_REVISION_MISMATCH = "revision_mismatch"
REASON_NO_INCLUDED_WALLS = "no_in_scope_firm_walls_available"
REASON_QUANTITY_WRONG_FAMILY = "quantity_wrong_family"
REASON_QUANTITY_WRONG_UNIT = "quantity_wrong_unit"
REASON_QUANTITY_WRONG_ENTITY = "quantity_wrong_entity"
REASON_EQUIVALENCE_BLOCKER = "equivalence_blocker_present"
REASON_STALE_QUANTITY_REVISION = "stale_quantity_revision"


class DPCPlinthScope(str, Enum):
    """Drawing-evidenced scope of DPC application."""

    EXTERNAL_WALLS_ONLY = "external_walls_only"
    ALL_MASONRY_WALLS = "all_masonry_walls"
    UNRESOLVED = "unresolved"


class WallMaterialStatus(str, Enum):
    """Drawing-evidenced material classification for wall candidate."""

    MASONRY = "masonry"
    NON_MASONRY = "non_masonry"
    UNRESOLVED = "unresolved"


class FoundationSupportStatus(str, Enum):
    """Drawing-evidenced foundation/plinth support classification."""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class WallMaterialEvidence:
    """Positive source-owned material evidence for a wall candidate."""

    evidence_id: str
    wall_id: str
    source_sha256: str
    revision_id: str
    material_status: WallMaterialStatus
    material_description: str = ""
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CANDIDATE
    reason_codes: Tuple[str, ...] = ()
    schema_version: str = DPC_PLINTH_RUN_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "wall_id": self.wall_id,
            "source_sha256": self.source_sha256,
            "revision_id": self.revision_id,
            "material_status": self.material_status.value,
            "material_description": self.material_description,
            "status": self.status.value,
            "reason_codes": list(self.reason_codes),
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class WallFoundationRelationshipEvidence:
    """Positive source-owned foundation/plinth support relationship for a wall candidate."""

    relationship_id: str
    wall_id: str
    source_sha256: str
    revision_id: str
    support_status: FoundationSupportStatus
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CANDIDATE
    supporting_evidence_ids: Tuple[str, ...] = ()
    reason_codes: Tuple[str, ...] = ()
    schema_version: str = DPC_PLINTH_RUN_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "relationship_id": self.relationship_id,
            "wall_id": self.wall_id,
            "source_sha256": self.source_sha256,
            "revision_id": self.revision_id,
            "support_status": self.support_status.value,
            "status": self.status.value,
            "supporting_evidence_ids": list(self.supporting_evidence_ids),
            "reason_codes": list(self.reason_codes),
            "schema_version": self.schema_version,
        }


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
    material_status: WallMaterialStatus
    foundation_supported: bool
    foundation_support: FoundationSupportStatus
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
            "material_status": self.material_status.value,
            "foundation_supported": self.foundation_supported,
            "foundation_support": self.foundation_support.value,
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
    r"|\bexternal\s+walls\s+only\b"
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
            # Bare D.P.C. callout or section marker without explicit scope wording
            # stays UNRESOLVED (fail-closed against guessing).
            scope = DPCPlinthScope.UNRESOLVED
            reasons = (REASON_DPC_SPEC_AUTHENTICATED, REASON_DPC_SCOPE_UNRESOLVED)

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
                revision_id=context.current_revision_id or "",
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
# Strict FIRM QuantityEvidence Validation
# ---------------------------------------------------------------------------

def validate_wall_length_quantity_evidence(
    *,
    quantity: Optional[QuantityEvidence],
    wall_id: str,
    equivalence: PhysicalWallEquivalenceResolution,
    context: ProviderContext,
    document: DocumentEvidence,
) -> Tuple[bool, Optional[float], Tuple[str, ...]]:
    """Strictly revalidate a supplied wall-length QuantityEvidence record.

    Validates:
    - quantity is not None and not abstained
    - family is "wall_length"
    - unit is "m"
    - status is "FIRM"
    - value is finite and > 0
    - input_entity_ids includes the exact representative wall_id
    - document/source ownership matches context.source_sha256
    - revision_id matches context.current_revision_id
    - wall_id is in equivalence.representative_wall_ids
    - no blockers exist for wall_id in equivalence
    """
    reasons: list[str] = []
    if quantity is None:
        reasons.append(REASON_WALL_LENGTH_NOT_FIRM)
        return False, None, tuple(reasons)

    if quantity.abstained:
        reasons.append(REASON_WALL_LENGTH_NOT_FIRM)
        return False, None, tuple(reasons)

    if quantity.family.lower() != "wall_length":
        reasons.append(REASON_QUANTITY_WRONG_FAMILY)
        reasons.append(REASON_WALL_LENGTH_NOT_FIRM)
        return False, None, tuple(reasons)

    if quantity.unit.lower() != "m":
        reasons.append(REASON_QUANTITY_WRONG_UNIT)
        reasons.append(REASON_WALL_LENGTH_NOT_FIRM)
        return False, None, tuple(reasons)

    if str(quantity.status).upper() != AuthorityStatus.FIRM.value.upper():
        reasons.append(REASON_WALL_LENGTH_NOT_FIRM)
        return False, None, tuple(reasons)

    if quantity.value is None or not math.isfinite(quantity.value) or quantity.value <= 0.0:
        reasons.append(REASON_WALL_LENGTH_NOT_FIRM)
        return False, None, tuple(reasons)

    # Must target the exact representative wall
    if wall_id not in quantity.input_entity_ids:
        reasons.append(REASON_QUANTITY_WRONG_ENTITY)
        reasons.append(REASON_WALL_LENGTH_NOT_FIRM)
        return False, None, tuple(reasons)

    # Document / source ownership check
    qty_sha = quantity.metadata.get("source_sha256")
    if qty_sha is not None and qty_sha != context.source_sha256:
        reasons.append(REASON_SOURCE_INTEGRITY_MISMATCH)
        reasons.append(REASON_WALL_LENGTH_NOT_FIRM)
        return False, None, tuple(reasons)
    if document.source_sha256 != context.source_sha256:
        reasons.append(REASON_SOURCE_INTEGRITY_MISMATCH)
        reasons.append(REASON_WALL_LENGTH_NOT_FIRM)
        return False, None, tuple(reasons)

    # Revision check
    qty_rev = quantity.metadata.get("revision_id")
    if qty_rev is not None and context.current_revision_id is not None:
        if qty_rev != context.current_revision_id:
            reasons.append(REASON_REVISION_MISMATCH)
            reasons.append(REASON_WALL_LENGTH_NOT_FIRM)
            return False, None, tuple(reasons)

    # Physical equivalence representative check
    if wall_id not in equivalence.representative_wall_ids:
        reasons.append(REASON_NON_REPRESENTATIVE_DUPLICATE)
        return False, None, tuple(reasons)

    # Equivalence blockers check
    if (
        equivalence.blockers_for(wall_id)
        or wall_id in equivalence.abstained_wall_ids
        or wall_id in equivalence.ambiguous_wall_ids
    ):
        reasons.append(REASON_EQUIVALENCE_BLOCKER)
        reasons.append(REASON_WALL_LENGTH_NOT_FIRM)
        return False, None, tuple(reasons)

    return True, round(float(quantity.value), 4), ()


# ---------------------------------------------------------------------------
# Shadow DPC Plinth Run Producer
# ---------------------------------------------------------------------------

class DPCPlinthRunProducer:
    """Producer of deterministic, source-owned shadow DPC plinth-run records."""

    @classmethod
    def assess_walls(
        cls,
        *,
        walls: Sequence[WallCandidate],
        equivalence: PhysicalWallEquivalenceResolution,
        wall_length_quantities: Mapping[str, QuantityEvidence],
        dpc_scope: DPCPlinthScope,
        context: ProviderContext,
        document: DocumentEvidence,
        wall_material_evidences: Optional[Mapping[str, WallMaterialEvidence]] = None,
        wall_foundation_relationships: Optional[Mapping[str, WallFoundationRelationshipEvidence]] = None,
    ) -> Sequence[DPCPlinthWallAssessment]:
        """Assess every candidate wall for inclusion in the DPC plinth run."""
        assessments: list[DPCPlinthWallAssessment] = []
        mat_map = wall_material_evidences or {}
        found_map = wall_foundation_relationships or {}

        for wall in walls:
            wid = wall.candidate_id
            reasons: list[str] = []

            # 1. Physical equivalence check
            is_rep = wid in equivalence.representative_wall_ids
            rep_id = wid if is_rep else None
            eq_blocked = (
                bool(equivalence.blockers_for(wid))
                or wid in equivalence.abstained_wall_ids
                or wid in equivalence.ambiguous_wall_ids
            )
            if not is_rep:
                reasons.append(REASON_NON_REPRESENTATIVE_DUPLICATE)
            elif eq_blocked:
                reasons.append(REASON_EQUIVALENCE_BLOCKER)

            # 2. Material verification (positive source-owned evidence required)
            mat_ev = mat_map.get(wid)
            if mat_ev is None:
                material_status = WallMaterialStatus.UNRESOLVED
                reasons.append(REASON_WALL_MATERIAL_UNRESOLVED)
            elif (
                mat_ev.wall_id != wid
                or mat_ev.source_sha256 != context.source_sha256
                or (context.current_revision_id and mat_ev.revision_id != context.current_revision_id)
                or mat_ev.status != EvidenceResolutionStatus.CORROBORATED
            ):
                material_status = WallMaterialStatus.UNRESOLVED
                reasons.append(REASON_SOURCE_INTEGRITY_MISMATCH)
                reasons.append(REASON_WALL_MATERIAL_UNRESOLVED)
            else:
                material_status = mat_ev.material_status
                if material_status == WallMaterialStatus.NON_MASONRY:
                    reasons.append(REASON_NON_MASONRY_ELEMENT)
                elif material_status == WallMaterialStatus.UNRESOLVED:
                    reasons.append(REASON_WALL_MATERIAL_UNRESOLVED)

            is_masonry = (material_status == WallMaterialStatus.MASONRY)

            # 3. Foundation / plinth relationship verification (positive evidence required)
            found_rel = found_map.get(wid)
            if found_rel is None:
                foundation_support = FoundationSupportStatus.UNRESOLVED
                reasons.append(REASON_FOUNDATION_SUPPORT_UNRESOLVED)
            elif (
                found_rel.wall_id != wid
                or found_rel.source_sha256 != context.source_sha256
                or (context.current_revision_id and found_rel.revision_id != context.current_revision_id)
                or found_rel.status != EvidenceResolutionStatus.CORROBORATED
            ):
                foundation_support = FoundationSupportStatus.UNRESOLVED
                reasons.append(REASON_SOURCE_INTEGRITY_MISMATCH)
                reasons.append(REASON_FOUNDATION_SUPPORT_UNRESOLVED)
            else:
                foundation_support = found_rel.support_status
                if foundation_support == FoundationSupportStatus.UNSUPPORTED:
                    reasons.append(REASON_WALL_NOT_FOUNDATION_SUPPORTED)
                elif foundation_support == FoundationSupportStatus.UNRESOLVED:
                    reasons.append(REASON_FOUNDATION_SUPPORT_UNRESOLVED)

            foundation_supported = (foundation_support == FoundationSupportStatus.SUPPORTED)

            # 4. Length QuantityEvidence revalidation
            qty = wall_length_quantities.get(wid)
            qty_valid, length_val, qty_reasons = validate_wall_length_quantity_evidence(
                quantity=qty,
                wall_id=wid,
                equivalence=equivalence,
                context=context,
                document=document,
            )
            reasons.extend(qty_reasons)
            length_m = length_val if qty_valid else None
            length_status = "firm" if qty_valid else ("rejected" if qty else "unresolved")
            length_qty_id = qty.quantity_id if qty else None

            # 5. DPC Scope check
            if dpc_scope == DPCPlinthScope.UNRESOLVED:
                dpc_scope_status = "unresolved"
                reasons.append(REASON_DPC_SCOPE_UNRESOLVED)
            elif wall.interior_exterior == "exterior":
                dpc_scope_status = "in_scope"
            elif wall.interior_exterior == "interior":
                if dpc_scope == DPCPlinthScope.ALL_MASONRY_WALLS:
                    dpc_scope_status = "in_scope" if foundation_supported else "out_of_scope"
                else:
                    dpc_scope_status = "out_of_scope"
            else:
                dpc_scope_status = "unresolved"
                reasons.append(REASON_DPC_SCOPE_UNRESOLVED)

            # 6. Overall wall evaluation status
            if rep_id is None:
                evaluation_status = "excluded"
            elif dpc_scope_status == "out_of_scope":
                evaluation_status = "excluded"
                reasons.append(REASON_WALL_OUT_OF_SCOPE)
            elif material_status == WallMaterialStatus.NON_MASONRY:
                evaluation_status = "excluded"
            elif foundation_support == FoundationSupportStatus.UNSUPPORTED:
                evaluation_status = "excluded"
            elif dpc_scope_status == "unresolved":
                evaluation_status = "abstained"
            elif material_status == WallMaterialStatus.UNRESOLVED:
                evaluation_status = "abstained"
            elif foundation_support == FoundationSupportStatus.UNRESOLVED:
                evaluation_status = "abstained"
            elif eq_blocked:
                evaluation_status = "abstained"
            elif length_status != "firm" or length_m is None or length_m <= 0:
                evaluation_status = "abstained"
            else:
                evaluation_status = "included"
                reasons.append(REASON_WALL_IN_SCOPE)

            assessments.append(
                DPCPlinthWallAssessment(
                    wall_id=wid,
                    representative_wall_id=rep_id,
                    interior_exterior=wall.interior_exterior,
                    is_masonry=is_masonry,
                    material_status=material_status,
                    foundation_supported=foundation_supported,
                    foundation_support=foundation_support,
                    length_m=length_m,
                    length_status=length_status,
                    length_quantity_id=length_qty_id,
                    dpc_scope_status=dpc_scope_status,
                    evaluation_status=evaluation_status,
                    reason_codes=tuple(dict.fromkeys(reasons)),
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

        # Document/source ownership verification
        if document.source_sha256 != context.source_sha256:
            blocking_reasons.append(REASON_SOURCE_INTEGRITY_MISMATCH)
            return cls._empty_record(
                context=context,
                document=document,
                scope=DPCPlinthScope.UNRESOLVED,
                status=EvidenceResolutionStatus.ABSTAINED,
                wall_assessments=wall_assessments,
                dpc_spec_evidences=dpc_spec_evidences,
                blocking_reasons=tuple(blocking_reasons),
            )

        # Validate DPC spec evidences against context and document
        valid_dpc_specs: list[DPCPlinthSpecificationEvidence] = []
        for ev in dpc_spec_evidences:
            if ev.source_sha256 != context.source_sha256:
                blocking_reasons.append(REASON_SOURCE_INTEGRITY_MISMATCH)
                continue
            if context.current_revision_id and ev.revision_id != context.current_revision_id:
                blocking_reasons.append(REASON_REVISION_MISMATCH)
                continue
            if ev.status != EvidenceResolutionStatus.CORROBORATED:
                continue
            valid_dpc_specs.append(ev)

        if not valid_dpc_specs:
            if not blocking_reasons:
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

        # Check for scope conflicts among valid DPC specs
        scopes = {ev.scope for ev in valid_dpc_specs}
        has_ext = DPCPlinthScope.EXTERNAL_WALLS_ONLY in scopes
        has_all = DPCPlinthScope.ALL_MASONRY_WALLS in scopes

        if has_ext and has_all:
            # Conflicting explicit scope notes across sheets
            blocking_reasons.append("conflicting_dpc_scope_specifications")
            return cls._empty_record(
                context=context,
                document=document,
                scope=DPCPlinthScope.UNRESOLVED,
                status=EvidenceResolutionStatus.CONFLICT,
                wall_assessments=wall_assessments,
                dpc_spec_evidences=tuple(valid_dpc_specs),
                blocking_reasons=tuple(blocking_reasons),
            )

        if has_ext:
            effective_scope = DPCPlinthScope.EXTERNAL_WALLS_ONLY
            reason_codes.append(REASON_DPC_SCOPE_EXTERNAL_ONLY)
        elif has_all:
            effective_scope = DPCPlinthScope.ALL_MASONRY_WALLS
            reason_codes.append(REASON_DPC_SCOPE_ALL_MASONRY)
        else:
            effective_scope = DPCPlinthScope.UNRESOLVED
            blocking_reasons.append(REASON_DPC_SCOPE_UNRESOLVED)

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

        # Fail-closed aggregate evaluation
        if effective_scope == DPCPlinthScope.UNRESOLVED:
            status = EvidenceResolutionStatus.ABSTAINED
            total_length_m = None
        elif abstained_wall_ids:
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

        source_pages = tuple(dict.fromkeys(ev.page_no for ev in valid_dpc_specs))
        viewport_ids = tuple(dict.fromkeys(ev.viewport_id for ev in valid_dpc_specs if ev.viewport_id))

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
            revision_id=context.current_revision_id or "",
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
            dpc_spec_evidence_ids=tuple(ev.evidence_id for ev in valid_dpc_specs),
            source_pages=source_pages,
            viewport_ids=viewport_ids,
            blocking_reasons=tuple(dict.fromkeys(blocking_reasons)),
            reason_codes=tuple(dict.fromkeys(reason_codes)),
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
            revision_id=context.current_revision_id or "",
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
