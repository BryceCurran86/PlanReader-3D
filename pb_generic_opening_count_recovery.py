"""Generic explicit opening-count recovery.

Item 23 production foundation.  This module reuses the gold-free opening-count
provider to recover source-evidenced *type counts* without changing the frozen
migration gate or pretending that a type count proves physical opening instances.

A recovered ``W7 = 4`` means only that the source evidence supports a W7 type
count of four under the current shadow reconciliation.  It does not create four
spatial openings, host bindings, physical voids, deductions, or commercial rows.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from pb_migration_provider_envelope import ProviderContext
from pb_opening_count_control_adapter import (
    OpeningCountControlAdapter,
    is_production_opening_identity,
)
from pb_shadow_opening_count_gate import OPENING_COUNT_AUTHORITY_STATE

GENERIC_OPENING_COUNT_RECOVERY_VERSION = "1.0.0"


@dataclass(frozen=True)
class RecoveredOpeningTypeCount:
    semantic_key: str
    family: str
    value: float
    unit: str
    status: str
    formula: str
    evidence_ids: tuple[str, ...]
    quantity_id: str
    source_authority: str
    spatially_reconstructed: bool = False
    publishable_as_authoritative: bool = False
    recovery_version: str = GENERIC_OPENING_COUNT_RECOVERY_VERSION


@dataclass(frozen=True)
class OpeningCountRecoveryResult:
    recovered: tuple[RecoveredOpeningTypeCount, ...]
    rejected_quantity_ids: tuple[str, ...]
    authority_state: str
    type_counts_do_not_imply_instances: bool = True
    recovery_version: str = GENERIC_OPENING_COUNT_RECOVERY_VERSION

    @property
    def by_semantic_key(self) -> Mapping[str, RecoveredOpeningTypeCount]:
        return MappingProxyType({item.semantic_key: item for item in self.recovered})


class GenericOpeningCountRecovery:
    """Recover generic explicit type counts without changing authority state."""

    def __init__(self, adapter: OpeningCountControlAdapter | None = None) -> None:
        self._adapter = adapter or OpeningCountControlAdapter()

    def recover(self, context: ProviderContext) -> OpeningCountRecoveryResult:
        provider_result = self._adapter.extract(context)
        recovered: list[RecoveredOpeningTypeCount] = []
        rejected: list[str] = []
        seen_keys: set[str] = set()

        for quantity in provider_result.quantities:
            key = str(quantity.semantic_key or "").strip()
            qid = str(quantity.quantity_id or "")

            # Family totals such as door_total/window_total are diagnostic
            # rollups, not explicit opening identities.  Dimensions or numeric
            # values never create an identity here.
            if not is_production_opening_identity(key):
                rejected.append(qid)
                continue
            if quantity.abstained or quantity.value is None:
                rejected.append(qid)
                continue
            if quantity.unit != "ea":
                rejected.append(qid)
                continue
            value = float(quantity.value)
            if value <= 0.0:
                rejected.append(qid)
                continue
            if not quantity.evidence_ids:
                rejected.append(qid)
                continue
            if key in seen_keys:
                # Reconciliation should already have made duplicate/conflicting
                # identities fail closed.  Do not choose first/last here if that
                # upstream invariant is ever violated.
                rejected.append(qid)
                recovered = [item for item in recovered if item.semantic_key != key]
                continue

            seen_keys.add(key)
            recovered.append(
                RecoveredOpeningTypeCount(
                    semantic_key=key,
                    family=str(quantity.family),
                    value=value,
                    unit="ea",
                    status=str(quantity.status),
                    formula=str(quantity.formula),
                    evidence_ids=tuple(str(item) for item in quantity.evidence_ids),
                    quantity_id=qid,
                    source_authority=str(quantity.authority),
                )
            )

        recovered.sort(key=lambda item: (item.family, item.semantic_key, item.quantity_id))
        return OpeningCountRecoveryResult(
            recovered=tuple(recovered),
            rejected_quantity_ids=tuple(sorted(set(rejected))),
            authority_state=OPENING_COUNT_AUTHORITY_STATE,
        )
