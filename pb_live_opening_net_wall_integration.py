"""Live opening to net-wall extractor integration adapter (Item 21).

Integrates the authenticated chain:
live drawing evidence
-> physical wall candidate authority
-> opening host binding authority
-> physical opening void authority
-> opening deduction applicability authority
-> gross wall geometry authority
-> net wall boolean union authority
into the live extraction pipeline.

Invariants:
- Zero mutation of benchmark gold, scorers, tolerances, or holdout expectations.
- Complete fail-closed publication gating: unresolved deductions, unauthenticated
  openings, or unverified wall geometry NEVER produce firm/publishable quantities.
- Authoritative quantities are emitted strictly when NetWallBooleanUnionAuthority
  resolves with CORROBORATED status and valid net_area_m2.
- Emits QuantityEvidence with family="wall_net_area" and status="corroborated".
- When unauthenticated or unresolved, abstains with value=None and publication_blocked=True.
- Caller/request wall identity must exactly match selector and authenticated record identity.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, List, Mapping, Optional, Sequence

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    QuantityEvidence,
    stable_contract_id,
)
from pb_net_wall_boolean_union_authority import (
    NetWallBooleanUnionAuthority,
    NetWallBooleanUnionRecord,
    NetWallBooleanUnionResult,
    NetWallBooleanUnionSelector,
)

LIVE_NET_WALL_INTEGRATION_SCHEMA_VERSION = "1.0.0"

LIVE_NET_WALL_RESOLVED = "live_net_wall_resolved"
LIVE_NET_WALL_AUTHORITY_UNAVAILABLE = "live_net_wall_authority_unavailable"
LIVE_NET_WALL_UPSTREAM_UNRESOLVED = "live_net_wall_upstream_unresolved"
LIVE_NET_WALL_IDENTITY_MISMATCH = "live_net_wall_identity_mismatch"


@dataclass(frozen=True)
class LiveNetWallEvidenceResult:
    """Result of attempting live net-wall authority resolution for a wall."""

    wall_id: str
    is_authoritative: bool
    net_area_m2: Optional[float]
    evidence: QuantityEvidence
    reason_codes: tuple[str, ...]
    union_record_id: Optional[str] = None
    schema_version: str = LIVE_NET_WALL_INTEGRATION_SCHEMA_VERSION


class LiveOpeningNetWallAdapter:
    """Binds authenticated NetWallBooleanUnionAuthority results to extractor pipelines."""

    def __init__(
        self,
        net_wall_authority: Optional[NetWallBooleanUnionAuthority] = None,
    ) -> None:
        if (
            net_wall_authority is not None
            and type(net_wall_authority) is not NetWallBooleanUnionAuthority
        ):
            raise TypeError("net_wall_authority must be NetWallBooleanUnionAuthority")
        self._auth = net_wall_authority

    def resolve_wall_net_area(
        self,
        selector: Optional[NetWallBooleanUnionSelector] = None,
        wall_id: str = "perimeter_walling",
        gross_area_m2: Optional[float] = None,
    ) -> LiveNetWallEvidenceResult:
        """Resolve net wall area using authenticated NetWallBooleanUnionAuthority.

        ``wall_id`` is a request/addressing identity only. It cannot relabel an
        authenticated selector/record. A mismatch is an explicit conflict and
        returns no numeric authority.
        """
        if self._auth is None or selector is None:
            evidence = QuantityEvidence(
                quantity_id=stable_contract_id(
                    "wall_net_area",
                    {
                        "wall_id": wall_id,
                        "gross_area_m2": gross_area_m2,
                        "authority_available": False,
                    },
                ),
                family="wall_net_area",
                semantic_key=wall_id,
                value=None,
                unit="m2",
                input_entity_ids=(wall_id,),
                formula="gross_area_m2 - sum(opening_areas)",
                authority="pb_live_opening_net_wall_integration.LiveOpeningNetWallAdapter",
                status="abstained",
                abstained=True,
                blocking_reasons=(LIVE_NET_WALL_AUTHORITY_UNAVAILABLE,),
                reason_codes=(LIVE_NET_WALL_AUTHORITY_UNAVAILABLE,),
            )
            return LiveNetWallEvidenceResult(
                wall_id=wall_id,
                is_authoritative=False,
                net_area_m2=None,
                evidence=evidence,
                reason_codes=(LIVE_NET_WALL_AUTHORITY_UNAVAILABLE,),
            )

        if type(selector) is not NetWallBooleanUnionSelector:
            raise TypeError("selector must be NetWallBooleanUnionSelector")

        # A caller/request identity may select only its exact physical wall.
        # The pipeline passes WallInstance.wall_id here, so this also blocks a
        # caller selector mapping from laundering Wall A authority onto Wall B.
        if wall_id != selector.physical_wall_id:
            evidence = QuantityEvidence(
                quantity_id=stable_contract_id(
                    "wall_net_area",
                    {
                        "wall_id": wall_id,
                        "selector_physical_wall_id": selector.physical_wall_id,
                        "status": "conflict",
                    },
                ),
                family="wall_net_area",
                semantic_key=wall_id,
                value=None,
                unit="m2",
                input_entity_ids=(wall_id, selector.physical_wall_id),
                formula="gross_wall_polygon - union(opening_void_polygons)",
                authority="pb_live_opening_net_wall_integration.LiveOpeningNetWallAdapter",
                status="conflict",
                abstained=True,
                blocking_reasons=(LIVE_NET_WALL_IDENTITY_MISMATCH,),
                reason_codes=(LIVE_NET_WALL_IDENTITY_MISMATCH,),
            )
            return LiveNetWallEvidenceResult(
                wall_id=wall_id,
                is_authoritative=False,
                net_area_m2=None,
                evidence=evidence,
                reason_codes=(LIVE_NET_WALL_IDENTITY_MISMATCH,),
            )

        res: NetWallBooleanUnionResult = self._auth.resolve(selector)
        if (
            res.status is EvidenceResolutionStatus.CORROBORATED
            and res.record is not None
            and res.record.net_area_m2 is not None
            and math.isfinite(res.record.net_area_m2)
            and res.record.net_area_m2 >= 0.0
            and res.record.physical_wall_id == selector.physical_wall_id
            and res.record.document_id == selector.document_id
            and res.record.revision_id == selector.revision_id
            and res.record.source_sha256 == selector.source_sha256
            and res.record.snapshot_id == selector.snapshot_id
            and res.record.page_id == selector.page_id
            and res.record.decision_scope_id == selector.decision_scope_id
            and res.record.gross_geometry_record_id
        ):
            record: NetWallBooleanUnionRecord = res.record
            net_val = float(record.net_area_m2)
            evidence = QuantityEvidence(
                quantity_id=record.record_id,
                family="wall_net_area",
                semantic_key=record.physical_wall_id,
                value=net_val,
                unit="m2",
                input_entity_ids=(record.physical_wall_id,) + tuple(record.physical_void_record_ids),
                formula="gross_wall_polygon - union(opening_void_polygons)",
                authority="pb_net_wall_boolean_union_authority.NetWallBooleanUnionAuthority",
                status="corroborated",
                abstained=False,
                blocking_reasons=(),
                reason_codes=(LIVE_NET_WALL_RESOLVED, *res.reason_codes),
            )
            return LiveNetWallEvidenceResult(
                wall_id=record.physical_wall_id,
                is_authoritative=True,
                net_area_m2=net_val,
                evidence=evidence,
                reason_codes=(LIVE_NET_WALL_RESOLVED, *res.reason_codes),
                union_record_id=record.record_id,
            )

        blocking_reasons = (
            LIVE_NET_WALL_UPSTREAM_UNRESOLVED,
            *res.reason_codes,
        )
        status_str = "conflict" if res.status is EvidenceResolutionStatus.CONFLICT else "abstained"
        evidence = QuantityEvidence(
            quantity_id=stable_contract_id(
                "wall_net_area",
                {
                    "wall_id": wall_id,
                    "selector_key": selector.key if hasattr(selector, "key") else str(selector),
                    "status": status_str,
                },
            ),
            family="wall_net_area",
            semantic_key=wall_id,
            value=None,
            unit="m2",
            input_entity_ids=(wall_id,),
            formula="gross_area_m2 - sum(opening_areas)",
            authority="pb_net_wall_boolean_union_authority.NetWallBooleanUnionAuthority",
            status=status_str,
            abstained=True,
            blocking_reasons=blocking_reasons,
            reason_codes=blocking_reasons,
        )
        return LiveNetWallEvidenceResult(
            wall_id=wall_id,
            is_authoritative=False,
            net_area_m2=None,
            evidence=evidence,
            reason_codes=blocking_reasons,
        )


def collect_live_net_wall_shadow(
    wall_results: Mapping[str, Any],
) -> Dict[str, Any]:
    """Collect diagnostic shadow record of net-wall authority status."""
    wall_summaries = []
    authoritative_count = 0
    blocked_count = 0

    for wid, res in wall_results.items():
        is_auth = False
        net_val = None
        evidence = getattr(res, "net_area_evidence", None)
        if evidence is not None and not getattr(evidence, "abstained", True):
            is_auth = True
            net_val = getattr(evidence, "value", None)
            authoritative_count += 1
        else:
            blocked_count += 1

        wall_summaries.append(
            {
                "wall_id": wid,
                "is_authoritative": is_auth,
                "net_area_m2": net_val,
                "status": getattr(evidence, "status", "abstained") if evidence else "unavailable",
                "blocking_reasons": getattr(evidence, "blocking_reasons", ()) if evidence else (),
            }
        )

    return {
        "status": "collected",
        "total_walls": len(wall_summaries),
        "authoritative_count": authoritative_count,
        "blocked_count": blocked_count,
        "walls": wall_summaries,
    }


__all__ = [
    "LIVE_NET_WALL_AUTHORITY_UNAVAILABLE",
    "LIVE_NET_WALL_IDENTITY_MISMATCH",
    "LIVE_NET_WALL_INTEGRATION_SCHEMA_VERSION",
    "LIVE_NET_WALL_RESOLVED",
    "LIVE_NET_WALL_UPSTREAM_UNRESOLVED",
    "LiveNetWallEvidenceResult",
    "LiveOpeningNetWallAdapter",
    "collect_live_net_wall_shadow",
]
