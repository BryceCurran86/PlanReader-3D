"""Live opening -> net-wall integration boundary.

Item 21 production foundation.  This module is deliberately fail-closed until
all upstream authority layers exist on the same production head:

- pb_physical_opening_void_authority
- pb_opening_deduction_authority
- pb_net_wall_boolean_union_authority
- pb_exact_wall_quantity_propagation

It never reconstructs those propositions from legacy arithmetic, caller host
IDs, guessed opening dimensions, or first/nearest/default wall selection.
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib
import importlib.util
from types import MappingProxyType
from typing import Mapping

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

LIVE_OPENING_NET_WALL_SCHEMA_VERSION = "1.0.0"
LIVE_OPENING_NET_WALL_RESOLVED = "live_opening_net_wall_resolved"
LIVE_OPENING_NET_WALL_UPSTREAM_UNAVAILABLE = "live_opening_net_wall_upstream_unavailable"
LIVE_OPENING_NET_WALL_RECORD_UNAVAILABLE = "live_opening_net_wall_record_unavailable"

_REQUIRED_AUTHORITY_MODULES = (
    "pb_physical_opening_void_authority",
    "pb_opening_deduction_authority",
    "pb_net_wall_boolean_union_authority",
    "pb_exact_wall_quantity_propagation",
)

_AUTHORITY_SEAL = object()
_INTEGRATOR_SEAL = object()
_Key = tuple[str, str, str, str, str, str]


def _nonempty(value: object, name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{name} must be non-empty")
    return clean


@dataclass(frozen=True)
class LiveOpeningNetWallSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    decision_scope_id: str
    physical_wall_identity_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "decision_scope_id",
            "physical_wall_identity_id",
        ):
            _nonempty(getattr(self, name), name)

    @property
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.decision_scope_id,
            self.physical_wall_identity_id,
        )


@dataclass(frozen=True)
class LiveOpeningNetWallResult:
    """One live integration result; unresolved net remains explicitly absent."""

    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    physical_wall_identity_id: str
    integration_record_id: str
    net_wall_record_id: str | None = None
    propagated_record_ids: tuple[str, ...] = ()
    schema_version: str = LIVE_OPENING_NET_WALL_SCHEMA_VERSION

    @property
    def abstained(self) -> bool:
        return self.status is not EvidenceResolutionStatus.CORROBORATED


class LiveOpeningNetWallIntegrator:
    """Sealed selector-only orchestrator over already-proved upstream authority."""

    def __init__(
        self,
        results: Mapping[_Key, LiveOpeningNetWallResult] | None = None,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _INTEGRATOR_SEAL:
            raise ValueError("LiveOpeningNetWallIntegrator is producer-owned")
        self._results = MappingProxyType(dict(results or {}))

    @classmethod
    def fail_closed_current_head(cls) -> "LiveOpeningNetWallIntegrator":
        """Create the current safe boundary without minting any positive records."""
        return cls({}, _seal=_INTEGRATOR_SEAL)

    @classmethod
    def from_authorities(cls, *authorities: object) -> "LiveOpeningNetWallIntegrator":
        """Accept only exact upstream producer authorities once all layers exist.

        The current repository does not yet contain every required production
        authority.  In that state construction fails closed instead of accepting
        substitute caller data.
        """
        modules: list[object] = []
        for module_name in _REQUIRED_AUTHORITY_MODULES:
            if importlib.util.find_spec(module_name) is None:
                raise RuntimeError(f"{LIVE_OPENING_NET_WALL_UPSTREAM_UNAVAILABLE}:{module_name}")
            modules.append(importlib.import_module(module_name))

        expected_names = (
            "PhysicalOpeningVoidAuthority",
            "OpeningDeductionAuthority",
            "NetWallBooleanUnionAuthority",
            "ExactWallQuantityPropagationAuthority",
        )
        if len(authorities) != len(expected_names):
            raise TypeError("all four exact upstream authorities are required")
        for authority, module, class_name in zip(authorities, modules, expected_names, strict=True):
            expected = getattr(module, class_name, None)
            if expected is None or type(authority) is not expected:
                raise TypeError(f"expected exact {class_name}")

        # Positive orchestration is intentionally not activated until the
        # upstream producers expose their reviewed cross-authority selectors.
        # Returning an empty sealed integrator preserves the production boundary
        # without silently guessing any missing proposition.
        return cls({}, _seal=_INTEGRATOR_SEAL)

    def resolve(self, selector: LiveOpeningNetWallSelector) -> LiveOpeningNetWallResult:
        if type(selector) is not LiveOpeningNetWallSelector:
            raise TypeError("selector must be LiveOpeningNetWallSelector")
        result = self._results.get(selector.key)
        if result is not None:
            return result
        return LiveOpeningNetWallResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(LIVE_OPENING_NET_WALL_RECORD_UNAVAILABLE,),
            physical_wall_identity_id=selector.physical_wall_identity_id,
            integration_record_id=stable_contract_id(
                "live_net",
                {
                    "selector": selector.key,
                    "status": "abstained",
                    "schema": LIVE_OPENING_NET_WALL_SCHEMA_VERSION,
                },
            ),
        )
