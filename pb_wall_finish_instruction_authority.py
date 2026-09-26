"""Source-owned wall-finish instruction authority for Item 19B.

Consumes only producer-owned callout->physical-wall bindings and parses the
already-trusted annotation text sealed on those records.

This layer intentionally stops before:
- physical face identity,
- finish-scope completeness,
- opening deduction,
- net-wall quantity,
- commercial quantity publication.

No caller text, project identity, benchmark value, nearest-wall rule, or
confidence ranking participates.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_wall_finish_callout_wall_authority import (
    WallFinishCalloutWallBindingRecord,
    WallFinishCalloutWallProducer,
)
from pb_wall_finish_face_binding_authority import _finish_semantics


WALL_FINISH_INSTRUCTION_SCHEMA_VERSION = "1.0.0"
WALL_FINISH_INSTRUCTION_RESOLVED = "wall_finish_instruction_resolved"
WALL_FINISH_INSTRUCTION_UNAVAILABLE = "wall_finish_instruction_unavailable"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RECORD_SEAL = object()


@dataclass(frozen=True)
class WallFinishInstructionSelector:
    binding_id: str
    trade_scope_id: str

    def __post_init__(self) -> None:
        if not str(self.binding_id or "").strip():
            raise ValueError("binding_id must be non-empty")
        if not str(self.trade_scope_id or "").strip():
            raise ValueError("trade_scope_id must be non-empty")

    @property
    def key(self) -> tuple[str, str]:
        return (self.binding_id, self.trade_scope_id)


@dataclass(frozen=True)
class WallFinishInstructionRecord:
    instruction_id: str
    binding_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: str
    physical_wall_decision_scope_id: str
    physical_wall_id: str
    raw_owner_wall_ids: tuple[str, ...]
    equivalence_group_wall_ids: tuple[str, ...]
    source_wall_primitive_ids: tuple[str, ...]
    trusted_annotation_text: str
    trade_scope_id: str
    finish_material: str
    semantic_direction: str
    source_evidence_ids: tuple[str, ...]
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    schema_version: str = WALL_FINISH_INSTRUCTION_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("WallFinishInstructionRecord is producer-owned")
        if self.status is not EvidenceResolutionStatus.CORROBORATED:
            raise ValueError("positive instruction must be CORROBORATED")
        if not self.trusted_annotation_text:
            raise ValueError("trusted annotation text is required")
        if self.semantic_direction not in ("internally", "externally"):
            raise ValueError("semantic_direction must be explicit")


@dataclass(frozen=True)
class WallFinishInstructionResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: WallFinishInstructionRecord | None = None
    schema_version: str = WALL_FINISH_INSTRUCTION_SCHEMA_VERSION


def _blocked() -> WallFinishInstructionResult:
    return WallFinishInstructionResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=(WALL_FINISH_INSTRUCTION_UNAVAILABLE,),
        record=None,
    )


class WallFinishInstructionAuthority:
    def __init__(
        self,
        results: Mapping[tuple[str, str], WallFinishInstructionResult],
        *,
        _seal=None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("WallFinishInstructionAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(
        self,
        selector: WallFinishInstructionSelector,
    ) -> WallFinishInstructionResult:
        if type(selector) is not WallFinishInstructionSelector:
            raise TypeError("selector must be WallFinishInstructionSelector")
        return self._results.get(selector.key, _blocked())


class WallFinishInstructionProducer:
    def __init__(
        self,
        results: Mapping[tuple[str, str], WallFinishInstructionResult],
        *,
        _seal=None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "WallFinishInstructionProducer must be obtained "
                "from_callout_wall_producer()"
            )
        self._results = MappingProxyType(dict(results))

    @classmethod
    def from_callout_wall_producer(
        cls,
        callout_wall_producer: WallFinishCalloutWallProducer,
    ) -> "WallFinishInstructionProducer":
        if type(callout_wall_producer) is not WallFinishCalloutWallProducer:
            raise TypeError(
                "callout_wall_producer must be an actual "
                "WallFinishCalloutWallProducer"
            )

        results: dict[tuple[str, str], WallFinishInstructionResult] = {}
        for scope_result in callout_wall_producer.published_results():
            for binding in scope_result.bindings:
                if type(binding) is not WallFinishCalloutWallBindingRecord:
                    continue
                semantics = _finish_semantics(binding.trusted_annotation_text)
                for semantic in semantics:
                    payload = {
                        "binding_id": binding.binding_id,
                        "document_id": binding.document_id,
                        "revision_id": binding.revision_id,
                        "source_sha256": binding.source_sha256,
                        "snapshot_id": binding.snapshot_id,
                        "page_id": binding.page_id,
                        "viewport_id": binding.viewport_id,
                        "physical_wall_decision_scope_id": (
                            binding.physical_wall_decision_scope_id
                        ),
                        "physical_wall_id": binding.physical_wall_id,
                        "raw_owner_wall_ids": binding.raw_owner_wall_ids,
                        "equivalence_group_wall_ids": (
                            binding.equivalence_group_wall_ids
                        ),
                        "source_wall_primitive_ids": (
                            binding.source_wall_primitive_ids
                        ),
                        "trusted_annotation_text": (
                            binding.trusted_annotation_text
                        ),
                        "trade_scope_id": semantic.trade_scope_id,
                        "finish_material": semantic.finish_material,
                        "semantic_direction": semantic.direction,
                    }
                    record = WallFinishInstructionRecord(
                        instruction_id=stable_contract_id(
                            "wall_finish_instruction",
                            payload,
                            digest_chars=32,
                        ),
                        **payload,
                        source_evidence_ids=tuple(binding.source_evidence_ids),
                        status=EvidenceResolutionStatus.CORROBORATED,
                        reason_codes=(WALL_FINISH_INSTRUCTION_RESOLVED,),
                        _seal=_RECORD_SEAL,
                    )
                    key = (record.binding_id, record.trade_scope_id)
                    prior = results.get(key)
                    if prior is not None and prior.record is not None:
                        # Same binding/trade must be deterministic. Different
                        # instructions for the same key cannot be ranked.
                        if prior.record.instruction_id != record.instruction_id:
                            results[key] = WallFinishInstructionResult(
                                status=EvidenceResolutionStatus.CONFLICT,
                                reason_codes=(
                                    WALL_FINISH_INSTRUCTION_UNAVAILABLE,
                                ),
                                record=None,
                            )
                        continue
                    results[key] = WallFinishInstructionResult(
                        status=EvidenceResolutionStatus.CORROBORATED,
                        reason_codes=(WALL_FINISH_INSTRUCTION_RESOLVED,),
                        record=record,
                    )

        return cls(results, _seal=_PRODUCER_SEAL)

    def authority(self) -> WallFinishInstructionAuthority:
        return WallFinishInstructionAuthority(
            self._results,
            _seal=_AUTHORITY_SEAL,
        )

    def published_results(self) -> tuple[WallFinishInstructionResult, ...]:
        return tuple(self._results[key] for key in sorted(self._results))


__all__ = [
    "WALL_FINISH_INSTRUCTION_RESOLVED",
    "WALL_FINISH_INSTRUCTION_SCHEMA_VERSION",
    "WALL_FINISH_INSTRUCTION_UNAVAILABLE",
    "WallFinishInstructionAuthority",
    "WallFinishInstructionProducer",
    "WallFinishInstructionRecord",
    "WallFinishInstructionResult",
    "WallFinishInstructionSelector",
]
