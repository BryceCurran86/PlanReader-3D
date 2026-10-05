"""Authenticated internal-elevation wall-finish semantic binding.

Composes only producer-owned facts:
- internal-elevation -> room-facing physical wall-face mapping;
- complete authenticated target-elevation physical-wall scope; and
- source-owned material schedule semantic occurrences.

A material code merely appearing in an elevation is not sufficient. The source
line must directly assert wall finish/lining scope, and a viewport-level finish
assertion may bind only when that authenticated elevation viewport contains
exactly one physical wall and it is the mapped target wall.

This authority publishes semantic binding only. It never publishes area and
never certifies a complete finish-face universe.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from types import MappingProxyType
from typing import Mapping, Optional

from pb_internal_elevation_wall_face_authority import (
    InternalElevationWallFaceAuthority,
    InternalElevationWallFaceSelector,
)
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_wall_candidate_authority import PhysicalWallCandidateAuthority
from pb_source_material_semantic_authority import (
    SourceMaterialOccurrenceSelector,
    SourceMaterialSemanticAuthority,
)

INTERNAL_ELEVATION_FINISH_SCHEMA_VERSION = "1.1.0"

INTERNAL_ELEVATION_FINISH_RESOLVED = "internal_elevation_finish_resolved"
INTERNAL_ELEVATION_FINISH_UNAVAILABLE = "internal_elevation_finish_unavailable"
INTERNAL_ELEVATION_FINISH_FACE_UNRESOLVED = "internal_elevation_finish_face_unresolved"
INTERNAL_ELEVATION_FINISH_SCOPE_UNRESOLVED = "internal_elevation_finish_scope_unresolved"
INTERNAL_ELEVATION_FINISH_TARGET_SCOPE_UNRESOLVED = (
    "internal_elevation_finish_target_scope_unresolved"
)
INTERNAL_ELEVATION_FINISH_TARGET_SCOPE_AMBIGUOUS = (
    "internal_elevation_finish_target_scope_ambiguous"
)
INTERNAL_ELEVATION_FINISH_DIRECT_ASSERTION_MISSING = (
    "internal_elevation_finish_direct_assertion_missing"
)
INTERNAL_ELEVATION_FINISH_CONFLICT = "internal_elevation_finish_conflict"
INTERNAL_ELEVATION_FINISH_LINEAGE_MISMATCH = "internal_elevation_finish_lineage_mismatch"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()

_Key = tuple[str, str, str, str, str, str, str]


def _normalise(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _direct_wall_finish_assertion(value: object, code: object) -> bool:
    text = _normalise(value)
    clean_code = str(code or "").strip()
    if not clean_code:
        return False
    wall_scope = bool(
        re.search(r"\bwall\s+(?:finish|finishes|lining|linings)\b", text)
        or re.search(r"\b(?:finish|finishes|lining|linings)\s+to\s+wall\b", text)
    )
    if not wall_scope:
        return False
    return (
        re.search(
            rf"(?<![A-Z0-9]){re.escape(clean_code)}(?![A-Z0-9])",
            str(value or ""),
            re.IGNORECASE,
        )
        is not None
    )


def _candidate_aliases(record: object) -> tuple[str, ...]:
    identity = getattr(record, "physical_identity", None)
    return tuple(
        sorted(
            {
                str(value).strip()
                for value in (
                    getattr(record, "wall_candidate_id", ""),
                    getattr(identity, "physical_wall_id", ""),
                    getattr(identity, "candidate_identity_id", ""),
                )
                if str(value or "").strip()
            }
        )
    )


@dataclass(frozen=True)
class InternalElevationFinishBindingRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    source_page_id: str
    target_page_id: str
    target_viewport_id: str
    physical_wall_id: str
    physical_face_id: str
    physical_wall_decision_scope_id: str
    source_room_face_id: str
    material_code: str
    semantic_finish: str
    trade_scope_id: str
    definition_record_id: str
    occurrence_record_ids: tuple[str, ...]
    source_evidence_ids: tuple[str, ...]
    wall_face_mapping_record_id: str
    decision_scope_complete: bool = False
    schema_version: str = INTERNAL_ELEVATION_FINISH_SCHEMA_VERSION


@dataclass(frozen=True)
class InternalElevationFinishBindingResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: Optional[InternalElevationFinishBindingRecord] = None
    schema_version: str = INTERNAL_ELEVATION_FINISH_SCHEMA_VERSION


def _blocked(
    status: EvidenceResolutionStatus,
    reason: str,
    *upstream_reasons: str,
) -> InternalElevationFinishBindingResult:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    return InternalElevationFinishBindingResult(
        status=status,
        reason_codes=tuple(
            dict.fromkeys(
                [reason, *(str(value) for value in upstream_reasons if str(value))]
            )
        ),
        record=None,
    )


class InternalElevationFinishBindingAuthority:
    def __init__(
        self,
        results: Mapping[_Key, InternalElevationFinishBindingResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("InternalElevationFinishBindingAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(
        self,
        selector: InternalElevationWallFaceSelector,
    ) -> InternalElevationFinishBindingResult:
        if type(selector) is not InternalElevationWallFaceSelector:
            raise TypeError("selector must be InternalElevationWallFaceSelector")
        return self._results.get(
            selector.key,
            _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                INTERNAL_ELEVATION_FINISH_UNAVAILABLE,
            ),
        )


class InternalElevationFinishBindingProducer:
    def __init__(
        self,
        *,
        wall_face_authority: InternalElevationWallFaceAuthority,
        material_authority: SourceMaterialSemanticAuthority,
        physical_wall_authority: PhysicalWallCandidateAuthority,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("Use from_authorities()")
        if type(wall_face_authority) is not InternalElevationWallFaceAuthority:
            raise TypeError("wall_face_authority must be producer-owned")
        if type(material_authority) is not SourceMaterialSemanticAuthority:
            raise TypeError("material_authority must be producer-owned")
        if type(physical_wall_authority) is not PhysicalWallCandidateAuthority:
            raise TypeError("physical_wall_authority must be producer-owned")
        self._wall_face = wall_face_authority
        self._material = material_authority
        self._physical_wall = physical_wall_authority
        self._results: dict[_Key, InternalElevationFinishBindingResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        wall_face_authority: InternalElevationWallFaceAuthority,
        material_authority: SourceMaterialSemanticAuthority,
        physical_wall_authority: PhysicalWallCandidateAuthority,
    ) -> "InternalElevationFinishBindingProducer":
        return cls(
            wall_face_authority=wall_face_authority,
            material_authority=material_authority,
            physical_wall_authority=physical_wall_authority,
            _seal=_PRODUCER_SEAL,
        )

    def authority(self) -> InternalElevationFinishBindingAuthority:
        return InternalElevationFinishBindingAuthority(
            self._results,
            _seal=_AUTHORITY_SEAL,
        )

    def _store(
        self,
        selector: InternalElevationWallFaceSelector,
        result: InternalElevationFinishBindingResult,
    ) -> InternalElevationFinishBindingResult:
        existing = self._results.get(selector.key)
        if existing is not None and existing != result:
            result = _blocked(
                EvidenceResolutionStatus.CONFLICT,
                INTERNAL_ELEVATION_FINISH_CONFLICT,
                "internal_elevation_finish_producer_equivocation",
            )
        self._results[selector.key] = result
        return result

    def publish(
        self,
        selector: InternalElevationWallFaceSelector,
    ) -> InternalElevationFinishBindingResult:
        if type(selector) is not InternalElevationWallFaceSelector:
            raise TypeError("selector must be InternalElevationWallFaceSelector")

        mapping_result = self._wall_face.resolve(selector)
        mapping = mapping_result.record
        if (
            mapping_result.status is not EvidenceResolutionStatus.CORROBORATED
            or mapping is None
        ):
            return self._store(
                selector,
                _blocked(
                    mapping_result.status,
                    INTERNAL_ELEVATION_FINISH_FACE_UNRESOLVED,
                    *mapping_result.reason_codes,
                ),
            )
        if (
            mapping.document_id != selector.document_id
            or mapping.revision_id != selector.revision_id
            or mapping.source_sha256 != selector.source_sha256
            or mapping.snapshot_id != selector.snapshot_id
            or mapping.source_page_id != selector.source_page_id
            or mapping.target_page_id != selector.target_page_id
            or mapping.physical_wall_id != selector.physical_wall_id
        ):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    INTERNAL_ELEVATION_FINISH_LINEAGE_MISMATCH,
                ),
            )

        target_selector = self._physical_wall.selector_for_viewport(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.target_page_id,
            viewport_id=mapping.target_viewport_id,
        )
        if target_selector is None:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    INTERNAL_ELEVATION_FINISH_TARGET_SCOPE_UNRESOLVED,
                ),
            )
        target_scope = self._physical_wall.resolve_scope(target_selector)
        if (
            target_scope.status is not EvidenceResolutionStatus.CORROBORATED
            or target_scope.scope_complete is not True
        ):
            return self._store(
                selector,
                _blocked(
                    target_scope.status,
                    INTERNAL_ELEVATION_FINISH_TARGET_SCOPE_UNRESOLVED,
                    *target_scope.reason_codes,
                ),
            )
        if len(target_scope.records) != 1:
            return self._store(
                selector,
                _blocked(
                    (
                        EvidenceResolutionStatus.CONFLICT
                        if len(target_scope.records) > 1
                        else EvidenceResolutionStatus.ABSTAINED
                    ),
                    INTERNAL_ELEVATION_FINISH_TARGET_SCOPE_AMBIGUOUS,
                ),
            )
        if mapping.target_physical_wall_id not in _candidate_aliases(
            target_scope.records[0]
        ):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    INTERNAL_ELEVATION_FINISH_LINEAGE_MISMATCH,
                    "mapped_target_wall_not_unique_viewport_wall",
                ),
            )

        occurrence_selector = SourceMaterialOccurrenceSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.target_page_id,
            viewport_id=mapping.target_viewport_id,
        )
        occurrence_scope = self._material.resolve_occurrences(occurrence_selector)
        if (
            occurrence_scope.status is not EvidenceResolutionStatus.CORROBORATED
            or occurrence_scope.scope_complete is not True
        ):
            return self._store(
                selector,
                _blocked(
                    occurrence_scope.status,
                    INTERNAL_ELEVATION_FINISH_SCOPE_UNRESOLVED,
                    *occurrence_scope.reason_codes,
                ),
            )

        direct = tuple(
            record
            for record in occurrence_scope.records
            if (
                record.document_id == selector.document_id
                and record.revision_id == selector.revision_id
                and record.source_sha256 == selector.source_sha256
                and record.snapshot_id == selector.snapshot_id
                and record.page_id == selector.target_page_id
                and record.viewport_id == mapping.target_viewport_id
                and record.semantic_finish
                and _direct_wall_finish_assertion(record.raw_text, record.code)
            )
        )
        if not direct:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    INTERNAL_ELEVATION_FINISH_DIRECT_ASSERTION_MISSING,
                ),
            )

        semantics = {
            (
                record.code,
                record.semantic_finish,
                record.definition_record_id,
            )
            for record in direct
        }
        if len(semantics) != 1:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    INTERNAL_ELEVATION_FINISH_CONFLICT,
                ),
            )

        code, semantic_finish, definition_record_id = next(iter(semantics))
        occurrence_ids = tuple(sorted({record.record_id for record in direct}))
        evidence_ids = tuple(sorted({record.source_evidence_id for record in direct}))
        trade_scope_id = f"internal_{semantic_finish}"
        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "source_page_id": selector.source_page_id,
            "target_page_id": selector.target_page_id,
            "target_viewport_id": mapping.target_viewport_id,
            "physical_wall_id": selector.physical_wall_id,
            "physical_face_id": mapping.physical_face_id,
            "physical_wall_decision_scope_id": mapping.physical_wall_decision_scope_id,
            "source_room_face_id": mapping.source_room_face_id,
            "material_code": code,
            "semantic_finish": semantic_finish,
            "trade_scope_id": trade_scope_id,
            "definition_record_id": definition_record_id,
            "occurrence_record_ids": occurrence_ids,
            "source_evidence_ids": evidence_ids,
            "wall_face_mapping_record_id": mapping.record_id,
            "decision_scope_complete": False,
        }
        record = InternalElevationFinishBindingRecord(
            record_id=stable_contract_id(
                "internal_elevation_finish_binding",
                payload,
                digest_chars=32,
            ),
            **payload,
        )
        return self._store(
            selector,
            InternalElevationFinishBindingResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(INTERNAL_ELEVATION_FINISH_RESOLVED,),
                record=record,
            ),
        )


__all__ = [
    "INTERNAL_ELEVATION_FINISH_CONFLICT",
    "INTERNAL_ELEVATION_FINISH_DIRECT_ASSERTION_MISSING",
    "INTERNAL_ELEVATION_FINISH_FACE_UNRESOLVED",
    "INTERNAL_ELEVATION_FINISH_LINEAGE_MISMATCH",
    "INTERNAL_ELEVATION_FINISH_RESOLVED",
    "INTERNAL_ELEVATION_FINISH_SCHEMA_VERSION",
    "INTERNAL_ELEVATION_FINISH_SCOPE_UNRESOLVED",
    "INTERNAL_ELEVATION_FINISH_TARGET_SCOPE_AMBIGUOUS",
    "INTERNAL_ELEVATION_FINISH_TARGET_SCOPE_UNRESOLVED",
    "INTERNAL_ELEVATION_FINISH_UNAVAILABLE",
    "InternalElevationFinishBindingAuthority",
    "InternalElevationFinishBindingProducer",
    "InternalElevationFinishBindingRecord",
    "InternalElevationFinishBindingResult",
]
